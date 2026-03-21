from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from finiteness_verification.problem_repository import ProblemRepository
from finiteness_verification.transform import enrich_schema_with_transform_space
from transform_space_tools import expand_transform_space


class SchemaPreparer:
    def __init__(self, source_dir: Path, cache_dir: Path):
        self.source_dir = source_dir
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def prepare(
        self,
        problem_ids: list[str],
        allow_llm_enrich: bool,
    ) -> Path:
        if not problem_ids:
            schema_files = sorted(self.source_dir.glob("*.json"))
        else:
            schema_files = [self.source_dir / f"{problem_id}.json" for problem_id in problem_ids]

        missing_transform = []
        for path in schema_files:
            if not path.exists():
                raise FileNotFoundError(f"Schema file not found: {path}")
            data = json.loads(path.read_text(encoding="utf-8"))
            if not data.get("transform_space"):
                missing_transform.append((path, data))
            else:
                target = self.cache_dir / path.name
                prepared = dict(data)
                prepared["transform_space"] = expand_transform_space(prepared)
                target.write_text(
                    json.dumps(prepared, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

        if not missing_transform:
            return self.cache_dir

        if not allow_llm_enrich:
            missing_ids = ", ".join(data.get("problem_id", path.stem) for path, data in missing_transform)
            raise RuntimeError(
                "以下 schema 缺少 transform_space，且当前未允许自动补全: "
                + missing_ids
            )

        repository = ProblemRepository()
        from finiteness_verification.qwen_client import QwenClient as FVQwenClient

        client = FVQwenClient()

        for path, data in missing_transform:
            problem = repository.get_problem(
                source=data.get("source", ""),
                problem_id=data.get("problem_id", path.stem),
            )
            enriched = enrich_schema_with_transform_space(data, problem, client)
            enriched["transform_space"] = expand_transform_space(enriched)
            target = self.cache_dir / path.name
            target.write_text(
                json.dumps(enriched, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        return self.cache_dir
