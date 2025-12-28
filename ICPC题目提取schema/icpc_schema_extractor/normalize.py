from __future__ import annotations

import re
from typing import Dict, Tuple

from .models import ProblemText
from .pdf_extract import RawProblem


SECTION_HEADERS = [
    "Input",
    "Output",
    "Constraints",
    "Input Format",
    "Output Format",
    "Input Specification",
    "Output Specification",
    "Limits",
]


def _normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # 合并多余空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _find_sections(text: str) -> Dict[str, Tuple[int, int]]:
    lines = text.split("\n")
    indices = []
    for i, line in enumerate(lines):
        key = line.strip()
        if not key:
            continue
        for h in SECTION_HEADERS:
            if key.lower() == h.lower():
                indices.append((i, h))
                break

    # 按出现顺序构建区间
    sections: Dict[str, Tuple[int, int]] = {}
    for idx, (start_i, header) in enumerate(indices):
        end_i = indices[idx + 1][0] if idx + 1 < len(indices) else len(lines)
        sections[header] = (start_i + 1, end_i)
    return sections


def _slice(lines, start_end: Tuple[int, int]) -> str:
    s, e = start_end
    return "\n".join(lines[s:e]).strip()


def normalize_problem(raw: RawProblem, source_pdf: str | None = None) -> ProblemText:
    title = raw.title_line
    body = _normalize_whitespace(raw.body_text)

    # 分段
    sections = _find_sections(body)
    lines = body.split("\n")

    # 选择 Input/Output/Constraints 的最佳来源
    def pick(*names: str) -> str:
        for n in names:
            if n in sections:
                return _slice(lines, sections[n])
        return ""

    input_text = pick("Input", "Input Format", "Input Specification")
    output_text = pick("Output", "Output Format", "Output Specification")
    constraints_text = pick("Constraints", "Limits")

    # Description：从开头到第一个段落头之前
    first_header_line = min((rng[0] - 1 for rng in sections.values()), default=len(lines))
    desc_lines = lines[:first_header_line]
    description = "\n".join(desc_lines).strip()

    # 兜底：如果 Input/Output 缺失，则尝试基于关键词切
    if not input_text or not output_text:
        joined = "\n".join(lines)
        m_in = re.search(r"\n\s*Input\s*\n", "\n" + joined + "\n", re.IGNORECASE)
        m_out = re.search(r"\n\s*Output\s*\n", "\n" + joined + "\n", re.IGNORECASE)
        if m_in and m_out and m_in.start() < m_out.start():
            description = _normalize_whitespace(joined[: m_in.start()])
            input_text = _normalize_whitespace(joined[m_in.end() : m_out.start()])
            output_text = _normalize_whitespace(joined[m_out.end() :])

    return ProblemText(
        problem_id=raw.problem_id,
        title=title.strip(),
        description=description.strip(),
        input=input_text.strip() or "(Not found)",
        output=output_text.strip() or "(Not found)",
        constraints=constraints_text.strip() or "(Not found)",
        source_pdf=source_pdf,
        pages=raw.pages,
    )
