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

DEFAULT_SOURCE_DIR = (
    PROJECT_ROOT / "四元组抽取" / "output" / "batch" / "normalized"
)
DEFAULT_OUTPUT_DIR = BASE_DIR / "output"
DEFAULT_ARTIFACT_DIR = BASE_DIR / "artifacts"
DEFAULT_REPORT_DIR = BASE_DIR / "reports"
DEFAULT_PREPARED_SCHEMA_DIR = BASE_DIR / "prepared_schemas"
DEFAULT_RULE_FILE = BASE_DIR / "planning_rules.json"

DEFAULT_MODEL = get_env_value("QWEN_MODEL", "qwen3.6-plus")
DEFAULT_EMBEDDING_MODEL = get_env_value("QWEN_EMBEDDING_MODEL", "text-embedding-v4")
DEFAULT_BASE_URL = get_env_value(
    "QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
)
DEFAULT_API_KEY = get_env_value("QWEN_API_KEY") or get_env_value("DASHSCOPE_API_KEY")
DEFAULT_TIMEOUT_S = _get_env_int("QWEN_TIMEOUT_S", 360)

DEFAULT_VARIANTS = 1
DEFAULT_TEMPERATURE = 0.2
DEFAULT_DISTANCE_CACHE_DIR = BASE_DIR / ".cache"
