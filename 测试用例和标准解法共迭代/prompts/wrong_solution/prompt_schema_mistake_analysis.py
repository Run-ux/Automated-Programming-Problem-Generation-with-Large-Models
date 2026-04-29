from __future__ import annotations

import json
from typing import Any

from ..prompt_sections import build_revision_guidance, problem_payload


def build_system_prompt() -> str:
    return "\n\n".join(
        [
            "任务目标：\n你是一名算法竞赛题包生成器，当前模块是 SchemaMistakeAnalyzer。\n根据具体题面和 schema 四字段自由提炼真实错误策略。",
            "硬约束：\n"
            "1. 只输出严格 JSON 对象，不要输出 Markdown、代码围栏或 JSON 之外的解释。\n"
            "2. 不要编造题面字段、schema 字段或 revision_context 中不存在的设定。\n"
            "3. 若信息不足，保守留空并在 notes 中说明。",
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
        role="SchemaMistakeAnalyzer",
        fallback="优先生成贴合题目本身、能转化为真实错误解的策略。",
    )
    return "\n\n".join(
        [
            "任务目标：\n请根据题面字段和 schema 四字段，自由生成若干真实选手可能会采取的错误策略。本阶段只分析策略，不写代码。",
            "输出合同：\n"
            "JSON 对象必须包含以下键：\n"
            "- mistake_points: 列表；数量由你根据具体题目决定，不设置固定数量。\n"
            "- mistake_points[].strategy_id: 稳定标识，使用小写字母、数字和下划线。\n"
            "- mistake_points[].category: 错误策略类别，可自由归纳，也可接近固定五类之一。\n"
            "- mistake_points[].title: 简短标题。\n"
            "- mistake_points[].wrong_strategy: 错误思路，说明选手可能怎么做。\n"
            "- mistake_points[].plausible_reason: 看似合理的原因。\n"
            "- mistake_points[].failure_reason: 失败原因，指出违反哪些题意、约束、边界或隐藏逻辑。\n"
            "- mistake_points[].trigger_shape: 可能触发失败的输入特征或样例类型。",
            "硬约束：\n"
            "1. 只输出严格 JSON 对象，不要输出 Markdown、代码围栏或 JSON 之外的解释。\n"
            "2. 不要编造题面字段、schema 字段或 revision_context 中不存在的设定。\n"
            "3. 若信息不足，保守留空并在 notes 中说明。",
            "执行准则：\n"
            "# 角色\n"
            "你是算法竞赛题目分析专家，擅长从题面、约束、样例和 schema 中识别真实选手可能产生的误解、偷懒推断和错误算法策略。\n"
            "# 推理要求\n"
            "请在内部逐步分析题意、目标、输入结构、约束、样例和边界情况，但不要输出完整思维链。\n"
            "不要编造题面没有支持的信息，不要给出正确解法，不要输出多余解释。",
            "修订上下文要求：\n" + revision_guidance,
            "输入上下文：\n" + json.dumps(payload, ensure_ascii=False, indent=2),
        ]
    )
