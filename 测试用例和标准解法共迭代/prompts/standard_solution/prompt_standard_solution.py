from __future__ import annotations

import json
from typing import Any

from ..prompt_sections import build_revision_guidance, problem_payload


def build_system_prompt() -> str:
    return "\n\n".join(
        [
            "任务目标：\n你是一名算法竞赛题包生成器，当前模块是 StandardSolutionGenerator。\n生成严格贴合题面和 schema 四字段的标准解。",
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
        role="StandardSolutionGenerator",
        fallback="优先保证首轮代码正确、稳健且满足复杂度约束。",
    )
    return "\n\n".join(
        [
            "任务目标：\n请根据题面字段和 schema 四字段，为 generated_problem 生成一份标准解。",
            "输出合同：\n"
            "JSON 对象必须包含以下键：\n"
            "- solution_markdown: 中文 Markdown 标准解，必须包含题意概括、核心观察、算法思路、正确性说明、复杂度分析、参考实现。\n"
            "- code: 完整可运行的 Python 代码字符串，必须实现 solve(input_str: str) -> str。\n"
            "- time_complexity: 时间复杂度。\n"
            "- space_complexity: 空间复杂度。\n"
            "- notes: 仅记录真正的实现取舍、保守假设或剩余风险。",
            "硬约束：\n"
            "1. 只输出严格 JSON 对象，不要输出 Markdown、代码围栏或 JSON 之外的解释。\n"
            "2. 不要编造题面字段、schema 字段或 revision_context 中不存在的设定。\n"
            "3. 若信息不足，保守留空并在 notes 中说明。",
            "执行准则：\n"
            "# 角色定位\n"
            "你是一位算法竞赛标准解生成专家，擅长根据题目结构化信息还原题意、识别核心约束、设计正确高效的算法，并生成可直接用于评测与讲解的标准解。\n"
            "# 思考方式\n"
            "请在内部按“理解题意 -> 抽象模型 -> 约束分析 -> 算法设计 -> 正确性检查 -> 实现检查”的顺序分析，但不要输出冗长思维链。\n"
            "# 输出要求\n"
            "solution_markdown 使用中文 Markdown，结构必须包含：## 题意概括、## 核心观察、## 算法思路、## 正确性说明、## 复杂度分析、## 参考实现。\n"
            "代码要求：使用标准 Python；变量命名清晰；关键逻辑添加中文注释；不使用题目约束之外的特判；不为样例硬编码。\n"
            "若题目信息存在冲突或不足以唯一确定算法，应在 notes 明确指出问题，不要猜测生成代码。",
            "修订上下文要求：\n" + revision_guidance,
            "输入上下文：\n" + json.dumps(payload, ensure_ascii=False, indent=2),
        ]
    )
