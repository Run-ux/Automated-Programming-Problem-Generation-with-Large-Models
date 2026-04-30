from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


DEFAULT_TEMPERATURE = 0.2
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_RETRIES = 2


class DotEnvError(ValueError):
    """表示 .env 文件缺失、格式错误或必要配置不完整。"""


def _module_root() -> Path:
    return Path(__file__).resolve().parent


def _resolve_env_path(path: str | Path) -> Path:
    env_path = Path(path)
    if env_path.is_absolute():
        return env_path
    return _module_root() / env_path


def _parse_quoted_value(raw_value: str, quote: str, line_number: int) -> str:
    end_index = raw_value.find(quote, 1)
    if end_index == -1:
        raise DotEnvError(f".env 第 {line_number} 行引号未闭合。")

    tail = raw_value[end_index + 1 :].strip()
    if tail and not tail.startswith("#"):
        raise DotEnvError(f".env 第 {line_number} 行引号后只能为空或注释。")
    return raw_value[1:end_index]


def _parse_env_value(raw_value: str, line_number: int) -> str:
    value = raw_value.strip()
    if not value:
        return ""

    if value[0] in ("'", '"'):
        return _parse_quoted_value(value, value[0], line_number)

    # 仅支持简单注释；未加引号时，只有行首或空白后的 # 被视为注释。
    for index, char in enumerate(value):
        if char == "#" and (index == 0 or value[index - 1].isspace()):
            return value[:index].strip()
    return value


def load_dotenv_values(path: str | Path) -> dict[str, str]:
    """读取简单 .env 文件，返回字符串配置字典。"""
    env_path = _resolve_env_path(path)
    if not env_path.exists():
        raise DotEnvError(f"找不到 .env 文件: {env_path}。请参考 .env.example 创建配置文件。")
    if not env_path.is_file():
        raise DotEnvError(f".env 路径不是文件: {env_path}")

    values: dict[str, str] = {}
    for line_number, line in enumerate(env_path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            raise DotEnvError(f".env 第 {line_number} 行格式错误，应为 KEY=VALUE。")

        key, raw_value = stripped.split("=", 1)
        key = key.strip()
        if not key or not key.replace("_", "").isalnum() or key[0].isdigit():
            raise DotEnvError(f".env 第 {line_number} 行配置名非法: {key!r}")
        values[key] = _parse_env_value(raw_value, line_number)

    return values


def _require_text(values: dict[str, str], key: str) -> str:
    value = values.get(key, "").strip()
    if not value:
        raise DotEnvError(f".env 缺少必要配置 {key}。请参考 .env.example。")
    return value


def _read_optional_text(values: dict[str, str], key: str) -> str | None:
    value = values.get(key, "").strip()
    return value or None


def _read_float(values: dict[str, str], key: str, default: float) -> float:
    raw_value = values.get(key, "").strip()
    if not raw_value:
        return default
    try:
        return float(raw_value)
    except ValueError as exc:
        raise DotEnvError(f".env 配置 {key} 必须是数字。") from exc


def _read_int(values: dict[str, str], key: str, default: int) -> int:
    raw_value = values.get(key, "").strip()
    if not raw_value:
        return default
    try:
        return int(raw_value)
    except ValueError as exc:
        raise DotEnvError(f".env 配置 {key} 必须是整数。") from exc


@dataclass(frozen=True)
class LLMConfig:
    api_key: str
    model: str
    base_url: str | None = None
    temperature: float = DEFAULT_TEMPERATURE
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_retries: int = DEFAULT_MAX_RETRIES

    @classmethod
    def from_dotenv(cls, path: str | Path = ".env") -> "LLMConfig":
        values = load_dotenv_values(path)
        return cls(
            api_key=_require_text(values, "OPENAI_API_KEY"),
            model=_require_text(values, "OPENAI_MODEL"),
            base_url=_read_optional_text(values, "OPENAI_BASE_URL"),
            temperature=_read_float(values, "OPENAI_TEMPERATURE", DEFAULT_TEMPERATURE),
            timeout_seconds=_read_float(values, "OPENAI_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS),
            max_retries=_read_int(values, "OPENAI_MAX_RETRIES", DEFAULT_MAX_RETRIES),
        )
