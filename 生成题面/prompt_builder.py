from __future__ import annotations

import json
from typing import Any

from models import VariantPlan
from schema_tools import dataclass_to_dict


def build_eligibility_system_prompt() -> str:
    return """你是一名算法竞赛题目变化规则资格审查官。

你的工作不是规划新题，也不是在多条规则之间做最终排序，而是针对单条规则做严格、保守的准入判断。

你必须扮演给定的 `review_role`，以该角色的审查重点判断当前规则是否值得进入后续规划阶段。

硬性要求：
1. 你一次只审查一条规则，不要比较其它规则。
2. 如果证据不足，默认拒绝，不要乐观放行。
3. 判断必须基于给定 schema、原题摘要、规则声明、全局约束和红线。
4. 你只能回答资格问题，不能替规划阶段发明新四元组。
5. 输出必须是严格 JSON，不要输出 Markdown。

返回格式：
{
  "status": "eligible|ineligible|schema_insufficient",
  "score": number,
  "reason_code": string,
  "selection_reason": string,
  "risk_tags": string[],
  "evidence": string,
  "feedback": string
}
"""


def build_eligibility_user_prompt(
    *,
    mode: str,
    review_role: str,
    rule: dict[str, Any],
    schema_context: dict[str, Any],
    original_problem_references: list[dict[str, Any]],
    global_constraints: dict[str, Any],
    global_redlines: list[str],
) -> str:
    payload = {
        "review_type": "eligibility",
        "mode": mode,
        "review_role": review_role,
        "rule_under_review": rule,
        "schema_context": schema_context,
        "original_problem_references": original_problem_references,
        "global_constraints": global_constraints,
        "global_redlines": global_redlines,
    }
    return (
        "请以给定角色完成单条规则资格审查。"
        "\n要求：\n"
        "- 只能判断该规则是否适合进入下一阶段规划。\n"
        "- `selection_reason` 直接写结论依据，不要泛泛而谈。\n"
        "- `evidence` 必须引用 schema、原题摘要或规则声明中的具体证据。\n"
        "- `score` 取 0 到 1，表示进入后续规划的把握度；拒绝时可以是 0 到 0.49。\n"
        "- `risk_tags` 只保留高价值风险标签，例如 `low_novelty`、`shared_core_risk`、`semantic_mismatch`。\n"
        "- 如果 schema 信息不足以判断，返回 `schema_insufficient`。\n"
        "- 如果不确定，返回 `ineligible`。\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def build_rule_plan_validation_system_prompt() -> str:
    return """你是一名算法竞赛规则规划审查官。

你的任务是只针对单条规则，审查一个规划结果是否兑现了该规则的专属语义合同。

硬性要求：
1. 你一次只审查一条规则，不要比较其它规则。
2. 通用代码级硬门槛已经由系统处理，你只负责规则专属语义合同。
3. 如果证据不足，默认返回 `fail`。
4. 不要替规划结果补设定，也不要发明新四元组。
5. 判断必须基于给定 `review_role`、`review_brief`、规则声明、source schema、candidate schema 与规划 payload。
6. 如果规则声明了 `helpers`，必须逐条检查这些 helper 是否都被应用，并且是否真的落到了四元组变化里。
7. 输出必须是严格 JSON，不要输出 Markdown。
8. JSON 只能包含规定字段，不能添加额外键。

返回格式：
{
  "status": "pass|fail",
  "reason_code": string,
  "message": string,
  "errors": string[],
  "evidence": string
}
"""


def build_rule_plan_validation_user_prompt(
    *,
    mode: str,
    review_role: str,
    review_brief: str,
    rule: dict[str, Any],
    source_schema: dict[str, Any],
    candidate_schema: dict[str, Any],
    changed_axes: list[str],
    planner_payload: dict[str, Any],
) -> str:
    payload = {
        "review_type": "rule_plan_validation",
        "mode": mode,
        "review_role": review_role,
        "review_brief": review_brief,
        "rule_under_review": _rule_review_excerpt(rule),
        "source_schema": source_schema,
        "candidate_schema": candidate_schema,
        "changed_axes": changed_axes,
        "planner_payload": planner_payload,
    }
    return (
        "请审查该规划是否兑现规则专属合同。"
        "\n要求：\n"
        "- `message` 直接概括结论，不要泛泛而谈。\n"
        "- `errors` 只写真正构成拒绝的规则专属问题；通过时返回空数组。\n"
        "- `evidence` 必须引用给定 payload、schema 或规则声明中的具体内容。\n"
        "- 如果规则声明了 `helpers`，要逐条核对 helper 是否全部出现，以及每个 helper 是否兑现了自己的目标变化轴、落点和 redlines。\n"
        "- 如果不能确认已经兑现规则专属合同，返回 `fail`。\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def build_rule_problem_validation_system_prompt() -> str:
    return """你是一名算法竞赛题面规则审查官。

你的任务是只针对单条规则，审查一份生成后的题面是否兑现了该规则的专属输出责任、失败语义与核心承诺。

硬性要求：
1. 你一次只审查一条规则，不要比较其它规则。
2. 通用结构校验已经由系统处理，你只负责规则专属语义合同。
3. 如果证据不足，默认返回 `fail`。
4. 不要替题面补设定，也不要假定未写出的语义已经成立。
5. 判断必须基于给定 `review_role`、`review_brief`、规则声明、计划摘要、`new_schema` 和题面内容。
6. 如果规则声明了 `helpers`，必须判断题面是否把这些 helper 对应的关键语义写实。
7. 输出必须是严格 JSON，不要输出 Markdown。
8. JSON 只能包含规定字段，不能添加额外键。

返回格式：
{
  "status": "pass|fail",
  "reason_code": string,
  "message": string,
  "errors": string[],
  "evidence": string
}
"""


def build_rule_problem_validation_user_prompt(
    *,
    mode: str,
    review_role: str,
    review_brief: str,
    rule: dict[str, Any],
    plan_context: dict[str, Any],
    generated_problem: dict[str, Any],
) -> str:
    payload = {
        "review_type": "rule_problem_validation",
        "mode": mode,
        "review_role": review_role,
        "review_brief": review_brief,
        "rule_under_review": _rule_review_excerpt(rule),
        "plan_context": plan_context,
        "generated_problem": generated_problem,
    }
    return (
        "请审查该题面是否兑现规则专属合同。"
        "\n要求：\n"
        "- `message` 直接概括结论，不要泛泛而谈。\n"
        "- `errors` 只写真正构成拒绝的规则专属问题；通过时返回空数组。\n"
        "- `evidence` 必须引用题面、`new_schema`、规划摘要或规则声明中的具体内容。\n"
        "- 如果规则声明了 `helpers`，要确认题面把这些 helper 的语义承诺写清，而不是只在规划摘要里出现。\n"
        "- 如果题面没有把关键语义写清楚，返回 `fail`。\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


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
  "ranked_rule_ids": string[],
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
    revision_context: dict[str, Any] | None = None,
) -> str:
    payload = {
        "mode": mode,
        "available_rules": available_rules,
        "schema_context": schema_context,
        "original_problem_references": original_problem_references,
        "global_constraints": global_constraints,
        "global_redlines": global_redlines,
        "revision_context": revision_context or {},
    }
    return (
        "请在当前规则集中选择最适合当前 schema 的规则。"
        "\n要求：\n"
        "- 目标是在保证可落地的前提下，让生成题的创新度和难度尽可能高。\n"
        "- 如果某条规则只会导致浅改、换皮、后处理增强或伪融合，不要选择它。\n"
        "- `selection_reason` 要直接说明为什么它优于其余规则。\n"
        "- 优先返回 `ranked_rule_ids`，按推荐尝试顺序排列前 2 到 3 条规则；`selected_rule_id` 保留为第一推荐项。\n"
        "- `innovation_reason` 要说明它会把哪些核心义务拉离原题。\n"
        "- `difficulty_reason` 要说明它会在哪个主求解责任上抬高难度。\n"
        "- `risk_reason` 要说明主要风险；如果风险可控，也要明确写出来。\n"
        "- 如果提供了 `revision_context`，要优先修复其中涉及规则选择、结构差异和反换皮风险的问题，并保留 `strengths_to_keep`。\n"
        "- 如果没有规则满足条件，返回失败状态，不要勉强挑选。\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def build_planner_system_prompt() -> str:
    return """你是一名算法竞赛出题规划器。你的任务不是直接写题面，而是依据四元组 schema、规则、原题参考和主题，输出一个严格 JSON 的规划结果。

硬性要求：
1. 只能在给定规则的边界内规划，不要自由创造未声明的规则类型。
2. 规划结果必须围绕四元组 `input_structure / core_constraints / objective / invariant` 展开。
3. 只围绕四元组与必要元信息规划，不要为 `new_schema` 扩展未声明字段。
4. 必须先判断规则是否适用；若不适用，返回 `status="difference_insufficient"` 或 `status="schema_insufficient"`。
5. 不能输出换皮题。要明确说明哪些局部子程序可复用，哪些主导义务不能直套原解。
6. 如果是 same_family_fusion，必须解释共享主核、两题不可删贡献，以及为何不是串联子任务。
7. 输出必须是严格 JSON，不要输出 Markdown。
8. 固定参数、输入特性、结构变化和不变量承诺都要直接写进四元组本身。
9. `algorithmic_delta_claim.new_proof_obligation` 表示新增正确性证明，要写清新题相对种子题多出来的关键证明点。

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
  "new_schema": {
    "problem_id": string,
    "source": string,
    "input_structure": object,
    "core_constraints": object,
    "objective": object,
    "invariant": object,
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
  "applied_helpers": [
    {
      "id": string,
      "selection_reason": string,
      "affected_axes": string[],
      "schema_changes": string[],
      "innovation_reason": string,
      "difficulty_reason": string
    }
  ],
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
    revision_context: dict[str, Any] | None = None,
) -> str:
    payload = {
        "mode": mode,
        "rule": rule,
        "theme": theme,
        "schema_context": schema_context,
        "original_problem_references": original_problem_references,
        "global_constraints": global_constraints,
        "global_redlines": global_redlines,
        "revision_context": revision_context or {},
    }
    return (
        "请为当前规则生成一个规划候选。"
        "\n要求：\n"
        "- 先判断该规则是否适用，再决定是否继续规划。\n"
        "- 必须输出完整 new_schema，不要只写自然语言摘要。\n"
        "- `difference_plan.changed_axes` 必须与 new_schema 的真实变化保持一致。\n"
        "- 所有参数、输入特性、结构变化和不变量承诺都必须 materialize 到四元组字段里。\n"
        "- `new_schema` 只能包含约定字段，不要附带任何额外键。\n"
        "- `algorithmic_delta_claim.new_proof_obligation` 表示新增正确性证明，不要把它写成泛泛的难度评价。\n"
        "- 必须应用当前规则声明的全部 `helpers`，并把它们完整写入 `applied_helpers`。\n"
        "- `applied_helpers` 中的每一项都要写清它作用到哪些变化轴、改变了哪些 schema 部分、怎样抬高创新度、怎样抬高难度。\n"
        "- 如果模式是 same_family_fusion，`shared_core_summary` 和三个 shared_core_anchors 不能为空。\n"
        "- 如果提供了 `revision_context`，要优先修复其中涉及结构差异、目标定义、规则落地和反换皮风险的问题，并保留 `strengths_to_keep`。\n"
        "- 如果你认为该规则不适用或只能做浅改，请返回失败状态，不要硬套。\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def build_generation_system_prompt() -> str:
    return """你是一名经验丰富的算法竞赛命题人。

你的任务是根据规则驱动的差异计划和 `new_schema`，生成一份完整、自然、可发布的中文题面。

硬性要求：
1. 不要暴露原题编号、原题出处、算法名或“这是某题改编”等信息。
2. 题面必须以 `new_schema` 为准，不能回退到种子题原始任务，也不能保留原题主算法作为主要解法。
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
    revision_context: dict[str, Any] | None = None,
) -> str:
    new_schema = dataclass_to_dict(plan.new_schema_snapshot)
    sample_shape_hint = _build_sample_shape_hint(new_schema)
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
        "applied_helpers": plan.applied_helpers,
        "shared_core_summary": plan.shared_core_summary,
        "shared_core_anchors": plan.shared_core_anchors,
        "seed_contributions": plan.seed_contributions,
        "fusion_ablation": plan.fusion_ablation,
        "new_schema": new_schema,
        "schema_context": schema_context,
        "original_problem_references": original_problem_references,
        "revision_context": revision_context or {},
    }
    return (
        "请基于以下规划生成完整题面。"
        "\n补充要求：\n"
        "- 必须让题面真实兑现 `difference_plan`、`algorithmic_delta_claim` 和 `new_schema`。\n"
        "- 不要复写种子题任务定义，也不要把规则只写成背景包装。\n"
        "- 新题的主要解法必须落到 `algorithmic_delta_claim.new_solver_core`，不能继续由 `algorithmic_delta_claim.seed_solver_core` 主导。\n"
        "- 只有 `algorithmic_delta_claim.reusable_subroutines` 里明确提到的局部子程序可以复用；不能把原题整体解法框架直接搬过来。\n"
        "- 如果熟悉原题的选手只需要小改状态、补一个后处理、外包一层二分或计数，就能沿用原解，请不要继续生成，直接返回 `difference_insufficient`。\n"
        "- `algorithmic_delta_claim.why_direct_reuse_fails` 必须能在题面定义里体现出来，而不是只写在规划字段里。\n"
        "- `applied_helpers` 里的每个 helper 都要在题面和 `new_schema` 中落地，不能只停留在规划说明里。\n"
        "- 如果提供了 `revision_context`，要优先修复其中涉及题面完整性、跨段一致性、样例质量和可读性的问题，并保留 `strengths_to_keep`。\n"
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


def _rule_review_excerpt(rule: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "id",
        "family",
        "summary",
        "audit_tags",
        "required_axis_changes",
        "core_transformation",
        "helpers",
        "validation_contract",
        "planner_output_contract",
        "examples",
        "failure_templates",
    )
    return {
        key: value
        for key, value in ((key, rule.get(key)) for key in keys)
        if value not in (None, "", [], {})
    }
