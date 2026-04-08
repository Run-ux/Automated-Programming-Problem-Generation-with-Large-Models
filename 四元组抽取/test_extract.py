from __future__ import annotations

import logging
import unittest

from extract import RateLimiter, extract_single_dimension, validate_input_structure_result


class FakeClient:
    def __init__(self, result):
        self.result = result

    def chat_json(self, system_prompt, user_prompt, temperature=0.4):
        return self.result


class InputStructureValidationTests(unittest.TestCase):
    def test_validate_composite_requires_role_description(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            r"components\[0\]\.role_description 必须是非空字符串",
        ):
            validate_input_structure_result(
                {
                    "type": "composite",
                    "length": {"min": None, "max": None},
                    "value_range": {"min": None, "max": None},
                    "properties": {},
                    "components": [
                        {
                            "role": "queries",
                            "type": "array",
                            "length": {"min": 1, "max": 5},
                            "value_range": {"min": 0, "max": 20},
                            "properties": {},
                        }
                    ],
                }
            )

    def test_validate_composite_accepts_role_description(self) -> None:
        validate_input_structure_result(
            {
                "type": "composite",
                "length": {"min": None, "max": None},
                "value_range": {"min": None, "max": None},
                "properties": {},
                "components": [
                    {
                        "role": "queries",
                        "role_description": "online query stream",
                        "type": "array",
                        "length": {"min": 1, "max": 5},
                        "value_range": {"min": 0, "max": 20},
                        "properties": {"online_queries": True},
                    }
                ],
            }
        )

    def test_validate_non_composite_keeps_existing_behavior(self) -> None:
        validate_input_structure_result(
            {
                "type": "array",
                "length": {"min": 1, "max": 5},
                "value_range": {"min": 0, "max": 20},
                "properties": {},
            }
        )

    def test_extract_single_dimension_marks_invalid_composite_as_failed(self) -> None:
        result = extract_single_dimension(
            client=FakeClient(
                {
                    "type": "composite",
                    "length": {"min": None, "max": None},
                    "value_range": {"min": None, "max": None},
                    "properties": {},
                    "components": [
                        {
                            "role": "queries",
                            "type": "array",
                            "length": {"min": 1, "max": 5},
                            "value_range": {"min": 0, "max": 20},
                            "properties": {},
                        }
                    ],
                }
            ),
            problem={
                "problem_id": "demo",
                "source": {"source_name": "cf"},
                "title": "",
                "description": "",
            },
            dimension_name="input_structure",
            rate_limiter=RateLimiter(min_interval=0.0),
            logger=logging.getLogger("extract-test"),
            temperature=0.0,
        )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["result"], {})
        self.assertIn("components[0].role_description", result["error"])


if __name__ == "__main__":
    unittest.main()
