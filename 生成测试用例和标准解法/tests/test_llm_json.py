from __future__ import annotations

import unittest

from llm_json import (
    LLMResponseError,
    parse_json_object,
    validate_checker_response,
    validate_solution_response,
    validate_strategy_analysis_response,
    validate_test_generator_response,
    validate_wrong_solution_response,
)


class LLMJsonTests(unittest.TestCase):
    def test_parse_json_object_rejects_non_json(self) -> None:
        with self.assertRaisesRegex(LLMResponseError, "合法 JSON"):
            parse_json_object("not-json", "standard_solution")

    def test_parse_json_object_rejects_non_object(self) -> None:
        with self.assertRaisesRegex(LLMResponseError, "必须是对象"):
            parse_json_object("[]", "standard_solution")

    def test_solution_ok_requires_empty_block_reason_and_non_empty_code(self) -> None:
        payload = {
            "status": "ok",
            "block_reason": "",
            "solution_markdown": "说明",
            "code": "def solve(input_str: str) -> str:\n    return ''",
            "time_complexity": "O(n)",
            "space_complexity": "O(1)",
        }

        self.assertIs(
            validate_solution_response(payload, task_name="standard_solution", markdown_key="solution_markdown"),
            payload,
        )

        bad_payload = dict(payload)
        bad_payload["code"] = ""
        with self.assertRaisesRegex(LLMResponseError, "code"):
            validate_solution_response(bad_payload, task_name="standard_solution", markdown_key="solution_markdown")

    def test_solution_blocked_requires_reason_and_empty_code(self) -> None:
        payload = {
            "status": "blocked",
            "block_reason": "题面缺少输入格式。",
            "solution_markdown": "",
            "code": "",
            "time_complexity": "",
            "space_complexity": "",
        }

        self.assertIs(
            validate_solution_response(payload, task_name="standard_solution", markdown_key="solution_markdown"),
            payload,
        )

        bad_payload = dict(payload)
        bad_payload["code"] = "def solve(input_str): return ''"
        with self.assertRaisesRegex(LLMResponseError, "blocked"):
            validate_solution_response(bad_payload, task_name="standard_solution", markdown_key="solution_markdown")

    def test_test_generator_requires_three_fields(self) -> None:
        with self.assertRaisesRegex(LLMResponseError, "validate_test_input_code"):
            validate_test_generator_response(
                {
                    "constraint_analysis": "约束",
                    "generate_test_input_code": "def generate_test_input():\n    return ''",
                },
                task_name="random_test_input",
            )

    def test_checker_false_branch_requires_reason(self) -> None:
        with self.assertRaisesRegex(LLMResponseError, "reason"):
            validate_checker_response({"needs_checker": False})

        with self.assertRaisesRegex(LLMResponseError, "checker_code"):
            validate_checker_response({"needs_checker": False, "reason": "不需要", "checker_code": "def x(): pass"})

    def test_checker_true_branch_requires_checker_code(self) -> None:
        with self.assertRaisesRegex(LLMResponseError, "checker_code"):
            validate_checker_response({"needs_checker": True, "output_rule_analysis": "规则", "notes": "无"})

    def test_strategy_analysis_rejects_empty_list(self) -> None:
        with self.assertRaisesRegex(LLMResponseError, "非空列表"):
            validate_strategy_analysis_response({"strategies": []})

    def test_wrong_solution_requires_code(self) -> None:
        with self.assertRaisesRegex(LLMResponseError, "code"):
            validate_wrong_solution_response({}, task_name="fixed_wrong_solution")


if __name__ == "__main__":
    unittest.main()

