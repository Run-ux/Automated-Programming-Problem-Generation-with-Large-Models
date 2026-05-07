from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any


EXECUTION_OK = "ok"
EXECUTION_ERROR = "error"
EXECUTION_TIMEOUT = "timeout"
EXECUTION_MEMORY_LIMIT = "memory_limit"


@dataclass
class ExecutionResult:
    """本地子进程执行结果。"""

    status: str
    return_value: Any = None
    phase: str = ""
    error_type: str = ""
    error_message: str = ""
    traceback: str = ""
    stdout: str = ""
    stderr: str = ""
    user_stdout: str = ""
    user_stderr: str = ""
    duration_seconds: float = 0.0
    timeout_seconds: float = 0.0
    memory_limit_mb: int = 0
    peak_memory_mb: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_WORKER_SCRIPT = r"""
import contextlib
import io
import json
import sys
import traceback


def emit(payload):
    sys.__stdout__.write(json.dumps(payload, ensure_ascii=False))
    sys.__stdout__.flush()


def main():
    captured_stdout = io.StringIO()
    captured_stderr = io.StringIO()
    try:
        payload = json.loads(sys.stdin.read())
    except BaseException as exc:
        emit(
            {
                "ok": False,
                "phase": "worker_input",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "traceback": traceback.format_exc(),
                "user_stdout": "",
                "user_stderr": "",
            }
        )
        return

    namespace = {"__name__": "__generated__"}
    try:
        with contextlib.redirect_stdout(captured_stdout), contextlib.redirect_stderr(captured_stderr):
            exec(payload["code"], namespace)
    except BaseException as exc:
        emit(
            {
                "ok": False,
                "phase": "compile",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "traceback": traceback.format_exc(),
                "user_stdout": captured_stdout.getvalue(),
                "user_stderr": captured_stderr.getvalue(),
            }
        )
        return

    function_name = payload["function_name"]
    function = namespace.get(function_name)
    if not callable(function):
        emit(
            {
                "ok": False,
                "phase": "interface",
                "error_type": "MissingFunctionError",
                "error_message": f"未找到可调用函数: {function_name}",
                "traceback": "",
                "user_stdout": captured_stdout.getvalue(),
                "user_stderr": captured_stderr.getvalue(),
            }
        )
        return

    try:
        with contextlib.redirect_stdout(captured_stdout), contextlib.redirect_stderr(captured_stderr):
            value = function(*payload.get("args", []))
    except BaseException as exc:
        emit(
            {
                "ok": False,
                "phase": "runtime",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "traceback": traceback.format_exc(),
                "user_stdout": captured_stdout.getvalue(),
                "user_stderr": captured_stderr.getvalue(),
            }
        )
        return

    try:
        emit(
            {
                "ok": True,
                "value": value,
                "user_stdout": captured_stdout.getvalue(),
                "user_stderr": captured_stderr.getvalue(),
            }
        )
    except BaseException as exc:
        emit(
            {
                "ok": False,
                "phase": "return_serialization",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "traceback": traceback.format_exc(),
                "user_stdout": captured_stdout.getvalue(),
                "user_stderr": captured_stderr.getvalue(),
            }
        )


main()
"""


def _read_windows_memory_mb(pid: int) -> float | None:
    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_VM_READ = 0x0010

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    kernel32 = ctypes.windll.kernel32
    psapi = ctypes.windll.psapi
    handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not handle:
        return None
    try:
        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(ProcessMemoryCounters)
        ok = psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb)
        if not ok:
            return None
        return counters.WorkingSetSize / 1024 / 1024
    finally:
        kernel32.CloseHandle(handle)


def _read_proc_memory_mb(pid: int) -> float | None:
    status_path = f"/proc/{pid}/status"
    try:
        with open(status_path, encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    if len(parts) >= 2:
                        return int(parts[1]) / 1024
    except OSError:
        return None
    return None


def _read_process_memory_mb(pid: int) -> float | None:
    if os.name == "nt":
        return _read_windows_memory_mb(pid)
    return _read_proc_memory_mb(pid)


def _monitor_memory(
    process: subprocess.Popen[str],
    *,
    memory_limit_mb: int,
    killed_by_memory: dict[str, bool],
    peak_memory: dict[str, float | None],
) -> None:
    while process.poll() is None:
        memory_mb = _read_process_memory_mb(process.pid)
        if memory_mb is not None:
            current_peak = peak_memory.get("value")
            if current_peak is None or memory_mb > current_peak:
                peak_memory["value"] = memory_mb
            if memory_mb > memory_limit_mb:
                killed_by_memory["value"] = True
                process.kill()
                return
        time.sleep(0.02)


def run_python_function(
    code: str,
    function_name: str,
    args: list[Any] | None = None,
    *,
    timeout_seconds: float,
    memory_limit_mb: int,
) -> ExecutionResult:
    """在隔离子进程中执行生成代码里的指定函数。"""

    payload = json.dumps(
        {
            "code": code,
            "function_name": function_name,
            "args": args or [],
        },
        ensure_ascii=False,
    )
    start_time = time.monotonic()
    process = subprocess.Popen(
        [sys.executable, "-I", "-c", _WORKER_SCRIPT],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    killed_by_memory = {"value": False}
    peak_memory: dict[str, float | None] = {"value": None}
    monitor = threading.Thread(
        target=_monitor_memory,
        kwargs={
            "process": process,
            "memory_limit_mb": memory_limit_mb,
            "killed_by_memory": killed_by_memory,
            "peak_memory": peak_memory,
        },
        daemon=True,
    )
    monitor.start()

    try:
        stdout, stderr = process.communicate(payload, timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        return ExecutionResult(
            status=EXECUTION_TIMEOUT,
            phase="timeout",
            error_type="TimeoutExpired",
            error_message=f"执行超过 {timeout_seconds} 秒。",
            stdout=stdout,
            stderr=stderr,
            duration_seconds=time.monotonic() - start_time,
            timeout_seconds=timeout_seconds,
            memory_limit_mb=memory_limit_mb,
            peak_memory_mb=peak_memory["value"],
        )

    duration = time.monotonic() - start_time
    if killed_by_memory["value"]:
        return ExecutionResult(
            status=EXECUTION_MEMORY_LIMIT,
            phase="memory",
            error_type="MemoryLimitExceeded",
            error_message=f"执行内存超过 {memory_limit_mb} MB。",
            stdout=stdout,
            stderr=stderr,
            duration_seconds=duration,
            timeout_seconds=timeout_seconds,
            memory_limit_mb=memory_limit_mb,
            peak_memory_mb=peak_memory["value"],
        )

    try:
        worker_payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return ExecutionResult(
            status=EXECUTION_ERROR,
            phase="worker_protocol",
            error_type=type(exc).__name__,
            error_message="执行子进程没有返回合法 JSON。",
            stdout=stdout,
            stderr=stderr,
            duration_seconds=duration,
            timeout_seconds=timeout_seconds,
            memory_limit_mb=memory_limit_mb,
            peak_memory_mb=peak_memory["value"],
        )

    if worker_payload.get("ok") is True:
        return ExecutionResult(
            status=EXECUTION_OK,
            return_value=worker_payload.get("value"),
            stdout=stdout,
            stderr=stderr,
            user_stdout=worker_payload.get("user_stdout", ""),
            user_stderr=worker_payload.get("user_stderr", ""),
            duration_seconds=duration,
            timeout_seconds=timeout_seconds,
            memory_limit_mb=memory_limit_mb,
            peak_memory_mb=peak_memory["value"],
        )

    return ExecutionResult(
        status=EXECUTION_ERROR,
        phase=str(worker_payload.get("phase", "")),
        error_type=str(worker_payload.get("error_type", "")),
        error_message=str(worker_payload.get("error_message", "")),
        traceback=str(worker_payload.get("traceback", "")),
        stdout=stdout,
        stderr=stderr,
        user_stdout=str(worker_payload.get("user_stdout", "")),
        user_stderr=str(worker_payload.get("user_stderr", "")),
        duration_seconds=duration,
        timeout_seconds=timeout_seconds,
        memory_limit_mb=memory_limit_mb,
        peak_memory_mb=peak_memory["value"],
    )


def run_generate_test_input(code: str, *, timeout_seconds: float, memory_limit_mb: int) -> ExecutionResult:
    return run_python_function(
        code,
        "generate_test_input",
        timeout_seconds=timeout_seconds,
        memory_limit_mb=memory_limit_mb,
    )


def run_validate_test_input(
    code: str,
    input_string: str,
    *,
    timeout_seconds: float,
    memory_limit_mb: int,
) -> ExecutionResult:
    return run_python_function(
        code,
        "validate_test_input",
        [input_string],
        timeout_seconds=timeout_seconds,
        memory_limit_mb=memory_limit_mb,
    )


def run_solution(
    code: str,
    input_string: str,
    *,
    timeout_seconds: float,
    memory_limit_mb: int,
) -> ExecutionResult:
    return run_python_function(
        code,
        "solve",
        [input_string],
        timeout_seconds=timeout_seconds,
        memory_limit_mb=memory_limit_mb,
    )


def run_checker(
    code: str,
    input_string: str,
    output_string: str,
    *,
    timeout_seconds: float,
    memory_limit_mb: int,
) -> ExecutionResult:
    return run_python_function(
        code,
        "check_output",
        [input_string, output_string],
        timeout_seconds=timeout_seconds,
        memory_limit_mb=memory_limit_mb,
    )
