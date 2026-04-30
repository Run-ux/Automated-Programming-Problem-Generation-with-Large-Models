from __future__ import annotations

import json
import unittest

from generation_pipeline import generate_all_artifacts
from prompts.wrong_solution.prompt_fixed_category_wrong_solution import FIXED_WRONG_CATEGORIES


class FakeLLMClient:
    model = "fake-model"
    base_url = "https://fake.test/v1"

    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def complete_json(self, *, task_name: str, system_prompt: str, user_prompt: str) -> str:
        self.calls.append(
            {
                "task_name": task_name,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
            }
        )
        if task_name == "standard_solution":
            return json.dumps(
                {
                    "status": "ok",
                    "block_reason": "",
                    "solution_markdown": "标准解说明",
                    "code": "def solve(input_str: str) -> str:\n    return '6'",
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
                    "bruteforce_markdown": "暴力解说明",
                    "code": "def solve(input_str: str) -> str:\n    return '6'",
                    "time_complexity": "O(n)",
                    "space_complexity": "O(1)",
                },
                ensure_ascii=False,
            )
        if task_name in ("random_test_input", "adversarial_test_input"):
            return json.dumps(
                {
                    "constraint_analysis": "n 与数组约束",
                    "generate_test_input_code": "import cyaron as cy\n\ndef generate_test_input():\n    return '1\\n1'",
                    "validate_test_input_code": "def validate_test_input(input_string):\n    return True",
                },
                ensure_ascii=False,
            )
        if task_name == "small_challenge_test_input":
            return json.dumps({"test_input": "2\n1 -1"}, ensure_ascii=False)
        if task_name == "checker":
            return json.dumps({"needs_checker": False, "reason": "唯一答案题。"}, ensure_ascii=False)
        if task_name == "strategy_analysis":
            return json.dumps(
                {
                    "strategies": [
                        {
                            "title": "忽略负数",
                            "wrong_idea": "只累加正数。",
                            "plausible_reason": "样例可能都是正数。",
                            "failure_reason": "题面允许负数。",
                            "trigger_case": "包含负数的数组。",
                        },
                        {
                            "title": "使用 32 位整数",
                            "wrong_idea": "用 32 位整型累加。",
                            "plausible_reason": "样例答案较小。",
                            "failure_reason": "答案可能超过 32 位。",
                            "trigger_case": "大数累加。",
                        },
                    ]
                },
                ensure_ascii=False,
            )
        if task_name.startswith("fixed_wrong_solution:") or task_name.startswith("strategy_wrong_solution:"):
            return json.dumps(
                {"code": "def solve(input_str: str) -> str:\n    return '0'"},
                ensure_ascii=False,
            )
        raise AssertionError(f"未预期的任务: {task_name}")


class GenerationPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.artifact = {
            "generated_problem": {
                "title": "SUM",
                "description": "给定 n 个整数，输出它们的和。",
                "input_format": "第一行 n，第二行 n 个整数。",
                "output_format": "输出一个整数。",
                "constraints": ["1 <= n <= 100000", "-10^9 <= ai <= 10^9"],
                "samples": [{"input": "3\n1 2 3", "output": "6"}],
                "notes": "样例只展示基础求和。",
            },
            "new_schema_snapshot": {
                "input_structure": {"n": "数组长度", "a": "整数数组"},
                "core_constraints": {"sum_range": "答案可能超过 32 位"},
                "objective": {"goal": "输出数组元素和"},
                "invariant": {"prefix_sum": "前缀和增量等于当前元素"},
            },
        }

    def test_generate_all_artifacts_calls_every_prompt_and_returns_public_shape(self) -> None:
        client = FakeLLMClient()

        result = generate_all_artifacts(self.artifact, client=client)

        task_names = [call["task_name"] for call in client.calls]
        self.assertIn("standard_solution", task_names)
        self.assertIn("bruteforce_solution", task_names)
        self.assertIn("random_test_input", task_names)
        self.assertIn("adversarial_test_input", task_names)
        self.assertIn("small_challenge_test_input", task_names)
        self.assertIn("checker", task_names)
        self.assertIn("strategy_analysis", task_names)
        for category in FIXED_WRONG_CATEGORIES:
            self.assertIn(f"fixed_wrong_solution:{category}", task_names)
        self.assertIn("strategy_wrong_solution:0", task_names)
        self.assertIn("strategy_wrong_solution:1", task_names)

        self.assertIn("standard_solution", result)
        self.assertIn("bruteforce_solution", result)
        self.assertIn("test_inputs", result)
        self.assertIn("checker", result)
        self.assertIn("wrong_solutions", result)
        self.assertIn("metadata", result)
        self.assertEqual(set(result["test_inputs"]), {"random", "adversarial", "small_challenge"})
        self.assertEqual(set(result["wrong_solutions"]["fixed_categories"]), set(FIXED_WRONG_CATEGORIES))
        self.assertEqual(len(result["wrong_solutions"]["strategy_based"]), 2)
        self.assertEqual(result["metadata"]["fixed_wrong_category_count"], len(FIXED_WRONG_CATEGORIES))
        self.assertEqual(result["metadata"]["strategy_wrong_solution_count"], 2)
        self.assertTrue(result["metadata"]["json_mode"])


if __name__ == "__main__":
    unittest.main()

