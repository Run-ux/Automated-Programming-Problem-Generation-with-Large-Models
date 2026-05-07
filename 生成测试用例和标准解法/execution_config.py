from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:  # 兼容包内导入与当前目录直接运行两种方式。
    from .llm_config import DotEnvError, load_dotenv_values
except ImportError:  # pragma: no cover - 当前测试以顶层模块方式导入。
    from llm_config import DotEnvError, load_dotenv_values


DEFAULT_TEST_INPUT_TIMEOUT_SECONDS = 5.0
DEFAULT_TEST_INPUT_MEMORY_LIMIT_MB = 512
DEFAULT_BRUTEFORCE_TIMEOUT_SECONDS = 5.0
DEFAULT_BRUTEFORCE_MEMORY_LIMIT_MB = 512
DEFAULT_CHECKER_TIMEOUT_SECONDS = 5.0
DEFAULT_CHECKER_MEMORY_LIMIT_MB = 512


def _read_positive_float(values: dict[str, str], key: str, default: float) -> float:
    raw_value = values.get(key, "").strip()
    if not raw_value:
        return default
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise DotEnvError(f".env 配置 {key} 必须是数字。") from exc
    if value <= 0:
        raise DotEnvError(f".env 配置 {key} 必须大于 0。")
    return value


def _read_positive_int(values: dict[str, str], key: str, default: int) -> int:
    raw_value = values.get(key, "").strip()
    if not raw_value:
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise DotEnvError(f".env 配置 {key} 必须是整数。") from exc
    if value <= 0:
        raise DotEnvError(f".env 配置 {key} 必须大于 0。")
    return value


@dataclass(frozen=True)
class ExecutionConfig:
    """本地执行生成代码、暴力解法和 checker 时使用的资源限制。"""

    test_input_timeout_seconds: float = DEFAULT_TEST_INPUT_TIMEOUT_SECONDS
    test_input_memory_limit_mb: int = DEFAULT_TEST_INPUT_MEMORY_LIMIT_MB
    bruteforce_timeout_seconds: float = DEFAULT_BRUTEFORCE_TIMEOUT_SECONDS
    bruteforce_memory_limit_mb: int = DEFAULT_BRUTEFORCE_MEMORY_LIMIT_MB
    checker_timeout_seconds: float = DEFAULT_CHECKER_TIMEOUT_SECONDS
    checker_memory_limit_mb: int = DEFAULT_CHECKER_MEMORY_LIMIT_MB

    @classmethod
    def from_dotenv(cls, path: str | Path = ".env") -> "ExecutionConfig":
        """从 .env 读取执行限制；.env 缺失时使用安全默认值。"""

        try:
            values = load_dotenv_values(path)
        except DotEnvError as exc:
            if "找不到 .env 文件" in str(exc):
                return cls()
            raise

        return cls(
            test_input_timeout_seconds=_read_positive_float(
                values,
                "EXECUTION_TEST_INPUT_TIMEOUT_SECONDS",
                DEFAULT_TEST_INPUT_TIMEOUT_SECONDS,
            ),
            test_input_memory_limit_mb=_read_positive_int(
                values,
                "EXECUTION_TEST_INPUT_MEMORY_LIMIT_MB",
                DEFAULT_TEST_INPUT_MEMORY_LIMIT_MB,
            ),
            bruteforce_timeout_seconds=_read_positive_float(
                values,
                "EXECUTION_BRUTEFORCE_TIMEOUT_SECONDS",
                DEFAULT_BRUTEFORCE_TIMEOUT_SECONDS,
            ),
            bruteforce_memory_limit_mb=_read_positive_int(
                values,
                "EXECUTION_BRUTEFORCE_MEMORY_LIMIT_MB",
                DEFAULT_BRUTEFORCE_MEMORY_LIMIT_MB,
            ),
            checker_timeout_seconds=_read_positive_float(
                values,
                "EXECUTION_CHECKER_TIMEOUT_SECONDS",
                DEFAULT_CHECKER_TIMEOUT_SECONDS,
            ),
            checker_memory_limit_mb=_read_positive_int(
                values,
                "EXECUTION_CHECKER_MEMORY_LIMIT_MB",
                DEFAULT_CHECKER_MEMORY_LIMIT_MB,
            ),
        )
