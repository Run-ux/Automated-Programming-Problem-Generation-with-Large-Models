from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from execution_config import ExecutionConfig
from local_execution import (
    EXECUTION_ERROR,
    EXECUTION_MEMORY_LIMIT,
    EXECUTION_OK,
    EXECUTION_TIMEOUT,
    ExecutionResult,
)
from verification_pipeline import (
    _result_summary,
    collect_verified_test_inputs,
    generate_verified_artifacts,
    verify_bruteforce_solution,
    verify_checker,
)


def sample_artifact() -> dict:
    return {
        "generated_problem": {
            "title": "SUM",
            "description": "给定 n 个整数，输出它们的和。",
            "input_format": "第一行 n，第二行 n 个整数。",
            "output_format": "输出一个整数。",
            "constraints": ["1 <= n <= 10", "-100 <= ai <= 100"],
            "samples": [{"input": "3\n1 2 3", "output": "6"}],
            "notes": "无",
        },
        "new_schema_snapshot": {
            "input_structure": {"n": "数组长度", "a": "整数数组"},
            "core_constraints": {"sum_range": "普通整数"},
            "objective": {"goal": "输出数组元素和"},
            "invariant": {"sum": "答案等于所有元素之和"},
        },
    }


class FakeLLMClient:
    model = "fake-model"
    base_url = None

    def __init__(self, *, checker: bool = False) -> None:
        self.checker = checker
        self.calls: list[str] = []

    def complete_json(self, *, task_name: str, system_prompt: str, user_prompt: str) -> str:
        self.calls.append(task_name)
        if task_name == "standard_solution":
            return json.dumps(
                {
                    "status": "ok",
                    "block_reason": "",
                    "solution_markdown": "说明",
                    "code": "def solve(input_str: str) -> str:\n    return '1'",
                    "time_complexity": "O(n)",
                    "space_complexity": "O(1)",
                },
                ensure_ascii=False,
            )
        if task_name == "bruteforce_solution":
            return json.dumps(
                {
                    "status": "ok",
                    "block_reason": "",
                    "bruteforce_markdown": "说明",
                    "code": "def solve(input_str: str) -> str:\n    return '1'",
                    "time_complexity": "O(n)",
                    "space_complexity": "O(1)",
                },
                ensure_ascii=False,
            )
        if task_name in ("random_test_input", "adversarial_test_input"):
            return json.dumps(
                {
                    "constraint_analysis": "约束",
                    "generate_test_input_code": "def generate_test_input():\n    return '1\\n1'",
                    "validate_test_input_code": "def validate_test_input(input_string):\n    return True",
                },
                ensure_ascii=False,
            )
        if task_name == "small_challenge_test_input" or task_name.startswith("small_challenge_test_input:"):
            return json.dumps({"test_input": "1\n1"}, ensure_ascii=False)
        if task_name == "checker":
            if self.checker:
                return json.dumps(
                    {
                        "needs_checker": True,
                        "output_rule_analysis": "输出任意合法和。",
                        "checker_code": "bad_checker",
                        "notes": "无",
                    },
                    ensure_ascii=False,
                )
            return json.dumps({"needs_checker": False, "reason": "唯一答案题。"}, ensure_ascii=False)
        if task_name == "strategy_analysis":
            return json.dumps(
                {
                    "strategies": [
                        {
                            "title": "忽略负数",
                            "wrong_idea": "忽略负数",
                            "plausible_reason": "样例简单",
                            "failure_reason": "题面允许负数",
                            "trigger_case": "含负数",
                        }
                    ]
                },
                ensure_ascii=False,
            )
        if task_name.startswith("fixed_wrong_solution:") or task_name.startswith("strategy_wrong_solution:"):
            return json.dumps({"code": "def solve(input_str):\n    return '0'"}, ensure_ascii=False)
        if task_name == "bruteforce_debug":
            return json.dumps({"code": "good_code"}, ensure_ascii=False)
        if task_name == "checker_false_reject_debug":
            return json.dumps(
                {"analysis": "过严", "fix_plan": "放宽合法格式", "checker_code": "accept_legal"},
                ensure_ascii=False,
            )
        if task_name == "checker_counterexample_generation":
            return json.dumps(
                {
                    "counterexamples": [
                        {
                            "source_case_id": "case_001",
                            "input": "1\n1",
                            "correct_output": "1",
                            "wrong_output": "2",
                            "primary_strategy": "OBJECTIVE_INCONSISTENT_VALUE",
                            "strategy_group": "目标错误",
                            "expected_verdict": "WA",
                            "reason": "2 不是该输入的和。",
                            "confidence": 0.95,
                        }
                    ],
                    "skipped": [],
                },
                ensure_ascii=False,
            )
        if task_name == "checker_false_accept_debug":
            return json.dumps(
                {"analysis": "过松", "fix_plan": "校验答案值", "checker_code": "reject_wrong"},
                ensure_ascii=False,
            )
        raise AssertionError(f"未预期的任务: {task_name}")


class VerificationPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = ExecutionConfig(
            test_input_timeout_seconds=1,
            test_input_memory_limit_mb=512,
            bruteforce_timeout_seconds=1,
            bruteforce_memory_limit_mb=512,
            checker_timeout_seconds=1,
            checker_memory_limit_mb=512,
        )

    def test_result_summary_truncates_middle_and_keeps_tail(self) -> None:
        result = ExecutionResult(
            status=EXECUTION_ERROR,
            stdout="stdout-head-" + "x" * 3000 + "-stdout-tail",
            stderr="stderr-head-" + "y" * 3000 + "-stderr-tail",
            traceback="trace-head-" + "z" * 5000 + "-trace-tail",
            user_stdout="user-stdout-head-" + "a" * 3000 + "-user-stdout-tail",
            user_stderr="user-stderr-head-" + "b" * 3000 + "-user-stderr-tail",
        )

        summary = _result_summary(result)

        for key, head, tail in [
            ("stdout", "stdout-head-", "-stdout-tail"),
            ("stderr", "stderr-head-", "-stderr-tail"),
            ("traceback", "trace-head-", "-trace-tail"),
            ("user_stdout", "user-stdout-head-", "-user-stdout-tail"),
            ("user_stderr", "user-stderr-head-", "-user-stderr-tail"),
        ]:
            self.assertTrue(summary[key].startswith(head))
            self.assertTrue(summary[key].endswith(tail))
            self.assertIn("...<truncated>...", summary[key])

    @patch("verification_pipeline.run_validate_test_input")
    @patch("verification_pipeline.run_generate_test_input")
    def test_collect_verified_test_inputs_uses_ten_small_challenge_cases(
        self,
        fake_generate,
        fake_validate,
    ) -> None:
        fake_generate.return_value = ExecutionResult(status=EXECUTION_OK, return_value="1\n1")
        fake_validate.return_value = ExecutionResult(status=EXECUTION_OK, return_value=True)
        client = FakeLLMClient()
        generated_artifacts = {
            "test_inputs": {
                "random": {
                    "generate_test_input_code": "random_generate",
                    "validate_test_input_code": "random_validate",
                },
                "adversarial": {
                    "generate_test_input_code": "adversarial_generate",
                    "validate_test_input_code": "adversarial_validate",
                },
                "small_challenge": {"test_input": "1\n1"},
            }
        }

        result = collect_verified_test_inputs(sample_artifact(), generated_artifacts, client, self.config)

        self.assertEqual(result["count"], 30)
        self.assertEqual(result["source_counts"]["small_challenge"], 10)
        self.assertEqual(client.calls.count("small_challenge_test_input:verified:2"), 1)
        self.assertEqual(fake_generate.call_count, 20)
        self.assertEqual(fake_validate.call_count, 30)

    @patch("verification_pipeline.run_solution")
    def test_verify_bruteforce_repairs_runtime_error_and_keeps_large_scale_inputs(self, fake_run_solution) -> None:
        client = FakeLLMClient()
        input_cases = [
            {"case_id": "case_001", "source": "random", "input": "1\n1"},
            {"case_id": "case_002", "source": "random", "input": "1\n2"},
            {"case_id": "case_003", "source": "random", "input": "1\n3"},
        ]

        def side_effect(code, input_string, *, timeout_seconds, memory_limit_mb):
            if code == "bad_code":
                return ExecutionResult(
                    status=EXECUTION_ERROR,
                    phase="runtime",
                    error_type="ValueError",
                    error_message="boom",
                )
            if input_string == "1\n2":
                return ExecutionResult(status=EXECUTION_TIMEOUT)
            if input_string == "1\n3":
                return ExecutionResult(status=EXECUTION_MEMORY_LIMIT)
            return ExecutionResult(status=EXECUTION_OK, return_value="1")

        fake_run_solution.side_effect = side_effect

        result = verify_bruteforce_solution(
            sample_artifact(),
            {"status": "ok", "code": "bad_code"},
            input_cases,
            client,
            self.config,
        )

        self.assertEqual(result["final_code"], "good_code")
        self.assertEqual(result["repair_iteration_count"], 1)
        self.assertEqual(result["solved_case_count"], 1)
        self.assertEqual(result["large_scale_input_count"], 2)

    @patch("verification_pipeline.run_checker")
    def test_verify_checker_repairs_false_reject_then_false_accept(self, fake_run_checker) -> None:
        client = FakeLLMClient(checker=True)
        solved_cases = [{"case_id": "case_001", "input": "1\n1", "output": "1"}]

        def side_effect(code, input_string, output_string, *, timeout_seconds, memory_limit_mb):
            if code == "bad_checker":
                return ExecutionResult(status=EXECUTION_OK, return_value=False)
            if code == "accept_legal" and output_string == "1":
                return ExecutionResult(status=EXECUTION_OK, return_value=True)
            if code == "accept_legal" and output_string == "2":
                return ExecutionResult(status=EXECUTION_OK, return_value=True)
            if code == "reject_wrong" and output_string == "1":
                return ExecutionResult(status=EXECUTION_OK, return_value=True)
            if code == "reject_wrong" and output_string == "2":
                return ExecutionResult(status=EXECUTION_OK, return_value=False)
            raise AssertionError((code, input_string, output_string))

        fake_run_checker.side_effect = side_effect

        result = verify_checker(
            sample_artifact(),
            {"needs_checker": True, "checker_code": "bad_checker"},
            solved_cases,
            client,
            self.config,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["final_checker_code"], "reject_wrong")
        self.assertEqual(result["property_1"]["status"], "ok")
        self.assertEqual(result["property_2"]["status"], "ok")
        self.assertEqual(result["repair_iteration_count"], 2)

    @patch("verification_pipeline.run_solution")
    @patch("verification_pipeline.run_validate_test_input")
    @patch("verification_pipeline.run_generate_test_input")
    def test_generate_verified_artifacts_keeps_no_checker_pipeline(
        self,
        fake_generate,
        fake_validate,
        fake_solution,
    ) -> None:
        fake_generate.return_value = ExecutionResult(status=EXECUTION_OK, return_value="1\n1")
        fake_validate.return_value = ExecutionResult(status=EXECUTION_OK, return_value=True)
        fake_solution.return_value = ExecutionResult(status=EXECUTION_OK, return_value="1")
        client = FakeLLMClient()

        result = generate_verified_artifacts(
            sample_artifact(),
            client=client,
            execution_config=self.config,
        )

        self.assertEqual(result["verified_test_inputs"]["count"], 30)
        self.assertEqual(result["bruteforce_verification"]["solved_case_count"], 30)
        self.assertEqual(result["bruteforce_solution"]["code"], result["bruteforce_solution"]["verified_code"])
        self.assertIn("initial_code", result["bruteforce_solution"])
        self.assertEqual(result["checker_verification"]["status"], "skipped")
        self.assertEqual(result["execution_metadata"]["large_scale_input_count"], 0)


if __name__ == "__main__":
    unittest.main()
