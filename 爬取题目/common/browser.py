from __future__ import annotations

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


class BrowserManager:

    def __init__(self, headless: bool = True, rate_limit: float = 1.0):
        self._headless = headless
        self._rate_limit = rate_limit
        self._last_request: float = 0.0
        self._pw = None
        self._browser = None

    def __enter__(self) -> "BrowserManager":
        self.start()
        return self

    def __exit__(self, *args) -> None:
        self.stop()

    def start(self) -> None:
        from playwright.sync_api import sync_playwright

        logger.info("Starting Playwright browser (headless=%s)...", self._headless)
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self._headless)
        logger.info("Playwright browser started.")

    def stop(self) -> None:
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()
        self._browser = None
        self._pw = None
        logger.info("Playwright browser stopped.")

    def _wait_rate_limit(self) -> None:
        elapsed = time.time() - self._last_request
        if elapsed < self._rate_limit:
            time.sleep(self._rate_limit - elapsed)
        self._last_request = time.time()

    def _fetch_in_fresh_context(
        self,
        url: str,
        wait_until: str,
        extra_wait: float,
        timeout: int,
    ) -> Optional[str]:
        from playwright_stealth import stealth_sync

        if not self._browser:
            raise RuntimeError("BrowserManager not started. Use start() or context manager.")

        ctx = self._browser.new_context(
            user_agent=_UA,
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
        )
        try:
            page = ctx.new_page()
            stealth_sync(page)
            resp = page.goto(url, wait_until=wait_until, timeout=timeout)

            if resp and resp.status in (403, 404):
                logger.debug("Got %d for %s", resp.status, url)
                return None

            if extra_wait > 0:
                time.sleep(extra_wait)
            return page.content()
        except Exception as exc:
            logger.warning("Failed to fetch %s: %s", url, exc)
            return None
        finally:
            ctx.close()

    def fetch_page(
        self,
        url: str,
        *,
        wait_until: str = "domcontentloaded",
        extra_wait: float = 2.0,
        timeout: int = 30000,
    ) -> Optional[str]:
        self._wait_rate_limit()
        return self._fetch_in_fresh_context(url, wait_until, extra_wait, timeout)

    def fetch_page_with_retry(
        self,
        url: str,
        *,
        max_retries: int = 2,
        wait_until: str = "domcontentloaded",
        extra_wait: float = 2.0,
        timeout: int = 30000,
    ) -> Optional[str]:
        for attempt in range(max_retries + 1):
            html = self.fetch_page(
                url, wait_until=wait_until, extra_wait=extra_wait, timeout=timeout
            )
            if html is not None:
                return html
            if attempt < max_retries:
                delay = 3.0 * (attempt + 1)
                logger.warning(
                    "Retry %d/%d for %s in %.1fs...", attempt + 1, max_retries, url, delay
                )
                time.sleep(delay)
        return None
