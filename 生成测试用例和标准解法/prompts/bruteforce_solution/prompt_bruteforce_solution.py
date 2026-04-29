from __future__ import annotations

from .._common import SOLVE_INTERFACE_RULE, generated_problem_section, json_contract, schema_section


def build_system_prompt() -> str:
    return (
        "你是一位算法题暴力解法生成专家，擅长从题面、输入结构、约束、样例和目标函数中还原问题本质，"
        "并设计朴素、直接、可验证正确的暴力算法。你不追求性能最优，只追求逻辑完整、边界正确、实现可靠。"
        "最终只输出单个 JSON 对象。"
    )


def build_user_prompt(artifact: dict) -> str:
    return "\n\n".join(
        [
            generated_problem_section(artifact),
            schema_section(artifact),
            """# 任务目标
请根据上述题目描述信息和题目结构信息生成一个暴力求解解法。
该解法允许时间复杂度和空间复杂度很高，但必须保证：对任意符合输入约束的测试数据，都能得到正确输出。""",
            """# 内部分析要求
请在内部完成以下检查，但不要输出冗长思维链：
1. 解析题意与输入结构，提取目标、格式、范围、输出要求、样例含义和特殊说明。
2. 使用最直接、最朴素的枚举、模拟、回溯、搜索或全排列等方法解决问题。
3. 不要使用复杂优化、剪枝技巧或高阶数据结构，除非它们只是为了保证实现清晰。
4. 检查暴力算法是否覆盖所有可能情况，没有遗漏边界条件。""",
            f"""# 代码要求
- 使用标准 Python。
- {SOLVE_INTERFACE_RULE}
- solve 接收完整输入字符串，返回符合题意的输出字符串。
- 代码应清晰易读，必要处添加简短中文注释。
- 必须生成暴力解法，不要生成最优解或复杂优化解。
- 不要编造题面没有要求的输入、输出或额外限制。
- 不为样例硬编码。
- 若题目信息存在冲突或不足以唯一确定暴力算法，返回 status="blocked"，不要猜测生成代码。""",
            """# bruteforce_markdown 内容要求
bruteforce_markdown 使用中文 Markdown，包含以下部分：
Part 1: 题意解析
Part 2: 暴力求解思路
Part 3: 正确性说明
Part 4: 参考代码说明
Part 5: 复杂度分析
不要在 bruteforce_markdown 中粘贴完整代码，完整代码只放入 code 字段。""",
            json_contract(
                """
{
  "status": "ok 或 blocked",
  "block_reason": "status 为 blocked 时说明冲突或信息缺失点；status 为 ok 时为空字符串",
  "bruteforce_markdown": "中文暴力解说明",
  "code": "完整 Python 代码字符串，status 为 ok 时必须实现 solve(input_str: str) -> str；status 为 blocked 时为空字符串",
  "time_complexity": "时间复杂度，即使很高也要明确说明",
  "space_complexity": "空间复杂度，即使很高也要明确说明"
}
"""
            ),
        ]
    )

