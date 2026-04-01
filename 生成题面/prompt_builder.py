from __future__ import annotations

import json
from typing import Any

from models import VariantPlan
from schema_tools import dataclass_to_dict


def build_rule_selection_system_prompt() -> str:
    return """你是一名算法竞赛出题规则选择器。你的任务不是直接规划新题，而是先阅读 schema、原题参考和候选规则，从中选出最适合当前种子题的那一条规则。

硬性要求：
1. 只能从给定 `available_rules` 中选择一条规则，不能发明新规则。
2. 选择目标是在可稳定落地的前提下，让后续生成题的创新度和难度尽可能高。
3. 如果所有规则都不适用，返回 `status="difference_insufficient"` 或 `status="schema_insufficient"`。
4. 不要为了追求表面新颖度去选择会退化成浅改、后处理、参数放大或串联拼接的规则。
5. 如果模式是 `same_family_fusion`，优先检查共享主核、双向不可删贡献和反串联条件是否真实成立。
6. 输出必须是严格 JSON，不要输出 Markdown。

返回格式：
{
  "status": "ok|schema_insufficient|difference_insufficient",
  "selected_rule_id": string,
  "selection_reason": string,
  "innovation_reason": string,
  "difficulty_reason": string,
  "risk_reason": string,
  "error_reason": string,
  "feedback": string
}
"""


def build_rule_selection_user_prompt(
    *,
    mode: str,
    available_rules: list[dict[str, Any]],
    schema_context: dict[str, Any],
    original_problem_references: list[dict[str, Any]],
    global_constraints: dict[str, Any],
    global_redlines: list[str],
) -> str:
    payload = {
        "mode": mode,
        "available_rules": available_rules,
        "schema_context": schema_context,
        "original_problem_references": original_problem_references,
        "global_constraints": global_constraints,
        "global_redlines": global_redlines,
    }
    return (
        "请在当前规则集中选择最适合当前 schema 的规则。"
        "\n要求：\n"
        "- 目标是在保证可落地的前提下，让生成题的创新度和难度尽可能高。\n"
        "- 如果某条规则只会导致浅改、换皮、后处理增强或伪融合，不要选择它。\n"
        "- `selection_reason` 要直接说明为什么它优于其余规则。\n"
        "- `innovation_reason` 要说明它会把哪些核心义务拉离原题。\n"
        "- `difficulty_reason` 要说明它会在哪个主求解责任上抬高难度。\n"
        "- `risk_reason` 要说明主要风险；如果风险可控，也要明确写出来。\n"
        "- 如果没有规则满足条件，返回失败状态，不要勉强挑选。\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def build_planner_system_prompt() -> str:
    return """你是一名算法竞赛出题规划器。你的任务不是直接写题面，而是依据四元组 schema、规则、原题参考和主题，输出一个严格 JSON 的规划结果。

硬性要求：
1. 只能在给定规则的边界内规划，不要自由创造未声明的规则类型。
2. 规划结果必须围绕四元组 `input_structure / core_constraints / objective / invariant` 展开。
3. 不要依赖 transform_space，不要回到旧的 option 枚举思路。
4. 必须先判断规则是否适用；若不适用，返回 `status="difference_insufficient"` 或 `status="schema_insufficient"`。
5. 不能输出换皮题。要明确说明哪些局部子程序可复用，哪些主导义务不能直套原解。
6. 如果是 same_family_fusion，必须解释共享主核、两题不可删贡献，以及为何不是串联子任务。
7. 输出必须是严格 JSON，不要输出 Markdown。

返回格式：
{
  "status": "ok|schema_insufficient|difference_insufficient",
  "error_reason": string,
  "feedback": string,
  "eligibility_reason": string,
  "core_transformation_summary": string,
  "difference_plan": {
    "changed_axes": string[],
    "rationale": string,
    "summary": string
  },
  "instantiated_schema": {
    "problem_id": string,
    "source": string,
    "input_structure": object,
    "core_constraints": object,
    "objective": object,
    "invariant": object,
    "instantiated_parameters": object,
    "selected_structural_options": string[],
    "selected_input_options": string[],
    "selected_invariant_options": string[],
    "difficulty": string
  },
  "algorithmic_delta_claim": {
    "seed_solver_core": string,
    "reusable_subroutines": string,
    "new_solver_core": string,
    "new_proof_obligation": string,
    "why_direct_reuse_fails": string
  },
  "anti_shallow_rationale": string,
  "auxiliary_moves": string[],
  "shared_core_summary": string,
  "shared_core_anchors": {
    "shared_state": string,
    "shared_transition": string,
    "shared_decision_basis": string
  },
  "seed_a_indispensable_obligation": string,
  "seed_b_indispensable_obligation": string,
  "why_not_sequential_composition": string,
  "fusion_ablation": {
    "without_seed_a": string,
    "without_seed_b": string
  }
}
"""


def build_planner_user_prompt(
    *,
    mode: str,
    rule: dict[str, Any],
    theme: dict[str, Any],
    schema_context: dict[str, Any],
    original_problem_references: list[dict[str, Any]],
    global_constraints: dict[str, Any],
    global_redlines: list[str],
) -> str:
    payload = {
        "mode": mode,
        "rule": rule,
        "theme": theme,
        "schema_context": schema_context,
        "original_problem_references": original_problem_references,
        "global_constraints": global_constraints,
        "global_redlines": global_redlines,
    }
    return (
        "请为当前规则生成一个规划候选。"
        "\n要求：\n"
        "- 先判断该规则是否适用，再决定是否继续规划。\n"
        "- 必须输出完整 instantiated_schema，不要只写自然语言摘要。\n"
        "- `difference_plan.changed_axes` 必须与 instantiated_schema 的真实变化保持一致。\n"
        "- 如果模式是 same_family_fusion，`shared_core_summary` 和三个 shared_core_anchors 不能为空。\n"
        "- 如果你认为该规则不适用或只能做浅改，请返回失败状态，不要硬套。\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def build_generation_system_prompt() -> str:
    return """你是一名经验丰富的算法竞赛命题人。

你的任务是根据规则驱动的差异计划和实例化后的四元组 schema，生成一份完整、自然、可发布的中文题面。

硬性要求：
1. 不要暴露原题编号、原题出处、算法名或“这是某题改编”等信息。
2. 题面必须以 `instantiated_schema` 为准，不能回退到种子题原始任务，也不能保留原题主算法作为主要解法。
3. 输出必须是严格 JSON 对象，不要输出 Markdown 或额外解释。
4. 如果规划信息不足以可靠生成，返回 `schema_insufficient`。
5. 如果你判断这仍会变成换皮题，或者熟悉原题的选手只需小改原解就能做出来，返回 `difference_insufficient`。
6. 样例至少 2 组，且必须和题目定义兼容。
7. `constraints` 中必须明确时间限制和空间限制。
8. 如果目标是计数类，必须说明精确计数还是取模及模数。
9. 不能复写种子题的句式骨架、样例套路或任务定义。
10. 新题的主要解法必须对应 `algorithmic_delta_claim.new_solver_core`，不能只是把 `seed_solver_core` 外面包一层后处理、二分、计数层或输出格式变化。

成功格式：
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

失败格式：
{
  "status": "schema_insufficient|difference_insufficient",
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
"""


def build_generation_user_prompt(
    schema_context: dict[str, Any],
    plan: VariantPlan,
    original_problem_references: list[dict[str, Any]],
) -> str:
    instantiated_schema = dataclass_to_dict(plan.instantiated_schema_snapshot)
    sample_shape_hint = _build_sample_shape_hint(instantiated_schema)
    payload = {
        "mode": plan.mode,
        "problem_id": plan.problem_id,
        "source_problem_ids": plan.source_problem_ids,
        "difficulty": plan.difficulty,
        "theme": {
            "id": plan.theme.theme_id,
            "name": plan.theme.name,
            "tone": plan.theme.tone,
            "keywords": plan.theme.keywords,
            "mapping_hint": plan.theme.mapping_hint,
        },
        "applied_rule": plan.applied_rule,
        "difference_plan": dataclass_to_dict(plan.difference_plan),
        "predicted_schema_distance": plan.predicted_schema_distance,
        "changed_axes_realized": plan.changed_axes_realized,
        "algorithmic_delta_claim": plan.algorithmic_delta_claim,
        "shared_core_summary": plan.shared_core_summary,
        "shared_core_anchors": plan.shared_core_anchors,
        "seed_contributions": plan.seed_contributions,
        "fusion_ablation": plan.fusion_ablation,
        "instantiated_schema": instantiated_schema,
        "schema_context": schema_context,
        "original_problem_references": original_problem_references,
    }
    return (
        "请基于以下规划生成完整题面。"
        "\n补充要求：\n"
        "- 必须让题面真实兑现 `difference_plan`、`algorithmic_delta_claim` 和 `instantiated_schema`。\n"
        "- 不要复写种子题任务定义，也不要把规则只写成背景包装。\n"
        "- 新题的主要解法必须落到 `algorithmic_delta_claim.new_solver_core`，不能继续由 `algorithmic_delta_claim.seed_solver_core` 主导。\n"
        "- 只有 `algorithmic_delta_claim.reusable_subroutines` 里明确提到的局部子程序可以复用；不能把原题整体解法框架直接搬过来。\n"
        "- 如果熟悉原题的选手只需要小改状态、补一个后处理、外包一层二分或计数，就能沿用原解，请不要继续生成，直接返回 `difference_insufficient`。\n"
        "- `algorithmic_delta_claim.why_direct_reuse_fails` 必须能在题面定义里体现出来，而不是只写在规划字段里。\n"
        f"- {sample_shape_hint}\n"
        "- `notes` 用于补充模数、字典序、证书定义、失败输出约定等关键说明；没有则返回空字符串。\n\n"
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
