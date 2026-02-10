from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from ..common.browser import BrowserManager
from ..common.models import ProblemText
from ..common.utils import RateLimiter, create_session, extract_text_from_tag, retry
from ..config import ATCODER_CONTEST_PREFIXES, ATCODER_RATE, USER_AGENT

logger = logging.getLogger(__name__)

_api_limiter = RateLimiter(1.0)

KENKOOOO_PROBLEMS = "https://kenkoooo.com/atcoder/resources/problems.json"


@retry(max_retries=3, delay=2.0)
def _fetch_json(session: requests.Session, url: str) -> list:
    _api_limiter.wait()
    resp = session.get(url, timeout=60)
    resp.raise_for_status()
    return resp.json()


def _get_contest_prefix(contest_id: str) -> Optional[str]:
    for prefix in ATCODER_CONTEST_PREFIXES:
        if contest_id.startswith(prefix):
            return prefix
    return None


def _should_include(contest_id: str, problem_index: str) -> bool:
    prefix = _get_contest_prefix(contest_id)
    if prefix is None:
        return False

    allowed_indices = ATCODER_CONTEST_PREFIXES[prefix]
    if allowed_indices is None:
        return True

    idx_upper = problem_index.upper()
    for allowed in allowed_indices:
        if idx_upper == allowed.upper():
            return True
        if allowed.lower() == "ex" and idx_upper.startswith("EX"):
            return True

    return False


def _extract_problem_index(problem_id: str, contest_id: str) -> str:
    return problem_id.replace(contest_id + "_", "", 1)


def _filter_problems(problems: list) -> List[dict]:
    filtered = []
    for p in problems:
        contest_id = p.get("contest_id", "")
        problem_id = p.get("id", "")
        problem_index = _extract_problem_index(problem_id, contest_id)

        if _should_include(contest_id, problem_index):
            p["_index"] = problem_index
            filtered.append(p)

    logger.info("Filtered %d target problems from %d total", len(filtered), len(problems))
    return filtered


def _parse_problem_html(html: str, problem_meta: dict) -> Optional[ProblemText]:
    soup = BeautifulSoup(html, "html.parser")

    for ja_span in soup.find_all("span", class_="lang-ja"):
        ja_span.decompose()

    task_statement = soup.find("div", id="task-statement")
    if not task_statement:
        return None

    title_tag = soup.find("span", class_="h2")
    title = title_tag.get_text(strip=True) if title_tag else problem_meta.get("title", "")
    title = re.sub(r"^[A-Za-z]+\s*[-–]\s*", "", title)

    sections: Dict[str, str] = {}

    h3_tags = task_statement.find_all("h3")

    if h3_tags:
        for h3 in h3_tags:
            header_text = h3.get_text(strip=True).lower()

            content_parts = []
            sibling = h3.next_sibling
            while sibling:
                if hasattr(sibling, "name") and sibling.name == "h3":
                    break
                if hasattr(sibling, "name"):
                    content_parts.append(extract_text_from_tag(sibling))
                elif isinstance(sibling, str) and sibling.strip():
                    content_parts.append(sibling.strip())
                sibling = sibling.next_sibling

            content = "\n".join(p for p in content_parts if p)

            if "problem statement" in header_text or "statement" in header_text:
                sections["description"] = content
            elif "constraint" in header_text:
                sections["constraints"] = content
            elif "input" in header_text and "sample" not in header_text:
                sections["input"] = content
            elif "output" in header_text and "sample" not in header_text:
                sections["output"] = content
    else:
        for section in task_statement.find_all("section"):
            h3 = section.find("h3")
            if not h3:
                text = extract_text_from_tag(section)
                if text and "description" not in sections:
                    sections["description"] = text
                continue

            header_text = h3.get_text(strip=True).lower()
            h3.decompose()
            content = extract_text_from_tag(section)

            if "problem statement" in header_text or "statement" in header_text:
                sections["description"] = content
            elif "constraint" in header_text:
                sections["constraints"] = content
            elif "input" in header_text and "sample" not in header_text:
                sections["input"] = content
            elif "output" in header_text and "sample" not in header_text:
                sections["output"] = content

    if not sections.get("description") and not sections.get("input"):
        full_text = extract_text_from_tag(task_statement)
        if full_text:
            sections["description"] = full_text

    if not sections.get("description"):
        return None

    contest_id = problem_meta.get("contest_id", "")
    problem_index = problem_meta.get("_index", "")
    display_id = f"{contest_id.upper()}_{problem_index.upper()}"

    return ProblemText(
        problem_id=display_id,
        title=title,
        description=sections.get("description", ""),
        input=sections.get("input", ""),
        output=sections.get("output", ""),
        constraints=sections.get("constraints", ""),
        source="atcoder",
        url=f"https://atcoder.jp/contests/{contest_id}/tasks/{problem_meta.get('id', '')}",
        tags=[],
        difficulty=None,
    )


def scrape_atcoder(max_problems: int | None = None) -> List[ProblemText]:
    session = create_session(USER_AGENT)
    logger.info("Fetching AtCoder problem list from kenkoooo...")

    problems = _fetch_json(session, KENKOOOO_PROBLEMS)
    filtered = _filter_problems(problems)

    if max_problems:
        filtered = filtered[:max_problems]

    results: List[ProblemText] = []
    total = len(filtered)

    with BrowserManager(rate_limit=ATCODER_RATE) as bm:
        for i, p in enumerate(filtered):
            contest_id = p["contest_id"]
            task_id = p["id"]
            logger.info("[%d/%d] Scraping %s/%s ...", i + 1, total, contest_id, task_id)

            url = f"https://atcoder.jp/contests/{contest_id}/tasks/{task_id}?lang=en"
            html = bm.fetch_page_with_retry(url, max_retries=2, extra_wait=2.0)
            if html is None:
                logger.warning("Failed to fetch %s/%s", contest_id, task_id)
                continue

            problem = _parse_problem_html(html, p)
            if problem:
                results.append(problem)
            else:
                logger.warning("Failed to parse %s/%s", contest_id, task_id)

    logger.info("Scraped %d AtCoder problems", len(results))
    return results
