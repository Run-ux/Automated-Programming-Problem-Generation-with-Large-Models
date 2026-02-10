from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import (
    ATCODER_OUTPUT_DIR,
    CF_OUTPUT_DIR,
    ICPC_OUTPUT_DIR,
    LOG_FORMAT,
    LOG_LEVEL,
    LUOGU_OUTPUT_DIR,
)
from .common.storage import save_problems_batch


def _setup_logging():
    logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT, stream=sys.stdout)


def _run_codeforces(max_problems: int | None):
    from .codeforces.scraper import scrape_codeforces
    problems = scrape_codeforces(max_problems=max_problems)
    return save_problems_batch(problems, CF_OUTPUT_DIR)


def _run_atcoder(max_problems: int | None):
    from .atcoder.scraper import scrape_atcoder
    problems = scrape_atcoder(max_problems=max_problems)
    return save_problems_batch(problems, ATCODER_OUTPUT_DIR)


def _run_luogu(max_problems: int | None):
    from .luogu.scraper import scrape_luogu
    problems = scrape_luogu(max_problems=max_problems)
    return save_problems_batch(problems, LUOGU_OUTPUT_DIR)


def _run_icpc(max_problems: int | None):
    from .icpc.scraper import scrape_icpc
    problems = scrape_icpc(max_problems=max_problems)
    return save_problems_batch(problems, ICPC_OUTPUT_DIR)


SCRAPERS = {
    "codeforces": _run_codeforces,
    "atcoder": _run_atcoder,
    "luogu": _run_luogu,
    "icpc": _run_icpc,
}


def main():
    _setup_logging()
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description="Competitive programming problem scraper")
    parser.add_argument(
        "sources",
        nargs="*",
        default=list(SCRAPERS.keys()),
        choices=list(SCRAPERS.keys()),
        help="Sources to scrape (default: all)",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=None,
        help="Max problems per source (for testing)",
    )

    args = parser.parse_args()

    total_saved = 0
    for source in args.sources:
        logger.info("=" * 60)
        logger.info("Starting scraper: %s", source)
        logger.info("=" * 60)
        try:
            count = SCRAPERS[source](args.max)
            total_saved += count
            logger.info("Finished %s: saved %d problems", source, count)
        except Exception:
            logger.exception("Scraper %s failed", source)

    logger.info("=" * 60)
    logger.info("All done. Total problems saved: %d", total_saved)


if __name__ == "__main__":
    main()
