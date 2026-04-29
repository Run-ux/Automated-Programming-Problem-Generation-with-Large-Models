from __future__ import annotations

import inspect
import unittest

from prompts import prompt_revision_advisor, prompt_sections
from prompts.bruteforce_solution import prompt_bruteforce_solution
from prompts.standard_solution import prompt_standard_solution
from prompts.tool_generation import (
    prompt_adversarial_test_input,
    prompt_checker,
    prompt_random_test_input,
    prompt_small_challenge_test_input,
    prompt_validator,
)
from prompts.wrong_solution import (
    prompt_fixed_category_wrong_solution,
    prompt_schema_mistake_analysis,
    prompt_strategy_wrong_solution,
)


class PromptBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = {
            "problem_id": "SUM",
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
                "core_constraints": {"sum_range": "答案可能超 32 位"},
                "objective": {"goal": "输出数组元素和"},
                "invariant": {"prefix_sum": "前缀和增量等于当前元素"},
            },
            "algorithmic_delta_claim": {"new_solver_core": "线性扫描累加"},
        }
        self.revision_context = {
            "summary": [{"category": "standard_bruteforce_mismatch", "count": 1, "severity": "blocker"}],
            "role_diagnostics": {
                "StandardSolutionGenerator": [
                    {
                        "category": "standard_bruteforce_mismatch",
                        "title": "标准解与正确暴力解不一致",
                        "detail": "测试 small 上标准解输出 5，正确暴力解输出 6。",
                    }
                ]
            },
        }

    def test_prompt_modules_expose_uniform_build_functions(self) -> None:
        modules = [
            prompt_standard_solution,
            prompt_bruteforce_solution,
            prompt_validator,
            prompt_checker,
            prompt_random_test_input,
            prompt_adversarial_test_input,
            prompt_small_challenge_test_input,
            prompt_fixed_category_wrong_solution,
            prompt_schema_mistake_analysis,
            prompt_strategy_wrong_solution,
            prompt_revision_advisor,
        ]

        for module in modules:
            self.assertTrue(callable(module.build_system_prompt))
            self.assertTrue(callable(module.build_user_prompt))
            self.assertTrue(module.build_system_prompt().strip())

    def test_solution_prompts_use_artifact_fields_without_delta_claim(self) -> None:
        prompts = [
            prompt_standard_solution.build_user_prompt(self.context, self.revision_context),
            prompt_bruteforce_solution.build_user_prompt(self.context, self.revision_context),
        ]
        for prompt in prompts:
            self.assertIn('"title": "SUM"', prompt)
            self.assertIn('"input_structure"', prompt)
            self.assertIn('"output_format": "输出一个整数。"', prompt)
            self.assertIn('"invariant"', prompt)
            self.assertIn("solve(input_str: str) -> str", prompt)
            self.assertNotIn("algorithmic_delta_claim", prompt)
            self.assertNotIn("new_solver_core", prompt)
            self.assertNotIn("execution_spec", prompt)

    def test_module_system_prompts_use_explicit_goals(self) -> None:
        standard_prompt = prompt_standard_solution.build_system_prompt()
        brute_prompt = prompt_bruteforce_solution.build_system_prompt()
        validator_system_prompt = prompt_validator.build_system_prompt()
        checker_system_prompt = prompt_checker.build_system_prompt()
        random_system_prompt = prompt_random_test_input.build_system_prompt()
        adversarial_system_prompt = prompt_adversarial_test_input.build_system_prompt()
        small_system_prompt = prompt_small_challenge_test_input.build_system_prompt()
        analyzer_prompt = prompt_schema_mistake_analysis.build_system_prompt()
        fixed_wrong_prompt = prompt_fixed_category_wrong_solution.build_system_prompt()
        strategy_wrong_prompt = prompt_strategy_wrong_solution.build_system_prompt()

        self.assertIn("题面和 schema 四字段", standard_prompt)
        self.assertIn("正确但允许很慢的暴力解", brute_prompt)
        self.assertIn("只生成 validator", validator_system_prompt)
        self.assertIn("只生成 checker", checker_system_prompt)
        self.assertIn("随机测试输入生成器", random_system_prompt)
        self.assertIn("边界与最坏情况测试输入生成器", adversarial_system_prompt)
        self.assertIn("小规模高区分度", small_system_prompt)
        self.assertIn("自由提炼真实错误策略", analyzer_prompt)
        self.assertIn("完整 Python 代码", fixed_wrong_prompt)
        self.assertIn("solve(input_str: str) -> str", strategy_wrong_prompt)
        self.assertNotIn("OracleGenerator", brute_prompt)
        self.assertNotIn("execution_spec", standard_prompt + brute_prompt + analyzer_prompt)

    def test_validator_and_checker_prompts_use_schema_and_checker_self_checks(self) -> None:
        validator_prompt = prompt_validator.build_user_prompt(self.context, None)
        checker_prompt = prompt_checker.build_user_prompt(
            self.context,
            {"name": "validator", "role": "validator", "code": "def validate(input_str): return True"},
            None,
        )

        self.assertIn("input_structure/core_constraints", validator_prompt)
        self.assertIn("check(input_str: str, output_str: str, expected_str: str | None) -> bool", checker_prompt)
        for marker in ["内部 CoT", "空输出", "多余 token", "样例", "多解语义", "invariant"]:
            self.assertIn(marker, checker_prompt)
        self.assertNotIn("execution_spec", checker_prompt)

    def test_test_input_prompts_split_three_artifacts(self) -> None:
        random_prompt = prompt_random_test_input.build_user_prompt(self.context, None)
        adversarial_prompt = prompt_adversarial_test_input.build_user_prompt(self.context, None)
        small_prompt = prompt_small_challenge_test_input.build_user_prompt(self.context, None)

        for prompt in [random_prompt, adversarial_prompt]:
            self.assertIn("cyaron==0.7.0", prompt)
            self.assertIn("import cyaron as cy", prompt)
            self.assertIn("generate_test_input() -> str", prompt)
            self.assertNotIn("generate_tests()", prompt)

        self.assertIn("直接输出完整输入", small_prompt)
        self.assertIn("expect_bruteforce", small_prompt)
        self.assertNotIn("import cyaron", small_prompt)

    def test_fixed_category_wrong_prompts_cover_all_categories(self) -> None:
        self.assertEqual(len(prompt_sections.FIXED_WRONG_CATEGORIES), 5)
        for category in prompt_sections.FIXED_WRONG_CATEGORIES:
            prompt = prompt_fixed_category_wrong_solution.build_user_prompt(self.context, category)
            self.assertIn(category, prompt)
            self.assertIn("语言使用：python", prompt)
            self.assertIn("output_format", prompt)
            self.assertIn("invariant", prompt)
            self.assertNotIn("algorithmic_delta_claim", prompt)

    def test_free_strategy_prompts_do_not_set_fixed_count(self) -> None:
        analysis_prompt = prompt_schema_mistake_analysis.build_user_prompt(self.context, None)
        self.assertIn("数量由你根据具体题目决定，不设置固定数量", analysis_prompt)
        self.assertNotIn("至少生成", analysis_prompt)
        self.assertNotIn("默认数量", analysis_prompt)

        strategy_prompt = prompt_strategy_wrong_solution.build_user_prompt(
            self.context,
            {
                "strategy_id": "overflow_32bit",
                "category": "规模误判",
                "wrong_strategy": "使用 32 位整数累加。",
                "failure_reason": "大数求和溢出。",
            },
        )
        self.assertIn("overflow_32bit", strategy_prompt)
        self.assertIn("最终只输出完整 Python 代码", strategy_prompt)
        self.assertNotIn("一次性生成全部", strategy_prompt)

    def test_prompt_modules_no_longer_depend_on_shared_composer_helpers(self) -> None:
        modules = [
            prompt_standard_solution,
            prompt_bruteforce_solution,
            prompt_validator,
            prompt_checker,
            prompt_random_test_input,
            prompt_adversarial_test_input,
            prompt_small_challenge_test_input,
            prompt_fixed_category_wrong_solution,
            prompt_schema_mistake_analysis,
            prompt_strategy_wrong_solution,
            prompt_revision_advisor,
        ]

        for module in modules:
            source = inspect.getsource(module)
            self.assertNotIn("compose_prompt", source)
            self.assertNotIn("build_json_generation_system_prompt", source)
            self.assertNotIn("build_text_code_generation_system_prompt", source)
            self.assertNotIn("fixed_category_template", source)

        prompt_sections_source = inspect.getsource(prompt_sections)
        self.assertFalse(hasattr(prompt_sections, "compose_prompt"))
        self.assertFalse(hasattr(prompt_sections, "build_json_generation_system_prompt"))
        self.assertFalse(hasattr(prompt_sections, "build_text_code_generation_system_prompt"))
        self.assertFalse(hasattr(prompt_sections, "build_json_hard_constraints"))
        self.assertFalse(hasattr(prompt_sections, "fixed_category_template"))
        self.assertNotIn("def compose_prompt", prompt_sections_source)
        self.assertNotIn("def build_json_generation_system_prompt", prompt_sections_source)
        self.assertNotIn("def build_text_code_generation_system_prompt", prompt_sections_source)
        self.assertNotIn("def build_json_hard_constraints", prompt_sections_source)
        self.assertNotIn("def fixed_category_template", prompt_sections_source)


if __name__ == "__main__":
    unittest.main()
