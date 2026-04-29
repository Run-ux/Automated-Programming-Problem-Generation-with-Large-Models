from __future__ import annotations

from .._common import SOLVE_INTERFACE_RULE, generated_problem_section, json_contract, schema_section


def build_system_prompt() -> str:
    return (
        "你是一位算法竞赛标准解生成专家，擅长根据题面和 schema 四字段还原题意、识别核心约束、"
        "设计正确高效的算法，并生成可直接用于评测与讲解的标准解。"
        "若题目信息冲突或不足以唯一确定算法，必须阻塞并说明原因。"
        "最终只输出单个 JSON 对象。"
    )


def build_user_prompt(artifact: dict) -> str:
    return "\n\n".join(
        [
            generated_problem_section(artifact),
            schema_section(artifact),
            """# 任务目标
请根据上述题目描述信息和题目结构信息，生成一份针对这道题目的标准解。
标准解必须严格贴合题目本身，不得引入题面未给出的假设，不得修改题意、输入输出格式或约束。""",
            """# 内部分析要求
请在内部按照以下顺序分析，但不要输出冗长思维链：
1. 理解题意：明确输入、输出、目标和合法操作。
2. 抽象模型：将题目转化为清晰的算法问题。
3. 约束分析：根据数据范围判断可接受复杂度。
4. 算法设计：选择满足约束的最小必要算法。
5. 正确性检查：验证算法覆盖一般情况、边界情况和样例。
6. 实现检查：确认数据流从输入到输出完整无断裂。""",
            f"""# 代码要求
- 使用标准 Python。
- {SOLVE_INTERFACE_RULE}
- solve 接收完整输入字符串，返回符合题意的输出字符串。
- 变量命名清晰，关键逻辑添加中文注释。
- 不使用题目约束之外的特判。
- 不为样例硬编码。
- 不暴露完整内部推理链，只输出必要推理摘要。
- 若题目信息存在冲突或不足以唯一确定算法，返回 status="blocked"，不要猜测生成代码。""",
            """# solution_markdown 内容要求
solution_markdown 使用中文 Markdown，包含以下小节：
## 题意概括
## 核心观察
## 算法思路
## 正确性说明
## 复杂度分析
## 参考实现说明
不要在 solution_markdown 中粘贴完整代码，完整代码只放入 code 字段。""",
            json_contract(
                """
{
  "status": "ok 或 blocked",
  "block_reason": "status 为 blocked 时说明冲突或信息缺失点；status 为 ok 时为空字符串",
  "solution_markdown": "中文标准解说明",
  "code": "完整 Python 代码字符串，status 为 ok 时必须实现 solve(input_str: str) -> str；status 为 blocked 时为空字符串",
  "time_complexity": "时间复杂度，例如 O(n)",
  "space_complexity": "空间复杂度，例如 O(n)"
}
"""
            ),
        ]
    )

