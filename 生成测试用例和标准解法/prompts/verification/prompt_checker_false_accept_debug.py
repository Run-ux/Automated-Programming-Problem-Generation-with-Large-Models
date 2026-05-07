from __future__ import annotations

from .._common import generated_problem_section, json_contract, schema_section


def build_system_prompt() -> str:
    return (
        "你是一个程序竞赛 checker 修复助手。你的任务是根据误收样例保守、精确地修改 checker："
        "某些本应 WA 的错误输出被当前 checker 判成 AC。最终只输出单个 JSON 对象。"
    )


def build_user_prompt(
    artifact: dict,
    *,
    checker_code: str,
    failing_input: str,
    wrong_output: str,
    error_report: str,
) -> str:
    return "\n\n".join(
        [
            generated_problem_section(artifact),
            schema_section(artifact),
            "# 当前 checker 完整代码",
            checker_code,
            "# 被误收的输入",
            failing_input,
            "# 被误收的错误输出",
            wrong_output,
            "# checker 执行结果",
            error_report,
            """# 修复流程
第一步：定位 checker 过松原因。
第二步：制定修改原则。
第三步：执行修改。

# 修改要求
- 做最小必要修改，不进行无关重构。
- 不允许添加针对具体 input、wrong_output 或 case_id 的硬编码特判。
- 修复逻辑必须对应题意中的通用规则。
- 修复后，对于原来非法的输出应该判 WA。
- 修复不能把 checker 改成只接受标准输出，必须保留题意允许的多解。
- 修改后代码必须实现 check_output(input_string, output_string) -> bool。""",
            json_contract(
                """
{
  "analysis": "误收原因分析",
  "fix_plan": "修改思路",
  "checker_code": "修改后的完整 Python checker 代码字符串，不包含 Markdown"
}
"""
            ),
        ]
    )
