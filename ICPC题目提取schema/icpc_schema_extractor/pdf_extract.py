from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import pdfplumber


@dataclass
class RawProblem:
    problem_id: str
    title_line: str
    body_text: str
    pages: List[int]


DEFAULT_PROBLEM_REGEXES = [
    # 常见："Problem A: Title" / "Problem A - Title"
    r"^\s*Problem\s+([A-Z])\s*[:\-]\s*(.+?)\s*$",
    # 常见："Problem A"（标题在下一行）
    r"^\s*Problem\s+([A-Z])\s*$",
    # 兜底：单行以 "A. Title" 开头
    r"^\s*([A-Z])\s*[\.|:]\s*(.+?)\s*$",
]


_SKIP_META_LINE = re.compile(r"^\s*(Time\s*limit|Memory\s*limit)\s*:\s*.+$", re.IGNORECASE)


def extract_pdf_text_by_page(pdf_path: Path) -> List[str]:
    pages_text: List[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            # 轻度清洗：统一换行，去掉过多空白
            text = text.replace("\r\n", "\n").replace("\r", "\n")
            pages_text.append(text)
    return pages_text


def _iter_lines_with_page(pages_text: List[str]) -> Iterable[Tuple[int, str]]:
    for idx, page_text in enumerate(pages_text, start=1):
        for line in page_text.split("\n"):
            yield idx, line.rstrip("\n")


def split_into_raw_problems(
    pages_text: List[str],
    problem_regexes: Optional[List[str]] = None,
) -> List[RawProblem]:
    regexes = problem_regexes or DEFAULT_PROBLEM_REGEXES
    patterns = [re.compile(rgx, re.IGNORECASE) for rgx in regexes]

    problems: List[RawProblem] = []

    current_id: Optional[str] = None
    current_title_line: Optional[str] = None
    current_lines: List[str] = []
    current_pages: List[int] = []

    def flush():
        nonlocal current_id, current_title_line, current_lines, current_pages
        if current_id and current_title_line is not None:
            body = "\n".join(current_lines).strip()
            problems.append(
                RawProblem(
                    problem_id=current_id,
                    title_line=current_title_line.strip(),
                    body_text=body,
                    pages=sorted(set(current_pages)),
                )
            )
        current_id = None
        current_title_line = None
        current_lines = []
        current_pages = []

    for page_no, line in _iter_lines_with_page(pages_text):
        if not line.strip():
            if current_id is not None:
                current_lines.append("")
                current_pages.append(page_no)
            continue

        # 如果已经识别到 Problem X 但还没捕获标题，则把下一条非空行当作标题
        if current_id is not None and current_title_line is None:
            if _SKIP_META_LINE.match(line):
                current_pages.append(page_no)
                continue
            current_title_line = f"{current_id}. {line.strip()}"
            current_pages.append(page_no)
            continue

        m = None
        for p in patterns:
            m = p.match(line)
            if m:
                break

        if m:
            # 新题开始
            flush()
            current_id = m.group(1).upper()
            title = m.group(2).strip() if m.lastindex and m.lastindex >= 2 else ""
            current_title_line = f"{current_id}. {title}".strip() if title else None
            current_pages.append(page_no)
            continue

        if current_id is not None:
            # 跳过题面页眉的时间/内存限制行（避免污染 Description）
            if _SKIP_META_LINE.match(line):
                current_pages.append(page_no)
                continue
            current_lines.append(line)
            current_pages.append(page_no)

    flush()

    # 去掉明显误分（比如只有标题没有正文）
    filtered = [p for p in problems if len(p.body_text.strip()) > 30]
    return filtered
