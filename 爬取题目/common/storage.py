from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List

from .models import ProblemText
from .utils import sanitize_filename

logger = logging.getLogger(__name__)


def save_problem_md(problem: ProblemText, output_dir: Path) -> Path:
    """Save as standardized .md: Title/Description/Input/Output/Constraints (no samples, no hints)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = sanitize_filename(problem.problem_id) + ".md"
    filepath = output_dir / filename

    lines = [
        problem.title,
        "",
        problem.description,
        "",
        "Input",
        problem.input,
        "",
        "Output",
        problem.output,
        "",
        "Constraints",
        problem.constraints,
    ]

    filepath.write_text("\n".join(lines), encoding="utf-8")
    logger.debug("Saved %s -> %s", problem.problem_id, filepath)
    return filepath


def update_index(problems: List[ProblemText], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    index_path = output_dir / "index.json"

    existing: dict = {}
    if index_path.exists():
        try:
            existing = {
                p["problem_id"]: p
                for p in json.loads(index_path.read_text(encoding="utf-8"))
            }
        except (json.JSONDecodeError, KeyError):
            existing = {}

    for p in problems:
        existing[p.problem_id] = p.model_dump()

    sorted_entries = sorted(existing.values(), key=lambda x: x["problem_id"])
    index_path.write_text(
        json.dumps(sorted_entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Updated index: %d problems -> %s", len(sorted_entries), index_path)
    return index_path


def save_problems_batch(
    problems: List[ProblemText],
    output_dir: Path,
    *,
    update_idx: bool = True,
) -> int:
    saved = 0
    for p in problems:
        try:
            save_problem_md(p, output_dir)
            saved += 1
        except Exception as exc:
            logger.error("Failed to save %s: %s", p.problem_id, exc)

    if update_idx and problems:
        update_index(problems, output_dir)

    logger.info("Batch save: %d/%d problems to %s", saved, len(problems), output_dir)
    return saved
