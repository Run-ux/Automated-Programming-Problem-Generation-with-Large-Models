from __future__ import annotations

from typing import Any

from .._common import format_prompt_value, generated_problem_section, json_contract, schema_section


def build_system_prompt() -> str:
    return (
        "你是一个用于验证程序竞赛 checker 正确性的反例输出生成器。"
        "你的任务是给定题目描述信息和若干组正确输入输出，构造必然错误的输出。"
        "最终只输出单个 JSON 对象。"
    )


def build_user_prompt(artifact: dict, *, solved_cases: list[dict[str, Any]]) -> str:
    return "\n\n".join(
        [
            generated_problem_section(artifact),
            schema_section(artifact),
            "# 正确输入输出用例",
            format_prompt_value(solved_cases),
            """# 重要原则
1. 输入必须保持不变，只能修改输出。
2. 构造出的 wrong_output 必须根据题意必然错误，而不仅仅是不同于标准输出。
3. 如果题目允许多解，不能把另一个合法解当成错误输出。
4. 如果无法确定某种破坏策略是否一定导致错误，必须跳过，不要猜测。
5. 每条反例优先只破坏一个核心规则，便于定位 checker 问题。
6. 反例应尽量做最小修改。
7. 可以生成格式非法的输出。
8. 不要修改、补全或重新设计题目输入。
9. wrong_output 必须是选手程序可能输出的原始文本。
10. 输出必须是严格 JSON，不要使用 Markdown。""",
            """# 可用破坏策略
可用破坏策略是候选启发清单，用于提醒覆盖方向；不是必须逐项使用，也不是唯一允许的思路。
只有当某策略能构造出根据题意必然非法的 wrong_output 时才使用。
若题目存在列表未覆盖但可高置信证明非法的输出，可归入最接近的策略，并在 reason 中说明具体违反的题意规则。

- FORMAT_MISSING_OUTPUT：格式错误，少输出必要 token、行或字段。
- FORMAT_EXTRA_OUTPUT：格式错误，多输出额外 token、行或字段。
- FORMAT_TYPE_ERROR：格式错误，将整数改成小数、字符串，或将枚举值改成非法文本。
- FORMAT_ILLEGAL_CHAR：格式错误，插入非法字符。
- RANGE_NEGATIVE：范围错误，将本应非负或正数的值改成负数。
- RANGE_OUT_OF_BOUND：范围错误，将值改成超过题目约束或输入规模的值。
- RANGE_INDEX_BASE_CONFUSION：范围错误，制造 0/1 基下标混淆。
- CONSTRAINT_DUPLICATE：约束错误，制造重复元素、重复边、重复选择等。
- CONSTRAINT_MISSING_COVERAGE：约束错误，遗漏必须覆盖、选择、访问或输出的元素。
- CONSTRAINT_NONEXISTENT_EDGE_OR_ITEM：约束错误，引用输入中不存在的边、点、物品、字符或关系。
- CONSTRAINT_DISCONNECTED_PATH：约束错误，构造不连续路径、不相邻转移或不可达序列。
- OBJECTIVE_NON_OPTIMAL_TOO_LARGE：目标错误，输出值比最优值更大，适用于最小化问题。
- OBJECTIVE_NON_OPTIMAL_TOO_SMALL：目标错误，输出值比最优值更小，适用于最大化问题。
- OBJECTIVE_INCONSISTENT_VALUE：目标错误，答案值与后续方案不一致。
- BOUNDARY_EMPTY_SET：边界错误，错误地输出空集合、空方案或 0 个元素。
- BOUNDARY_MAX_VALUE：边界错误，使用最大值附近但非法的值。
- BOUNDARY_MIN_VALUE：边界错误，使用最小值附近但非法的值。
- BOUNDARY_DUPLICATE_VALUE：边界错误，在边界处制造重复值。
- NUMERIC_OVERFLOW：数值错误，输出超大整数或超过常见 64 位范围的数。
- NUMERIC_PRECISION_JUST_OUTSIDE：数值错误，浮点值刚好超过允许误差。
- NUMERIC_NAN_INF：数值错误，输出 nan、inf、-inf 等非法数值。
- FORGED_UNRELATED_OUTPUT：伪造错误，输出格式看似合理，但内容与输入无关，不能满足题意。""",
            """# 自检流程
生成每条候选反例后，必须在内部检查：
1. input 是否完全未修改。
2. wrong_output 是否不同于原 correct_output。
3. wrong_output 是否根据题意必然非法。
4. 是否存在多解导致 wrong_output 可能合法。
5. 是否只破坏了 primary_strategy 对应的主要规则。
6. 如果 checker 正确，是否应该返回 WA。
7. 如果无法高置信判断，丢弃该候选。""",
            json_contract(
                """
{
  "counterexamples": [
    {
      "source_case_id": "case_001",
      "input": "保持不变的原始输入文本",
      "correct_output": "原始正确输出文本",
      "wrong_output": "构造出的错误输出文本",
      "primary_strategy": "FORMAT_MISSING_OUTPUT",
      "strategy_group": "格式错误",
      "expected_verdict": "WA",
      "reason": "简要说明为什么该输出根据题意必然错误",
      "confidence": 0.85
    }
  ],
  "skipped": [
    {
      "source_case_id": "case_001",
      "strategy": "OBJECTIVE_NON_OPTIMAL_TOO_LARGE",
      "reason": "该题或该输出无法确认是最小化问题，因此跳过"
    }
  ]
}
"""
            ),
        ]
    )
