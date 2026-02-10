from __future__ import annotations

import logging
import re
from typing import List, Optional, Set

import requests
from bs4 import BeautifulSoup

from ..common.browser import BrowserManager
from ..common.models import ProblemText
from ..common.utils import RateLimiter, clean_mathjax, create_session, extract_text_from_tag, retry
from ..config import (
    CF_API_RATE,
    CF_DIV1_INDICES,
    CF_DIV1_PATTERN,
    CF_DIV2_INDICES,
    CF_DIV2_PATTERN,
    CF_HTML_RATE,
    CF_MAX_RATING,
    CF_MIN_RATING,
    USER_AGENT,
)

logger = logging.getLogger(__name__)

_api_limiter = RateLimiter(CF_API_RATE)


@retry(max_retries=3, delay=3.0)
def _api_get(session: requests.Session, url: str, params: dict | None = None) -> dict:
    _api_limiter.wait()
    resp = session.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "OK":
        raise requests.RequestException(f"CF API error: {data.get('comment', 'unknown')}")
    return data["result"]


def _fetch_div_contest_ids(session: requests.Session) -> tuple[Set[int], Set[int]]:
    contests = _api_get(session, "https://codeforces.com/api/contest.list")
    div1_ids: Set[int] = set()
    div2_ids: Set[int] = set()
    for c in contests:
        if c.get("phase") != "FINISHED":
            continue
        name = c.get("name", "")
        if re.search(CF_DIV1_PATTERN, name, re.IGNORECASE):
            div1_ids.add(c["id"])
        if re.search(CF_DIV2_PATTERN, name, re.IGNORECASE):
            div2_ids.add(c["id"])
    logger.info("Found %d Div1 contests, %d Div2 contests", len(div1_ids), len(div2_ids))
    return div1_ids, div2_ids


def _filter_problems(
    div1_ids: Set[int], div2_ids: Set[int], session: requests.Session
) -> List[dict]:
    result = _api_get(session, "https://codeforces.com/api/problemset.problems")
    problems = result["problems"]

    filtered = []
    for p in problems:
        cid = p.get("contestId")
        idx = p.get("index", "")
        rating = p.get("rating", 0)

        if rating and (rating < CF_MIN_RATING or rating > CF_MAX_RATING):
            continue

        is_target = False
        if cid in div2_ids and idx in CF_DIV2_INDICES:
            is_target = True
        if cid in div1_ids and idx in CF_DIV1_INDICES:
            is_target = True

        if is_target:
            filtered.append(p)

    logger.info("Filtered %d target problems from %d total", len(filtered), len(problems))
    return filtered


def _parse_problem_html(html: str, contest_id: int, index: str) -> Optional[ProblemText]:
    soup = BeautifulSoup(html, "html.parser")
    statement = soup.find("div", class_="problem-statement")
    if not statement:
        return None

    children = [c for c in statement.children if hasattr(c, "name") and c.name]

    title_text = ""
    description_parts = []
    input_text = ""
    output_text = ""
    constraints_parts = []

    for child in children:
        classes = child.get("class", [])

        if "header" in classes:
            title_div = child.find("div", class_="title")
            if title_div:
                title_text = title_div.get_text(strip=True)
            time_limit = child.find("div", class_="time-limit")
            memory_limit = child.find("div", class_="memory-limit")
            if time_limit:
                constraints_parts.append(extract_text_from_tag(time_limit))
            if memory_limit:
                constraints_parts.append(extract_text_from_tag(memory_limit))
            continue

        if "input-specification" in classes:
            div_title = child.find("div", class_="section-title")
            if div_title:
                div_title.decompose()
            input_text = extract_text_from_tag(child)
            continue

        if "output-specification" in classes:
            div_title = child.find("div", class_="section-title")
            if div_title:
                div_title.decompose()
            output_text = extract_text_from_tag(child)
            continue

        if "sample-tests" in classes or "note" in classes:
            continue

        text = extract_text_from_tag(child, paragraph_mode=True)
        if text:
            description_parts.append(text)

    description = "\n\n".join(description_parts)

    description = clean_mathjax(description)
    input_text = clean_mathjax(input_text)
    output_text = clean_mathjax(output_text)
    constraints = clean_mathjax("\n".join(constraints_parts))

    if not description and not input_text:
        return None

    return ProblemText(
        problem_id=f"CF{contest_id}{index}",
        title=title_text,
        description=description,
        input=input_text,
        output=output_text,
        constraints=constraints,
        source="codeforces",
        url=f"https://codeforces.com/contest/{contest_id}/problem/{index}",
        tags=[],
        difficulty=None,
    )


def scrape_codeforces(max_problems: int | None = None) -> List[ProblemText]:
    session = create_session(USER_AGENT)
    logger.info("Fetching Codeforces contest list...")

    div1_ids, div2_ids = _fetch_div_contest_ids(session)
    problems_meta = _filter_problems(div1_ids, div2_ids, session)

    # Sort by contest ID ascending so we get older, established problems first
    # (newest contests may still be running and return 403)
    problems_meta.sort(key=lambda p: (p.get("contestId", 0), p.get("index", "")))

    if max_problems:
        problems_meta = problems_meta[:max_problems]

    results: List[ProblemText] = []
    total = len(problems_meta)

    with BrowserManager(rate_limit=CF_HTML_RATE) as bm:
        for i, p in enumerate(problems_meta):
            cid = p["contestId"]
            idx = p["index"]
            logger.info("[%d/%d] Scraping CF%d%s ...", i + 1, total, cid, idx)

            url = f"https://codeforces.com/contest/{cid}/problem/{idx}"
            html = bm.fetch_page_with_retry(url, max_retries=2, extra_wait=3.0)
            if html is None:
                logger.warning("Failed to fetch CF%d%s", cid, idx)
                continue

            problem = _parse_problem_html(html, cid, idx)
            if problem:
                problem.tags = p.get("tags", [])
                problem.difficulty = str(p["rating"]) if p.get("rating") else None
                results.append(problem)
            else:
                logger.warning("Failed to parse CF%d%s", cid, idx)

    logger.info("Scraped %d Codeforces problems", len(results))
    return results
