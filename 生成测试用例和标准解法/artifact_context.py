from __future__ import annotations

import json
from typing import Any


GENERATED_PROBLEM_FIELDS = (
    "title",
    "description",
    "input_format",
    "output_format",
    "constraints",
    "samples",
    "notes",
)

SCHEMA_FIELDS = (
    "input_structure",
    "core_constraints",
    "objective",
    "invariant",
)


def extract_generated_problem(artifact: dict[str, Any]) -> dict[str, Any]:
    """从 artifact 中抽取题面字段；缺字段立即报错。"""
    if not isinstance(artifact, dict):
        raise ValueError("artifact 必须是字典。")
    source = artifact.get("generated_problem")
    if not isinstance(source, dict):
        raise ValueError("artifact.generated_problem 必须是字典。")

    missing = [field for field in GENERATED_PROBLEM_FIELDS if field not in source]
    if missing:
        raise ValueError("artifact.generated_problem 缺少字段: " + ", ".join(missing))

    return {field: source[field] for field in GENERATED_PROBLEM_FIELDS}


def extract_schema_snapshot(artifact: dict[str, Any]) -> dict[str, Any]:
    """从 artifact 中抽取 new_schema_snapshot 四字段；缺字段立即报错。"""
    if not isinstance(artifact, dict):
        raise ValueError("artifact 必须是字典。")
    source = artifact.get("new_schema_snapshot")
    if not isinstance(source, dict):
        raise ValueError("artifact.new_schema_snapshot 必须是字典。")

    missing = [field for field in SCHEMA_FIELDS if field not in source]
    if missing:
        raise ValueError("artifact.new_schema_snapshot 缺少字段: " + ", ".join(missing))

    return {field: source[field] for field in SCHEMA_FIELDS}


def build_prompt_payload(artifact: dict[str, Any], *, include_schema: bool = False) -> dict[str, Any]:
    payload = extract_generated_problem(artifact)
    if include_schema:
        payload.update(extract_schema_snapshot(artifact))
    return payload


def format_prompt_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return "" if value is None else str(value)

