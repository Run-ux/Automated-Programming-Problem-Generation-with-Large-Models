from __future__ import annotations

from .._common import (
    SOLVE_INTERFACE_RULE,
    format_strategy,
    generated_problem_section,
    json_contract,
    schema_section,
)


def build_system_prompt() -> str:
    return (
        "你是一位竞赛编程错误解法生成专家。你的任务是根据输入的单条真实选手错误策略，"
        "生成一份符合该策略的错误 Python 解法。不要修正错误策略，不要生成正确解法。"
        "最终只输出单个 JSON 对象。"
    )


def build_user_prompt(artifact: dict, strategy: dict) -> str:
    return "\n\n".join(
        [
            generated_problem_section(artifact),
            schema_section(artifact),
            "# 错误策略\n" + format_strategy(strategy),
            """# 生成要求
- 只根据上面这一条错误策略生成对应错误解，不要一次性生成多个错误解。
- 先在内部分析错误策略如何影响算法设计、边界处理和代码实现，但不要输出推理过程。
- 生成的解法应像真实选手写出的代码：逻辑完整、可运行、看似合理，但会因给定错误策略导致错误结果。
- 不要修正错误策略，不要加入额外兜底，不要生成正确解法。
- 不要写明显无意义、随机或语法错误的代码。
- 不要暴露“这是故意错误解法”。
- 代码应使用标准 Python，不依赖第三方库。
- 关键逻辑可以添加自然的中文注释，但不要写“错误”“故意”“测试用错误解”等暴露意图的注释。""",
            f"""# 代码接口
- {SOLVE_INTERFACE_RULE}
- solve 接收完整输入字符串，返回该错误解法认为正确的输出字符串。""",
            json_contract(
                """
{
  "code": "完整 Python 代码字符串，必须实现 solve(input_str: str) -> str"
}
"""
            ),
        ]
    )

