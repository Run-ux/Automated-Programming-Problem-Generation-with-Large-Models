from __future__ import annotations

import json
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from normalize import (
    apply_mapping_to_result,
    build_final_problem_output,
    extract_raw_entries_for_dimension,
    load_raw_files,
    normalize_all_problems,
)


class FakeQwenClient:
    def __init__(self, cfg) -> None:
        self.cfg = cfg


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class NormalizeHelpersTests(unittest.TestCase):
    def test_extract_raw_entries_use_stable_entry_ids(self) -> None:
        problem_dimension = {
            "status": "success",
            "result": {
                "type": "array",
                "length": {"min": 1, "max": 10},
                "properties": {"multiple_test_cases": True},
                "components": [
                    {
                        "role": "queries",
                        "type": "array",
                        "length": {"min": 1, "max": 5},
                        "value_range": {"min": 0, "max": 20},
                        "properties": {"online_queries": True},
                    }
                ],
            },
        }

        entries = extract_raw_entries_for_dimension(problem_dimension, "input_structure")

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["entry_id"], "input_structure")
        self.assertEqual(entries[0]["name"], "array")
        self.assertNotIn("round", entries[0]["entry_id"])

    def test_apply_mapping_to_result_updates_single_dimension(self) -> None:
        problem_dimension = {
            "status": "success",
            "result": {
                "invariants": [
                    {"name": "mono", "description": "keeps order"},
                    {"name": "state_transition", "description": "valid states"},
                ]
            },
        }

        apply_mapping_to_result(
            problem_dimension,
            "invariant",
            {"mono": "monotonicity"},
        )

        self.assertEqual(
            [item["name"] for item in problem_dimension["result"]["invariants"]],
            ["monotonicity", "state_transition"],
        )

    def test_build_final_problem_output_uses_defaults_for_failed_dimensions(self) -> None:
        problem_data = {
            "problem_id": "demo",
            "source": "cf",
            "input_structure": {
                "status": "success",
                "result": {
                    "type": "array",
                    "length": {"min": 1, "max": 10},
                },
            },
            "core_constraints": {"status": "failed", "result": {}},
            "objective": {"status": "failed", "result": {}},
            "invariant": {"status": "success", "result": {"invariants": []}},
        }

        output = build_final_problem_output(problem_data)

        self.assertEqual(output["input_structure"]["type"], "array")
        self.assertEqual(output["core_constraints"], {"constraints": []})
        self.assertEqual(output["objective"], {"type": None})
        self.assertEqual(output["invariant"], {"invariants": []})
        self.assertNotIn("status", output["input_structure"])

    def test_load_raw_files_keeps_first_duplicate_dimension(self) -> None:
        logger = logging.getLogger("normalize-test")
        with tempfile.TemporaryDirectory() as tmp_dir:
            raw_dir = Path(tmp_dir)
            write_json(
                raw_dir / "001.json",
                {
                    "problem_id": "demo",
                    "source": "cf",
                    "dimension": "input_structure",
                    "status": "success",
                    "result": {"type": "array"},
                },
            )
            write_json(
                raw_dir / "002.json",
                {
                    "problem_id": "demo",
                    "source": "cf",
                    "dimension": "input_structure",
                    "status": "success",
                    "result": {"type": "tree"},
                },
            )

            problems = load_raw_files(raw_dir, logger)

        self.assertEqual(
            problems["demo"]["input_structure"]["result"]["type"],
            "array",
        )


class NormalizePipelineTests(unittest.TestCase):
    def test_normalize_all_problems_writes_final_output(self) -> None:
        logger = logging.getLogger("normalize-pipeline-test")
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            raw_dir = base_dir / "raw"
            normalized_dir = base_dir / "normalized"
            registry_dir = base_dir / "label_registry"
            raw_dir.mkdir()

            write_json(
                raw_dir / "demo_input_structure.json",
                {
                    "problem_id": "demo",
                    "source": "cf",
                    "dimension": "input_structure",
                    "status": "success",
                    "result": {
                        "type": "arr",
                        "length": {"min": 1, "max": 10},
                        "value_range": {"min": 0, "max": 100},
                        "properties": {"multiple_test_cases": True},
                        "components": [
                            {
                                "role": "queries",
                                "type": "array",
                                "length": {"min": 1, "max": 5},
                                "value_range": {"min": 0, "max": 20},
                                "properties": {"online_queries": True},
                            }
                        ],
                    },
                },
            )
            write_json(
                raw_dir / "demo_core_constraints.json",
                {
                    "problem_id": "demo",
                    "source": "cf",
                    "dimension": "core_constraints",
                    "status": "success",
                    "result": {
                        "constraints": [
                            {"name": "range cap", "description": "n <= 1e5"}
                        ]
                    },
                },
            )
            write_json(
                raw_dir / "demo_objective.json",
                {
                    "problem_id": "demo",
                    "source": "cf",
                    "dimension": "objective",
                    "status": "failed",
                    "result": {},
                },
            )
            write_json(
                raw_dir / "demo_invariant.json",
                {
                    "problem_id": "demo",
                    "source": "cf",
                    "dimension": "invariant",
                    "status": "success",
                    "result": {
                        "invariants": [
                            {
                                "name": "mono",
                                "description": "keeps a valid boundary",
                                "properties": {"ordered": True},
                            }
                        ]
                    },
                },
            )

            def fake_embedding(*, raw_labels, **kwargs):
                if raw_labels == ["arr"]:
                    return {"arr": "array"}, []
                if raw_labels == ["range cap"]:
                    return {"range cap": "range_bound"}, []
                return {}, raw_labels

            def fake_llm(*, dimension, raw_entries, **kwargs):
                names = {entry["name"] for entry in raw_entries}
                if dimension == "invariant" and "mono" in names:
                    return {"mono": "monotonicity"}, []
                return {}, []

            with patch("normalize.QwenClient", FakeQwenClient), patch(
                "normalize.normalize_labels_with_embedding",
                side_effect=fake_embedding,
            ), patch(
                "normalize.normalize_labels_with_llm",
                side_effect=fake_llm,
            ):
                normalize_all_problems(
                    raw_dir=raw_dir,
                    normalized_dir=normalized_dir,
                    registry_dir=registry_dir,
                    embedding_threshold=0.85,
                    logger=logger,
                )

            output = json.loads(
                (normalized_dir / "demo.json").read_text(encoding="utf-8")
            )

        self.assertEqual(output["problem_id"], "demo")
        self.assertEqual(output["input_structure"]["type"], "array")
        self.assertEqual(
            output["core_constraints"]["constraints"][0]["name"],
            "range_bound",
        )
        self.assertEqual(output["objective"], {"type": None})
        self.assertEqual(
            output["invariant"]["invariants"][0]["name"],
            "monotonicity",
        )
        self.assertNotIn("status", output["input_structure"])
        self.assertNotIn("all_" "rounds", output["input_structure"])


if __name__ == "__main__":
    unittest.main()
