from __future__ import annotations

import unittest

from prompts.bruteforce_solution import prompt_bruteforce_solution
from prompts.standard_solution import prompt_standard_solution
from prompts.tool_generation import (
    prompt_adversarial_test_input,
    prompt_checker,
    prompt_random_test_input,
    prompt_small_challenge_test_input,
)
from prompts.wrong_solution import (
    prompt_fixed_category_wrong_solution,
    prompt_schema_mistake_analysis,
    prompt_strategy_wrong_solution,
)


class PromptModuleTests(unittest.TestCase):
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
        self.modules = [
            prompt_random_test_input,
            prompt_adversarial_test_input,
            prompt_small_challenge_test_input,
            prompt_checker,
            prompt_standard_solution,
            prompt_bruteforce_solution,
            prompt_fixed_category_wrong_solution,
            prompt_schema_mistake_analysis,
            prompt_strategy_wrong_solution,
        ]

    def test_modules_expose_uniform_build_functions(self) -> None:
        for module in self.modules:
            self.assertTrue(callable(module.build_system_prompt))
            self.assertTrue(callable(module.build_user_prompt))
            self.assertTrue(module.build_system_prompt().strip())

    def test_all_system_prompts_require_single_json_object(self) -> None:
        for module in self.modules:
            self.assertIn("最终只输出单个 JSON 对象", module.build_system_prompt())

    def test_tool_prompts_use_only_problem_fields(self) -> None:
        prompts = [
            prompt_random_test_input.build_user_prompt(self.artifact),
            prompt_adversarial_test_input.build_user_prompt(self.artifact),
            prompt_small_challenge_test_input.build_user_prompt(self.artifact),
            prompt_checker.build_user_prompt(self.artifact),
            prompt_fixed_category_wrong_solution.build_user_prompt(self.artifact, "目标/输出义务误读"),
        ]
        for prompt in prompts:
            self.assertIn("output_format:", prompt)
            self.assertIn("输出一个整数。", prompt)
            self.assertNotIn("input_structure:", prompt)
            self.assertNotIn("core_constraints:", prompt)

    def test_schema_prompts_include_schema_four_fields(self) -> None:
        prompts = [
            prompt_standard_solution.build_user_prompt(self.artifact),
            prompt_bruteforce_solution.build_user_prompt(self.artifact),
            prompt_schema_mistake_analysis.build_user_prompt(self.artifact),
            prompt_strategy_wrong_solution.build_user_prompt(
                self.artifact,
                {
                    "title": "使用 32 位整数",
                    "wrong_idea": "用 int32 累加所有元素。",
                    "plausible_reason": "样例数值很小。",
                    "failure_reason": "答案可能超过 32 位。",
                    "trigger_case": "大 n 且元素绝对值很大。",
                },
            ),
        ]
        for prompt in prompts:
            for field in ["input_structure:", "core_constraints:", "objective:", "invariant:"]:
                self.assertIn(field, prompt)

    def test_random_and_adversarial_prompts_contain_cyaron_constraints(self) -> None:
        for prompt in [
            prompt_random_test_input.build_user_prompt(self.artifact),
            prompt_adversarial_test_input.build_user_prompt(self.artifact),
        ]:
            self.assertIn("cyaron==0.7.0", prompt)
            self.assertIn("import cyaron as cy", prompt)
            self.assertIn("cy.Integer()", prompt)
            self.assertIn("cy.randint", prompt)
            self.assertIn("cy.String.random", prompt)
            self.assertIn("generate_test_input() 不接收任何参数", prompt)
            self.assertIn("constraint_analysis", prompt)
            self.assertIn("generate_test_input_code", prompt)
            self.assertIn("validate_test_input_code", prompt)
            self.assertIn("输出样例（仅供格式参考）", prompt)
            self.assertIn("不得复用样例变量、约束", prompt)

    def test_small_challenge_prompt_only_requests_input(self) -> None:
        prompt = prompt_small_challenge_test_input.build_user_prompt(self.artifact)
        self.assertIn('"test_input"', prompt)
        self.assertIn("不要输出用于生成它的代码", prompt)
        self.assertNotIn("import cyaron as cy", prompt)
        self.assertNotIn("generate_test_input_code", prompt)

    def test_solution_and_wrong_solution_prompts_use_solve_interface(self) -> None:
        prompts = [
            prompt_standard_solution.build_user_prompt(self.artifact),
            prompt_bruteforce_solution.build_user_prompt(self.artifact),
            prompt_fixed_category_wrong_solution.build_user_prompt(self.artifact, "核心约束简化"),
            prompt_strategy_wrong_solution.build_user_prompt(
                self.artifact,
                {
                    "title": "忽略负数",
                    "wrong_idea": "只累加正数。",
                    "plausible_reason": "样例都是正数。",
                    "failure_reason": "题面允许负数。",
                    "trigger_case": "包含负数的数组。",
                },
            ),
        ]
        for prompt in prompts:
            self.assertIn("solve(input_str: str) -> str", prompt)
            self.assertNotIn("slove", prompt)

    def test_standard_and_bruteforce_json_contracts(self) -> None:
        standard_prompt = prompt_standard_solution.build_user_prompt(self.artifact)
        brute_prompt = prompt_bruteforce_solution.build_user_prompt(self.artifact)

        for field in ["status", "block_reason", "code", "time_complexity", "space_complexity"]:
            self.assertIn(f'"{field}"', standard_prompt)
            self.assertIn(f'"{field}"', brute_prompt)
        self.assertIn('"solution_markdown"', standard_prompt)
        self.assertIn('"bruteforce_markdown"', brute_prompt)
        self.assertIn('status="blocked"', standard_prompt)
        self.assertIn('status="blocked"', brute_prompt)

    def test_checker_json_contract_has_two_branches(self) -> None:
        prompt = prompt_checker.build_user_prompt(self.artifact)
        for marker in [
            '"needs_checker": false',
            '"reason"',
            '"needs_checker": true',
            '"output_rule_analysis"',
            '"checker_code"',
            '"notes"',
            "check_output(input_string, output_string)",
        ]:
            self.assertIn(marker, prompt)
        self.assertIn("唯一答案题示例", prompt)
        self.assertIn("普通标准输出比对即可，不需要 checker", prompt)
        self.assertIn("多解构造题示例", prompt)
        self.assertIn("不是与某个固定输出比较", prompt)

    def test_schema_mistake_strategy_contract(self) -> None:
        prompt = prompt_schema_mistake_analysis.build_user_prompt(self.artifact)
        for field in ["strategies", "title", "wrong_idea", "plausible_reason", "failure_reason", "trigger_case"]:
            self.assertIn(f'"{field}"', prompt)
        self.assertIn("不设置固定数量", prompt)

    def test_fixed_wrong_categories_are_exact_and_unknown_rejected(self) -> None:
        self.assertEqual(
            prompt_fixed_category_wrong_solution.FIXED_WRONG_CATEGORIES,
            (
                "目标/输出义务误读",
                "核心约束简化",
                "invariant 误读",
                "边界/最小性错误",
                "复杂度/规模误判",
            ),
        )
        for category in prompt_fixed_category_wrong_solution.FIXED_WRONG_CATEGORIES:
            prompt = prompt_fixed_category_wrong_solution.build_user_prompt(self.artifact, category)
            self.assertIn(category, prompt)
            self.assertIn('"code"', prompt)

        with self.assertRaisesRegex(ValueError, "未知固定错误解类别"):
            prompt_fixed_category_wrong_solution.build_user_prompt(self.artifact, "其它错误")

    def test_strategy_wrong_solution_rejects_strategy_list(self) -> None:
        with self.assertRaisesRegex(ValueError, "单条策略"):
            prompt_strategy_wrong_solution.build_user_prompt(self.artifact, [{"title": "错误策略"}])


if __name__ == "__main__":
    unittest.main()
