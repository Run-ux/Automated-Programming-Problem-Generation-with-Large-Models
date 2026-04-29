from __future__ import annotations

import json
from typing import Any


def build_system_prompt() -> str:
    return "\n\n".join(
        [
            "任务目标：\n你是一名错误回流修订顾问。你只根据 failure_packet 中的失败证据，输出能直接指导下一轮生成器修复的具体 revision 建议。",
            "硬约束：\n"
            "1. 只输出严格 JSON 对象，不要输出 Markdown、代码围栏或 JSON 之外的解释。\n"
            "2. 不要编造题面字段、schema 字段或 revision_context 中不存在的设定。\n"
            "3. 若信息不足，保守留空并在 notes 中说明。",
            "执行准则：\n"
            "1. 最高优先级是基于证据定位失败机制，禁止泛泛建议。\n"
            "2. revision_advice 必须指出应修改的对象、触发失败的具体输入/输出/状态、建议修改方向和验证方式。\n"
            "3. 如果证据不足以唯一定位根因，必须说明不可确认点，并给出保守但可执行的下一步修订建议。",
        ]
    )


def build_user_prompt(failure_packet: dict[str, Any]) -> str:
    return "\n\n".join(
        [
            "任务目标：\n请为该失败诊断输出定向 revision 建议。",
            "输出合同：\n"
            "JSON 对象必须包含以下键：\n"
            "- root_cause: 根据证据判断的失败机制；若不能唯一确定，说明最可能原因和不确定点。\n"
            "- revision_advice: 可直接执行的修订建议，必须具体说明改什么、为什么、用哪个证据验证。\n"
            "- target_roles: 建议作用的生成器角色列表，必须来自 failure_packet.diagnostic.target_roles。\n"
            "- evidence_used: 实际使用的关键信息列表。\n"
            "- confidence: 只能是 low、medium 或 high。\n"
            "- risk_notes: 可能误判、证据不足或改动风险；没有则返回空字符串。",
            "硬约束：\n"
            "1. 只输出严格 JSON 对象，不要输出 Markdown、代码围栏或 JSON 之外的解释。\n"
            "2. 不要编造题面字段、schema 字段或 revision_context 中不存在的设定。\n"
            "3. 若信息不足，保守留空并在 notes 中说明。",
            "执行准则：\n"
            "建议质量要求：\n"
            "1. 针对运行错误，指出异常类型、触发输入和应修正的解析/分支/数据结构路径。\n"
            "2. 针对输出不一致，指出首个不同 token/行、相关输入结构，并说明应优先核对标准解还是暴力解。\n"
            "3. 针对 checker/validator/测试输入生成器，指出接口合同、输入合法性或输出合法性谓词的具体冲突。\n"
            "4. 针对错误解存活，指出幸存错误模式和应新增的反例形状。",
            "输入上下文：\n" + json.dumps({"failure_packet": failure_packet}, ensure_ascii=False, indent=2),
        ]
    )
