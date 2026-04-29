from __future__ import annotations

import json
from typing import Any

from ..prompt_sections import artifact_context, build_revision_guidance, problem_payload


def build_system_prompt() -> str:
    return "\n\n".join(
        [
            "任务目标：\n你是一名算法竞赛题包生成器，当前模块是 CheckerGenerator。\n只生成 checker，校验输出格式和答案合法性。",
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
    validator_artifact: dict[str, Any],
    revision_context: dict[str, Any] | None = None,
) -> str:
    payload = problem_payload(context, include_revision=True, revision_context=revision_context)
    payload["validator_artifact"] = artifact_context(validator_artifact)
    revision_guidance = build_revision_guidance(
        revision_context,
        role="CheckerGenerator",
        fallback="优先生成判题语义明确、与 validator 输入合同一致的 checker。",
    )
    return "\n\n".join(
        [
            "任务目标：\n请生成 checker。此阶段必须基于题面输出要求和 validator 的输入合同口径。",
            "输出合同：\n"
            "JSON 对象必须包含以下键：\n"
            "- checker_code: 完整可运行的 Python 代码字符串，必须实现 check(input_str: str, output_str: str, expected_str: str | None) -> bool。\n"
            "- notes: 说明判题语义、输出合法性谓词和与 validator 的合同衔接。",
            "硬约束：\n"
            "1. 只输出严格 JSON 对象，不要输出 Markdown、代码围栏或 JSON 之外的解释。\n"
            "2. 不要编造题面字段、schema 字段或 revision_context 中不存在的设定。\n"
            "3. 若信息不足，保守留空并在 notes 中说明。",
            "执行准则：\n"
            "组织方式请模仿图 1：先解析输入与输出约束，再实现 checker，再自检接口和边界。\n"
            "checker 职责要求：\n"
            "1. 对唯一标准输出题，expected_str 非空时做规范化比较；对构造/多解/证书题，校验输出格式和答案合法性。\n"
            "2. 不要把完整标准解算法塞进 checker；只实现判题必须的解析、格式和证书合法性校验。\n"
            "3. input_str 的解析口径必须与 validator_artifact 保持一致；若输入不合法或输出非法，返回 False。\n"
            "4. expected_str 为 None 时，只有在题面存在可直接校验的合法性谓词时才可忽略标准输出。\n"
            "5. 输出前自检 check(input_str, output_str, expected_str) 接口、空输出、多余 token、格式错误、样例和多解语义。\n"
            "采用内部 CoT 逐步分析，但不要输出完整推理链。",
            "修订上下文要求：\n" + revision_guidance,
            "输入上下文：\n" + json.dumps(payload, ensure_ascii=False, indent=2),
        ]
    )
