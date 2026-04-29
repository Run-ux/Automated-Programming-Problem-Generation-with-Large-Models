from __future__ import annotations

import json
from typing import Any

from ..prompt_sections import build_revision_guidance, problem_payload


def build_system_prompt() -> str:
    return "\n\n".join(
        [
            "任务目标：\n你是一名算法竞赛题包生成器，当前模块是 RandomTestInputGenerator。\n生成随机测试输入生成器，广泛覆盖合法输入空间。",
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
        fallback="优先生成合法、覆盖面广且可被 validator 接受的随机输入生成器。",
    )
    return "\n\n".join(
        [
            "任务目标：\n请生成随机测试输入生成器。",
            "输出合同：\n"
            "JSON 对象必须包含以下键：\n"
            "- test_generator_code: 完整可运行的 Python 代码字符串，必须实现 generate_test_input() -> str 和 validate_test_input(input_string: str) -> bool。\n"
            "- notes: 说明随机采样范围和覆盖意图。",
            "硬约束：\n"
            "1. 只输出严格 JSON 对象，不要输出 Markdown、代码围栏或 JSON 之外的解释。\n"
            "2. 不要编造题面字段、schema 字段或 revision_context 中不存在的设定。\n"
            "3. 若信息不足，保守留空并在 notes 中说明。",
            "执行准则：\n"
            "提示词组织模仿图 1，语言为中文。\n"
            "你需要完成以下步骤：\n"
            "1. 从题面 description/input_format/constraints 和 schema.input_structure 中解析输入约束。\n"
            "2. 使用 CYaRon 生成随机测试输入，从有效输入空间中广泛采样，包括小规模和大规模输入。\n"
            "3. 编写 validate_test_input 校验生成输入满足题面要求。\n"
            "4. 代码必须 import cyaron as cy，并兼容 cyaron==0.7.0；使用 cy.randint，不使用 cy.Integer()。\n"
            "5. generate_test_input() 不接受参数，返回单个输入字符串。",
            "修订上下文要求：\n" + revision_guidance,
            "输入上下文：\n" + json.dumps(payload, ensure_ascii=False, indent=2),
        ]
    )
