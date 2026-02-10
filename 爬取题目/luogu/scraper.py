from __future__ import annotations

import json
import logging
import re
from typing import List, Optional, Set

from bs4 import BeautifulSoup

from ..common.browser import BrowserManager
from ..common.models import ProblemText
from ..config import LUOGU_RATE

logger = logging.getLogger(__name__)

_DIFFICULTY_LEVELS = [5, 6, 7]

_DIFFICULTY_MAP = {
    0: "暂无评定", 1: "入门", 2: "普及-", 3: "普及/提高-", 4: "普及+/提高",
    5: "提高+/省选-", 6: "省选/NOI-", 7: "NOI/NOI+/CTSC",
}


def _collect_pids_via_browser(bm: BrowserManager, max_count: int | None = None) -> List[dict]:
    seen: Set[str] = set()
    all_problems: List[dict] = []

    for diff in _DIFFICULTY_LEVELS:
        if max_count and len(all_problems) >= max_count:
            break

        page_num = 1
        while True:
            if max_count and len(all_problems) >= max_count:
                break

            url = f"https://www.luogu.com.cn/problem/list?difficulty={diff}&type=P&page={page_num}"
            logger.info("Fetching Luogu list: difficulty=%d, page=%d", diff, page_num)
            html = bm.fetch_page(url, wait_until="networkidle", extra_wait=3.0)
            if html is None:
                logger.warning("Failed to fetch list page diff=%d page=%d", diff, page_num)
                break

            soup = BeautifulSoup(html, "html.parser")
            links = soup.find_all("a", href=re.compile(r"^/problem/P\d+"))

            if not links:
                break

            new_count = 0
            for a in links:
                href = a.get("href", "")
                match = re.search(r"/problem/(P\d+)", href)
                if not match:
                    continue
                pid = match.group(1)
                if pid in seen:
                    continue
                seen.add(pid)
                title = a.get_text(strip=True)
                all_problems.append({"pid": pid, "title": title, "difficulty": diff})
                new_count += 1

            logger.info("  Found %d new problems on page %d (total: %d)", new_count, page_num, len(all_problems))

            next_btn = soup.find("li", class_="next")
            if next_btn and "disabled" in next_btn.get("class", []):
                break
            has_next = bool(soup.find("a", href=re.compile(rf"page={page_num + 1}")))
            if not has_next and new_count == 0:
                break

            page_num += 1

    logger.info("Collected %d unique problem PIDs from Luogu", len(all_problems))
    return all_problems


def _extract_json_data(html: str) -> Optional[dict]:
    """Extract problem data from the embedded <script type='application/json'> tag.

    Luogu embeds the full problem content (raw markdown with LaTeX) in a JSON
    script tag, which is far cleaner than parsing the KaTeX-rendered DOM.
    """
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script", type="application/json"):
        text = script.string or ""
        if '"problem"' not in text:
            continue
        try:
            data = json.loads(text)
            problem = data.get("data", {}).get("problem", {})
            if problem and "content" in problem:
                return problem
        except (json.JSONDecodeError, KeyError):
            continue
    return None


def _extract_constraints_from_hint(hint: str) -> str:
    """Extract constraint lines from the hint/说明 section."""
    if not hint:
        return ""
    constraint_markers = ["数据范围", "数据规模", "对于", "范围", "限制", "Constraints"]
    lines = hint.split("\n")
    constraint_lines = []
    in_constraints = False

    for line in lines:
        stripped = line.strip()
        if any(marker in stripped for marker in constraint_markers):
            in_constraints = True
        if in_constraints and stripped:
            constraint_lines.append(stripped)
        elif re.search(r"\d+\s*[≤<=≥>=]\s*\w+|[≤<=≥>=]\s*\d+", stripped):
            if not in_constraints:
                constraint_lines.append(stripped)

    return "\n".join(constraint_lines)


def _extract_constraints_from_description(description: str) -> tuple[str, str]:
    """Split constraint info out of description if no separate hint section."""
    lines = description.split("\n")
    desc_lines = []
    constraint_lines = []
    in_constraints = False

    for line in lines:
        stripped = line.strip()
        if any(m in stripped for m in ["数据范围", "数据规模", "对于 100%", "对于100%"]):
            in_constraints = True
        if in_constraints and stripped:
            constraint_lines.append(stripped)
        else:
            desc_lines.append(line)

    return "\n".join(desc_lines).strip(), "\n".join(constraint_lines)


def _parse_from_json(problem_data: dict, pid: str, difficulty: int) -> Optional[ProblemText]:
    """Parse a ProblemText from Luogu's embedded JSON data.

    The JSON 'content' dict has keys: name, background, description,
    formatI, formatO, hint, locale — all raw markdown with inline LaTeX.
    """
    content = problem_data.get("content", {})
    if not content or not isinstance(content, dict):
        return None

    title = content.get("name", "")
    background = (content.get("background") or "").strip()
    description = (content.get("description") or "").strip()
    format_input = (content.get("formatI") or "").strip()
    format_output = (content.get("formatO") or "").strip()
    hint = (content.get("hint") or "").strip()

    if background and description:
        description = background + "\n\n" + description
    elif background:
        description = background

    constraints = _extract_constraints_from_hint(hint)
    if not constraints:
        description, constraints = _extract_constraints_from_description(description)

    if not description and not format_input:
        return None

    return ProblemText(
        problem_id=pid,
        title=title,
        description=description,
        input=format_input,
        output=format_output,
        constraints=constraints,
        source="luogu",
        url=f"https://www.luogu.com.cn/problem/{pid}",
        tags=[],
        difficulty=_DIFFICULTY_MAP.get(difficulty, str(difficulty)),
    )


def scrape_luogu(max_problems: int | None = None) -> List[ProblemText]:
    logger.info("Collecting NOI/省选 problem list from Luogu...")

    results: List[ProblemText] = []

    with BrowserManager(rate_limit=LUOGU_RATE) as bm:
        problem_metas = _collect_pids_via_browser(bm, max_count=max_problems)
        if max_problems:
            problem_metas = problem_metas[:max_problems]

        total = len(problem_metas)
        for i, meta in enumerate(problem_metas):
            pid = meta.get("pid", "")
            diff = meta.get("difficulty", 0)
            logger.info("[%d/%d] Scraping %s ...", i + 1, total, pid)

            url = f"https://www.luogu.com.cn/problem/{pid}"
            html = bm.fetch_page_with_retry(
                url, max_retries=2, wait_until="networkidle", extra_wait=3.0
            )
            if html is None:
                logger.warning("Failed to fetch %s", pid)
                continue

            problem_data = _extract_json_data(html)
            if problem_data:
                problem = _parse_from_json(problem_data, pid, diff)
            else:
                logger.warning("No JSON data found for %s, skipping", pid)
                problem = None

            if problem:
                results.append(problem)
            else:
                logger.warning("Failed to parse %s", pid)

    logger.info("Scraped %d Luogu NOI/省选 problems", len(results))
    return results
