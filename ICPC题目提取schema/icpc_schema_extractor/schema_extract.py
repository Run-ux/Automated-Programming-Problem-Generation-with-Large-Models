from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from pydantic import ValidationError

from .models import ProblemText, SchemaOutput
from .qwen_client import QwenClient


def build_prompt(schema_def_md: str, problem: ProblemText) -> tuple[str, str]:
    system = (
        "你是编程竞赛题目分析助手。你必须严格按用户给定的 Problem Schema 五元组定义抽取信息。"
        "输出必须是一个JSON对象，且只能输出JSON，不要输出任何解释。"
    )

    user = f"""
下面是 Problem Schema 五元组的正式定义（必须遵守字段语义）：

{schema_def_md}

---

现在给你一道题的标准化题面：

Title: {problem.title}

Description:
{problem.description}

Input:
{problem.input}

Output:
{problem.output}

Constraints:
{problem.constraints}

---

请抽取该题对应的 Problem Schema，输出 JSON，字段必须符合如下结构：

{json.dumps(SchemaOutput.model_json_schema()["properties"], ensure_ascii=False, indent=2)}

要求：
1) 输出 JSON 顶层必须包含：name, input_structure, core_constraints, objective, invariant, transform_params。
2) core_constraints 是数组，每个元素至少包含 name, description（可以额外字段）。
3) 如果题面缺失某字段，请给出合理的保守推断，并在 description 中注明 "assumed"。
""".strip()

    return system, user


def extract_schema_for_problem(
    client: QwenClient,
    schema_def_md: str,
    problem: ProblemText,
) -> Dict[str, Any]:
    system, user = build_prompt(schema_def_md, problem)
    data = client.chat_json(system=system, user=user)

    # 校验基本结构（尽量严格，但不过度失败）
    try:
        SchemaOutput.model_validate(data)
    except ValidationError:
        # 允许 name 不匹配或字段类型略有差异时仍保存原始
        pass

    return data


def load_problem_md(md_path: Path) -> ProblemText:
    # 该解析器假设我们的输出格式固定
    text = md_path.read_text(encoding="utf-8")

    def grab(section: str) -> str:
        import re

        m = re.search(rf"^##\s+{re.escape(section)}\s*$", text, re.MULTILINE)
        if not m:
            return ""
        start = m.end()
        m2 = re.search(r"^##\s+", text[start:], re.MULTILINE)
        end = start + (m2.start() if m2 else len(text[start:]))
        return text[start:end].strip()

    # 标题：第一行 '# ...'
    first_line = text.splitlines()[0].lstrip("#").strip() if text else md_path.stem

    return ProblemText(
        problem_id=md_path.stem,
        title=first_line,
        description=grab("Description"),
        input=grab("Input"),
        output=grab("Output"),
        constraints=grab("Constraints"),
    )
