from __future__ import annotations

import logging
import re
import string
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from ..common.browser import BrowserManager
from ..common.models import ProblemText
from ..common.utils import RateLimiter, clean_mathjax, create_session, extract_text_from_tag, retry
from ..config import CF_API_RATE, ICPC_GYM_NAME_PATTERNS, ICPC_GYM_RATE, USER_AGENT

logger = logging.getLogger(__name__)

_api_limiter = RateLimiter(CF_API_RATE)

_PROBLEM_INDICES = list(string.ascii_uppercase[:14])


@retry(max_retries=3, delay=3.0)
def _api_get(session: requests.Session, url: str, params: dict | None = None) -> list:
    _api_limiter.wait()
    resp = session.get(url, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "OK":
        raise requests.RequestException(f"CF API error: {data.get('comment', 'unknown')}")
    return data["result"]


def _fetch_icpc_gym_contests(session: requests.Session) -> List[dict]:
    contests = _api_get(session, "https://codeforces.com/api/contest.list", {"gym": "true"})

    compiled_patterns = [re.compile(p, re.IGNORECASE) for p in ICPC_GYM_NAME_PATTERNS]
    icpc_contests = []

    for c in contests:
        if c.get("phase") != "FINISHED":
            continue
        name = c.get("name", "")
        if any(pat.search(name) for pat in compiled_patterns):
            icpc_contests.append(c)

    logger.info("Found %d ICPC Gym contests from %d total gym contests", len(icpc_contests), len(contests))
    return icpc_contests


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

    description = clean_mathjax("\n\n".join(description_parts))
    input_text = clean_mathjax(input_text)
    output_text = clean_mathjax(output_text)
    constraints = clean_mathjax("\n".join(constraints_parts))

    if not description and not input_text:
        return None

    return ProblemText(
        problem_id=f"GYM{contest_id}{index}",
        title=title_text,
        description=description,
        input=input_text,
        output=output_text,
        constraints=constraints,
        source="icpc_gym",
        url=f"https://codeforces.com/gym/{contest_id}/problem/{index}",
        tags=[],
        difficulty=None,
    )


def scrape_icpc(max_problems: int | None = None) -> List[ProblemText]:
    session = create_session(USER_AGENT)
    logger.info("Fetching ICPC Gym contest list...")

    contests = _fetch_icpc_gym_contests(session)
    contests.sort(key=lambda c: c["id"], reverse=True)
    results: List[ProblemText] = []
    problems_found = 0

    with BrowserManager(rate_limit=ICPC_GYM_RATE) as bm:
        for ci, contest in enumerate(contests):
            if max_problems and problems_found >= max_problems:
                break

            contest_id = contest["id"]
            contest_name = contest.get("name", "")
            logger.info("[Contest %d/%d] %s (ID: %d)", ci + 1, len(contests), contest_name, contest_id)

            consecutive_misses = 0
            for index in _PROBLEM_INDICES:
                if max_problems and problems_found >= max_problems:
                    break

                url = f"https://codeforces.com/gym/{contest_id}/problem/{index}"
                html = bm.fetch_page(url, extra_wait=1.0, timeout=20000)

                if html is None or "problem-statement" not in html:
                    consecutive_misses += 1
                    if consecutive_misses >= 2:
                        break
                    continue

                consecutive_misses = 0
                problem = _parse_problem_html(html, contest_id, index)
                if problem:
                    results.append(problem)
                    problems_found += 1
                    logger.info("  Scraped GYM%d%s: %s", contest_id, index, problem.title)
                else:
                    logger.debug("Could not parse GYM%d%s", contest_id, index)

    logger.info("Scraped %d ICPC Gym problems from %d contests", len(results), len(contests))
    return results
