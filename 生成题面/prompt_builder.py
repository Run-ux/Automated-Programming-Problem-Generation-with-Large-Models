from __future__ import annotations

import json
from typing import Any

from models import VariantPlan
from schema_tools import dataclass_to_dict


def build_system_prompt() -> str:
    return """你是一名经验丰富的算法竞赛命题人。

你的任务是根据给定的 Problem Schema、差异计划和实例化后的新 Schema，生成一份完整、自然、可发布的中文题面。

硬性要求：
1. 不要暴露原题编号、原题出处、算法名或“这是某题改编”之类的信息。
2. 题面必须自洽，背景和输入输出定义要精确匹配。
3. 不要虚构与目标无关的规则；所有规则都必须服务于可实现的算法问题。
4. 输出必须是严格 JSON 对象，不要输出 Markdown，不要输出额外解释。
5. JSON 必须使用以下二选一结构之一：
   - 成功生成且满足差异约束时：
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
   - 如果你判断差异计划本身无法在“不复述原题任务”的前提下可靠落地，只会变成换皮题时：
     {
       "status": "difference_insufficient",
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
10. 保留可追溯的同族算法线索，但必须实现差异计划中要求的核心轴变化；不得复述原题任务，不得只改故事包装。
11. 禁止出现以下换皮行为：原题叙事结构复写、输入输出关系不变只换名词、关键约束和目标几乎不变、原题思路几乎可直接照搬。
12. 如果信息不足，不要自行脑补关键规则；必须返回 `status="schema_insufficient"`，并在 `error_reason` 中明确指出缺失了哪些关键信息、为什么这会阻止可靠生成，在 `feedback` 中说明上游 schema 需要补充什么。
13. 如果差异计划无法可靠落地，不要硬写近似原题；必须返回 `status="difference_insufficient"`。"""


def build_user_prompt(
    schema: dict[str, Any],
    plan: VariantPlan,
    original_problem: dict[str, Any] | None = None,
) -> str:
    instantiated_schema = dataclass_to_dict(plan.instantiated_schema_snapshot)
    sample_shape_hint = _build_sample_shape_hint(instantiated_schema)
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
        "difference_plan": dataclass_to_dict(plan.difference_plan),
        "predicted_schema_distance": plan.predicted_schema_distance,
        "changed_axes_realized": plan.changed_axes_realized,
        "selected_objective": plan.objective,
        "selected_parameters": plan.numerical_parameters,
        "selected_structural_options": plan.structural_options,
        "selected_input_structure_options": plan.input_structure_options,
        "selected_invariant_options": plan.invariant_options,
        "instantiated_schema": instantiated_schema,
        "raw_schema_reference": {
            "input_structure": schema.get("input_structure", {}),
            "core_constraints": schema.get("core_constraints", {}),
            "objective": schema.get("objective", {}),
            "invariant": schema.get("invariant", {}),
            "transform_space": schema.get("transform_space", {}),
        },
        "original_problem_reference": _build_original_problem_reference(original_problem),
    }
    return (
        "请基于以下规划生成完整题面。"
        "\n\n生成要求补充：\n"
        "- 将抽象结构映射到故事主题中，但不要让故事掩盖规则，更不要让主题替代真实差异。\n"
        "- 输入输出格式写得像正常 OJ 题面。\n"
        "- 必须以 `instantiated_schema` 为准落地输入、目标、约束和结构选项，不要回退到原始 schema。\n"
        "- 若你判断上游 schema 信息不足，不能做补全；必须返回 `status=\"schema_insufficient\"`，并填写 `error_reason` 与 `feedback`，说明为什么不足以及上游需要补什么。\n"
        "- 若你发现差异计划无法可靠表达，只会变成原题换皮，必须返回 `status=\"difference_insufficient\"`。\n"
        "- 不要复写 `original_problem_reference` 中的任务定义、句式骨架、样例套路或标题语义。\n"
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


def _build_original_problem_reference(original_problem: dict[str, Any] | None) -> dict[str, Any]:
    if not original_problem:
        return {}

    return {
        "problem_id": original_problem.get("problem_id", ""),
        "title": original_problem.get("title", ""),
        "description_summary": _truncate_text(original_problem.get("description", ""), 500),
        "input_summary": _truncate_text(original_problem.get("input", ""), 220),
        "output_summary": _truncate_text(original_problem.get("output", ""), 220),
        "constraints_summary": _truncate_text(original_problem.get("constraints", ""), 220),
    }


def _truncate_text(text: str, limit: int) -> str:
    cleaned = " ".join(str(text).split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."
