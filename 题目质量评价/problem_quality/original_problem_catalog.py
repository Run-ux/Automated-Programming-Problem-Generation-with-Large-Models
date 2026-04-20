from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PLATFORMS = ["codeforces", "luogu", "icpc", "atcoder"]
IMANDRA_DIR_NAME = "imandra_curated_schema_inputs"


class OriginalProblemCatalog:
    def __init__(self, output_dir: str | Path | None = None) -> None:
        if output_dir is None:
            output_dir = Path(__file__).resolve().parents[2] / "爬取题目" / "output"
        self.output_dir = Path(output_dir)
        self._index_by_problem_id: dict[str, dict[str, Any]] = {}
        self._imandra_cache: dict[str, dict[str, Any]] = {}
        self._imandra_miss: set[str] = set()
        self._load_platform_indexes()

    def get_by_problem_id(self, problem_id: str | None) -> dict[str, Any] | None:
        if not isinstance(problem_id, str):
            return None
        normalized = problem_id.strip()
        if not normalized:
            return None

        direct = self._index_by_problem_id.get(normalized)
        if direct is not None:
            return direct

        if normalized in self._imandra_miss:
            return None

        cached = self._imandra_cache.get(normalized)
        if cached is not None:
            return cached

        matched = self._scan_imandra_by_problem_id(normalized)
        if matched is None:
            self._imandra_miss.add(normalized)
            return None
        self._imandra_cache[normalized] = matched
        return matched

    def _load_platform_indexes(self) -> None:
        for platform in PLATFORMS:
            index_path = self.output_dir / platform / "index.json"
            if not index_path.exists():
                continue
            records = self._read_json_array(index_path)
            for record in records:
                key = self._extract_problem_id(record)
                if key and key not in self._index_by_problem_id:
                    self._index_by_problem_id[key] = record

    def _scan_imandra_by_problem_id(self, problem_id: str) -> dict[str, Any] | None:
        imandra_dir = self.output_dir / IMANDRA_DIR_NAME
        if not imandra_dir.exists() or not imandra_dir.is_dir():
            return None

        for json_path in sorted(imandra_dir.glob("*.json")):
            if json_path.name == "manifest.json":
                continue
            record = self._read_json_object(json_path)
            if record is None:
                continue
            key = self._extract_problem_id(record)
            if not key:
                continue
            if key == problem_id:
                return record
        return None

    def _read_json_array(self, path: Path) -> list[dict[str, Any]]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(payload, list):
            return []
        result: list[dict[str, Any]] = []
        for item in payload:
            if isinstance(item, dict):
                result.append(item)
        return result

    def _read_json_object(self, path: Path) -> dict[str, Any] | None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    def _extract_problem_id(self, record: dict[str, Any]) -> str | None:
        raw = record.get("problem_id")
        if not isinstance(raw, str):
            return None
        normalized = raw.strip()
        if not normalized:
            return None
        return normalized
