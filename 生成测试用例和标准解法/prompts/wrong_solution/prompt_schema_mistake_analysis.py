from __future__ import annotations

from .._common import generated_problem_section, json_contract, schema_section


def build_system_prompt() -> str:
    return (
        "你是算法竞赛题目分析专家，擅长从题面、约束、样例和 schema 四字段中识别真实选手可能产生的误解、"
        "偷懒推断和错误算法策略。你只分析错误策略，不生成代码。"
        "最终只输出单个 JSON 对象。"
    )


def build_user_prompt(artifact: dict) -> str:
    return "\n\n".join(
        [
            generated_problem_section(artifact),
            schema_section(artifact),
            """# 任务
请生成若干条真实选手可能会采取的错误策略。
每条错误策略应贴合题目本身，体现选手在理解题意、建模、复杂度估计、边界处理、样例归纳或算法选择上的常见偏差。
数量由题目实际情况决定，不设置固定数量，不需要补齐。""",
            """# 推理要求
请在内部逐步分析题意、目标、输入结构、约束、样例和边界情况，但不要输出完整思维链。
最终只输出经过验证的错误策略结论。
不要编造题面没有支持的信息，不要给出正确解法，不要输出多余解释。""",
            json_contract(
                """
{
  "strategies": [
    {
      "title": "简短标题",
      "wrong_idea": "真实选手可能怎么做",
      "plausible_reason": "为什么真实选手可能会这样想",
      "failure_reason": "该策略违反了哪些题意、约束、边界或隐藏逻辑",
      "trigger_case": "能击穿该策略的输入特征或样例类型"
    }
  ]
}
"""
            ),
        ]
    )

