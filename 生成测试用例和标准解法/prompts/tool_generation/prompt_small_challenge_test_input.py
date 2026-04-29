from __future__ import annotations

from .._common import generated_problem_section, json_contract


def build_system_prompt() -> str:
    return (
        "你是算法竞赛小规模高区分度测试输入生成器，负责构造规模小但能击穿细微错误解法的输入。"
        "你不生成代码、不生成标准输出，只生成一条合法测试输入。"
        "最终只输出单个 JSON 对象。"
    )


def build_user_prompt(artifact: dict) -> str:
    return "\n\n".join(
        [
            "我会向你提供一道编程题的题面描述。你的任务是为这道算法题生成一个具有挑战性的测试输入。",
            generated_problem_section(artifact),
            """# 生成要求
- 重点关注边界情况，或那些能最大程度提高错误解法失败概率的场景。
- 由于输出长度受限，应生成一个规模较小但完整且合法的测试输入。
- 直接给出测试输入本身，不要输出用于生成它的代码。
- 不要生成标准输出、解释、列表或多条测试输入。
- 不要根据样例硬编码；可以参考样例理解格式，但必须构造新的有效输入。""",
            json_contract(
                """
{
  "test_input": "完整、合法、小规模但有挑战性的测试输入字符串"
}
"""
            ),
        ]
    )

