from __future__ import annotations

from .._common import generated_problem_section, json_contract, schema_section


def build_system_prompt() -> str:
    return (
        "你是一个程序竞赛 checker 修复助手。你的任务是根据误拒样例保守修改 checker："
        "某些本应 AC 的合法输出被当前 checker 判成 WA。最终只输出单个 JSON 对象。"
    )


def build_user_prompt(
    artifact: dict,
    *,
    checker_code: str,
    failing_input: str,
    failing_output: str,
    error_report: str,
) -> str:
    return "\n\n".join(
        [
            generated_problem_section(artifact),
            schema_section(artifact),
            "# 当前 checker 完整代码",
            checker_code,
            "# 被误拒的合法输入",
            failing_input,
            "# 被误拒的合法输出",
            failing_output,
            "# checker 执行结果",
            error_report,
            """# 修复流程
第一步：定位 checker 过严原因。
第二步：制定修改原则。
第三步：执行修改。

# 修改要求
- 做最小必要修改，不进行无关重构。
- 不允许添加针对具体样例的硬编码特判。
- 不允许为了通过误拒样例而跳过关键校验。
- 修复逻辑必须对应题意中的通用规则。
- 修复后，对于原来的正确合法输出应该 AC。
- 修改后代码必须实现 check_output(input_string, output_string) -> bool。""",
            json_contract(
                """
{
  "analysis": "误拒原因分析",
  "fix_plan": "修改思路",
  "checker_code": "修改后的完整 Python checker 代码字符串，不包含 Markdown"
}
"""
            ),
        ]
    )
