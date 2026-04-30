from __future__ import annotations

from .._common import generated_problem_section, json_contract, schema_section


def build_system_prompt() -> str:
    return (
        "你是算法竞赛 checker 生成专家，负责判断题目是否需要特殊判题，并在确有多解时生成 checker。"
        "唯一答案题不要勉强生成 checker。"
        "最终只输出单个 JSON 对象。"
    )


def build_user_prompt(artifact: dict) -> str:
    return "\n\n".join(
        [
            "我会向你提供一道编程题的题目描述。只有当题目不是唯一答案时，才需要生成 checker。",
            generated_problem_section(artifact),
            schema_section(artifact),
            """# 判断步骤
1. 先判断该题是否需要 checker。
2. 判断依据包括：是否允许多组合法输出、是否为构造题、是否只要求满足性质、是否存在“任意一个合法解均可接受”、输出顺序或方案是否不唯一。
3. 如果题目答案唯一、可以直接用标准输出逐字或按常规容错规则比较，则不要生成 checker。
4. 如果需要 checker，则解析输出格式、数据类型、合法性条件、范围、最优性、去重、顺序和格式容忍规则。
5. checker 必须验证 output_string 是否为 input_string 的合法正确输出，而不是与样例输出或某个固定参考输出做字符串比较。""",
            """# checker 代码要求
- 核心接口必须是 check_output(input_string, output_string) -> bool。
- 代码使用标准 Python，不依赖第三方库、外部文件或网络。
- 对空输出、格式错误、行数不符、字段数量不符、类型错误、越界、非法方案等情况返回 False。
- 不允许抛出未处理异常。
- 不要根据样例反推规则并硬编码。
- 如果题目要求最优性，应校验最优性；若无法仅凭题意安全实现，应在 notes 中明确限制，不要凭猜测补规则。
- 如果题目涉及浮点数比较，必须按题意误差要求处理；题意未说明误差时，在 notes 中明确假设。""",
            """# 输出样例（仅供用途和格式参考）
以下样例只说明 checker 的用途边界和 JSON 输出结构。实际回答时必须完全根据当前题目判断，不得复用样例题意、变量或校验逻辑。

唯一答案题示例：如果题目要求“输出 n 个整数的和”，答案唯一，普通标准输出比对即可，不需要 checker，应返回：
{
  "needs_checker": false,
  "reason": "该题输出为唯一整数答案，使用普通标准答案比对即可，不需要 checker。"
}

多解构造题示例：如果题目要求“输出任意一个长度为 n、元素和为 s 的非负整数数组”，存在多个合法输出，才需要 checker，可返回类似结构：
{
  "needs_checker": true,
  "output_rule_analysis": "输出应包含 n 个非负整数，元素和必须等于 s；允许任意满足条件的数组。",
  "checker_code": "def check_output(input_string, output_string):\\n    try:\\n        data = list(map(int, input_string.split()))\\n        if len(data) != 2:\\n            return False\\n        n, s = data\\n        values = list(map(int, output_string.split()))\\n        if len(values) != n:\\n            return False\\n        if any(x < 0 for x in values):\\n            return False\\n        return sum(values) == s\\n    except Exception:\\n        return False",
  "notes": "示例仅用于说明多解 checker 应验证合法性，而不是与某个固定输出比较。"
}""",
            json_contract(
                """
不需要 checker 时：
{
  "needs_checker": false,
  "reason": "说明该题答案唯一，普通标准输出比对即可"
}

需要 checker 时：
{
  "needs_checker": true,
  "output_rule_analysis": "按题目描述写明 checker 需要校验的输出规则",
  "checker_code": "完整 Python 代码字符串，必须实现 def check_output(input_string, output_string): ...",
  "notes": "必要补充说明；如果没有额外说明，写“无”"
}
"""
            ),
        ]
    )
