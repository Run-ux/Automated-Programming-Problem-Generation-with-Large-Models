from __future__ import annotations

import json
from typing import Any

from models import VariantPlan


def build_system_prompt() -> str:
    return """你是一名经验丰富的算法竞赛命题人。

你的任务是根据给定的 Problem Schema 和变体规划，生成一份完整、自然、可发布的中文题面。

硬性要求：
1. 不要暴露原题编号、原题出处、算法名或“这是某题改编”之类的信息。
2. 题面必须自洽，背景和输入输出定义要精确匹配。
3. 不要虚构与目标无关的规则；所有规则都必须服务于可实现的算法问题。
4. 输出必须是严格 JSON 对象，不要输出 Markdown，不要输出额外解释。
5. JSON 必须使用以下二选一结构之一：
   - 成功生成时：
     {
       "status": "ok",
       "error_reason": "",
       "feedback": "",
       "title": string,
       "description": string,
       "input_format": string,
       "output_format": string,
       "constraints": string[],
       "samples": [{"input": string, "output": string, "explanation": string}],
       "notes": string
     }
   - 如果你判断上游 schema 信息不足，无法在“不虚构关键规则”的前提下可靠生成题面时：
     {
       "status": "schema_insufficient",
       "error_reason": string,
       "feedback": string,
       "title": "",
       "description": "",
       "input_format": "",
       "output_format": "",
       "constraints": [],
       "samples": [],
       "notes": ""
     }
6. `description` 需要自然分段，但仍是单个字符串。
7. 样例至少 2 组，输入输出必须与题意兼容；如果无法可靠构造复杂样例，可以给出小规模可验证样例。
8. `constraints` 中必须明确时间限制和空间限制。
9. 如果目标是计数类问题，说明是否取模以及模数。
10. 保留 Problem Schema 的核心不变量，不改变问题本质。
11. 如果信息不足，不要自行脑补关键规则；必须返回 `status="schema_insufficient"`，并在 `error_reason` 中明确指出缺失了哪些关键信息、为什么这会阻止可靠生成，在 `feedback` 中说明上游 schema 需要补充什么。"""


def build_user_prompt(schema: dict[str, Any], plan: VariantPlan) -> str:
    sample_shape_hint = _build_sample_shape_hint(schema)
    payload = {
        "problem_id": plan.problem_id,
        "difficulty": plan.difficulty,
        "theme": {
            "id": plan.theme.theme_id,
            "name": plan.theme.name,
            "tone": plan.theme.tone,
            "keywords": plan.theme.keywords,
            "mapping_hint": plan.theme.mapping_hint,
        },
        "selected_objective": plan.objective,
        "selected_parameters": plan.numerical_parameters,
        "selected_structural_options": plan.structural_options,
        "input_summary": plan.input_summary,
        "constraint_summary": plan.constraint_summary,
        "invariant_summary": plan.invariant_summary,
        "raw_schema": {
            "input_structure": schema.get("input_structure", {}),
            "core_constraints": schema.get("core_constraints", {}),
            "objective": schema.get("objective", {}),
            "invariant": schema.get("invariant", {}),
            "transform_space": schema.get("transform_space", {}),
        },
    }
    return (
        "请基于以下规划生成完整题面。"
        "\n\n生成要求补充：\n"
        "- 将抽象结构映射到故事主题中，但不要让故事掩盖规则。\n"
        "- 输入输出格式写得像正常 OJ 题面。\n"
        "- 若你判断上游 schema 信息不足，不能做补全；必须返回 `status=\"schema_insufficient\"`，并填写 `error_reason` 与 `feedback`，说明为什么不足以及上游需要补什么。\n"
        f"- {sample_shape_hint}\n"
        "- `notes` 用于补充取模、字典序、合法性边界等关键说明；没有则返回空字符串。\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def _build_sample_shape_hint(schema: dict[str, Any]) -> str:
    input_structure = schema.get("input_structure", {})
    if input_structure.get("type") != "array":
        return "样例输入必须严格匹配题目定义，使用纯文本，不要输出 Markdown 标记或 HTML 片段。"

    length = input_structure.get("length", {})
    min_length = length.get("min")
    max_length = length.get("max")
    if isinstance(min_length, int) and min_length == max_length and 1 <= min_length <= 10:
        return (
            f"样例输入必须严格写成 {min_length} 行纯文本，每行一个输入项；"
            "不要把多行输入压成一行，不要包含 Markdown 标记、HTML 片段或异常引号。"
        )

    return "样例输入必须严格匹配题目定义，使用纯文本，不要输出 Markdown 标记或 HTML 片段。"
