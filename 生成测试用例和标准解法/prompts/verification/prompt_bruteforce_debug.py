from __future__ import annotations

from .._common import generated_problem_section, json_contract, schema_section


def build_system_prompt() -> str:
    return (
        "你是一个算法竞赛代码调试助手。你的任务是修复给定的暴力解法代码，"
        "使其符合题意，并且能够正常编译和运行。最终只输出单个 JSON 对象。"
    )


def build_user_prompt(
    artifact: dict,
    *,
    bruteforce_code: str,
    failing_input: str,
    error_report: str,
) -> str:
    return "\n\n".join(
        [
            generated_problem_section(artifact),
            schema_section(artifact),
            "# 暴力解法完整代码",
            bruteforce_code,
            "# 触发错误的测试用例输入",
            failing_input,
            "# 完整错误信息",
            error_report,
            """# 修复要求
- 优先修复编译错误和运行时错误。
- 在不改变暴力枚举思路的前提下，修复明显不符合题意的逻辑错误。
- 通过这个触发错误的测试用例输入，定位到原暴力解法的错误之处并做出通用修改。
- 保持暴力解法定位，不要改写为复杂高效算法。
- 保持输入输出格式完全一致，不要添加额外输出。
- 不要依赖非标准库或外部文件。
- 不要静默吞掉错误。
- 修复后代码必须是完整可编译源码，并实现 solve(input_str: str) -> str。""",
            json_contract(
                """
{
  "code": "修改后的完整 Python 代码字符串，只包含可执行源码，不包含 Markdown"
}
"""
            ),
        ]
    )
