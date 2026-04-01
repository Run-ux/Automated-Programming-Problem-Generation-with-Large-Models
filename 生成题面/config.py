from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

DEFAULT_SOURCE_DIR = (
    PROJECT_ROOT / "finiteness_verification" / "output" / "pilot" / "voted"
)
DEFAULT_OUTPUT_DIR = BASE_DIR / "output"
DEFAULT_ARTIFACT_DIR = BASE_DIR / "artifacts"
DEFAULT_REPORT_DIR = BASE_DIR / "reports"
DEFAULT_PREPARED_SCHEMA_DIR = BASE_DIR / "prepared_schemas"
DEFAULT_RULE_FILE = BASE_DIR / "planning_rules.json"

DEFAULT_MODEL = os.getenv("QWEN_MODEL", "qwen3.5-plus")
DEFAULT_BASE_URL = os.getenv(
    "QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
)
DEFAULT_API_KEY = os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY")

DEFAULT_VARIANTS = 1
DEFAULT_TEMPERATURE = 0.2
