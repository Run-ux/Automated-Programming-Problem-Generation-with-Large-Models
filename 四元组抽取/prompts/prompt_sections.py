from __future__ import annotations

from typing import Any, Dict


EMPTY_SECTION_TEXT = "未提供明确内容"


def _clean_text(value: Any) -> str:
    if isinstance(value, str):
        text = value.strip()
        if text:
            return text
    return EMPTY_SECTION_TEXT


def render_named_section(title: str, content: Any) -> str:
    return f"{title}：\n{_clean_text(content)}"


def build_problem_context(
    problem: Dict[str, Any],
    solution_code: str = "",
) -> str:
    sections = [
        render_named_section("标题", problem.get("title", "")),
        render_named_section("题面全文", problem.get("description", "")),
        render_named_section("Input 分节", problem.get("input", "")),
        render_named_section("Output 分节", problem.get("output", "")),
        render_named_section("Constraints 分节", problem.get("constraints", "")),
    ]

    if solution_code.strip():
        sections.append(
            "标准解法代码：\n```text\n"
            + solution_code.strip()
            + "\n```"
        )

    return "\n\n".join(sections)
