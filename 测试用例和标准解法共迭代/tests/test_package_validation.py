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
from generators import SchemaAwareWrongSolutionGenerator, SchemaMistakeAnalyzer, StandardSolutionGenerator, ToolGenerator
from models import ExecutionSpec, FailureIssue, GeneratedCodeArtifact, TestCase, WrongSolution
from pipeline import PackageValidationPipeline, _build_revision_context, _evaluate_semantic_gate, _update_active_revision_context
from runners import CodeRunner


SUM_SOLUTION = """def solve(input_str: str) -> str:
    nums = [int(x) for x in input_str.split()]
    return str(sum(nums))
"""

BAD_ORACLE = """def solve(input_str: str) -> str:
    nums = [int(x) for x in input_str.split()]
    return str(sum(nums) + 1)
"""

RAISING_SOLUTION = """def solve(input_str: str) -> str:
    raise ValueError("boom")
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

BAD_TEST_GENERATOR_SYNTAX = """def generate_tests() -> list[dict]:
    return [
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

PARTIAL_BAD_FOR_BASIC = """def solve(input_str: str) -> str:
    text = input_str.strip()
    nums = [int(x) for x in text.split()]
    if text == "1 2":
        return str(sum(nums) + 1)
    return str(sum(nums))
"""

CANDIDATE_BREAKS_ZERO = """def solve(input_str: str) -> str:
    text = input_str.strip()
    nums = [int(x) for x in text.split()]
    if text == "0 0":
        return "1"
    return str(sum(nums))
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
        self.assertEqual(result["stats"]["high_value_survivor_count"], 0)
        self.assertEqual(result["stats"]["unexpected_correct_count"], 1)
        self.assertTrue(result["stats"]["passed_threshold"])


class FakeSchemaClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    def chat_json(self, *, system_prompt, user_prompt, temperature, timeout_s=None, request_name="chat_json"):
        self.prompts.append(
            {
                "system": system_prompt,
                "user": user_prompt,
                "temperature": temperature,
                "timeout_s": timeout_s,
                "request_name": request_name,
            }
        )
        return self.responses.pop(0)


class StandardSolutionGeneratorTests(unittest.TestCase):
    def test_standard_solution_generator_passes_request_name_and_timeout(self) -> None:
        client = FakeSchemaClient(
            [
                {
                    "code": SUM_SOLUTION,
                    "algorithm": "线性扫描累加",
                    "correctness": "逐项累加即可。",
                    "time_complexity": "O(n)",
                    "space_complexity": "O(1)",
                    "notes": "",
                }
            ]
        )
        generator = StandardSolutionGenerator(client, timeout_s=900)

        artifact = generator.generate(
            {"problem_id": "SUM", "statement_markdown": "给定若干整数，输出它们的和。"},
            FakeSpecExtractor().generate({}),
        )

        self.assertEqual(artifact.code, SUM_SOLUTION.strip())
        self.assertEqual(client.prompts[0]["request_name"], "standard_solution_generation")
        self.assertEqual(client.prompts[0]["timeout_s"], 900)


class ToolGeneratorTests(unittest.TestCase):
    def test_tool_generator_calls_three_split_prompts_in_order(self) -> None:
        client = FakeSchemaClient(
            [
                {"validator_code": VALIDATOR, "notes": "validator notes"},
                {"checker_code": CHECKER, "notes": "checker notes"},
                {"test_generator_code": TEST_GENERATOR, "notes": "test generator notes"},
            ]
        )
        generator = ToolGenerator(client)

        result = generator.generate(
            {"problem_id": "SUM", "statement_markdown": "给定若干整数，输出它们的和。"},
            FakeSpecExtractor().generate({}),
            {"role_diagnostics": {"ToolGenerator": [{"category": "validator_rejects_generated_case"}]}},
        )

        self.assertEqual(list(result), ["validator", "checker", "test_generator"])
        self.assertEqual(result["validator"].code, VALIDATOR.strip())
        self.assertEqual(result["checker"].code, CHECKER.strip())
        self.assertEqual(result["test_generator"].code, TEST_GENERATOR.strip())
        self.assertEqual(result["validator"].metadata["stage"], "validator")
        self.assertEqual(result["checker"].metadata["stage"], "checker")
        self.assertEqual(result["test_generator"].metadata["stage"], "test_generator")

        self.assertEqual(len(client.prompts), 3)
        self.assertIn("当前角色是 ValidatorGenerator", client.prompts[0]["system"])
        self.assertIn("validator_code", client.prompts[0]["user"])
        self.assertEqual(client.prompts[0]["request_name"], "validator_generation")
        self.assertIn("当前角色是 CheckerGenerator", client.prompts[1]["system"])
        self.assertIn("validator_artifact", client.prompts[1]["user"])
        self.assertIn("validator notes", client.prompts[1]["user"])
        self.assertEqual(client.prompts[1]["request_name"], "checker_generation")
        self.assertIn("当前角色是 TestGenerator", client.prompts[2]["system"])
        self.assertIn("validator_artifact", client.prompts[2]["user"])
        self.assertIn("checker_artifact", client.prompts[2]["user"])
        self.assertIn("checker notes", client.prompts[2]["user"])
        self.assertEqual(client.prompts[2]["request_name"], "test_generator_generation")

    def test_tool_generator_passes_custom_timeout_to_all_subrequests(self) -> None:
        client = FakeSchemaClient(
            [
                {"validator_code": VALIDATOR, "notes": "validator notes"},
                {"checker_code": CHECKER, "notes": "checker notes"},
                {"test_generator_code": TEST_GENERATOR, "notes": "test generator notes"},
            ]
        )

        ToolGenerator(client, timeout_s=1200).generate(
            {"problem_id": "SUM", "statement_markdown": "给定若干整数，输出它们的和。"},
            FakeSpecExtractor().generate({}),
        )

        self.assertEqual([item["timeout_s"] for item in client.prompts], [1200, 1200, 1200])

    def test_split_tool_generator_outputs_are_executable(self) -> None:
        client = FakeSchemaClient(
            [
                {"validator_code": VALIDATOR, "notes": "validator notes"},
                {"checker_code": CHECKER, "notes": "checker notes"},
                {"test_generator_code": TEST_GENERATOR, "notes": "test generator notes"},
            ]
        )
        tools = ToolGenerator(client).generate(
            {"problem_id": "SUM", "statement_markdown": "给定若干整数，输出它们的和。"},
            FakeSpecExtractor().generate({}),
        )
        runner = CodeRunner(timeout_s=1)

        validation = runner.run_validate(
            artifact_name="validator",
            code=tools["validator"].code,
            input_data="1 2",
            test_source="unit",
        )
        check = runner.run_check(
            artifact_name="checker",
            code=tools["checker"].code,
            input_data="1 2",
            output_data="3",
            expected_data="3",
            test_source="unit",
        )
        generated = runner.run_generate_tests(
            artifact_name="test_generator",
            code=tools["test_generator"].code,
        )

        self.assertEqual(validation.status, "ok")
        self.assertTrue(validation.result)
        self.assertEqual(check.status, "ok")
        self.assertTrue(check.result)
        self.assertEqual(generated.status, "ok")
        self.assertIsInstance(generated.result, list)


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
        self.assertIn("CheckerGenerator", large_diag["target_roles"])

    def test_revision_context_enriches_diagnostics_with_advisor_revision(self) -> None:
        advisor = RecordingRevisionAdvisor(
            {
                "root_cause": "标准解少累计了最后一个整数。",
                "revision_advice": "修改 StandardSolutionGenerator 的求和循环，使用 basic 输入验证输出从 3 修正为 4。",
                "target_roles": ["StandardSolutionGenerator"],
                "evidence_used": ["basic", "standard_output=3", "oracle_output=4"],
                "confidence": "high",
                "risk_notes": "",
            }
        )
        package = _fake_package()
        revision_context = _build_revision_context(
            [
                FailureIssue(
                    category="standard_oracle_mismatch",
                    severity="blocker",
                    title="标准解与 oracle 不一致",
                    detail="basic 上输出不同。",
                    evidence={
                        "test": {"source": "basic", "purpose": "基础反例", "metadata": {}},
                        "input": "2\n1 2\n",
                        "standard_output": "3\n",
                        "oracle_output": "4\n",
                    },
                    fix_hint="旧模板建议。",
                )
            ],
            {"independent_solutions": []},
            revision_advisor=advisor,
            current_package=package,
        )

        diagnostic = revision_context["diagnostics_by_category"]["standard_oracle_mismatch"][0]
        self.assertEqual(diagnostic["advisor_revision"]["revision_advice"], "修改 StandardSolutionGenerator 的求和循环，使用 basic 输入验证输出从 3 修正为 4。")
        self.assertEqual(diagnostic["advisor_revision"]["confidence"], "high")
        role_diag = revision_context["role_diagnostics"]["StandardSolutionGenerator"][0]
        self.assertEqual(role_diag["advisor_revision"]["root_cause"], "标准解少累计了最后一个整数。")
        self.assertEqual(diagnostic["target_roles"], ["StandardSolutionGenerator"])
        self.assertNotIn("OracleGenerator", revision_context["role_diagnostics"])
        self.assertEqual(len(advisor.packets), 1)
        self.assertIn("standard_solution", advisor.packets[0]["current_artifact"])
        self.assertEqual(advisor.packets[0]["legacy_fix_hint"], "旧模板建议。")

    def test_derived_kill_rate_skip_issue_is_reported_but_not_routed(self) -> None:
        revision_context = _build_revision_context(
            [
                FailureIssue(
                    category="performance_failure",
                    severity="blocker",
                    title="标准解超时",
                    detail="large 上超时。",
                    evidence={"test": {"source": "large"}},
                ),
                FailureIssue(
                    category="kill_rate_skipped_due_to_invalid_baseline",
                    severity="high",
                    title="基础自洽失败，跳过错误解杀伤率统计",
                    detail="杀伤率不可作为可信指标。",
                ),
            ],
            {"independent_solutions": []},
        )

        self.assertIn("kill_rate_skipped_due_to_invalid_baseline", revision_context["diagnostics_by_category"])
        self.assertIn("performance_failure", revision_context["diagnostics_by_category"])
        self.assertEqual(set(revision_context["role_diagnostics"]), {"StandardSolutionGenerator"})
        routed = revision_context["role_diagnostics"]["StandardSolutionGenerator"]
        self.assertEqual([item["category"] for item in routed], ["performance_failure"])

        active_context, _ = _update_active_revision_context({}, revision_context)
        self.assertIn("kill_rate_skipped_due_to_invalid_baseline", active_context["diagnostics_by_category"])
        self.assertEqual(set(active_context["role_diagnostics"]), {"StandardSolutionGenerator"})

    def test_revision_advisor_limits_repeated_category_calls(self) -> None:
        advisor = RecordingRevisionAdvisor(
            {
                "root_cause": "validator 与测试生成器约束不一致。",
                "revision_advice": "对每个被拒绝的生成输入，统一 validator 与 test_generator 的输入范围。",
                "target_roles": ["ValidatorGenerator"],
                "evidence_used": ["validator_result"],
                "confidence": "medium",
                "risk_notes": "",
            }
        )
        issues = [
            FailureIssue(
                category="validator_rejects_generated_case",
                severity="high",
                title="validator 拒绝测试",
                detail=f"case_{index} 未通过输入合法性检查。",
                evidence={"test": {"source": f"case_{index}", "purpose": "重复失败"}, "input": f"{index}\n"},
            )
            for index in range(5)
        ]

        revision_context = _build_revision_context(
            issues,
            {"independent_solutions": []},
            revision_advisor=advisor,
            current_package=_fake_package(),
        )

        diagnostics = revision_context["diagnostics_by_category"]["validator_rejects_generated_case"]
        self.assertEqual(len(advisor.packets), 3)
        self.assertTrue(all("advisor_revision" in item for item in diagnostics))
        self.assertTrue(diagnostics[3]["advisor_revision"]["cluster_reused"])
        self.assertEqual(len(revision_context["role_diagnostics"]["ValidatorGenerator"]), 3)

    def test_revision_advisor_failure_raises(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "RevisionAdvisor 生成修订建议失败"):
            _build_revision_context(
                [
                    FailureIssue(
                        category="standard_solution_failed",
                        severity="blocker",
                        title="标准解执行失败",
                        detail="运行异常。",
                        evidence={"test": {"source": "runtime"}},
                    )
                ],
                {"independent_solutions": []},
                revision_advisor=RaisingRevisionAdvisor(),
                current_package=_fake_package(),
            )

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
        self.assertEqual(len(revision_context["role_diagnostics"]["ValidatorGenerator"]), 3)

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


class StaticWeakPlayerGenerator:
    def __init__(self, solutions: list[WrongSolution]):
        self.solutions = list(solutions)

    def generate(self, statement_only_context, revision_context=None):
        del statement_only_context, revision_context
        return list(self.solutions)


class FakeSchemaMistakeAnalyzer:
    def generate(self, context, spec, revision_context=None):
        del context, spec, revision_context
        return [dict(SCHEMA_MISTAKE_POINT)]


class EmptySchemaMistakeAnalyzer:
    def generate(self, context, spec, revision_context=None):
        del context, spec, revision_context
        return []


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


class StaticSchemaWrongSolutionGenerator:
    def __init__(self, solutions: list[WrongSolution] | None = None):
        self.solutions = list(solutions or [])

    def generate(self, context, spec, mistake_points, revision_context=None):
        del context, spec, mistake_points, revision_context
        return list(self.solutions)


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


class BadTestGeneratorOnlyTool(FakeToolGenerator):
    def generate_test_generator(self, context, spec, validator, checker, revision_context=None):
        del context, spec, validator, checker, revision_context
        return GeneratedCodeArtifact(
            name="test_generator",
            role="test_generator",
            code=BAD_TEST_GENERATOR_SYNTAX,
        )


class RecordingRevisionAdvisor:
    def __init__(self, response: dict):
        self.response = response
        self.packets: list[dict] = []

    def generate(self, failure_packet):
        self.packets.append(failure_packet)
        return dict(self.response)


class RaisingRevisionAdvisor:
    def generate(self, failure_packet):
        del failure_packet
        raise RuntimeError("advisor unavailable")


def _fake_package() -> dict:
    return {
        "context": {"problem_id": "SUM"},
        "execution_spec": FakeSpecExtractor().generate({}),
        "standard_solution": GeneratedCodeArtifact(name="standard_solution", role="standard_solution", code=SUM_SOLUTION),
        "oracle_solution": GeneratedCodeArtifact(name="oracle_solution", role="oracle_solution", code=BAD_ORACLE),
        "validator": GeneratedCodeArtifact(name="validator", role="validator", code=VALIDATOR),
        "checker": GeneratedCodeArtifact(name="checker", role="checker", code=CHECKER),
        "test_generator": GeneratedCodeArtifact(name="test_generator", role="test_generator", code=TEST_GENERATOR),
        "schema_mistake_points": [dict(SCHEMA_MISTAKE_POINT)],
        "wrong_solutions": [
            WrongSolution(
                solution_id="first_token",
                code=FIRST_TOKEN_WRONG,
                source="weak_llm_player",
                bug_type="format_misread",
                expected_failure="只能过部分用例。",
            )
        ],
    }


class PipelineTests(unittest.TestCase):
    def _make_pipeline(
        self,
        *,
        weak_solutions: list[WrongSolution],
        schema_solutions: list[WrongSolution] | None = None,
        kill_rate_threshold: float = 0.5,
    ) -> PackageValidationPipeline:
        return PackageValidationPipeline(
            client=None,
            spec_extractor=FakeSpecExtractor(),
            standard_generator=FakeStandardGenerator(),
            oracle_generator=FakeOracleGenerator(),
            tool_generator=FakeToolGenerator(),
            weak_player_generator=StaticWeakPlayerGenerator(weak_solutions),
            schema_mistake_analyzer=EmptySchemaMistakeAnalyzer(),
            schema_wrong_solution_generator=StaticSchemaWrongSolutionGenerator(schema_solutions),
            progress_writer=lambda message: None,
            kill_rate_threshold=kill_rate_threshold,
        )

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
            self.assertTrue(result["summary"]["rounds"][0]["baseline_passed"])
            self.assertEqual(result["summary"]["rounds"][0]["baseline_failed_categories"], [])
            self.assertEqual(result["summary"]["rounds"][0]["baseline_failure_streak"], 0)
            wrong_dirs = {item.name for item in Path(result["run_dir"], "round1", "wrong_solutions").iterdir()}
            self.assertIn("SUM_schema_ignore_contract", wrong_dirs)
            self.assertNotIn("SUM_empty_output", wrong_dirs)

    def test_pipeline_revises_when_high_value_survivor_exists_despite_passing_kill_rate(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            artifact_path = Path(tempdir) / "artifact.json"
            artifact_path.write_text(
                json.dumps({"problem_id": "SUM", "generated_problem": {"title": "求和"}}, ensure_ascii=False),
                encoding="utf-8",
            )
            pipeline = self._make_pipeline(
                weak_solutions=[
                    WrongSolution(
                        solution_id="first_token",
                        code=FIRST_TOKEN_WRONG,
                        source="weak_llm_player",
                        bug_type="format_misread",
                        expected_failure="只能过部分用例。",
                    ),
                    WrongSolution(
                        solution_id="survivor_logic_gap",
                        code=SUM_SOLUTION,
                        source="weak_llm_player",
                        bug_type="logic_gap",
                        expected_failure="边界输入应失败。",
                    ),
                ]
            )

            result = pipeline.run(artifact_path=artifact_path, rounds=1)
            report = json.loads(Path(result["run_dir"], "round1", "execution_report.json").read_text(encoding="utf-8"))
            categories = {item["category"] for item in report["issues"]}

            self.assertEqual(result["summary"]["final_status"], "not_deliverable")
            self.assertEqual(result["summary"]["stop_reason"], "reached_requested_rounds")
            self.assertEqual(report["overall"]["status"], "revise")
            self.assertTrue(report["wrong_solution_stats"]["passed_threshold"])
            self.assertEqual(report["wrong_solution_stats"]["high_value_survivor_count"], 1)
            self.assertEqual(report["wrong_solution_stats"]["unexpected_correct_count"], 0)
            self.assertIn("wrong_solution_survived", categories)
            self.assertEqual(len(report["revision_context"]["surviving_wrong_solution_details"]), 1)

    def test_pipeline_allows_pass_when_only_unexpected_correct_survives(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            artifact_path = Path(tempdir) / "artifact.json"
            artifact_path.write_text(
                json.dumps({"problem_id": "SUM", "generated_problem": {"title": "求和"}}, ensure_ascii=False),
                encoding="utf-8",
            )
            pipeline = self._make_pipeline(
                weak_solutions=[
                    WrongSolution(
                        solution_id="first_token",
                        code=FIRST_TOKEN_WRONG,
                        source="weak_llm_player",
                        bug_type="format_misread",
                        expected_failure="只能过部分用例。",
                    ),
                    WrongSolution(
                        solution_id="unexpected_correct_sum",
                        code=SUM_SOLUTION,
                        source="weak_llm_player",
                        bug_type="unexpected_correct",
                        expected_failure="无",
                    ),
                ]
            )

            result = pipeline.run(artifact_path=artifact_path, rounds=1)
            report = json.loads(Path(result["run_dir"], "round1", "execution_report.json").read_text(encoding="utf-8"))
            categories = {item["category"] for item in report["issues"]}

            self.assertEqual(result["summary"]["final_status"], "pass")
            self.assertEqual(result["summary"]["stop_reason"], "all_checks_passed")
            self.assertEqual(report["overall"]["status"], "pass")
            self.assertTrue(report["wrong_solution_stats"]["passed_threshold"])
            self.assertEqual(report["wrong_solution_stats"]["high_value_survivor_count"], 0)
            self.assertEqual(report["wrong_solution_stats"]["unexpected_correct_count"], 1)
            self.assertNotIn("wrong_solution_survived", categories)
            self.assertEqual(report["revision_context"]["surviving_wrong_solution_details"], [])

    def test_pipeline_wrong_solution_issue_reports_threshold_and_survivor_details(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            artifact_path = Path(tempdir) / "artifact.json"
            artifact_path.write_text(
                json.dumps({"problem_id": "SUM", "generated_problem": {"title": "求和"}}, ensure_ascii=False),
                encoding="utf-8",
            )
            pipeline = self._make_pipeline(
                weak_solutions=[
                    WrongSolution(
                        solution_id="survivor_logic_gap",
                        code=SUM_SOLUTION,
                        source="weak_llm_player",
                        bug_type="logic_gap",
                        expected_failure="边界输入应失败。",
                    )
                ]
            )

            result = pipeline.run(artifact_path=artifact_path, rounds=1)
            report = json.loads(Path(result["run_dir"], "round1", "execution_report.json").read_text(encoding="utf-8"))
            issue = next(item for item in report["issues"] if item["category"] == "wrong_solution_survived")

            self.assertEqual(report["overall"]["status"], "revise")
            self.assertFalse(report["wrong_solution_stats"]["passed_threshold"])
            self.assertEqual(report["wrong_solution_stats"]["high_value_survivor_count"], 1)
            self.assertIn("当前杀伤率 0.0，阈值 0.5。", issue["detail"])
            self.assertIn("高价值幸存错误解 1 个。", issue["detail"])
            self.assertIn("是否仅剩 unexpected_correct 候选：否。", issue["detail"])
            self.assertIn("当前杀伤率尚未达标。", issue["detail"])

    def test_pipeline_runs_until_requested_rounds_when_not_passed(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            artifact_path = Path(tempdir) / "artifact.json"
            artifact_path.write_text(
                json.dumps({"problem_id": "SUM", "generated_problem": {"title": "求和"}}, ensure_ascii=False),
                encoding="utf-8",
            )
            pipeline = self._make_pipeline(
                weak_solutions=[
                    WrongSolution(
                        solution_id="first_token",
                        code=FIRST_TOKEN_WRONG,
                        source="weak_llm_player",
                        bug_type="format_misread",
                        expected_failure="只能过部分用例。",
                    ),
                    WrongSolution(
                        solution_id="survivor_logic_gap",
                        code=SUM_SOLUTION,
                        source="weak_llm_player",
                        bug_type="logic_gap",
                        expected_failure="边界输入应失败。",
                    ),
                ]
            )

            result = pipeline.run(artifact_path=artifact_path, rounds=2)

            self.assertEqual(result["summary"]["final_status"], "not_deliverable")
            self.assertEqual(result["summary"]["stop_reason"], "reached_requested_rounds")
            self.assertEqual(result["summary"]["final_round_index"], 2)
            self.assertEqual(len(result["summary"]["rounds"]), 2)
            self.assertTrue(Path(result["run_dir"], "round2", "execution_report.json").exists())

    def test_pipeline_stops_when_concrete_baseline_fingerprints_stall(self) -> None:
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

            result = pipeline.run(artifact_path=artifact_path, rounds=3)

            self.assertEqual(result["summary"]["final_status"], "not_deliverable")
            self.assertEqual(result["summary"]["stop_reason"], "stalled_on_baseline")
            self.assertEqual(result["summary"]["final_round_index"], 2)
            self.assertEqual([item["baseline_failure_streak"] for item in result["summary"]["rounds"]], [1, 2])
            self.assertTrue(all(not item["baseline_passed"] for item in result["summary"]["rounds"]))
            self.assertTrue(Path(result["run_dir"], "round2", "execution_report.json").exists())
            self.assertFalse(Path(result["run_dir"], "round3", "execution_report.json").exists())

    def test_pipeline_does_not_stall_when_baseline_fingerprints_change(self) -> None:
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
                standard_generator=SequenceStandardGenerator([SUM_SOLUTION, RAISING_SOLUTION]),
                oracle_generator=FakeOracleGenerator(BAD_ORACLE),
                tool_generator=FakeToolGenerator(),
                weak_player_generator=FakeWeakPlayerGenerator(),
                schema_mistake_analyzer=FakeSchemaMistakeAnalyzer(),
                schema_wrong_solution_generator=FakeSchemaWrongSolutionGenerator(),
                progress_writer=lambda message: None,
                kill_rate_threshold=0.5,
            )

            result = pipeline.run(artifact_path=artifact_path, rounds=2)

            self.assertEqual(result["summary"]["stop_reason"], "reached_requested_rounds")
            self.assertEqual(result["summary"]["final_round_index"], 2)
            self.assertEqual([item["baseline_failure_streak"] for item in result["summary"]["rounds"]], [1, 1])
            self.assertIn("standard_oracle_mismatch", result["summary"]["rounds"][0]["baseline_failed_categories"])
            self.assertIn("component_gate_failed", result["summary"]["rounds"][1]["baseline_failed_categories"])

    def test_pipeline_emits_detailed_progress_messages(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            artifact_path = Path(tempdir) / "artifact.json"
            artifact_path.write_text(
                json.dumps(
                    {
                        "problem_id": "SUM",
                        "generated_problem": {"title": "求和", "samples": []},
                        "new_schema_snapshot": {"problem_id": "SUM"},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            messages: list[str] = []
            pipeline = PackageValidationPipeline(
                client=None,
                output_dir=Path(tempdir) / "out",
                spec_extractor=FakeSpecExtractor(),
                standard_generator=FakeStandardGenerator(),
                oracle_generator=FakeOracleGenerator(),
                tool_generator=FakeToolGenerator(),
                weak_player_generator=FakeWeakPlayerGenerator(),
                schema_mistake_analyzer=FakeSchemaMistakeAnalyzer(),
                schema_wrong_solution_generator=FakeSchemaWrongSolutionGenerator(),
                progress_writer=messages.append,
                kill_rate_threshold=0.5,
            )

            pipeline.run(artifact_path=artifact_path, rounds=1)

            self.assertTrue(any("[启动] 题目 SUM" in message for message in messages), messages)
            self.assertTrue(any("[生成] 抽取 execution_spec" in message for message in messages), messages)
            self.assertTrue(any("[验证] 可执行测试用例数量：" in message for message in messages), messages)
            self.assertTrue(any("[筛选] 开始错误解筛选" in message for message in messages), messages)
            self.assertTrue(any("[筛选] 错误解筛选完成" in message for message in messages), messages)
            self.assertTrue(any("[完成] 迭代结束" in message for message in messages), messages)

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

    def test_bad_test_generator_candidate_does_not_overwrite_previous_component(self) -> None:
        pipeline = PackageValidationPipeline(
            client=None,
            spec_extractor=CountingSpecExtractor(),
            standard_generator=SequenceStandardGenerator([SUM_SOLUTION]),
            oracle_generator=CountingOracleGenerator(),
            tool_generator=BadTestGeneratorOnlyTool(),
            weak_player_generator=FakeWeakPlayerGenerator(),
            schema_mistake_analyzer=FakeSchemaMistakeAnalyzer(),
            schema_wrong_solution_generator=FakeSchemaWrongSolutionGenerator(),
            progress_writer=lambda message: None,
            kill_rate_threshold=0.5,
        )
        current_package = _fake_package()
        diagnostic = {
            "category": "test_generator_failed",
            "severity": "blocker",
            "title": "测试生成器执行失败",
            "detail": "需要只修复 test_generator。",
            "target_roles": ["TestGenerator"],
            "evidence": {"test": {"source": "test_generator"}},
            "issue_fingerprint": "test-generator-only",
        }
        revision_context = {
            "summary": [{"category": "test_generator_failed", "count": 1, "severity": "blocker"}],
            "diagnostics_by_category": {"test_generator_failed": [diagnostic]},
            "role_diagnostics": {"TestGenerator": [diagnostic]},
            "failed_hard_checks": ["test_generator_failed"],
            "surviving_wrong_solution_details": [],
            "revision_mode": "incremental_patch",
        }

        package = pipeline._generate_incremental_round_package({"problem_id": "SUM"}, current_package, revision_context)

        self.assertEqual(package["test_generator"].code, current_package["test_generator"].code)
        self.assertEqual(pipeline._component_gate_issues[0].category, "component_gate_failed")
        self.assertEqual(pipeline._component_gate_issues[0].evidence["component"], "test_generator")

    def test_candidate_package_gate_rejects_known_good_regression(self) -> None:
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
                standard_generator=SequenceStandardGenerator([PARTIAL_BAD_FOR_BASIC, CANDIDATE_BREAKS_ZERO]),
                oracle_generator=FakeOracleGenerator(),
                tool_generator=FakeToolGenerator(),
                weak_player_generator=FakeWeakPlayerGenerator(),
                schema_mistake_analyzer=FakeSchemaMistakeAnalyzer(),
                schema_wrong_solution_generator=FakeSchemaWrongSolutionGenerator(),
                progress_writer=lambda message: None,
                kill_rate_threshold=0.5,
            )

            result = pipeline.run(artifact_path=artifact_path, rounds=2)
            round2_report = json.loads(Path(result["run_dir"], "round2", "execution_report.json").read_text(encoding="utf-8"))
            categories = {item["category"] for item in round2_report["issues"]}
            gate_result = round2_report["candidate_package_gate_results"]["standard_solution"]

            self.assertIn("candidate_regression_detected", categories)
            self.assertFalse(gate_result["passed"])
            self.assertIn("known_good_case_failed", gate_result["rejection_reasons"])
            self.assertTrue(gate_result["known_good_failed_sources"])
            self.assertEqual(
                Path(result["run_dir"], "round2", "standard_solution.py").read_text(encoding="utf-8").strip(),
                PARTIAL_BAD_FOR_BASIC.strip(),
            )
            self.assertTrue(Path(result["run_dir"], "known_good_cases.json").exists())
            self.assertGreater(result["summary"]["known_good_case_count"], 0)
            self.assertEqual(result["summary"]["regression_prevention_count"], 1)

    def test_candidate_package_gate_rejects_not_better_candidate(self) -> None:
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
                standard_generator=SequenceStandardGenerator([PARTIAL_BAD_FOR_BASIC, PARTIAL_BAD_FOR_BASIC]),
                oracle_generator=FakeOracleGenerator(),
                tool_generator=FakeToolGenerator(),
                weak_player_generator=FakeWeakPlayerGenerator(),
                schema_mistake_analyzer=FakeSchemaMistakeAnalyzer(),
                schema_wrong_solution_generator=FakeSchemaWrongSolutionGenerator(),
                progress_writer=lambda message: None,
                kill_rate_threshold=0.5,
            )

            result = pipeline.run(artifact_path=artifact_path, rounds=2)
            round2_report = json.loads(Path(result["run_dir"], "round2", "execution_report.json").read_text(encoding="utf-8"))
            categories = {item["category"] for item in round2_report["issues"]}
            gate_result = round2_report["candidate_package_gate_results"]["standard_solution"]

            self.assertIn("candidate_not_better_than_current", categories)
            self.assertFalse(gate_result["passed"])
            self.assertIn("candidate_not_better_than_current", gate_result["rejection_reasons"])
            self.assertEqual(result["summary"]["candidate_gate_rejection_count"], 3)

    def test_advisor_narrow_target_roles_control_incremental_regeneration(self) -> None:
        advisor = RecordingRevisionAdvisor(
            {
                "root_cause": "标准解复杂度不达标。",
                "revision_advice": "只修改 StandardSolutionGenerator 的算法路径，不改工具和 oracle。",
                "target_roles": ["StandardSolutionGenerator"],
                "evidence_used": ["large"],
                "confidence": "high",
                "risk_notes": "",
            }
        )
        revision_context = _build_revision_context(
            [
                FailureIssue(
                    category="standard_oracle_mismatch",
                    severity="blocker",
                    title="标准解与 oracle 不一致",
                    detail="large 上输出不同。",
                    evidence={"test": {"source": "large"}, "standard_output": "1", "oracle_output": "2"},
                )
            ],
            {"independent_solutions": []},
            revision_advisor=advisor,
            current_package=_fake_package(),
        )
        revision_context["revision_mode"] = "incremental_patch"

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

        package = pipeline._generate_incremental_round_package({"problem_id": "SUM"}, _fake_package(), revision_context)

        self.assertEqual(set(revision_context["role_diagnostics"]), {"StandardSolutionGenerator"})
        self.assertEqual(standard_generator.calls, 1)
        self.assertEqual(oracle_generator.calls, 0)
        self.assertEqual(tool_generator.calls, 0)
        self.assertEqual(package["oracle_solution"].code, BAD_ORACLE)

    def test_performance_failure_with_derived_kill_rate_skip_only_regenerates_standard_solution(self) -> None:
        revision_context = _build_revision_context(
            [
                FailureIssue(
                    category="performance_failure",
                    severity="blocker",
                    title="标准解超时",
                    detail="large 上超时。",
                    evidence={"test": {"source": "large"}},
                ),
                FailureIssue(
                    category="kill_rate_skipped_due_to_invalid_baseline",
                    severity="high",
                    title="基础自洽失败，跳过错误解杀伤率统计",
                    detail="杀伤率不可作为可信指标。",
                ),
            ],
            {"independent_solutions": []},
        )
        revision_context["revision_mode"] = "incremental_patch"
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

        pipeline._generate_incremental_round_package({"problem_id": "SUM"}, _fake_package(), revision_context)

        self.assertEqual(set(revision_context["role_diagnostics"]), {"StandardSolutionGenerator"})
        self.assertEqual(standard_generator.calls, 1)
        self.assertEqual(oracle_generator.calls, 0)
        self.assertEqual(tool_generator.calls, 0)

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
            self.assertEqual(report["wrong_solution_stats"]["candidate_count"], 0)
            mismatch_issue = next(item for item in report["issues"] if item["category"] == "standard_oracle_mismatch")
            self.assertIn("checker_result", mismatch_issue["evidence"])
            self.assertEqual(result["summary"]["final_status"], "not_deliverable")
            self.assertEqual(result["summary"]["deliverable_dir"], "")
            self.assertTrue(Path(result["run_dir"], "last_attempt").exists())
            self.assertFalse(Path(result["run_dir"], "final").exists())
            self.assertTrue(Path(result["run_dir"], "NOT_DELIVERABLE.md").exists())
            self.assertTrue(Path(result["run_dir"], "regression_cases.json").exists())

    def test_semantic_gate_requires_minimal_certificate_checker_kernel(self) -> None:
        spec = ExecutionSpec(
            problem_id="CERT",
            input_contract={"format": "任意"},
            output_contract={"description": "NO 时必须输出字典序最小的冲突区间。"},
            judge_type="checker",
            oracle_limits={},
            test_buckets=[],
        )
        checker = GeneratedCodeArtifact(
            name="checker",
            role="checker",
            code="def check(input_str, output_str, expected_str):\n    return bool(output_str.strip())\n",
        )

        issues = _evaluate_semantic_gate(spec, checker)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].category, "semantic_kernel_required")

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
