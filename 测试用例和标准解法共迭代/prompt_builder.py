from __future__ import annotations

import json
from typing import Any


def build_spec_system_prompt() -> str:
    return """你是一名算法竞赛题包规格抽取器。

任务：把题面、new_schema 与算法变化声明转换为可执行规格。输出必须是严格 JSON，不要输出 Markdown。

必须保守处理歧义：若题面或输出合同不完整，在 ambiguity_notes 中记录，不要自行补设定。
"""


def build_spec_user_prompt(context: dict[str, Any], revision_context: dict[str, Any] | None = None) -> str:
    payload = {"context": context, "revision_context": revision_context or {}}
    return (
        "请输出 execution_spec。字段必须包含：problem_id、input_contract、output_contract、judge_type、"
        "oracle_limits、test_buckets、sample_tests、performance_limits、ambiguity_notes。\n"
        "judge_type 只能是 exact 或 checker；构造、多解、证书题必须使用 checker。\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def build_code_system_prompt(role: str) -> str:
    return f"""你是一名算法竞赛题包生成器，当前角色是 {role}。

只输出严格 JSON。代码必须是 Python 3 标准库代码，不要依赖第三方包。
所有代码必须使用指定函数接口，不要读写文件，不要联网，不要在导入阶段执行求解逻辑。
"""


def build_standard_solution_prompt(context: dict[str, Any], spec: dict[str, Any], revision_context: dict[str, Any] | None = None) -> str:
    payload = {"context": context, "execution_spec": spec, "revision_context": revision_context or {}}
    return (
        "请生成标准解法。返回 JSON 字段：code、algorithm、correctness、time_complexity、space_complexity、notes。\n"
        "code 必须实现 solve(input_str: str) -> str。\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def build_oracle_prompt(context: dict[str, Any], spec: dict[str, Any], revision_context: dict[str, Any] | None = None) -> str:
    payload = {"context": context, "execution_spec": spec, "revision_context": revision_context or {}}
    return (
        "请生成小规模暴力 oracle。返回 JSON 字段：code、oracle_scope、method、notes。\n"
        "code 必须实现 solve(input_str: str) -> str，只保证在 oracle_scope 声明的小规模范围内正确。\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def build_tools_prompt(context: dict[str, Any], spec: dict[str, Any], revision_context: dict[str, Any] | None = None) -> str:
    payload = {"context": context, "execution_spec": spec, "revision_context": revision_context or {}}
    return (
        "请生成 validator、checker、test_generator。返回 JSON 字段：validator_code、checker_code、test_generator_code、notes。\n"
        "validator_code 必须实现 validate(input_str: str) -> bool。\n"
        "checker_code 必须实现 check(input_str: str, output_str: str, expected_str: str | None) -> bool。\n"
        "test_generator_code 必须实现 generate_tests() -> list[dict]，每条测试包含 input、source、purpose。\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def build_weak_player_prompt(statement_only_context: dict[str, Any], revision_context: dict[str, Any] | None = None) -> str:
    payload = {"statement_context": statement_only_context, "revision_context": revision_context or {}}
    return (
        "你现在扮演编码能力较弱、容易误解边界的参赛选手。只能根据题面和样例写解法，不能假设隐藏 schema。\n"
        "请生成 3 到 5 份候选选手代码，返回 JSON 字段 wrong_solutions。\n"
        "每项包含 solution_id、code、bug_type、expected_failure、source。\n"
        "code 必须实现 solve(input_str: str) -> str。\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )

