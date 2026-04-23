from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_DIR = ROOT / "题包生成验证"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from curation import WrongSolutionCurator
from models import ExecutionSpec, GeneratedCodeArtifact, TestCase, WrongSolution
from pipeline import PackageValidationPipeline
from runners import CodeRunner


SUM_SOLUTION = """def solve(input_str: str) -> str:
    nums = [int(x) for x in input_str.split()]
    return str(sum(nums))
"""

BAD_ORACLE = """def solve(input_str: str) -> str:
    nums = [int(x) for x in input_str.split()]
    return str(sum(nums) + 1)
"""

VALIDATOR = """def validate(input_str: str) -> bool:
    try:
        [int(x) for x in input_str.split()]
        return bool(input_str.strip())
    except Exception:
        return False
"""

CHECKER = """def check(input_str: str, output_str: str, expected_str: str | None) -> bool:
    del input_str
    if expected_str is None:
        return bool(output_str.strip())
    return output_str.strip() == expected_str.strip()
"""

TEST_GENERATOR = """def generate_tests() -> list[dict]:
    return [
        {"input": "0 0", "source": "zero", "purpose": "零值边界"},
        {"input": "1 2", "source": "basic", "purpose": "基础求和"}
    ]
"""

FIRST_TOKEN_WRONG = """def solve(input_str: str) -> str:
    return input_str.split()[0]
"""


class CodeRunnerTests(unittest.TestCase):
    def test_run_solve_success(self) -> None:
        runner = CodeRunner(timeout_s=1)
        result = runner.run_solve(
            artifact_name="sum",
            code=SUM_SOLUTION,
            input_data="1 2 3",
            test_source="unit",
        )

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.result, "6")

    def test_run_solve_reports_invalid_interface(self) -> None:
        runner = CodeRunner(timeout_s=1)
        result = runner.run_solve(
            artifact_name="bad",
            code="def answer(x):\n    return x\n",
            input_data="1",
            test_source="unit",
        )

        self.assertEqual(result.status, "invalid_interface")

    def test_run_solve_reports_compile_error(self) -> None:
        runner = CodeRunner(timeout_s=1)
        result = runner.run_solve(
            artifact_name="syntax",
            code="def solve(:\n    return ''\n",
            input_data="1",
            test_source="unit",
        )

        self.assertEqual(result.status, "compile_error")


class WrongSolutionCuratorTests(unittest.TestCase):
    def test_curator_splits_valuable_and_possibly_correct_solutions(self) -> None:
        runner = CodeRunner(timeout_s=1)
        tests = [
            TestCase(input="0 0", source="zero", purpose="零值"),
            TestCase(input="1 2", source="basic", purpose="基础"),
        ]
        expected_outputs = {"zero": "0", "basic": "3"}
        curator = WrongSolutionCurator(runner=runner, kill_rate_threshold=0.5)

        result = curator.curate(
            candidates=[
                WrongSolution(
                    solution_id="first_token",
                    code=FIRST_TOKEN_WRONG,
                    source="weak_llm_player",
                    bug_type="format_misread",
                    expected_failure="误读输入。",
                ),
                WrongSolution(
                    solution_id="sum_solution",
                    code=SUM_SOLUTION,
                    source="weak_llm_player",
                    bug_type="unexpected_correct",
                    expected_failure="无",
                ),
            ],
            tests=tests,
            checker_code=CHECKER,
            expected_outputs=expected_outputs,
        )

        self.assertEqual(result["stats"]["valuable_count"], 1)
        self.assertEqual(result["stats"]["independent_count"], 1)
        self.assertTrue(result["stats"]["passed_threshold"])


class FakeSpecExtractor:
    def generate(self, context, revision_context=None):
        del context, revision_context
        return ExecutionSpec(
            problem_id="SUM",
            input_contract={"format": "若干整数"},
            output_contract={"type": "sum"},
            judge_type="exact",
            oracle_limits={"max_tokens": 10},
            test_buckets=[{"name": "basic"}],
        )


class FakeStandardGenerator:
    def generate(self, context, spec, revision_context=None):
        del context, spec, revision_context
        return GeneratedCodeArtifact(name="standard_solution", role="standard_solution", code=SUM_SOLUTION)


class FakeOracleGenerator:
    def __init__(self, code: str = SUM_SOLUTION):
        self.code = code

    def generate(self, context, spec, revision_context=None):
        del context, spec, revision_context
        return GeneratedCodeArtifact(name="oracle_solution", role="oracle_solution", code=self.code)


class FakeToolGenerator:
    def generate(self, context, spec, revision_context=None):
        del context, spec, revision_context
        return {
            "validator": GeneratedCodeArtifact(name="validator", role="validator", code=VALIDATOR),
            "checker": GeneratedCodeArtifact(name="checker", role="checker", code=CHECKER),
            "test_generator": GeneratedCodeArtifact(name="test_generator", role="test_generator", code=TEST_GENERATOR),
        }


class FakeWeakPlayerGenerator:
    def generate(self, statement_only_context, revision_context=None):
        del statement_only_context, revision_context
        return [
            WrongSolution(
                solution_id="first_token",
                code=FIRST_TOKEN_WRONG,
                source="weak_llm_player",
                bug_type="format_misread",
                expected_failure="只能过部分用例。",
            )
        ]


class PipelineTests(unittest.TestCase):
    def test_pipeline_can_produce_pass_package(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            artifact_path = Path(tempdir) / "artifact.json"
            artifact_path.write_text(
                json.dumps(
                    {
                        "problem_id": "SUM",
                        "generated_problem": {"title": "求和", "samples": []},
                        "new_schema_snapshot": {"problem_id": "SUM"},
                        "algorithmic_delta_claim": {"new_solver_core": "求和"},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            output_dir = Path(tempdir) / "out"
            pipeline = PackageValidationPipeline(
                client=None,
                output_dir=output_dir,
                spec_extractor=FakeSpecExtractor(),
                standard_generator=FakeStandardGenerator(),
                oracle_generator=FakeOracleGenerator(),
                tool_generator=FakeToolGenerator(),
                weak_player_generator=FakeWeakPlayerGenerator(),
                progress_writer=lambda message: None,
                kill_rate_threshold=0.5,
            )

            result = pipeline.run(artifact_path=artifact_path, rounds=1)

            self.assertEqual(result["summary"]["final_status"], "pass")
            self.assertTrue(Path(result["run_dir"], "final", "execution_spec.json").exists())
            self.assertTrue(Path(result["run_dir"], "round1", "execution_report.json").exists())

    def test_pipeline_reports_standard_oracle_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            artifact_path = Path(tempdir) / "artifact.json"
            artifact_path.write_text(
                json.dumps({"problem_id": "SUM", "generated_problem": {"title": "求和"}}, ensure_ascii=False),
                encoding="utf-8",
            )
            pipeline = PackageValidationPipeline(
                client=None,
                output_dir=Path(tempdir) / "out",
                spec_extractor=FakeSpecExtractor(),
                standard_generator=FakeStandardGenerator(),
                oracle_generator=FakeOracleGenerator(BAD_ORACLE),
                tool_generator=FakeToolGenerator(),
                weak_player_generator=FakeWeakPlayerGenerator(),
                progress_writer=lambda message: None,
                kill_rate_threshold=0.5,
            )

            result = pipeline.run(artifact_path=artifact_path, rounds=1)
            report_paths = list(Path(result["run_dir"]).glob("round1/execution_report.json"))
            report = json.loads(report_paths[0].read_text(encoding="utf-8"))
            categories = {item["category"] for item in report["issues"]}

            self.assertIn("standard_oracle_mismatch", categories)
            self.assertEqual(result["summary"]["final_status"], "not_deliverable")


if __name__ == "__main__":
    unittest.main()

