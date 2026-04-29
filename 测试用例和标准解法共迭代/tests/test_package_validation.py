from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from artifact_context import build_problem_context, normalize_small_challenge_tests, normalize_tests
from generators import (
    FixedCategoryWrongSolutionGenerator,
    SchemaMistakeAnalyzer,
    StrategyWrongSolutionGenerator,
)
from models import GeneratedCodeArtifact, TestCase, WrongSolution
from pipeline import PackageValidationPipeline, _build_context
from runners import CodeRunner


VALIDATOR_CODE = """def validate(input_str: str) -> bool:
    return bool(input_str.strip())
"""

STANDARD_SUM_CODE = """def solve(input_str: str) -> str:
    nums = list(map(int, input_str.split()))
    return str(sum(nums))
"""

BRUTE_FORCE_OFF_BY_ONE_CODE = """def solve(input_str: str) -> str:
    nums = list(map(int, input_str.split()))
    return str(sum(nums) + 1)
"""

CHECKER_EXACT_CODE = """def check(input_str: str, output_str: str, expected_str: str | None) -> bool:
    if expected_str is None:
        return bool(output_str.strip())
    return output_str.strip() == expected_str.strip()
"""

RANDOM_GENERATOR_CODE = """def generate_test_input() -> str:
    return "1 2"

def validate_test_input(input_string: str) -> bool:
    return input_string.strip() == "1 2"
"""

ADVERSARIAL_GENERATOR_CODE = """def generate_test_input() -> str:
    return "100 200"

def validate_test_input(input_string: str) -> bool:
    return input_string.strip() == "100 200"
"""

WRONG_SOLUTION_CODE = """def solve(input_str: str) -> str:
    return "0"
"""


def make_context() -> dict[str, Any]:
    return {
        "problem_id": "SUM",
        "generated_problem": {
            "title": "SUM",
            "description": "给定若干整数，输出它们的和。",
            "input_format": "一行若干整数。",
            "output_format": "输出一个整数。",
            "constraints": ["整数个数至少为 1"],
            "samples": [{"input": "3 4", "output": "7", "explanation": "基础样例"}],
            "notes": "",
        },
        "new_schema_snapshot": {
            "input_structure": {"values": "整数序列"},
            "core_constraints": {"count": "至少一个整数"},
            "objective": {"goal": "输出总和"},
        },
    }


def make_package(*, wrong_solutions: list[WrongSolution] | None = None) -> dict[str, Any]:
    context = make_context()
    return {
        "context": context,
        "problem_context": build_problem_context(context),
        "standard_solution": GeneratedCodeArtifact(
            name="standard_solution",
            role="standard_solution",
            code=STANDARD_SUM_CODE,
        ),
        "bruteforce_solution": GeneratedCodeArtifact(
            name="bruteforce_solution",
            role="bruteforce_solution",
            code=BRUTE_FORCE_OFF_BY_ONE_CODE,
        ),
        "validator": GeneratedCodeArtifact(name="validator", role="validator", code=VALIDATOR_CODE),
        "checker": GeneratedCodeArtifact(name="checker", role="checker", code=CHECKER_EXACT_CODE),
        "random_test_generator": GeneratedCodeArtifact(
            name="random_test_generator",
            role="test_input_generator",
            code=RANDOM_GENERATOR_CODE,
        ),
        "adversarial_test_generator": GeneratedCodeArtifact(
            name="adversarial_test_generator",
            role="test_input_generator",
            code=ADVERSARIAL_GENERATOR_CODE,
        ),
        "small_challenge_tests": [
            {
                "input": "5 6",
                "source": "small_challenge_1",
                "purpose": "小规模暴力校验",
                "expect_bruteforce": True,
                "is_large": False,
                "metadata": {"kind": "small"},
            }
        ],
        "schema_mistake_points": [],
        "wrong_solutions": wrong_solutions or [],
    }


class TextClient:
    def __init__(self, text: str = WRONG_SOLUTION_CODE):
        self.text = text
        self.calls: list[dict[str, Any]] = []

    def chat_text(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        return self.text


class JsonClient:
    def __init__(self, payload: dict[str, Any]):
        self.payload = payload
        self.calls: list[dict[str, Any]] = []

    def chat_json(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return self.payload


class PackageValidationTests(unittest.TestCase):
    def test_problem_context_accepts_schema_snapshot_and_defaults_invariant(self) -> None:
        problem = build_problem_context(make_context())

        self.assertEqual(problem.problem_id, "SUM")
        self.assertEqual(problem.generated_problem["output_format"], "输出一个整数。")
        self.assertEqual(problem.schema_snapshot["input_structure"], {"values": "整数序列"})
        self.assertEqual(problem.schema_snapshot["invariant"], {})
        self.assertEqual(problem.sample_tests[0]["input"], "3 4")

    def test_normalize_tests_injects_samples_and_uses_bruteforce_flag(self) -> None:
        problem = build_problem_context(make_context())
        tests = normalize_tests(
            [
                {
                    "input": "1 2",
                    "source": "random",
                    "purpose": "随机",
                    "expect_bruteforce": True,
                    "is_large": False,
                },
                {
                    "input": "100 200",
                    "source": "legacy_large",
                    "purpose": "旧字段兼容",
                    "expect_oracle": False,
                    "is_large": True,
                },
            ],
            problem,
        )

        self.assertEqual([item.source for item in tests], ["sample_1", "random", "legacy_large"])
        self.assertTrue(tests[0].is_sample)
        self.assertTrue(tests[1].expect_bruteforce)
        self.assertFalse(tests[2].expect_bruteforce)

    def test_small_challenge_normalization_accepts_strings_and_dicts(self) -> None:
        tests = normalize_small_challenge_tests(
            [
                "1 2",
                {
                    "input": "3 4",
                    "source": "manual_small",
                    "purpose": "手写小规模挑战",
                    "expect_oracle": False,
                    "is_large": False,
                },
            ]
        )

        self.assertEqual(len(tests), 2)
        self.assertEqual(tests[0]["expect_bruteforce"], True)
        self.assertEqual(tests[1]["expect_bruteforce"], False)

    def test_fixed_category_wrong_solution_generator_outputs_five_candidates(self) -> None:
        client = TextClient()
        generator = FixedCategoryWrongSolutionGenerator(client)

        wrong_solutions = generator.generate(make_context())

        self.assertEqual(len(wrong_solutions), 5)
        self.assertEqual(len(client.calls), 5)
        self.assertTrue(all(item.metadata["source_kind"] == "fixed_category" for item in wrong_solutions))
        self.assertTrue(all(item.metadata["strategy_category"] for item in wrong_solutions))

    def test_free_strategy_analyzer_and_generator_preserve_returned_count(self) -> None:
        payload = {
            "mistake_points": [
                {
                    "strategy_id": "ignore_negative",
                    "category": "目标误读",
                    "wrong_strategy": "只累加正数。",
                    "failure_reason": "负数会被漏算。",
                },
                {
                    "strategy_id": "overflow",
                    "category": "规模误判",
                    "wrong_strategy": "使用 32 位整数。",
                    "failure_reason": "大数溢出。",
                },
            ]
        }
        analyzer = SchemaMistakeAnalyzer(JsonClient(payload))
        mistakes = analyzer.generate(make_context())
        wrong_generator = StrategyWrongSolutionGenerator(TextClient())
        wrong_solutions = wrong_generator.generate(make_context(), mistakes)

        self.assertEqual(len(mistakes), 2)
        self.assertEqual(len(wrong_solutions), 2)
        self.assertEqual(wrong_solutions[0].metadata["source_kind"], "free_strategy")
        self.assertEqual(wrong_solutions[0].metadata["strategy"]["strategy_id"], "ignore_negative")

    def test_build_context_does_not_forward_algorithmic_delta_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_path = Path(temp_dir) / "artifact.json"
            artifact = make_context()
            artifact["algorithmic_delta_claim"] = {"new_solver_core": "不应进入后续上下文"}
            artifact_path.write_text(json.dumps(artifact, ensure_ascii=False), encoding="utf-8")

            context = _build_context(
                artifact=json.loads(artifact_path.read_text(encoding="utf-8")),
                markdown="",
                artifact_path=artifact_path,
                markdown_path=None,
            )

        self.assertIn("new_schema_snapshot", context)
        self.assertNotIn("algorithmic_delta_claim", context)
        self.assertNotIn("difference_plan", context)

    def test_runner_uses_single_input_generator_interface(self) -> None:
        runner = CodeRunner(timeout_s=1)

        generated = runner.run_generate_test_input(
            artifact_name="random_test_generator",
            code=RANDOM_GENERATOR_CODE,
        )
        validated = runner.run_validate_test_input(
            artifact_name="random_test_generator",
            code=RANDOM_GENERATOR_CODE,
            input_data=str(generated.result),
        )

        self.assertEqual(generated.status, "ok")
        self.assertEqual(generated.result, "1 2")
        self.assertEqual(validated.status, "ok")
        self.assertTrue(validated.result)

    def test_round_package_writes_new_artifact_layout(self) -> None:
        wrong = WrongSolution(
            solution_id="fixed_wrong_1",
            code=WRONG_SOLUTION_CODE,
            source="fixed_category_llm_player",
            bug_type="目标/输出义务误读",
            expected_failure="固定错误策略类别",
            metadata={"source_kind": "fixed_category", "strategy_category": "目标/输出义务误读"},
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            pipeline = PackageValidationPipeline(
                client=None,
                output_dir=Path(temp_dir),
                progress_writer=lambda _message: None,
            )
            round_dir = Path(temp_dir) / "round1"
            pipeline._write_round_package(round_dir, make_package(wrong_solutions=[wrong]))

            self.assertTrue((round_dir / "problem_context.json").exists())
            self.assertTrue((round_dir / "bruteforce_solution.py").exists())
            self.assertTrue((round_dir / "test_inputs" / "random_generator.py").exists())
            self.assertTrue((round_dir / "test_inputs" / "adversarial_generator.py").exists())
            self.assertTrue((round_dir / "test_inputs" / "small_challenge_inputs.json").exists())
            self.assertTrue((round_dir / "wrong_solutions" / "fixed_wrong_1" / "metadata.json").exists())
            self.assertFalse((round_dir / "execution_spec.json").exists())
            self.assertFalse((round_dir / "oracle_solution.py").exists())

    def test_validation_reports_standard_bruteforce_diff(self) -> None:
        pipeline = PackageValidationPipeline(
            client=None,
            runner=CodeRunner(timeout_s=1),
            progress_writer=lambda _message: None,
        )

        report = pipeline._validate_package(make_package(), build_revision_advice=False)
        categories = [item["category"] for item in report.issues]
        diagnostic = report.revision_context["diagnostics_by_category"]["standard_bruteforce_mismatch"][0]

        self.assertIn("standard_bruteforce_mismatch", categories)
        self.assertIn("checker_rejects_standard_output", categories)
        diff_token = diagnostic["diff"]["first_different_token"]
        self.assertIn("bruteforce", diff_token)
        self.assertNotEqual(diff_token["standard"], diff_token["bruteforce"])
        self.assertEqual(report.base_consistency["bruteforce_checked_count"], 0)


if __name__ == "__main__":
    unittest.main()
