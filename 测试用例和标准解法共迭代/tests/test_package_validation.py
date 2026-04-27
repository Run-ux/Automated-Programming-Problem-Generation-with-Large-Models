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
from generators import SchemaAwareWrongSolutionGenerator, SchemaMistakeAnalyzer
from models import ExecutionSpec, FailureIssue, GeneratedCodeArtifact, TestCase, WrongSolution
from pipeline import PackageValidationPipeline, _build_revision_context, _update_active_revision_context
from runners import CodeRunner


SUM_SOLUTION = """def solve(input_str: str) -> str:
    nums = [int(x) for x in input_str.split()]
    return str(sum(nums))
"""

BAD_ORACLE = """def solve(input_str: str) -> str:
    nums = [int(x) for x in input_str.split()]
    return str(sum(nums) + 1)
"""

CONST_A_SOLUTION = """def solve(input_str: str) -> str:
    del input_str
    return "A"
"""

CONST_B_SOLUTION = """def solve(input_str: str) -> str:
    del input_str
    return "B"
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

CHECKER_ACCEPTS_A_OR_B = """def check(input_str: str, output_str: str, expected_str: str | None) -> bool:
    del input_str, expected_str
    return output_str.strip() in {"A", "B"}
"""

CHECKER_ACCEPTS_ONLY_A = """def check(input_str: str, output_str: str, expected_str: str | None) -> bool:
    del input_str, expected_str
    return output_str.strip() == "A"
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

SCHEMA_AWARE_WRONG = """def solve(input_str: str) -> str:
    nums = [int(x) for x in input_str.split()]
    if len(nums) == 2 and nums[0] == 0:
        return str(sum(nums))
    return str(nums[0] if nums else 0)
"""


SCHEMA_MISTAKE_POINT = {
    "mistake_id": "ignore_schema_sum_contract",
    "schema_basis": ["objective:sum_all_values"],
    "player_visible_misread": "把输出所有数之和误读为输出第一个数。",
    "wrong_strategy": "解析输入后只使用首个数。",
    "target_failure_bucket": "小规模挑战",
    "expected_counterexample_shape": "至少两个非零数的输入。",
    "triviality_risk": "仍会解析输入并在部分零值样例上给出正确结果。",
}


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


class FakeSchemaClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    def chat_json(self, *, system_prompt, user_prompt, temperature):
        self.prompts.append({"system": system_prompt, "user": user_prompt, "temperature": temperature})
        return self.responses.pop(0)


class SchemaAwareGeneratorTests(unittest.TestCase):
    def test_schema_mistake_analyzer_normalizes_llm_output(self) -> None:
        client = FakeSchemaClient(
            [
                {
                    "mistake_points": [
                        {
                            "mistake_id": "ignore_schema_sum_contract",
                            "schema_basis": "objective:sum_all_values",
                            "player_visible_misread": "把输出所有数之和误读为输出第一个数。",
                            "wrong_strategy": "只取第一个数。",
                            "target_failure_bucket": "小规模挑战",
                            "expected_counterexample_shape": "两个以上数字。",
                            "triviality_risk": "仍需解析输入。",
                        }
                    ]
                }
            ]
        )
        analyzer = SchemaMistakeAnalyzer(client)

        result = analyzer.generate(
            {
                "problem_id": "SUM",
                "statement_markdown": "给定若干整数，输出它们的和。",
                "new_schema": {"objective": {"type": "sum_all_values"}},
            },
            FakeSpecExtractor().generate({}),
        )

        self.assertEqual(result[0]["mistake_id"], "ignore_schema_sum_contract")
        self.assertEqual(result[0]["schema_basis"], ["objective:sum_all_values"])
        self.assertIn("new_schema", client.prompts[0]["user"])

    def test_schema_aware_wrong_solution_generator_binds_mistake_metadata(self) -> None:
        client = FakeSchemaClient(
            [
                {
                    "wrong_solutions": [
                        {
                            "solution_id": "SUM_schema_ignore_contract",
                            "mistake_id": "ignore_schema_sum_contract",
                            "code": SCHEMA_AWARE_WRONG,
                            "bug_type": "schema_objective_misread",
                            "expected_failure": "多个非零数时输出错误。",
                            "schema_signals": ["objective:sum_all_values"],
                        }
                    ]
                }
            ]
        )
        generator = SchemaAwareWrongSolutionGenerator(client)

        result = generator.generate(
            {
                "problem_id": "SUM",
                "statement_markdown": "给定若干整数，输出它们的和。",
                "new_schema": {"objective": {"type": "sum_all_values"}},
            },
            FakeSpecExtractor().generate({}),
            [SCHEMA_MISTAKE_POINT],
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].source, "schema_aware_llm_player")
        self.assertEqual(result[0].metadata["mistake_id"], "ignore_schema_sum_contract")
        self.assertEqual(result[0].metadata["mistake_point"]["wrong_strategy"], "解析输入后只使用首个数。")


class RevisionContextTests(unittest.TestCase):
    def test_build_revision_context_outputs_structured_schema_only(self) -> None:
        small_evidence = {
            "test": {
                "source": "basic",
                "purpose": "基础反例",
                "expect_oracle": True,
                "is_sample": False,
                "is_large": False,
                "metadata": {"bucket": "basic"},
            },
            "test_source": "basic",
            "input": "2\n1 2\n",
            "standard_output": "3\n",
            "oracle_output": "4\n",
            "checker_result": {
                "status": "ok",
                "result": False,
                "error_reason": "",
                "stdout": "",
                "stderr": "",
                "elapsed_ms": 4,
            },
        }
        issues = [
            FailureIssue(
                category="standard_oracle_mismatch",
                severity="blocker",
                title="标准解与 oracle 不一致",
                detail="basic_case 上两者输出不同。",
                evidence=small_evidence,
                fix_hint="回流 StandardSolutionGenerator 与 OracleGenerator，定位反例。",
            ),
            FailureIssue(
                category="wrong_solution_survived",
                severity="high",
                title="错误解存活",
                detail="wrong_1 未被当前测试击中。",
            ),
        ]

        revision_context = _build_revision_context(
            issues,
            {
                "independent_solutions": [
                    {
                        "solution_id": "wrong_1",
                        "bug_type": "boundary_misread",
                        "expected_failure": "边界输入失败。",
                        "reason": "当前测试未能杀掉该候选解。",
                        "passed_tests": ["basic"],
                        "killed_tests": [],
                        "metadata": {"target_failure_bucket": "边界条件"},
                    }
                ]
            },
        )

        self.assertEqual(
            set(revision_context),
            {
                "summary",
                "diagnostics_by_category",
                "role_diagnostics",
                "failed_hard_checks",
                "surviving_wrong_solution_details",
            },
        )
        for old_key in (
            "issues_by_category",
            "tool_feedback",
            "solution_feedback",
            "oracle_feedback",
            "test_feedback",
            "surviving_wrong_solutions",
        ):
            self.assertNotIn(old_key, revision_context)

        diagnostic = revision_context["diagnostics_by_category"]["standard_oracle_mismatch"][0]
        self.assertEqual(diagnostic["category"], "standard_oracle_mismatch")
        self.assertEqual(diagnostic["severity"], "blocker")
        self.assertIn("StandardSolutionGenerator", diagnostic["target_roles"])
        self.assertIn("OracleGenerator", diagnostic["target_roles"])
        self.assertEqual(diagnostic["evidence"]["input"]["content"], "2\n1 2\n")
        self.assertFalse(diagnostic["evidence"]["input"]["truncated"])
        self.assertEqual(diagnostic["diff"]["first_different_token"]["standard"], "3")
        self.assertEqual(diagnostic["diff"]["first_different_token"]["oracle"], "4")
        self.assertEqual(revision_context["failed_hard_checks"], ["standard_oracle_mismatch"])

        survivor = revision_context["surviving_wrong_solution_details"][0]
        self.assertEqual(survivor["solution_id"], "wrong_1")
        self.assertEqual(survivor["bug_type"], "boundary_misread")
        self.assertEqual(survivor["expected_failure"], "边界输入失败。")
        self.assertEqual(survivor["reason"], "当前测试未能杀掉该候选解。")
        self.assertEqual(survivor["passed_tests"], ["basic"])
        self.assertEqual(survivor["killed_tests"], [])
        self.assertEqual(survivor["metadata"], {"target_failure_bucket": "边界条件"})

    def test_revision_context_records_runtime_checker_and_large_evidence(self) -> None:
        large_input = " ".join(str(index) for index in range(1000))
        traceback_text = (
            "Traceback (most recent call last):\n"
            "  File \"runner.py\", line 1, in main\n"
            "  File \"candidate.py\", line 2, in solve\n"
            "ValueError: bad input\n"
        )
        issues = [
            FailureIssue(
                category="standard_solution_failed",
                severity="blocker",
                title="标准解执行失败",
                detail="运行异常。",
                evidence={
                    "test": {
                        "source": "runtime",
                        "purpose": "运行错误",
                        "expect_oracle": True,
                        "is_sample": False,
                        "is_large": False,
                        "metadata": {},
                    },
                    "test_source": "runtime",
                    "input": "bad\n",
                    "standard_result": {
                        "status": "runtime_error",
                        "result": None,
                        "error_reason": traceback_text,
                        "stdout": "",
                        "stderr": traceback_text,
                        "elapsed_ms": 7,
                    },
                },
            ),
            FailureIssue(
                category="checker_rejects_standard_output",
                severity="blocker",
                title="checker 拒绝标准解输出",
                detail="标准解输出未被 checker 接受。",
                evidence={
                    "test": {
                        "source": "large",
                        "purpose": "大输入",
                        "expect_oracle": False,
                        "is_sample": False,
                        "is_large": True,
                        "metadata": {"n": 1000},
                    },
                    "test_source": "large",
                    "input": large_input,
                    "standard_output": large_input,
                    "checker_result": {
                        "status": "ok",
                        "result": False,
                        "error_reason": "checker returned false",
                        "stdout": "",
                        "stderr": "",
                        "elapsed_ms": 3,
                    },
                },
            ),
        ]

        revision_context = _build_revision_context(issues, {"independent_solutions": []})

        runtime_diag = revision_context["diagnostics_by_category"]["standard_solution_failed"][0]
        self.assertEqual(runtime_diag["evidence"]["standard_result"]["traceback"]["exception_type"], "ValueError")
        self.assertIn("candidate.py", runtime_diag["evidence"]["standard_result"]["traceback"]["last_frames"][-1])

        large_diag = revision_context["diagnostics_by_category"]["checker_rejects_standard_output"][0]
        self.assertTrue(large_diag["evidence"]["input"]["truncated"])
        self.assertEqual(large_diag["evidence"]["input"]["kept_strategy"], "head_tail")
        self.assertGreater(large_diag["evidence"]["input"]["original_length"], 1800)
        self.assertIn("ToolGenerator", large_diag["target_roles"])

    def test_revision_context_aggregates_duplicates_and_limits_role_diagnostics(self) -> None:
        issues = [
            FailureIssue(
                category="validator_rejects_generated_case",
                severity="high",
                title="validator 拒绝测试",
                detail=f"case_{index} 未通过输入合法性检查。",
                evidence={
                    "test": {
                        "source": f"case_{index}",
                        "purpose": "重复失败",
                        "expect_oracle": True,
                        "is_sample": False,
                        "is_large": False,
                        "metadata": {},
                    },
                    "test_source": f"case_{index}",
                    "input": f"{index}\n",
                },
            )
            for index in range(5)
        ]

        revision_context = _build_revision_context(issues, {"independent_solutions": []})

        summary = revision_context["summary"][0]
        self.assertEqual(summary["category"], "validator_rejects_generated_case")
        self.assertEqual(summary["count"], 5)
        self.assertEqual(summary["representative_sources"], ["case_0", "case_1", "case_2"])
        self.assertEqual(len(revision_context["diagnostics_by_category"]["validator_rejects_generated_case"]), 5)
        self.assertEqual(len(revision_context["role_diagnostics"]["ToolGenerator"]), 3)

    def test_active_revision_context_removes_resolved_issues(self) -> None:
        first_revision = _build_revision_context(
            [
                FailureIssue(
                    category="standard_oracle_mismatch",
                    severity="blocker",
                    title="标准解与 oracle 不一致",
                    detail="basic 上输出不同。",
                    evidence={"test": {"source": "basic"}},
                )
            ],
            {"independent_solutions": []},
        )
        active_context, first_stats = _update_active_revision_context({}, first_revision)

        self.assertEqual(first_stats["active_issue_count"], 1)
        self.assertEqual(first_stats["new_issue_count"], 1)

        empty_revision = _build_revision_context([], {"independent_solutions": []})
        active_context, second_stats = _update_active_revision_context(active_context, empty_revision)

        self.assertEqual(second_stats["active_issue_count"], 0)
        self.assertEqual(second_stats["resolved_issue_count"], 1)
        self.assertEqual(active_context["diagnostics_by_category"], {})

    def test_active_revision_context_carries_stable_fingerprint_with_latest_evidence(self) -> None:
        first_revision = _build_revision_context(
            [
                FailureIssue(
                    category="standard_oracle_mismatch",
                    severity="blocker",
                    title="标准解与 oracle 不一致",
                    detail="旧诊断。",
                    evidence={"test": {"source": "basic"}, "standard_output": "1", "oracle_output": "2"},
                )
            ],
            {"independent_solutions": []},
        )
        first_active, _ = _update_active_revision_context({}, first_revision)
        first_diagnostic = first_active["diagnostics_by_category"]["standard_oracle_mismatch"][0]

        second_revision = _build_revision_context(
            [
                FailureIssue(
                    category="standard_oracle_mismatch",
                    severity="blocker",
                    title="标准解与 oracle 不一致",
                    detail="新诊断。",
                    evidence={"test": {"source": "basic"}, "standard_output": "3", "oracle_output": "4"},
                )
            ],
            {"independent_solutions": []},
        )
        second_active, second_stats = _update_active_revision_context(first_active, second_revision)
        second_diagnostic = second_active["diagnostics_by_category"]["standard_oracle_mismatch"][0]

        self.assertEqual(first_diagnostic["issue_fingerprint"], second_diagnostic["issue_fingerprint"])
        self.assertEqual(second_stats["carried_issue_count"], 1)
        self.assertEqual(second_diagnostic["detail"], "新诊断。")


class FakeSpecExtractor:
    def __init__(self, judge_type: str = "exact"):
        self.judge_type = judge_type

    def generate(self, context, revision_context=None):
        del context, revision_context
        return ExecutionSpec(
            problem_id="SUM",
            input_contract={"format": "若干整数"},
            output_contract={"type": "sum"},
            judge_type=self.judge_type,
            oracle_limits={"max_tokens": 10},
            test_buckets=[{"name": "basic"}],
        )


class FakeStandardGenerator:
    def __init__(self, code: str = SUM_SOLUTION):
        self.code = code

    def generate(self, context, spec, revision_context=None):
        del context, spec, revision_context
        return GeneratedCodeArtifact(name="standard_solution", role="standard_solution", code=self.code)


class FakeOracleGenerator:
    def __init__(self, code: str = SUM_SOLUTION):
        self.code = code

    def generate(self, context, spec, revision_context=None):
        del context, spec, revision_context
        return GeneratedCodeArtifact(name="oracle_solution", role="oracle_solution", code=self.code)


class FakeToolGenerator:
    def __init__(self, checker_code: str = CHECKER):
        self.checker_code = checker_code

    def generate(self, context, spec, revision_context=None):
        del context, spec, revision_context
        return {
            "validator": GeneratedCodeArtifact(name="validator", role="validator", code=VALIDATOR),
            "checker": GeneratedCodeArtifact(name="checker", role="checker", code=self.checker_code),
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


class FakeSchemaMistakeAnalyzer:
    def generate(self, context, spec, revision_context=None):
        del context, spec, revision_context
        return [dict(SCHEMA_MISTAKE_POINT)]


class FakeSchemaWrongSolutionGenerator:
    def generate(self, context, spec, mistake_points, revision_context=None):
        del context, spec, revision_context
        return [
            WrongSolution(
                solution_id="SUM_schema_ignore_contract",
                code=SCHEMA_AWARE_WRONG,
                source="schema_aware_llm_player",
                bug_type="schema_objective_misread",
                expected_failure="多个非零数时输出错误。",
                metadata={"mistake_id": mistake_points[0]["mistake_id"], "mistake_point": dict(mistake_points[0])},
            )
        ]


class CountingSpecExtractor(FakeSpecExtractor):
    def __init__(self, judge_type: str = "exact"):
        super().__init__(judge_type)
        self.calls = 0

    def generate(self, context, revision_context=None):
        self.calls += 1
        return super().generate(context, revision_context)


class SequenceStandardGenerator:
    def __init__(self, codes: list[str]):
        self.codes = codes
        self.calls = 0
        self.revision_contexts: list[dict] = []

    def generate(self, context, spec, revision_context=None):
        del context, spec
        self.revision_contexts.append(revision_context or {})
        index = min(self.calls, len(self.codes) - 1)
        self.calls += 1
        return GeneratedCodeArtifact(name="standard_solution", role="standard_solution", code=self.codes[index])


class CountingOracleGenerator(FakeOracleGenerator):
    def __init__(self, code: str = SUM_SOLUTION):
        super().__init__(code)
        self.calls = 0

    def generate(self, context, spec, revision_context=None):
        self.calls += 1
        return super().generate(context, spec, revision_context)


class CountingToolGenerator(FakeToolGenerator):
    def __init__(self, checker_code: str = CHECKER):
        super().__init__(checker_code)
        self.calls = 0

    def generate(self, context, spec, revision_context=None):
        self.calls += 1
        return super().generate(context, spec, revision_context)


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
                schema_mistake_analyzer=FakeSchemaMistakeAnalyzer(),
                schema_wrong_solution_generator=FakeSchemaWrongSolutionGenerator(),
                progress_writer=lambda message: None,
                kill_rate_threshold=0.5,
            )

            result = pipeline.run(artifact_path=artifact_path, rounds=1)

            self.assertEqual(result["summary"]["final_status"], "pass")
            self.assertTrue(Path(result["run_dir"], "final", "execution_spec.json").exists())
            self.assertTrue(Path(result["run_dir"], "round1", "execution_report.json").exists())
            mistake_path = Path(result["run_dir"], "round1", "schema_mistake_points.json")
            self.assertTrue(mistake_path.exists())
            mistakes = json.loads(mistake_path.read_text(encoding="utf-8"))
            self.assertEqual(mistakes[0]["mistake_id"], "ignore_schema_sum_contract")

            report = json.loads(Path(result["run_dir"], "round1", "execution_report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["wrong_solution_stats"]["candidate_count"], 2)
            self.assertTrue(report["base_consistency"]["passed"])
            self.assertTrue(report["wrong_solution_stats"]["valid"])
            wrong_dirs = {item.name for item in Path(result["run_dir"], "round1", "wrong_solutions").iterdir()}
            self.assertIn("SUM_schema_ignore_contract", wrong_dirs)
            self.assertNotIn("SUM_empty_output", wrong_dirs)

    def test_incremental_round_regenerates_only_active_roles(self) -> None:
        standard_generator = SequenceStandardGenerator([SUM_SOLUTION])
        oracle_generator = CountingOracleGenerator()
        tool_generator = CountingToolGenerator()
        pipeline = PackageValidationPipeline(
            client=None,
            spec_extractor=CountingSpecExtractor(),
            standard_generator=standard_generator,
            oracle_generator=oracle_generator,
            tool_generator=tool_generator,
            weak_player_generator=FakeWeakPlayerGenerator(),
            schema_mistake_analyzer=FakeSchemaMistakeAnalyzer(),
            schema_wrong_solution_generator=FakeSchemaWrongSolutionGenerator(),
            progress_writer=lambda message: None,
            kill_rate_threshold=0.5,
        )
        spec = FakeSpecExtractor().generate({})
        current_package = {
            "context": {"problem_id": "SUM"},
            "execution_spec": spec,
            "standard_solution": GeneratedCodeArtifact(name="standard_solution", role="standard_solution", code=BAD_ORACLE),
            "oracle_solution": GeneratedCodeArtifact(name="oracle_solution", role="oracle_solution", code=SUM_SOLUTION),
            "validator": GeneratedCodeArtifact(name="validator", role="validator", code=VALIDATOR),
            "checker": GeneratedCodeArtifact(name="checker", role="checker", code=CHECKER),
            "test_generator": GeneratedCodeArtifact(name="test_generator", role="test_generator", code=TEST_GENERATOR),
            "schema_mistake_points": [dict(SCHEMA_MISTAKE_POINT)],
            "wrong_solutions": [],
        }
        diagnostic = {
            "category": "standard_solution_failed",
            "severity": "blocker",
            "title": "标准解运行失败",
            "detail": "需要修复标准解。",
            "target_roles": ["StandardSolutionGenerator"],
            "evidence": {"test": {"source": "basic"}},
            "issue_fingerprint": "standard-only",
        }
        revision_context = {
            "summary": [{"category": "standard_solution_failed", "count": 1, "severity": "blocker"}],
            "diagnostics_by_category": {"standard_solution_failed": [diagnostic]},
            "role_diagnostics": {"StandardSolutionGenerator": [diagnostic]},
            "failed_hard_checks": ["standard_solution_failed"],
            "surviving_wrong_solution_details": [],
            "revision_mode": "incremental_patch",
        }

        package = pipeline._generate_incremental_round_package({"problem_id": "SUM"}, current_package, revision_context)

        self.assertEqual(package["standard_solution"].code, SUM_SOLUTION)
        self.assertEqual(package["oracle_solution"].code, SUM_SOLUTION)
        self.assertEqual(package["validator"].code, VALIDATOR)
        self.assertEqual(standard_generator.calls, 1)
        self.assertEqual(oracle_generator.calls, 0)
        self.assertEqual(tool_generator.calls, 0)
        self.assertIn("active_revision_context", standard_generator.revision_contexts[0])
        self.assertIn("current_artifact", standard_generator.revision_contexts[0])

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
                schema_mistake_analyzer=FakeSchemaMistakeAnalyzer(),
                schema_wrong_solution_generator=FakeSchemaWrongSolutionGenerator(),
                progress_writer=lambda message: None,
                kill_rate_threshold=0.5,
            )

            result = pipeline.run(artifact_path=artifact_path, rounds=1)
            report_paths = list(Path(result["run_dir"]).glob("round1/execution_report.json"))
            report = json.loads(report_paths[0].read_text(encoding="utf-8"))
            categories = {item["category"] for item in report["issues"]}

            self.assertIn("standard_oracle_mismatch", categories)
            self.assertIn("kill_rate_skipped_due_to_invalid_baseline", categories)
            self.assertFalse(report["wrong_solution_stats"]["valid"])
            self.assertEqual(report["wrong_solution_stats"]["skip_reason"], "baseline_validation_failed")
            mismatch_issue = next(item for item in report["issues"] if item["category"] == "standard_oracle_mismatch")
            self.assertIn("checker_result", mismatch_issue["evidence"])
            self.assertEqual(result["summary"]["final_status"], "not_deliverable")

    def test_checker_problem_allows_different_valid_standard_and_oracle_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            artifact_path = Path(tempdir) / "artifact.json"
            artifact_path.write_text(
                json.dumps({"problem_id": "SUM", "generated_problem": {"title": "求和"}}, ensure_ascii=False),
                encoding="utf-8",
            )
            pipeline = PackageValidationPipeline(
                client=None,
                output_dir=Path(tempdir) / "out",
                spec_extractor=FakeSpecExtractor(judge_type="checker"),
                standard_generator=FakeStandardGenerator(CONST_A_SOLUTION),
                oracle_generator=FakeOracleGenerator(CONST_B_SOLUTION),
                tool_generator=FakeToolGenerator(CHECKER_ACCEPTS_A_OR_B),
                weak_player_generator=FakeWeakPlayerGenerator(),
                schema_mistake_analyzer=FakeSchemaMistakeAnalyzer(),
                schema_wrong_solution_generator=FakeSchemaWrongSolutionGenerator(),
                progress_writer=lambda message: None,
                kill_rate_threshold=0.5,
            )

            result = pipeline.run(artifact_path=artifact_path, rounds=1)
            report = json.loads(Path(result["run_dir"], "round1", "execution_report.json").read_text(encoding="utf-8"))
            categories = {item["category"] for item in report["issues"]}

            self.assertNotIn("standard_oracle_mismatch", categories)
            self.assertTrue(report["base_consistency"]["passed"])
            self.assertTrue(report["wrong_solution_stats"]["valid"])

    def test_checker_rejecting_standard_output_skips_wrong_solution_curation(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            artifact_path = Path(tempdir) / "artifact.json"
            artifact_path.write_text(
                json.dumps({"problem_id": "SUM", "generated_problem": {"title": "求和"}}, ensure_ascii=False),
                encoding="utf-8",
            )
            pipeline = PackageValidationPipeline(
                client=None,
                output_dir=Path(tempdir) / "out",
                spec_extractor=FakeSpecExtractor(judge_type="checker"),
                standard_generator=FakeStandardGenerator(CONST_A_SOLUTION),
                oracle_generator=FakeOracleGenerator(CONST_B_SOLUTION),
                tool_generator=FakeToolGenerator(CHECKER),
                weak_player_generator=FakeWeakPlayerGenerator(),
                schema_mistake_analyzer=FakeSchemaMistakeAnalyzer(),
                schema_wrong_solution_generator=FakeSchemaWrongSolutionGenerator(),
                progress_writer=lambda message: None,
                kill_rate_threshold=0.5,
            )

            result = pipeline.run(artifact_path=artifact_path, rounds=1)
            report = json.loads(Path(result["run_dir"], "round1", "execution_report.json").read_text(encoding="utf-8"))
            categories = {item["category"] for item in report["issues"]}

            self.assertIn("checker_rejects_standard_output", categories)
            self.assertIn("kill_rate_skipped_due_to_invalid_baseline", categories)
            self.assertNotIn("standard_oracle_mismatch", categories)
            self.assertFalse(report["base_consistency"]["passed"])
            self.assertFalse(report["wrong_solution_stats"]["valid"])
            self.assertEqual(report["wrong_solution_stats"]["kill_rate"], None)
            self.assertEqual(report["wrong_solution_stats"]["skip_reason"], "baseline_validation_failed")

    def test_checker_rejecting_oracle_output_reports_oracle_issue(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            artifact_path = Path(tempdir) / "artifact.json"
            artifact_path.write_text(
                json.dumps({"problem_id": "SUM", "generated_problem": {"title": "求和"}}, ensure_ascii=False),
                encoding="utf-8",
            )
            pipeline = PackageValidationPipeline(
                client=None,
                output_dir=Path(tempdir) / "out",
                spec_extractor=FakeSpecExtractor(judge_type="checker"),
                standard_generator=FakeStandardGenerator(CONST_A_SOLUTION),
                oracle_generator=FakeOracleGenerator(CONST_B_SOLUTION),
                tool_generator=FakeToolGenerator(CHECKER_ACCEPTS_ONLY_A),
                weak_player_generator=FakeWeakPlayerGenerator(),
                schema_mistake_analyzer=FakeSchemaMistakeAnalyzer(),
                schema_wrong_solution_generator=FakeSchemaWrongSolutionGenerator(),
                progress_writer=lambda message: None,
                kill_rate_threshold=0.5,
            )

            result = pipeline.run(artifact_path=artifact_path, rounds=1)
            report = json.loads(Path(result["run_dir"], "round1", "execution_report.json").read_text(encoding="utf-8"))
            categories = {item["category"] for item in report["issues"]}

            self.assertIn("oracle_output_rejected_by_checker", categories)
            self.assertIn("kill_rate_skipped_due_to_invalid_baseline", categories)
            self.assertFalse(report["wrong_solution_stats"]["valid"])
            oracle_issue = next(item for item in report["issues"] if item["category"] == "oracle_output_rejected_by_checker")
            self.assertIn("evidence", oracle_issue)
            self.assertIn("checker 题允许多解", oracle_issue["detail"])


if __name__ == "__main__":
    unittest.main()
