from __future__ import annotations

import unittest

from artifact_context import build_prompt_payload, extract_generated_problem, extract_schema_snapshot


class ArtifactContextTests(unittest.TestCase):
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

    def test_extract_generated_problem_uses_output_format(self) -> None:
        problem = extract_generated_problem(self.artifact)
        self.assertEqual(problem["output_format"], "输出一个整数。")
        self.assertNotIn("ouput_format", problem)

    def test_missing_output_format_fails_even_if_typo_field_exists(self) -> None:
        artifact = {
            "generated_problem": {
                "title": "SUM",
                "description": "",
                "input_format": "",
                "ouput_format": "拼写错误字段",
                "constraints": [],
                "samples": [],
                "notes": "",
            }
        }
        with self.assertRaisesRegex(ValueError, "output_format"):
            extract_generated_problem(artifact)

    def test_missing_generated_problem_field_fails_fast(self) -> None:
        artifact = {"generated_problem": dict(self.artifact["generated_problem"])}
        del artifact["generated_problem"]["notes"]
        with self.assertRaisesRegex(ValueError, "notes"):
            extract_generated_problem(artifact)

    def test_extract_schema_snapshot_requires_four_fields(self) -> None:
        schema = extract_schema_snapshot(self.artifact)
        self.assertEqual(set(schema), {"input_structure", "core_constraints", "objective", "invariant"})

    def test_build_prompt_payload_optionally_includes_schema(self) -> None:
        without_schema = build_prompt_payload(self.artifact)
        with_schema = build_prompt_payload(self.artifact, include_schema=True)

        self.assertIn("title", without_schema)
        self.assertNotIn("input_structure", without_schema)
        self.assertIn("input_structure", with_schema)
        self.assertIn("invariant", with_schema)


if __name__ == "__main__":
    unittest.main()

