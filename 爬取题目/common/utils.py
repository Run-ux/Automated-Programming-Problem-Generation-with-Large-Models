from __future__ import annotations

import logging
import re
import time
from functools import wraps
from typing import Callable, TypeVar

import requests
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------

class RateLimiter:

    def __init__(self, min_interval: float = 1.0):
        self.min_interval = min_interval
        self._last_request_time: float = 0.0

    def wait(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_request_time = time.time()


# ---------------------------------------------------------------------------
# Retry Decorator
# ---------------------------------------------------------------------------

def retry(
    max_retries: int = 3,
    delay: float = 2.0,
    backoff: float = 2.0,
    exceptions: tuple = (requests.RequestException,),
) -> Callable:
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            current_delay = delay
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt < max_retries:
                        logger.warning(
                            "Attempt %d/%d failed for %s: %s. Retrying in %.1fs...",
                            attempt + 1,
                            max_retries,
                            func.__name__,
                            exc,
                            current_delay,
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
            raise last_exc  # type: ignore[misc]

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# HTML Text Cleaning
# ---------------------------------------------------------------------------

def clean_html_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    # Collapse multiple blank lines into single
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_mathjax_rendering(tag: Tag) -> None:
    """Replace MathJax rendered spans with original LaTeX from <script type='math/tex'> tags.

    Codeforces renders math via MathJax which creates complex nested spans.
    The original LaTeX is preserved in <script type="math/tex"> elements.
    This function replaces the rendered output with $latex$ inline text."""
    from bs4 import NavigableString

    for script in tag.find_all("script", attrs={"type": re.compile(r"math/tex")}):
        latex = script.string or ""
        is_display = "display" in (script.get("type") or "")
        if is_display:
            replacement = f"$${latex}$$"
        else:
            replacement = f"${latex}$"
        script.replace_with(NavigableString(replacement))

    for span in tag.find_all("span", class_="MathJax"):
        span.decompose()
    for span in tag.find_all("span", class_="MathJax_Preview"):
        span.decompose()
    for span in tag.find_all("span", class_="MJX_Assistive_MathML"):
        span.decompose()


def extract_text_from_tag(tag: Tag | None, *, paragraph_mode: bool = False) -> str:
    if tag is None:
        return ""
    strip_mathjax_rendering(tag)

    if paragraph_mode:
        paragraphs = []
        for p in tag.find_all("p"):
            t = p.get_text(" ", strip=True)
            if t:
                paragraphs.append(t)
        if paragraphs:
            text = "\n\n".join(paragraphs)
        else:
            text = tag.get_text(" ", strip=True)
    else:
        text = tag.get_text(" ", strip=True)

    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r" ([,.\);\]])", r"\1", text)
    text = re.sub(r"([\(\[]) ", r"\1", text)
    return text


# ---------------------------------------------------------------------------
# LaTeX / MathJax Cleaning
# ---------------------------------------------------------------------------

def clean_mathjax(text: str) -> str:
    # Codeforces uses $$$ as inline math delimiter, normalize to single $
    text = re.sub(r"\$\$\$(.*?)\$\$\$", r"$\1$", text)
    return text


# ---------------------------------------------------------------------------
# Filename Sanitizer
# ---------------------------------------------------------------------------

_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename(name: str, max_length: int = 200) -> str:
    name = _INVALID_CHARS.sub("_", name)
    name = name.strip(". ")
    if len(name) > max_length:
        name = name[:max_length]
    return name or "unnamed"


# ---------------------------------------------------------------------------
# HTTP Session Factory
# ---------------------------------------------------------------------------

def create_session(user_agent: str | None = None) -> requests.Session:
    session = requests.Session()
    ua = user_agent or (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    session.headers.update({
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/json",
        "Accept-Language": "en-US,en;q=0.9",
    })
    return session
