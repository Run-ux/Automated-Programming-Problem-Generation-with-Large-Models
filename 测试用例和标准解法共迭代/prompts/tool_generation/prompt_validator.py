from __future__ import annotations

import json
from typing import Any

from ..prompt_sections import build_revision_guidance, problem_payload


def build_system_prompt() -> str:
    return "\n\n".join(
        [
            "任务目标：\n你是一名算法竞赛题包生成器，当前模块是 ValidatorGenerator。\n只生成 validator，严格校验输入格式和显式约束。",
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
        role="ValidatorGenerator",
        fallback="优先生成接口正确、边界清晰且保守的 validator。",
    )
    return "\n\n".join(
        [
            "任务目标：\n请生成输入 validator。此阶段只负责输入合法性校验。",
            "输出合同：\n"
            "JSON 对象必须包含以下键：\n"
            "- validator_code: 完整可运行的 Python 代码字符串，必须实现 validate(input_str: str) -> bool。\n"
            "- notes: 说明输入合同、边界处理和保守假设。",
            "硬约束：\n"
            "1. 只输出严格 JSON 对象，不要输出 Markdown、代码围栏或 JSON 之外的解释。\n"
            "2. 不要编造题面字段、schema 字段或 revision_context 中不存在的设定。\n"
            "3. 若信息不足，保守留空并在 notes 中说明。",
            "执行准则：\n"
            "validator 职责要求：\n"
            "1. 只验证输入是否合法，不做求解，不验证输出，不依赖隐藏条件。\n"
            "2. 严格服从题面 input_format、constraints 以及 schema 的 input_structure/core_constraints。\n"
            "3. 非法输入、解析失败、字段数量不匹配、范围越界或异常路径必须返回 False。\n"
            "4. 合法输入返回 True；函数内部自行捕获可恢复解析异常，禁止静默接受格式错误。",
            "修订上下文要求：\n" + revision_guidance,
            "输入上下文：\n" + json.dumps(payload, ensure_ascii=False, indent=2),
        ]
    )
