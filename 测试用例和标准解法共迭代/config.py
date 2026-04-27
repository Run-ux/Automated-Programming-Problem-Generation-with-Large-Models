from __future__ import annotations

from pathlib import Path

try:
    from .env_loader import get_env_value
except ImportError:
    from env_loader import get_env_value


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent


def _get_env_text(name: str, default: str | None = None) -> str | None:
    raw = get_env_value(name)
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip()


def _get_env_int(name: str, default: int) -> int:
    raw = get_env_value(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return int(str(raw).strip())
    except ValueError:
        return default


def _get_env_float(name: str, default: float) -> float:
    raw = get_env_value(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return float(str(raw).strip())
    except ValueError:
        return default


DEFAULT_OUTPUT_DIR = BASE_DIR / "output"
DEFAULT_MODEL = _get_env_text("LLM_MODEL", "qwen3.6-plus")
DEFAULT_BASE_URL = _get_env_text("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
DEFAULT_API_KEY = _get_env_text("LLM_API_KEY")
DEFAULT_TIMEOUT_S = _get_env_int("LLM_TIMEOUT_S", 360)
DEFAULT_REVISION_ADVISOR_MODEL = _get_env_text("REVISION_ADVISOR_LLM_MODEL", DEFAULT_MODEL)
DEFAULT_REVISION_ADVISOR_BASE_URL = _get_env_text("REVISION_ADVISOR_LLM_BASE_URL", DEFAULT_BASE_URL)
DEFAULT_REVISION_ADVISOR_API_KEY = _get_env_text("REVISION_ADVISOR_LLM_API_KEY", DEFAULT_API_KEY)
DEFAULT_REVISION_ADVISOR_TIMEOUT_S = _get_env_int("REVISION_ADVISOR_LLM_TIMEOUT_S", DEFAULT_TIMEOUT_S)
DEFAULT_ROUNDS = _get_env_int("PACKAGE_ITERATIONS", 6)
DEFAULT_KILL_RATE_THRESHOLD = _get_env_float("WRONG_SOLUTION_KILL_RATE", 0.8)
DEFAULT_RUN_TIMEOUT_S = _get_env_float("PACKAGE_RUN_TIMEOUT_S", 2.0)
DEFAULT_LARGE_RUN_TIMEOUT_S = _get_env_float("PACKAGE_LARGE_RUN_TIMEOUT_S", 6.0)
