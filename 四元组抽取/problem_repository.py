from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_INDEX_ROOT = Path(__file__).resolve().parent.parent / "爬取题目" / "output"
INDEX_FILES = {
    "codeforces": "codeforces/index.json",
    "luogu": "luogu/index.json",
    "icpc": "icpc/index.json",
    "atcoder": "atcoder/index.json",
}
SOURCE_ALIASES = {
    "icpc_gym": "icpc",
}


class ProblemRepository:
    def __init__(self, index_root: Path | None = None):
        self.index_root = index_root or DEFAULT_INDEX_ROOT
        self._cache: dict[str, dict[str, dict[str, Any]]] = {}

    def get_problem(self, source: str, problem_id: str) -> dict[str, Any]:
        source = self._normalize_source(source)
        if source not in INDEX_FILES:
            raise KeyError(f"Unsupported source: {source}")
        if source not in self._cache:
            self._cache[source] = self._load_index(source)

        try:
            return self._cache[source][problem_id]
        except KeyError as exc:
            raise KeyError(
                f"Problem {problem_id} not found in source index {source}"
            ) from exc

    def _load_index(self, source: str) -> dict[str, dict[str, Any]]:
        path = self.index_root / INDEX_FILES[source]
        if not path.exists():
            raise FileNotFoundError(f"Index file not found: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return {item["problem_id"]: item for item in data if item.get("problem_id")}

    def _normalize_source(self, source: str) -> str:
        source = source.lower()
        return SOURCE_ALIASES.get(source, source)
