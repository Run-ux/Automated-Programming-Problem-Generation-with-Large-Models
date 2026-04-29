from __future__ import annotations

from .._common import generated_problem_section, json_contract


def build_system_prompt() -> str:
    return (
        "你是算法竞赛边界与最坏情况测试输入生成器，负责构造对抗性但合法的单条测试输入。"
        "你只生成 CYaRon 测试输入生成代码和输入校验代码，不生成标准解、checker 或错误解。"
        "最终只输出单个 JSON 对象。"
    )


def build_user_prompt(artifact: dict) -> str:
    return "\n\n".join(
        [
            "我会向你提供一道编程题的题面描述。你的任务是使用 CYaRon 库生成具有对抗性的测试输入样例。",
            generated_problem_section(artifact),
            """# 任务步骤
1. 从题面描述中解析输入约束，包括数据范围、结构限制、最小值、最大值和相互依赖关系。
2. 使用 CYaRon 库编写 generate_test_input() 函数，生成一条单独的对抗性输入字符串。
3. generate_test_input() 必须在内部随机选择一种题目相关的对抗策略，例如边界规模、极值、退化结构、最坏时间复杂度结构或容易暴露鲁棒性问题的结构。
4. 生成的输入必须完全满足题目约束，不能为了对抗性制造非法输入。
5. 编写 validate_test_input(input_string) 函数，校验输入字符串是否满足题面输入格式与约束，并返回 True/False。""",
            """# 硬性约束
- 使用 cyaron==0.7.0。
- 生成代码必须包含 import cyaron as cy，并可按需使用 import random。
- 不支持 cy.Integer()；应使用 cy.randint。
- 使用 cy.String.random，不要使用 cy.String。
- generate_test_input() 不接收任何参数。
- generate_test_input() 必须返回一条单独的对抗性输入字符串，而不是列表。
- 对抗策略必须贴合当前题目，不要照搬无关题目的变量名或策略名。
- validate_test_input(input_string) 必须能处理空输入、格式错误、类型错误和越界数据，并返回 False，不应抛出未处理异常。
- 不要根据样例硬编码。""",
            """# 输出样例（仅供格式参考）
以下样例只说明 JSON 输出结构、策略分支写法和 CYaRon 代码风格。实际生成时必须完全根据当前题目重写，不得复用样例变量、约束或策略。

{
  "constraint_analysis": "示例：输入包含 n 和 n 个整数；1 <= n <= 100，-1000 <= ai <= 1000。实际回答时必须替换为当前题目的真实约束，并说明当前题目适用的对抗策略方向。",
  "generate_test_input_code": "import random\\nimport cyaron as cy\\n\\ndef generate_test_input():\\n    strategy = random.choice(['min_size', 'max_size', 'extreme_values'])\\n    if strategy == 'min_size':\\n        n = 1\\n        values = [cy.randint(-1000, 1000)]\\n    elif strategy == 'max_size':\\n        n = 100\\n        values = [cy.randint(-1000, 1000) for _ in range(n)]\\n    else:\\n        n = cy.randint(2, 100)\\n        values = [1000 if i % 2 == 0 else -1000 for i in range(n)]\\n    input_lines = [str(n), ' '.join(map(str, values))]\\n    return '\\\\n'.join(input_lines)",
  "validate_test_input_code": "def validate_test_input(input_string):\\n    try:\\n        lines = input_string.strip().split('\\\\n')\\n        if len(lines) != 2:\\n            return False\\n        n = int(lines[0])\\n        values = list(map(int, lines[1].split()))\\n        if len(values) != n:\\n            return False\\n        return 1 <= n <= 100 and all(-1000 <= x <= 1000 for x in values)\\n    except Exception:\\n        return False"
}""",
            json_contract(
                """
{
  "constraint_analysis": "按题目描述写明输入约束，并说明采用哪些对抗性策略方向。",
  "generate_test_input_code": "完整 Python 代码字符串，包含 import cyaron as cy 和 def generate_test_input(): ...",
  "validate_test_input_code": "完整 Python 代码字符串，包含 def validate_test_input(input_string): ..."
}
"""
            ),
        ]
    )
