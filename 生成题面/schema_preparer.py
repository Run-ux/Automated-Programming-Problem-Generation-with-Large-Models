from __future__ import annotations

import json
from pathlib import Path


FOUR_TUPLE_KEYS = ("problem_id", "source", "input_structure", "core_constraints", "objective", "invariant")


class SchemaPreparer:
    def __init__(self, source_dir: Path, cache_dir: Path):
        self.source_dir = source_dir
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def prepare(self, problem_ids: list[str]) -> Path:
        if not problem_ids:
            schema_files = sorted(self.source_dir.glob("*.json"))
        else:
            schema_files = [self.source_dir / f"{problem_id}.json" for problem_id in problem_ids]

        for path in schema_files:
            if not path.exists():
                raise FileNotFoundError(f"Schema file not found: {path}")
            raw = json.loads(path.read_text(encoding="utf-8"))
            prepared = self._normalize_four_tuple(raw)
            target = self.cache_dir / path.name
            target.write_text(json.dumps(prepared, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.cache_dir

    def _normalize_four_tuple(self, data: dict) -> dict:
        prepared = {key: data.get(key) for key in FOUR_TUPLE_KEYS if key in data}
        prepared.setdefault("problem_id", data.get("problem_id", "unknown"))
        prepared.setdefault("source", data.get("source", ""))
        prepared.setdefault("input_structure", data.get("input_structure", {}))
        prepared.setdefault(
            "core_constraints",
            data.get("core_constraints") or {"constraints": data.get("C", []) if isinstance(data.get("C"), list) else []},
        )
        prepared.setdefault("objective", data.get("objective") or data.get("O") or {})
        prepared.setdefault(
            "invariant",
            data.get("invariant") or {"invariants": data.get("V", []) if isinstance(data.get("V"), list) else []},
        )
        if "transform_space" in data:
            prepared["transform_space"] = data.get("transform_space")
        return prepared
