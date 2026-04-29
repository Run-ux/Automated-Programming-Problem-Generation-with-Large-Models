from __future__ import annotations

import json
from typing import Any

from artifact_context import build_llm_problem_payload


def build_system_prompt() -> str:
    return "\n\n".join(
        [
            "任务目标：\n你是一名算法竞赛错误解法生成器，当前模块是 StrategyWrongSolutionGenerator。\n按给定自由错误策略逐条生成真实选手风格的错误解。",
            "硬约束：\n"
            "1. 最终只输出完整 Python 代码，不要输出 Markdown 代码围栏或额外解释。\n"
            "2. 代码必须定义 solve(input_str: str) -> str。\n"
            "3. 代码只使用 Python 标准库，不读写文件、不访问网络、不启动子进程。\n"
            "4. 不要暴露这是故意错误解法。",
        ]
    )


def build_user_prompt(context: dict[str, Any], strategy: dict[str, Any]) -> str:
    payload = build_llm_problem_payload(context)
    return "\n\n".join(
        [
            "你是一位竞赛编程错误解法生成专家。你的任务是根据输入的“真实选手可能采取的错误策略”，生成一份符合该错误策略的错误 Python 解法。",
            "要求：",
            "先在内部使用 CoT 逐步分析错误策略如何影响算法设计、边界处理和代码实现，但不要输出推理过程。",
            "生成的解法应像真实选手写出的代码：逻辑完整、可运行、看似合理，但会因给定错误策略导致错误结果。",
            "不要修正错误策略，不要加入额外兜底，不要生成正确解法。",
            "代码应使用标准 Python，不依赖第三方库。",
            "最终只输出完整 Python 代码，不要输出 Markdown 代码块或任何解释。",
            "题目信息：",
            json.dumps(payload, ensure_ascii=False, indent=2),
            "错误策略：",
            json.dumps(strategy, ensure_ascii=False, indent=2),
        ]
    )
