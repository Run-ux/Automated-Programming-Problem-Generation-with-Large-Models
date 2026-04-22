from __future__ import annotations

from pathlib import Path

try:
    from .env_loader import get_env_value
except ImportError:
    from env_loader import get_env_value


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent


def _get_env_int(name: str, default: int) -> int:
    raw = get_env_value(name)
    if raw is None:
        return default
    try:
        return int(str(raw).strip())
    except ValueError:
        return default


def _get_env_float(name: str, default: float) -> float:
    raw = get_env_value(name)
    if raw is None:
        return default
    try:
        return float(str(raw).strip())
    except ValueError:
        return default


DEFAULT_OUTPUT_DIR = BASE_DIR / "output"
DEFAULT_MODEL = get_env_value("QWEN_MODEL", "qwen3.6-plus")
DEFAULT_BASE_URL = get_env_value(
    "QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
)
DEFAULT_API_KEY = get_env_value("QWEN_API_KEY") or get_env_value("DASHSCOPE_API_KEY")
DEFAULT_TIMEOUT_S = _get_env_int("QWEN_TIMEOUT_S", 360)
DEFAULT_ROUNDS = _get_env_int("PACKAGE_ITERATIONS", 3)
DEFAULT_KILL_RATE_THRESHOLD = _get_env_float("WRONG_SOLUTION_KILL_RATE", 0.8)
DEFAULT_RUN_TIMEOUT_S = _get_env_float("PACKAGE_RUN_TIMEOUT_S", 2.0)
DEFAULT_LARGE_RUN_TIMEOUT_S = _get_env_float("PACKAGE_LARGE_RUN_TIMEOUT_S", 6.0)

