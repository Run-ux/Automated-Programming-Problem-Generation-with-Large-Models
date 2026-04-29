from __future__ import annotations

from typing import Any

from artifact_context import build_llm_problem_payload

from ..prompt_sections import format_prompt_value


def build_system_prompt() -> str:
    return "\n\n".join(
        [
            "任务目标：\n你是一名算法竞赛错误解法生成器，当前模块是 FixedCategoryWrongSolutionGenerator。\n按固定错误类别生成真实选手风格的错误解。",
            "硬约束：\n"
            "1. 最终只输出完整 Python 代码，不要输出 Markdown 代码围栏或额外解释。\n"
            "2. 代码必须定义 solve(input_str: str) -> str。\n"
            "3. 代码只使用 Python 标准库，不读写文件、不访问网络、不启动子进程。\n"
            "4. 不要暴露这是故意错误解法。",
        ]
    )


def build_user_prompt(context: dict[str, Any], category: str) -> str:
    payload = build_llm_problem_payload(context)
    payload["language"] = "python"
    lead, task, requirement = _category_profile(category)
    formatted = {key: format_prompt_value(value) for key, value in payload.items()}
    return f"""{lead}

请根据以下题目信息，生成一份“{task}”。

输入信息
input_structure：{formatted["input_structure"]}

core_constraints：{formatted["core_constraints"]}

objective：{formatted["objective"]}

invariant：{formatted["invariant"]}

title：{formatted["title"]}

description：{formatted["description"]}

input_format：{formatted["input_format"]}

output_format：{formatted["output_format"]}

constraints：{formatted["constraints"]}

samples：{formatted["samples"]}

notes：{formatted["notes"]}

生成要求
错误策略必须属于：{category}。
错误解法应像真实选手提交的代码，而不是刻意破坏的代码。
代码整体逻辑应自洽，能通过部分样例或弱数据。
{requirement}
不要写明显无意义、随机或语法错误的代码。
不要暴露“这是故意错误解法”。
输出完整可运行代码，语言使用：{formatted["language"]}。
最终只输出 Python 代码，不要输出 Markdown 代码围栏或额外解释。"""


def _category_profile(category: str) -> tuple[str, str, str]:
    if category == "目标/输出义务误读":
        return (
            "你是一名算法竞赛错误解法生成专家，熟悉真实选手在阅读题面时常见的目标误读、输出格式误解和评价标准偏差。",
            "真实选手因误读目标或输出义务而写出的错误解法",
            "错误应来源于对“要求输出什么”“优化目标是什么”“是否需要构造/计数/判定”等内容的误解。",
        )
    if category == "核心约束简化":
        return (
            "你是一名算法竞赛错误解法生成专家，擅长模拟选手将复杂约束错误简化后写出的看似合理但不完整的解法。",
            "真实选手因简化核心约束而写出的错误解法",
            "错误解法应体现选手忽略、弱化或局部化某个关键约束；不能直接无视所有条件。",
        )
    if category == "invariant 误读":
        return (
            "你是一名算法竞赛错误解法生成专家，熟悉不变量、状态维护、单调性、守恒关系和递推条件被误读后产生的典型错误。",
            "真实选手因误读 invariant 而写出的错误解法",
            "错误解法应体现对状态不变量、必要条件、保持条件或等价关系的错误理解。",
        )
    if category == "边界/最小性错误":
        return (
            "你是一名算法竞赛错误解法生成专家，擅长模拟真实选手在边界情况、最小规模、极端输入和初始化条件上犯错的代码。",
            "真实选手因边界或最小性理解错误而写出的错误解法",
            "错误解法应在一般情况中看起来正确，但在最小输入、空状态、单元素、相等值、极端值或临界条件下失败。",
        )
    if category == "复杂度/规模误判":
        return (
            "你是一名算法竞赛错误解法生成专家，熟悉真实选手因低估输入规模、误判复杂度或使用不可扩展算法而产生的错误提交。",
            "真实选手因复杂度或规模误判而写出的错误解法",
            "错误解法应在小数据上正确或近似正确，但在最大规模下超时、超内存或退化。",
        )
    raise ValueError(f"未知固定错误策略类别：{category}")
