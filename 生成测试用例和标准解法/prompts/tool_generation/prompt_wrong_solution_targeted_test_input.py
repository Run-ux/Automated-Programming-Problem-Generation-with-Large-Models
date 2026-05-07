from __future__ import annotations

from typing import Any

from .._common import format_prompt_value, generated_problem_section, json_contract, schema_section


def build_system_prompt() -> str:
    return (
        "你是算法竞赛定向测试输入生成器，负责根据当前尚未暴露问题的错误解法构造一条合法输入，"
        "尽量让该错误解法在新输入上产生错误结果。你不生成标准输出、checker 或代码。"
        "最终只输出单个 JSON 对象。"
    )


def build_user_prompt(
    artifact: dict[str, Any],
    *,
    wrong_solution_candidate: dict[str, Any],
    verified_input_cases: list[dict[str, Any]],
) -> str:
    return "\n\n".join(
        [
            generated_problem_section(artifact),
            schema_section(artifact),
            "# 当前尚未暴露问题的错误解候选",
            format_prompt_value(wrong_solution_candidate),
            "# 当前已验证输入摘要",
            format_prompt_value(verified_input_cases),
            """# 任务
请生成一条新的合法测试输入，目标是尽量让上面的错误解候选暴露问题。

# 推理要求
请在内部逐步分析题面、输入结构、核心约束、错误策略、已有输入覆盖范围和可能遗漏的边界情况，但不要输出推理过程。
最终只输出经过自检的测试输入结论。

# 生成要求
- 输入必须完全符合题面输入格式和约束。
- 优先围绕错误策略的触发条件、边界情况、核心约束和 invariant 相关的薄弱点构造。
- 当前已验证输入摘要只用于避免重复和识别覆盖不足之处，不要照搬已有输入。
- 不要生成标准输出、解释、列表或多条测试输入。
- 不要根据样例硬编码；可以参考样例理解格式，但必须构造新的有效输入。
- 输入规模应优先小而有区分度，除非错误策略明显属于复杂度或规模判断错误。

# 自检流程
生成候选输入后，必须在内部检查：
1. 输入是否严格符合题面格式和约束。
2. 输入是否不同于当前已验证输入摘要中的已有输入。
3. 输入是否确实针对错误策略中描述的误解、边界或约束缺失。
4. 输入是否避免了无关的大规模随机数据。
5. 如果无法构造更有区分度的输入，返回最小但最可能暴露问题的合法输入。""",
            json_contract(
                """
{
  "test_input": "完整合法测试输入字符串"
}
"""
            ),
        ]
    )
