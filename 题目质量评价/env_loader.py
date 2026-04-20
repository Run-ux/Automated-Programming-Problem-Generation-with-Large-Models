from __future__ import annotations

from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parent
MODULE_ENV_FILE = MODULE_DIR / ".env"


def read_module_env(env_file: Path | None = None) -> dict[str, str]:
    target = env_file or MODULE_ENV_FILE
    if not target.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in target.read_text(encoding="utf-8").splitlines():
        parsed = _parse_env_line(raw_line)
        if parsed is None:
            continue
        key, value = parsed
        values[key] = value
    return values


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("export "):
        stripped = stripped[len("export ") :].lstrip()
    if "=" not in stripped:
        return None

    key, value = stripped.split("=", 1)
    key = key.strip()
    if not key:
        return None

    value = value.strip()
    if value and value[0] in {'"', "'"} and value[-1:] == value[0]:
        value = value[1:-1]
    else:
        comment_index = value.find(" #")
        if comment_index >= 0:
            value = value[:comment_index].rstrip()
    return key, value


MODULE_ENV = read_module_env()


def get_env_value(name: str, default: str | None = None) -> str | None:
    return MODULE_ENV.get(name, default)
