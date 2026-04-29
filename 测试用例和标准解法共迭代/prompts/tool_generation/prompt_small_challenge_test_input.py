from __future__ import annotations

import json
from typing import Any

from ..prompt_sections import build_revision_guidance, problem_payload


def build_system_prompt() -> str:
    return "\n\n".join(
        [
            "任务目标：\n你是一名算法竞赛题包生成器，当前模块是 SmallChallengeTestInputGenerator。\n生成小规模高区分度测试输入列表，用于暴力解校验和细微错误筛查。",
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
        role="TestGenerator",
        fallback="优先生成小规模高区分度输入。",
    )
    return "\n\n".join(
        [
            "任务目标：\n请直接生成小规模但具有挑战性的测试输入。",
            "输出合同：\n"
            "JSON 对象必须包含以下键：\n"
            "- tests: 列表；每项包含 input、source、purpose、expect_bruteforce、is_large、metadata。\n"
            "- notes: 说明这些小规模输入主要卡哪些细微错误。",
            "硬约束：\n"
            "1. 只输出严格 JSON 对象，不要输出 Markdown、代码围栏或 JSON 之外的解释。\n"
            "2. 不要编造题面字段、schema 字段或 revision_context 中不存在的设定。\n"
            "3. 若信息不足，保守留空并在 notes 中说明。",
            "执行准则：\n"
            "提示词组织模仿图 5，语言为中文。\n"
            "要求：\n"
            "1. 产生小规模但具有挑战性的输入，用于卡掉包含细微、难以发现错误的解法。\n"
            "2. 直接输出完整输入，不输出生成代码。\n"
            "3. 每个 input 必须完整、合法，规模应适合暴力解校验。\n"
            "4. 不要生成重复或低价值输入。",
            "修订上下文要求：\n" + revision_guidance,
            "输入上下文：\n" + json.dumps(payload, ensure_ascii=False, indent=2),
        ]
    )
