from __future__ import annotations

from typing import Any

from artifact_context import extract_generated_problem, extract_schema_snapshot, format_prompt_value


JSON_ONLY_RULE = (
    "最终只输出单个 JSON 对象；不要输出 Markdown 代码块；不要在 JSON 外输出解释、前后缀或多余文本。"
    "代码内容必须放在 JSON 字符串字段中，代码字符串本身不要包含 ```。"
)

SOLVE_INTERFACE_RULE = "代码必须实现统一接口 solve(input_str: str) -> str。"


def generated_problem_section(artifact: dict[str, Any]) -> str:
    problem = extract_generated_problem(artifact)
    return "\n".join(
        [
            "# 题目描述信息",
            "",
            "title:",
            format_prompt_value(problem["title"]),
            "",
            "description:",
            format_prompt_value(problem["description"]),
            "",
            "input_format:",
            format_prompt_value(problem["input_format"]),
            "",
            "output_format:",
            format_prompt_value(problem["output_format"]),
            "",
            "constraints:",
            format_prompt_value(problem["constraints"]),
            "",
            "samples:",
            format_prompt_value(problem["samples"]),
            "",
            "notes:",
            format_prompt_value(problem["notes"]),
        ]
    )


def schema_section(artifact: dict[str, Any]) -> str:
    schema = extract_schema_snapshot(artifact)
    return "\n".join(
        [
            "# 题目结构信息",
            "",
            "input_structure:",
            format_prompt_value(schema["input_structure"]),
            "",
            "core_constraints:",
            format_prompt_value(schema["core_constraints"]),
            "",
            "objective:",
            format_prompt_value(schema["objective"]),
            "",
            "invariant:",
            format_prompt_value(schema["invariant"]),
        ]
    )


def json_contract(schema_text: str) -> str:
    return "\n".join(
        [
            "# 输出 JSON 合同",
            JSON_ONLY_RULE,
            "",
            "JSON 字段必须严格符合以下结构：",
            schema_text.strip(),
        ]
    )


def format_strategy(strategy: Any) -> str:
    if isinstance(strategy, list):
        raise ValueError("错误策略必须是单条策略，不能一次传入策略列表。")
    return format_prompt_value(strategy)

