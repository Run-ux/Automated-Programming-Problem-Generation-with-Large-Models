from __future__ import annotations

from .._common import generated_problem_section, json_contract


def build_system_prompt() -> str:
    return (
        "你是算法竞赛随机测试输入生成器，负责从有效输入空间中广泛采样，覆盖小规模与大规模输入。"
        "你只生成 CYaRon 测试输入生成代码和输入校验代码，不生成标准解、checker 或错误解。"
        "最终只输出单个 JSON 对象。"
    )


def build_user_prompt(artifact: dict) -> str:
    return "\n\n".join(
        [
            "我会向你提供一道编程题的题目描述。你的任务是使用 CYaRon 库生成标准化的随机测试输入样例。",
            generated_problem_section(artifact),
            """# 任务步骤
1. 从题目描述中解析输入约束，包括数据范围、数据类型、结构关系和特殊限制。
2. 使用 CYaRon 库编写 generate_test_input() 函数，从有效输入空间中随机生成一条完整输入字符串。
3. generate_test_input() 必须在函数内部完成规模选择与参数生成，不接收任何参数。
4. 若内部生成的参数不满足题面约束，应返回 None；合法时返回 input_string。
5. 编写 validate_test_input(input_string) 函数，校验输入字符串是否满足题面输入格式与约束，并返回 True/False。""",
            """# 硬性约束
- 使用 cyaron==0.7.0。
- 生成代码必须包含 import cyaron as cy。
- 不支持 cy.Integer()；应使用 cy.randint。
- 使用 cy.String.random，不要使用 cy.String。
- generate_test_input() 不接收任何参数。
- generate_test_input() 返回单条输入字符串，不返回列表。
- validate_test_input(input_string) 必须能处理空输入、格式错误、类型错误和越界数据，并返回 False，不应抛出未处理异常。
- 不要根据样例硬编码。""",
            """# 输出样例（仅供格式参考）
以下样例只说明 JSON 输出结构和 CYaRon 代码风格。实际生成时必须完全根据当前题目重写，不得复用样例变量、约束或生成逻辑。

{
  "constraint_analysis": "示例：输入包含 n 和 n 个整数；1 <= n <= 100，-1000 <= ai <= 1000。实际回答时必须替换为当前题目的真实约束。",
  "generate_test_input_code": "import cyaron as cy\\n\\ndef generate_test_input():\\n    n = cy.randint(1, 100)\\n    values = [cy.randint(-1000, 1000) for _ in range(n)]\\n    input_lines = [str(n), ' '.join(map(str, values))]\\n    return '\\\\n'.join(input_lines)",
  "validate_test_input_code": "def validate_test_input(input_string):\\n    try:\\n        lines = input_string.strip().split('\\\\n')\\n        if len(lines) != 2:\\n            return False\\n        n = int(lines[0])\\n        values = list(map(int, lines[1].split()))\\n        if len(values) != n:\\n            return False\\n        return 1 <= n <= 100 and all(-1000 <= x <= 1000 for x in values)\\n    except Exception:\\n        return False"
}""",
            json_contract(
                """
{
  "constraint_analysis": "按题目描述写明输入约束。",
  "generate_test_input_code": "完整 Python 代码字符串，包含 import cyaron as cy 和 def generate_test_input(): ...",
  "validate_test_input_code": "完整 Python 代码字符串，包含 def validate_test_input(input_string): ..."
}
"""
            ),
        ]
    )
