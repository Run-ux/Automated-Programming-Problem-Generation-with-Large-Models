from __future__ import annotations

import json
from typing import Any

from artifact_context import build_llm_problem_payload


FIXED_WRONG_CATEGORIES = (
    "目标/输出义务误读",
    "核心约束简化",
    "invariant 误读",
    "边界/最小性错误",
    "复杂度/规模误判",
)


def problem_payload(
    context: dict[str, Any],
    *,
    include_revision: bool,
    revision_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = build_llm_problem_payload(context)
    if include_revision:
        payload["revision_context"] = revision_context or {}
    return payload


def build_revision_guidance(
    revision_context: dict[str, Any] | None,
    *,
    role: str,
    fallback: str,
) -> str:
    revision_context = revision_context or {}
    active_revision_context = revision_context.get("active_revision_context")
    if isinstance(active_revision_context, dict) and not any(
        key in revision_context for key in ("summary", "role_diagnostics", "surviving_wrong_solution_details")
    ):
        merged_context = dict(active_revision_context)
        for key in ("revision_mode", "baseline_repair_mode", "current_artifact", "frozen_contract_summary"):
            if key in revision_context:
                merged_context[key] = revision_context[key]
        revision_context = merged_context
    if not has_structured_revision_context(revision_context):
        return f"- 当前没有结构化 revision_context；{fallback}"

    guidance: list[str] = []
    if revision_context.get("revision_mode") == "incremental_patch":
        guidance.append("当前是增量修订轮：只能修 active_revision_context 中仍未解决且命中当前角色的问题；输出仍需是完整替换产物。")
    if revision_context.get("baseline_repair_mode") is True:
        guidance.append("当前基线未通过；只修复基础自洽相关的 blocker/high 问题，不要为了提高 kill_rate 扩展错误解覆盖。")

    failed_hard_checks = dedupe_strings(stringify_items(revision_context.get("failed_hard_checks")))
    if failed_hard_checks:
        guidance.append("优先修复 blocker 类问题：" + "、".join(failed_hard_checks))

    summary = format_summary(revision_context.get("summary"))
    if summary:
        guidance.append("失败概览：" + summary)

    role_items = diagnostics_for_role(revision_context, role)
    if role_items:
        guidance.append(f"{role} 定向诊断：" + "；".join(format_diagnostic(item) for item in role_items))

    survivor_text = format_surviving_wrong_solution_details(revision_context.get("surviving_wrong_solution_details"))
    if survivor_text and role in {
        "ToolGenerator",
        "TestGenerator",
        "SchemaMistakeAnalyzer",
        "FixedCategoryWrongSolutionGenerator",
        "StrategyWrongSolutionGenerator",
    }:
        guidance.append("仍存活的错误解详情：" + survivor_text + "。请优先针对这些错误模式补足区分度。")

    current_artifact_text = format_current_artifact(revision_context.get("current_artifact"))
    if current_artifact_text:
        guidance.append("当前工作副本摘要：" + current_artifact_text + "。应在此基础上做最小必要修改，并输出完整替换结果。")

    known_good_text = format_known_good_case_summaries(revision_context.get("known_good_case_summaries"))
    if known_good_text:
        guidance.append("known-good 回归合同：" + known_good_text + "。候选必须保持这些已通过路径全部通过。")

    if not guidance:
        return f"- 当前没有可执行修订项；{fallback}"
    guidance.append("无法在不改接口/合同的情况下修复时，在 notes 中返回结构性诊断，不要硬改既有接口。")
    return "\n".join(f"- {item}" for item in guidance)


def has_structured_revision_context(revision_context: dict[str, Any]) -> bool:
    return any(
        key in revision_context
        for key in ("summary", "role_diagnostics", "surviving_wrong_solution_details", "active_revision_context")
    )


def diagnostics_for_role(revision_context: dict[str, Any], role: str) -> list[dict[str, Any]]:
    role_diagnostics = revision_context.get("role_diagnostics")
    if not isinstance(role_diagnostics, dict):
        return []
    items = role_diagnostics.get(role, [])
    if not items and role in {"ValidatorGenerator", "CheckerGenerator", "TestGenerator"}:
        items = role_diagnostics.get("ToolGenerator", [])
    return [item for item in items if isinstance(item, dict)]


def format_summary(summary: Any) -> str:
    if not isinstance(summary, list):
        return ""
    parts: list[str] = []
    for item in summary[:6]:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category", "")).strip()
        count = item.get("count", 0)
        severity = str(item.get("severity", "")).strip()
        if category:
            parts.append(f"{category} x{count} [{severity}]")
    return "；".join(parts)


def format_diagnostic(diagnostic: dict[str, Any]) -> str:
    parts = [
        str(diagnostic.get("category", "")).strip(),
        str(diagnostic.get("title", "")).strip(),
        str(diagnostic.get("detail", "")).strip(),
    ]
    advisor = diagnostic.get("advisor_revision")
    if isinstance(advisor, dict) and str(advisor.get("revision_advice", "")).strip():
        parts.append("advisor修订建议：" + str(advisor.get("revision_advice", "")).strip())
    return "，".join(part for part in parts if part)


def format_surviving_wrong_solution_details(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    parts: list[str] = []
    for item in value[:5]:
        if not isinstance(item, dict):
            continue
        solution_id = str(item.get("solution_id", "")).strip()
        bug_type = str(item.get("bug_type", "")).strip()
        reason = str(item.get("reason", "")).strip()
        if solution_id:
            parts.append(f"{solution_id}（bug_type={bug_type or '未知'}，原因={reason or '当前测试未杀死'}）")
    return "；".join(parts)


def format_current_artifact(value: Any) -> str:
    if not isinstance(value, dict) or not value:
        return ""
    parts: list[str] = []
    for key in [
        "problem_context",
        "standard_solution",
        "bruteforce_solution",
        "validator",
        "checker",
        "random_test_generator",
        "adversarial_test_generator",
        "small_challenge_tests",
        "schema_mistake_points",
        "wrong_solutions",
    ]:
        if key not in value:
            continue
        item = value.get(key)
        if isinstance(item, dict):
            code_length = item.get("code_length")
            code_text = f"，代码长度={code_length}" if code_length else ""
            parts.append(f"{key}({item.get('name') or item.get('problem_id') or '已存在'}{code_text})")
        elif isinstance(item, list):
            parts.append(f"{key}(数量={len(item)})")
        else:
            parts.append(f"{key}(已存在)")
    return "；".join(parts[:8])


def format_known_good_case_summaries(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    parts: list[str] = []
    for item in value[:5]:
        if isinstance(item, dict):
            label = str(item.get("source") or item.get("purpose") or "").strip()
            if label:
                parts.append(label)
    return "；".join(parts)


def artifact_context(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        "name": value.get("name", ""),
        "role": value.get("role", ""),
        "code": value.get("code", ""),
        "metadata": value.get("metadata", {}),
    }


def stringify_items(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def dedupe_strings(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def format_prompt_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)
