from __future__ import annotations

import json
from typing import Any

from ..prompt_sections import build_revision_guidance, problem_payload


def build_system_prompt() -> str:
    return "\n\n".join(
        [
            "任务目标：\n你是一名算法竞赛题包生成器，当前模块是 BruteForceSolutionGenerator。\n生成正确但允许很慢的暴力解，作为小规模真值参照。",
            "硬约束：\n"
            "1. 只输出严格 JSON 对象，不要输出 Markdown、代码围栏或 JSON 之外的解释。\n"
            "2. 不要编造题面字段、schema 字段或 revision_context 中不存在的设定。\n"
            "3. JSON 中的代码字段必须是 Python 3 标准库代码，禁止第三方依赖；测试输入生成器是唯一例外，可使用 cyaron。\n"
            "4. 代码禁止读写文件、访问网络、启动子进程、读取环境变量。\n"
            "5. 不要在导入阶段执行求解逻辑；只能定义函数、常量和必要辅助逻辑。",
            "执行准则：\n"
            "1. 最高优先级是接口合同、正确性和输入输出格式一致性。\n"
            "2. 只根据题面字段、schema 四字段与 revision_context 中已经暴露的问题生成结果。\n"
            "3. 在内部完成约束抽取、算法选择、边界检查和最小自检，最终只输出 JSON。\n"
            "4. 中间推理、草稿和候选方案不写入最终输出。",
        ]
    )


def build_user_prompt(
    context: dict[str, Any],
    revision_context: dict[str, Any] | None = None,
) -> str:
    payload = problem_payload(context, include_revision=True, revision_context=revision_context)
    revision_guidance = build_revision_guidance(
        revision_context,
        role="BruteForceSolutionGenerator",
        fallback="优先保证暴力逻辑完整、边界正确、实现可靠。",
    )
    return "\n\n".join(
        [
            "任务目标：\n请根据题面字段和 schema 四字段，生成一份正确但允许很慢的暴力求解解法。",
            "输出合同：\n"
            "JSON 对象必须包含以下键：\n"
            "- bruteforce_markdown: 中文 Markdown 暴力解说明，严格包含 Part 1 到 Part 5。\n"
            "- code: 完整可运行的 Python 代码字符串，必须实现 solve(input_str: str) -> str。\n"
            "- time_complexity: 时间复杂度，即使很高也要说明。\n"
            "- space_complexity: 空间复杂度，即使很高也要说明。\n"
            "- notes: 仅记录正确性边界或实现取舍。",
            "硬约束：\n"
            "1. 只输出严格 JSON 对象，不要输出 Markdown、代码围栏或 JSON 之外的解释。\n"
            "2. 不要编造题面字段、schema 字段或 revision_context 中不存在的设定。\n"
            "3. 若信息不足，保守留空并在 notes 中说明。",
            "执行准则：\n"
            "你是一位算法题解专家，擅长从题面、输入结构、约束、样例和目标函数中还原问题本质，并设计朴素、直接、可验证正确的暴力算法。\n"
            "暴力解法允许时间复杂度和空间复杂度很高，但必须保证：对任意符合输入约束的测试数据，都能得到正确输出。\n"
            "不要使用复杂优化、剪枝技巧或高阶数据结构，除非它们只是为了保证实现清晰。\n"
            "bruteforce_markdown 必须严格包含：Part 1: 题意解析、Part 2: 暴力求解思路、Part 3: 正确性说明、Part 4: 参考代码、Part 5: 复杂度分析。\n"
            "必须生成暴力解法，不要生成最优解或复杂优化解；不要依赖题面中未明确成立的假设。",
            "修订上下文要求：\n" + revision_guidance,
            "输入上下文：\n" + json.dumps(payload, ensure_ascii=False, indent=2),
        ]
    )
