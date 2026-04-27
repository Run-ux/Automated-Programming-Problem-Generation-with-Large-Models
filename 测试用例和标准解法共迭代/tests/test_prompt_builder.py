from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prompt_builder import (  # noqa: E402
    build_checker_prompt,
    build_code_system_prompt,
    build_oracle_prompt,
    build_revision_advisor_system_prompt,
    build_revision_advisor_user_prompt,
    build_schema_aware_wrong_solution_prompt,
    build_schema_mistake_analysis_prompt,
    build_spec_system_prompt,
    build_spec_user_prompt,
    build_standard_solution_prompt,
    build_test_generator_prompt,
    build_tools_prompt,
    build_validator_prompt,
    build_weak_player_prompt,
)


class PromptBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = {
            "problem_id": "SUM",
            "statement_markdown": "给定 n 个整数，输出它们的和。",
            "generated_problem": {
                "title": "求和",
                "samples": [{"input": "3\n1 2 3\n", "output": "6\n"}],
            },
            "new_schema": {"problem_id": "SUM"},
            "algorithmic_delta_claim": {"new_solver_core": "线性扫描累加"},
        }
        self.spec = {
            "problem_id": "SUM",
            "input_contract": {"format": "第一行 n，第二行 n 个整数"},
            "output_contract": {"type": "单个整数"},
            "judge_type": "exact",
            "oracle_limits": {"max_n": 8},
            "test_buckets": [{"name": "basic", "purpose": "基础正确性", "size_intent": "small"}],
            "sample_tests": [{"input": "3\n1 2 3\n", "output": "6\n"}],
            "performance_limits": {"max_n": 200000},
            "ambiguity_notes": ["未明确说明整数是否有负数。"],
        }
        self.revision_context = {
            "summary": [
                {
                    "category": "standard_oracle_mismatch",
                    "count": 1,
                    "severity": "blocker",
                    "representative_sources": ["basic"],
                    "titles": ["标准解与 oracle 不一致"],
                },
                {
                    "category": "validator_rejects_generated_case",
                    "count": 1,
                    "severity": "high",
                    "representative_sources": ["edge"],
                    "titles": ["validator 拒绝测试"],
                },
                {
                    "category": "wrong_solution_survived",
                    "count": 1,
                    "severity": "high",
                    "representative_sources": [],
                    "titles": ["错误解存活"],
                },
            ],
            "failed_hard_checks": ["standard_oracle_mismatch"],
            "role_diagnostics": {
                "StandardSolutionGenerator": [
                    {
                        "category": "standard_oracle_mismatch",
                        "severity": "blocker",
                        "title": "标准解与 oracle 不一致",
                        "detail": "测试 basic 上标准解与 oracle 输出不同。",
                        "fix_hint": "定位反例。",
                        "advisor_revision": {
                            "root_cause": "标准解在 basic 输入上少累计了一个数。",
                            "revision_advice": "修改 StandardSolutionGenerator 的累加路径，用 basic 输入验证输出必须从 5 变为 6。",
                            "target_roles": ["StandardSolutionGenerator"],
                            "evidence_used": ["basic", "首个不同 token"],
                            "confidence": "high",
                            "risk_notes": "",
                        },
                        "target_roles": ["StandardSolutionGenerator", "OracleGenerator"],
                        "evidence": {"test": {"source": "basic"}},
                        "diff": {
                            "first_different_token": {"index": 0, "standard": "5", "oracle": "6"},
                            "first_different_line": {"index": 0, "standard": "5", "oracle": "6"},
                        },
                    }
                ],
                "OracleGenerator": [
                    {
                        "category": "oracle_failed",
                        "severity": "high",
                        "title": "oracle 执行失败",
                        "detail": "oracle 在 small_random 上漏掉重复元素情况。",
                        "fix_hint": "修正暴力逻辑。",
                        "target_roles": ["OracleGenerator"],
                        "evidence": {"test": {"source": "small_random"}},
                    }
                ],
                "ToolGenerator": [
                    {
                        "category": "validator_rejects_generated_case",
                        "severity": "high",
                        "title": "validator 拒绝测试",
                        "detail": "validator 拒绝了 test_generator 生成的边界测试。",
                        "fix_hint": "修正输入约束或测试生成逻辑。",
                        "target_roles": ["ToolGenerator"],
                        "evidence": {"test": {"source": "edge"}},
                    }
                ],
                "WeakPlayerGenerator": [
                    {
                        "category": "wrong_solution_survived",
                        "severity": "high",
                        "title": "错误解存活",
                        "detail": "当前测试没有杀死 surviving_wrong_1。",
                        "fix_hint": "补充反例。",
                        "target_roles": ["WeakPlayerGenerator"],
                        "evidence": {},
                    }
                ],
                "SchemaMistakeAnalyzer": [],
                "SchemaAwareWrongSolutionGenerator": [],
            },
            "surviving_wrong_solution_details": [
                {
                    "solution_id": "surviving_wrong_1",
                    "bug_type": "boundary_misread",
                    "expected_failure": "边界输入失败。",
                    "reason": "当前测试未能杀掉该候选解。",
                    "passed_tests": ["basic"],
                    "killed_tests": [],
                    "metadata": {"target_failure_bucket": "边界条件"},
                }
            ],
        }

    def test_build_spec_system_prompt_contains_conservative_rules(self) -> None:
        prompt = build_spec_system_prompt()

        self.assertIn("忠实抽取题面与 schema 信息 > 保守处理歧义 > 产出可执行规格", prompt)
        self.assertIn("只输出严格 JSON 对象", prompt)
        self.assertIn("任务目标：", prompt)
        self.assertIn("硬约束：", prompt)
        self.assertIn("执行准则：", prompt)
        self.assertIn("未给出的输入范围、输出唯一性、特殊判题规则或额外保证统一记录到 ambiguity_notes", prompt)
        self.assertIn("ambiguity_notes", prompt)

    def test_build_spec_user_prompt_contains_field_contracts_and_revision_guidance(self) -> None:
        prompt = build_spec_user_prompt(self.context, self.revision_context)

        self.assertIn("任务目标：", prompt)
        self.assertIn("输出合同：", prompt)
        self.assertIn("硬约束：", prompt)
        self.assertIn("执行准则：", prompt)
        self.assertIn("修订上下文要求：", prompt)
        self.assertIn("输入上下文：", prompt)
        self.assertIn("judge_type: 只能是 exact 或 checker", prompt)
        self.assertIn("oracle_limits: 给出小规模暴力 oracle 可承受的明确范围", prompt)
        self.assertIn("test_buckets: 给出后续测试生成要覆盖的测试桶", prompt)
        self.assertIn("ambiguity_notes: 集中记录缺失、冲突、无法确定的信息", prompt)
        self.assertIn("优先修复 blocker 类问题", prompt)
        self.assertIn("judge_type 的边界必须明确", prompt)
        self.assertIn("standard_oracle_mismatch", prompt)
        self.assertIn('"problem_id": "SUM"', prompt)

    def test_build_code_system_prompt_has_role_specific_goals(self) -> None:
        standard_prompt = build_code_system_prompt("StandardSolutionGenerator")
        oracle_prompt = build_code_system_prompt("OracleGenerator")
        tools_prompt = build_code_system_prompt("ToolGenerator")
        weak_prompt = build_code_system_prompt("WeakPlayerGenerator")

        self.assertIn("任务目标：", standard_prompt)
        self.assertIn("硬约束：", standard_prompt)
        self.assertIn("执行准则：", standard_prompt)
        self.assertIn("在内部完成约束抽取、算法选择、边界检查和最小自检", standard_prompt)
        self.assertIn("中间推理、草稿和候选方案不写入最终输出", standard_prompt)
        self.assertIn("内部解题流程", standard_prompt)
        self.assertIn("先抽取输入、输出、判题方式与复杂度约束", standard_prompt)
        self.assertIn("选择最简单且能满足约束的正确算法", standard_prompt)
        self.assertIn("实现前做一次边界覆盖检查", standard_prompt)
        self.assertIn("复杂度达标", standard_prompt)
        self.assertIn("先在内部判定合适的暴力空间", oracle_prompt)
        self.assertIn("生成职责分离的 validator、checker、test_generator", tools_prompt)
        self.assertIn("先模拟错误理解路径", weak_prompt)
        self.assertNotEqual(standard_prompt, oracle_prompt)

        validator_prompt = build_code_system_prompt("ValidatorGenerator")
        checker_prompt = build_code_system_prompt("CheckerGenerator")
        test_generator_prompt = build_code_system_prompt("TestGenerator")

        self.assertIn("只生成 validator", validator_prompt)
        self.assertIn("不做求解、不校验输出", validator_prompt)
        self.assertIn("只生成 checker", checker_prompt)
        self.assertIn("严格服从 execution_spec.judge_type", checker_prompt)
        self.assertIn("只生成 test_generator", test_generator_prompt)
        self.assertIn("默认所有生成输入都应被 validator 接受", test_generator_prompt)

    def test_revision_advisor_prompts_require_specific_json_advice(self) -> None:
        system_prompt = build_revision_advisor_system_prompt()
        user_prompt = build_revision_advisor_user_prompt(
            {
                "diagnostic": {
                    "category": "standard_oracle_mismatch",
                    "severity": "blocker",
                    "title": "标准解与 oracle 不一致",
                    "detail": "basic 上输出不同。",
                    "target_roles": ["StandardSolutionGenerator", "OracleGenerator"],
                },
                "evidence": {"test": {"source": "basic"}, "input": {"content": "3\n1 2 3\n"}},
                "diff": {"first_different_token": {"index": 0, "standard": "5", "oracle": "6"}},
            }
        )

        self.assertIn("错误回流修订顾问", system_prompt)
        self.assertIn("禁止泛泛建议", system_prompt)
        self.assertIn("root_cause", user_prompt)
        self.assertIn("revision_advice", user_prompt)
        self.assertIn("必须具体说明改什么、为什么、用哪个证据验证", user_prompt)
        self.assertIn("first_different_token", user_prompt)

    def test_build_standard_solution_prompt_emphasizes_contract_reasoning_and_revision(self) -> None:
        prompt = build_standard_solution_prompt(self.context, self.spec, self.revision_context)

        self.assertIn("code: 完整可运行的 Python 代码字符串，必须实现 solve(input_str: str) -> str。", prompt)
        self.assertIn("code 只定义 solve(input_str: str) -> str", prompt)
        self.assertIn("先严格服从 execution_spec，再根据 revision_context 修复已暴露问题", prompt)
        self.assertIn("如果 execution_spec.ambiguity_notes 非空，只能按最保守、最可执行的方式实现", prompt)
        self.assertIn("在内部列出真正决定算法的约束", prompt)
        self.assertIn("判断是否存在多解、构造或证书语义", prompt)
        self.assertIn("实现前至少检查 5 类测试用例：基础、边界、随机、对抗、性能", prompt)
        self.assertIn("自检 code、algorithm、correctness、time_complexity、space_complexity、notes 是否彼此一致", prompt)
        guidance = prompt.split("输入上下文", 1)[0]
        self.assertIn("StandardSolutionGenerator 定向诊断", guidance)
        self.assertIn("测试 basic 上标准解与 oracle 输出不同。", guidance)
        self.assertIn("advisor修订建议", guidance)
        self.assertIn("用 basic 输入验证输出必须从 5 变为 6", guidance)
        self.assertNotIn("oracle 在 small_random 上漏掉重复元素情况。", guidance)

    def test_incremental_revision_prompt_mentions_active_context_and_current_artifact(self) -> None:
        revision_context = {
            **self.revision_context,
            "active_revision_context": self.revision_context,
            "revision_mode": "incremental_patch",
            "current_artifact": {
                "standard_solution": {
                    "name": "standard_solution",
                    "role": "standard_solution",
                    "code": "def solve(input_str: str) -> str:\n    return '0'\n",
                    "metadata": {"algorithm": "旧实现"},
                }
            },
            "frozen_contract_summary": {
                "problem_id": "SUM",
                "judge_type": "exact",
                "input_contract": {"format": "第一行 n，第二行 n 个整数"},
                "output_contract": {"type": "单个整数"},
            },
        }

        prompt = build_standard_solution_prompt(self.context, self.spec, revision_context)
        guidance = prompt.split("输入上下文", 1)[0]

        self.assertIn("当前是增量修订轮", guidance)
        self.assertIn("active_revision_context 中仍未解决的问题", guidance)
        self.assertIn("当前工作副本摘要", guidance)
        self.assertIn("最小必要修改", guidance)
        self.assertIn("已通过路径的冻结合同", guidance)
        self.assertIn("输出仍需是完整替换产物", guidance)

    def test_build_oracle_prompt_emphasizes_scope_and_independence(self) -> None:
        prompt = build_oracle_prompt(self.context, self.spec, self.revision_context)

        self.assertIn("oracle_scope: 清晰描述 oracle 保证正确的小规模范围", prompt)
        self.assertIn("code 只定义 solve(input_str: str) -> str", prompt)
        self.assertIn("采用与标准解尽量独立的推理路径", prompt)
        self.assertIn("优先使用全枚举、状态搜索、直接定义校验或朴素模拟", prompt)
        self.assertIn("tiny-scope 必须具体到输入规模、结构限制或枚举空间", prompt)
        self.assertIn("所有依赖假设都必须严格落在 oracle_scope 内", prompt)
        guidance = prompt.split("输入上下文", 1)[0]
        self.assertIn("OracleGenerator 定向诊断", guidance)
        self.assertIn("oracle 在 small_random 上漏掉重复元素情况。", guidance)
        self.assertNotIn("validator 拒绝了 test_generator 生成的边界测试。", guidance)

    def test_build_tools_prompt_emphasizes_role_boundaries_and_test_planning(self) -> None:
        prompt = build_tools_prompt(self.context, self.spec, self.revision_context)

        self.assertIn("validator 只验证输入是否合法，不做求解", prompt)
        self.assertIn("checker 必须服从 execution_spec.judge_type", prompt)
        self.assertIn("expect_oracle、is_sample、is_large、metadata", prompt)
        self.assertIn("仍存活的错误解详情：surviving_wrong_1", prompt)
        self.assertIn("validator -> checker -> test_generator", prompt)
        self.assertIn("checker 校验输出格式和答案合法性，不能隐含标准解算法", prompt)
        self.assertIn("test_generator 生成的每个 input 都应能被 validator 接受", prompt)
        self.assertIn("测试覆盖按基础、边界、随机、对抗、性能逐项判断是否相关", prompt)
        self.assertIn("若 oracle_limits 支持，应显式标注哪些测试 expect_oracle=True", prompt)
        self.assertIn("validator 拒绝了 test_generator 生成的边界测试。", prompt)

    def test_split_tool_prompts_have_separate_output_contracts_and_tool_diagnostics(self) -> None:
        validator_prompt = build_validator_prompt(self.context, self.spec, self.revision_context)
        checker_prompt = build_checker_prompt(
            self.context,
            self.spec,
            {
                "name": "validator",
                "role": "validator",
                "code": "def validate(input_str: str) -> bool:\n    return True\n",
                "metadata": {"notes": "validator notes", "stage": "validator"},
            },
            self.revision_context,
        )
        test_generator_prompt = build_test_generator_prompt(
            self.context,
            self.spec,
            {
                "name": "validator",
                "role": "validator",
                "code": "def validate(input_str: str) -> bool:\n    return True\n",
                "metadata": {"notes": "validator notes", "stage": "validator"},
            },
            {
                "name": "checker",
                "role": "checker",
                "code": "def check(input_str: str, output_str: str, expected_str: str | None) -> bool:\n    return True\n",
                "metadata": {"notes": "checker notes", "stage": "checker"},
            },
            self.revision_context,
        )

        validator_contract = validator_prompt.split("硬约束：", 1)[0]
        checker_contract = checker_prompt.split("硬约束：", 1)[0]
        test_generator_contract = test_generator_prompt.split("硬约束：", 1)[0]

        self.assertIn("validator_code", validator_contract)
        self.assertNotIn("checker_code", validator_contract)
        self.assertNotIn("test_generator_code", validator_contract)
        self.assertIn("ToolGenerator 定向诊断", validator_prompt)
        self.assertIn("validator 拒绝了 test_generator 生成的边界测试。", validator_prompt)

        self.assertIn("checker_code", checker_contract)
        self.assertNotIn("validator_code", checker_contract)
        self.assertNotIn("test_generator_code", checker_contract)
        self.assertIn("validator_artifact", checker_prompt)
        self.assertIn("validator notes", checker_prompt)
        self.assertIn("ToolGenerator 定向诊断", checker_prompt)

        self.assertIn("test_generator_code", test_generator_contract)
        self.assertNotIn("validator_code", test_generator_contract)
        self.assertNotIn("checker_code", test_generator_contract)
        self.assertIn("validator_artifact", test_generator_prompt)
        self.assertIn("checker_artifact", test_generator_prompt)
        self.assertIn("checker notes", test_generator_prompt)
        self.assertIn("仍存活的错误解详情：surviving_wrong_1", test_generator_prompt)

    def test_build_weak_player_prompt_emphasizes_realistic_wrong_reasoning(self) -> None:
        prompt = build_weak_player_prompt(
            {
                "problem_id": "SUM",
                "statement_markdown": "给定 n 个整数，输出它们的和。",
                "generated_problem": {"title": "求和"},
            },
            self.revision_context,
        )

        self.assertIn("长度为 3 到 5 的列表；优先生成 5 份", prompt)
        self.assertIn("player_profile: 选手画像", prompt)
        self.assertIn("target_failure_bucket: 目标失败桶", prompt)
        self.assertIn("不能假设隐藏 schema、隐藏数据范围或内部规格", prompt)
        self.assertIn("expected_failure: 具体说明它会在哪类测试上失败", prompt)
        self.assertIn("小规模样例/直观用例可过但隐藏小规模反例不过", prompt)
        self.assertIn("大规模复杂度不过", prompt)
        self.assertIn("边界条件不过", prompt)
        self.assertIn("最坏情况不过", prompt)
        self.assertIn("小规模但结构刁钻的用例不过", prompt)
        self.assertIn("样例拟合型、贪心过度自信型、复杂度误判型、边界粗心型、实现细节薄弱型", prompt)
        self.assertIn("先模拟一种常见但错误的理解，再据此写代码", prompt)
        self.assertIn("边界、贪心、复杂度、重复值、排序稳定性、索引偏移或输入格式误读", prompt)
        self.assertIn("避免同质化", prompt)
        self.assertIn("错误解必须有竞争力", prompt)
        self.assertIn("expected_failure 要具体描述失败输入结构或输出义务", prompt)
        self.assertIn("仍存活的错误解详情：surviving_wrong_1", prompt)

    def test_schema_mistake_prompt_contains_schema_mapping_contract(self) -> None:
        prompt = build_schema_mistake_analysis_prompt(self.context, self.spec, self.revision_context)

        self.assertIn("new_schema", prompt)
        self.assertIn("schema_basis", prompt)
        self.assertIn("player_visible_misread", prompt)
        self.assertIn("expected_counterexample_shape", prompt)
        self.assertIn("本阶段只分析误解点，不写代码", prompt)
        self.assertIn("构造输出、证书输出、字典序规范性、耦合约束", prompt)

    def test_schema_aware_wrong_solution_prompt_binds_mistake_points(self) -> None:
        mistake_points = [
            {
                "mistake_id": "ignore_canonical_order",
                "schema_basis": ["objective:construct_canonical_sequence"],
                "player_visible_misread": "只输出任意最长序列。",
                "wrong_strategy": "求出长度后随便回溯一条路径。",
                "target_failure_bucket": "小规模挑战",
                "expected_counterexample_shape": "存在多条同长序列且字典序不同。",
                "triviality_risk": "仍需输出合法长度和序列。",
            }
        ]

        prompt = build_schema_aware_wrong_solution_prompt(self.context, self.spec, mistake_points, self.revision_context)

        self.assertIn("mistake_id", prompt)
        self.assertIn("schema_signals", prompt)
        self.assertIn("schema-aware", prompt)
        self.assertIn("只能从 mistake_points 中选择 mistake_id", prompt)
        self.assertIn("不新增隐藏误解点、隐藏题意或隐藏数据范围", prompt)
        self.assertIn("说明可通过的自然测试和会失败的定向反例", prompt)
        self.assertIn("ignore_canonical_order", prompt)

    def test_revision_guidance_missing_structured_fields_uses_fallback(self) -> None:
        prompt = build_standard_solution_prompt(
            self.context,
            self.spec,
            {"solution_feedback": ["旧格式反馈不再兼容。"]},
        )

        self.assertIn("当前没有结构化 revision_context；若 revision_context 为空，优先保证首轮代码正确、稳健且满足复杂度约束。", prompt)
        self.assertNotIn("优先修复 blocker 类问题", prompt)


if __name__ == "__main__":
    unittest.main()
