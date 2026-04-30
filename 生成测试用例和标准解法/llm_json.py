from __future__ import annotations

import json
from typing import Any


class LLMResponseError(ValueError):
    """表示 LLM 返回内容不是合法 JSON 或不符合当前产物合同。"""


def parse_json_object(raw_response: str, task_name: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise LLMResponseError(f"{task_name} 返回内容不是合法 JSON 对象。") from exc
    if not isinstance(parsed, dict):
        raise LLMResponseError(f"{task_name} 返回 JSON 必须是对象。")
    return parsed


def _require_keys(payload: dict[str, Any], keys: tuple[str, ...], task_name: str) -> None:
    missing = [key for key in keys if key not in payload]
    if missing:
        raise LLMResponseError(f"{task_name} 缺少字段: {', '.join(missing)}")


def _require_non_empty_string(payload: dict[str, Any], key: str, task_name: str) -> None:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise LLMResponseError(f"{task_name}.{key} 必须是非空字符串。")


def _require_string(payload: dict[str, Any], key: str, task_name: str) -> None:
    if not isinstance(payload.get(key), str):
        raise LLMResponseError(f"{task_name}.{key} 必须是字符串。")


def validate_solution_response(payload: dict[str, Any], *, task_name: str, markdown_key: str) -> dict[str, Any]:
    _require_keys(
        payload,
        ("status", "block_reason", markdown_key, "code", "time_complexity", "space_complexity"),
        task_name,
    )
    status = payload["status"]
    if status not in ("ok", "blocked"):
        raise LLMResponseError(f"{task_name}.status 必须是 ok 或 blocked。")

    _require_string(payload, "block_reason", task_name)
    _require_string(payload, markdown_key, task_name)
    _require_string(payload, "code", task_name)
    _require_string(payload, "time_complexity", task_name)
    _require_string(payload, "space_complexity", task_name)

    if status == "ok":
        if payload["block_reason"] != "":
            raise LLMResponseError(f"{task_name} status=ok 时 block_reason 必须为空字符串。")
        _require_non_empty_string(payload, markdown_key, task_name)
        _require_non_empty_string(payload, "code", task_name)
    else:
        _require_non_empty_string(payload, "block_reason", task_name)
        if payload["code"] != "":
            raise LLMResponseError(f"{task_name} status=blocked 时 code 必须为空字符串。")
    return payload


def validate_test_generator_response(payload: dict[str, Any], *, task_name: str) -> dict[str, Any]:
    _require_keys(payload, ("constraint_analysis", "generate_test_input_code", "validate_test_input_code"), task_name)
    _require_non_empty_string(payload, "constraint_analysis", task_name)
    _require_non_empty_string(payload, "generate_test_input_code", task_name)
    _require_non_empty_string(payload, "validate_test_input_code", task_name)
    return payload


def validate_small_challenge_response(payload: dict[str, Any], *, task_name: str) -> dict[str, Any]:
    _require_keys(payload, ("test_input",), task_name)
    _require_non_empty_string(payload, "test_input", task_name)
    return payload


def validate_checker_response(payload: dict[str, Any], *, task_name: str = "checker") -> dict[str, Any]:
    _require_keys(payload, ("needs_checker",), task_name)
    needs_checker = payload["needs_checker"]
    if not isinstance(needs_checker, bool):
        raise LLMResponseError(f"{task_name}.needs_checker 必须是布尔值。")

    if needs_checker:
        _require_keys(payload, ("output_rule_analysis", "checker_code", "notes"), task_name)
        _require_non_empty_string(payload, "output_rule_analysis", task_name)
        _require_non_empty_string(payload, "checker_code", task_name)
        _require_non_empty_string(payload, "notes", task_name)
    else:
        _require_keys(payload, ("reason",), task_name)
        _require_non_empty_string(payload, "reason", task_name)
        if payload.get("checker_code"):
            raise LLMResponseError(f"{task_name} needs_checker=false 时不应返回 checker_code。")
    return payload


def validate_strategy_analysis_response(payload: dict[str, Any], *, task_name: str = "strategy_analysis") -> dict[str, Any]:
    _require_keys(payload, ("strategies",), task_name)
    strategies = payload["strategies"]
    if not isinstance(strategies, list) or not strategies:
        raise LLMResponseError(f"{task_name}.strategies 必须是非空列表。")

    required_fields = ("title", "wrong_idea", "plausible_reason", "failure_reason", "trigger_case")
    for index, strategy in enumerate(strategies):
        item_task_name = f"{task_name}.strategies[{index}]"
        if not isinstance(strategy, dict):
            raise LLMResponseError(f"{item_task_name} 必须是对象。")
        _require_keys(strategy, required_fields, item_task_name)
        for field in required_fields:
            _require_non_empty_string(strategy, field, item_task_name)
    return payload


def validate_wrong_solution_response(payload: dict[str, Any], *, task_name: str) -> dict[str, Any]:
    _require_keys(payload, ("code",), task_name)
    _require_non_empty_string(payload, "code", task_name)
    return payload

