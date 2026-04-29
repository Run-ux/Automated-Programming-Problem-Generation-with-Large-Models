from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from models import ExecutionResult


class CodeRunner:
    def __init__(self, *, timeout_s: float = 2.0, python_executable: str | None = None):
        self.timeout_s = timeout_s
        self.python_executable = python_executable or sys.executable

    def run_solve(
        self,
        *,
        artifact_name: str,
        code: str,
        input_data: str,
        test_source: str,
        timeout_s: float | None = None,
    ) -> ExecutionResult:
        return self.run_function(
            artifact_name=artifact_name,
            code=code,
            function_name="solve",
            args=[input_data],
            test_source=test_source,
            timeout_s=timeout_s,
        )

    def run_validate(
        self,
        *,
        artifact_name: str,
        code: str,
        input_data: str,
        test_source: str,
        timeout_s: float | None = None,
    ) -> ExecutionResult:
        return self.run_function(
            artifact_name=artifact_name,
            code=code,
            function_name="validate",
            args=[input_data],
            test_source=test_source,
            timeout_s=timeout_s,
        )

    def run_check(
        self,
        *,
        artifact_name: str,
        code: str,
        input_data: str,
        output_data: str,
        expected_data: str | None,
        test_source: str,
        timeout_s: float | None = None,
    ) -> ExecutionResult:
        return self.run_function(
            artifact_name=artifact_name,
            code=code,
            function_name="check",
            args=[input_data, output_data, expected_data],
            test_source=test_source,
            timeout_s=timeout_s,
        )

    def run_generate_test_input(
        self,
        *,
        artifact_name: str,
        code: str,
        timeout_s: float | None = None,
    ) -> ExecutionResult:
        return self.run_function(
            artifact_name=artifact_name,
            code=code,
            function_name="generate_test_input",
            args=[],
            test_source=artifact_name,
            timeout_s=timeout_s,
        )

    def run_validate_test_input(
        self,
        *,
        artifact_name: str,
        code: str,
        input_data: str,
        timeout_s: float | None = None,
    ) -> ExecutionResult:
        return self.run_function(
            artifact_name=artifact_name,
            code=code,
            function_name="validate_test_input",
            args=[input_data],
            test_source=artifact_name,
            timeout_s=timeout_s,
        )

    def run_function(
        self,
        *,
        artifact_name: str,
        code: str,
        function_name: str,
        args: list[Any],
        test_source: str,
        timeout_s: float | None = None,
    ) -> ExecutionResult:
        syntax_error = _compile_error(code)
        if syntax_error:
            return ExecutionResult(
                artifact_name=artifact_name,
                function_name=function_name,
                test_source=test_source,
                status="compile_error",
                stderr=syntax_error,
                error_reason=syntax_error,
            )

        with tempfile.TemporaryDirectory(prefix="apg_pkg_run_") as tempdir:
            temp_path = Path(tempdir)
            module_path = temp_path / "candidate.py"
            wrapper_path = temp_path / "runner.py"
            module_path.write_text(code, encoding="utf-8")
            wrapper_path.write_text(_build_wrapper(function_name), encoding="utf-8")

            started = time.perf_counter()
            try:
                completed = subprocess.run(
                    [self.python_executable, str(wrapper_path)],
                    input=json.dumps({"args": args}, ensure_ascii=False),
                    text=True,
                    cwd=str(temp_path),
                    capture_output=True,
                    timeout=timeout_s or self.timeout_s,
                    shell=False,
                )
            except subprocess.TimeoutExpired as exc:
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                return ExecutionResult(
                    artifact_name=artifact_name,
                    function_name=function_name,
                    test_source=test_source,
                    status="timeout",
                    stdout=exc.stdout or "",
                    stderr=exc.stderr or "",
                    elapsed_ms=elapsed_ms,
                    error_reason="执行超时。",
                )

            elapsed_ms = int((time.perf_counter() - started) * 1000)
            stdout = completed.stdout.strip()
            stderr = completed.stderr.strip()
            if completed.returncode == 3:
                return ExecutionResult(
                    artifact_name=artifact_name,
                    function_name=function_name,
                    test_source=test_source,
                    status="invalid_interface",
                    stdout=stdout,
                    stderr=stderr,
                    elapsed_ms=elapsed_ms,
                    error_reason=stderr or f"缺少可调用函数 {function_name}。",
                )
            if completed.returncode != 0:
                return ExecutionResult(
                    artifact_name=artifact_name,
                    function_name=function_name,
                    test_source=test_source,
                    status="runtime_error",
                    stdout=stdout,
                    stderr=stderr,
                    elapsed_ms=elapsed_ms,
                    error_reason=stderr or "执行失败。",
                )

            try:
                payload = json.loads(stdout)
            except json.JSONDecodeError as exc:
                return ExecutionResult(
                    artifact_name=artifact_name,
                    function_name=function_name,
                    test_source=test_source,
                    status="runtime_error",
                    stdout=stdout,
                    stderr=stderr,
                    elapsed_ms=elapsed_ms,
                    error_reason=f"执行器返回非 JSON：{exc}",
                )
            if not payload.get("ok"):
                return ExecutionResult(
                    artifact_name=artifact_name,
                    function_name=function_name,
                    test_source=test_source,
                    status="runtime_error",
                    stdout=stdout,
                    stderr=str(payload.get("error", "")),
                    elapsed_ms=elapsed_ms,
                    error_reason=str(payload.get("error", "执行失败。")),
                )
            return ExecutionResult(
                artifact_name=artifact_name,
                function_name=function_name,
                test_source=test_source,
                status="ok",
                stdout=stdout,
                stderr=stderr,
                result=payload.get("result"),
                elapsed_ms=elapsed_ms,
            )


def _compile_error(code: str) -> str:
    try:
        compile(code, "<generated_code>", "exec")
    except SyntaxError as exc:
        return f"{exc.__class__.__name__}: {exc}"
    return ""


def _build_wrapper(function_name: str) -> str:
    # wrapper 只负责加载临时代码并调用约定函数，避免使用 shell 执行字符串。
    return f"""from __future__ import annotations

import importlib.util
import json
import traceback
from pathlib import Path


def main() -> int:
    payload = json.loads(__import__("sys").stdin.read() or "{{}}")
    spec = importlib.util.spec_from_file_location("candidate", Path(__file__).with_name("candidate.py"))
    module = importlib.util.module_from_spec(spec)
    try:
        assert spec is not None and spec.loader is not None
        spec.loader.exec_module(module)
    except Exception:
        traceback.print_exc()
        return 1
    func = getattr(module, "{function_name}", None)
    if not callable(func):
        print(f"缺少可调用函数 {function_name}", file=__import__("sys").stderr)
        return 3
    try:
        result = func(*payload.get("args", []))
        print(json.dumps({{"ok": True, "result": result}}, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({{"ok": False, "error": traceback.format_exc()}}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
"""
