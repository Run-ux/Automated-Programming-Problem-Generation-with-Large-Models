from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prompt_builder import (  # noqa: E402
    build_code_system_prompt,
    build_oracle_prompt,
    build_spec_system_prompt,
    build_spec_user_prompt,
    build_standard_solution_prompt,
    build_tools_prompt,
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
            "failed_hard_checks": ["standard_oracle_mismatch", "wrong_solution_survived"],
            "solution_feedback": ["测试 basic 上标准解与 oracle 输出不同。"],
            "oracle_feedback": ["oracle 在 small_random 上漏掉重复元素情况。"],
            "tool_feedback": ["validator 拒绝了 test_generator 生成的边界测试。"],
            "test_feedback": ["当前测试没有杀死 surviving_wrong_1。"],
            "surviving_wrong_solutions": ["surviving_wrong_1"],
        }

    def test_build_spec_system_prompt_contains_conservative_rules(self) -> None:
        prompt = build_spec_system_prompt()

        self.assertIn("忠实抽取题面与 schema 信息 > 保守处理歧义 > 产出可执行规格", prompt)
        self.assertIn("只输出严格 JSON 对象", prompt)
        self.assertIn("不要脑补未给出的输入范围、输出唯一性、特殊判题规则", prompt)
        self.assertIn("ambiguity_notes", prompt)

    def test_build_spec_user_prompt_contains_field_contracts_and_revision_guidance(self) -> None:
        prompt = build_spec_user_prompt(self.context, self.revision_context)

        self.assertIn("judge_type: 只能是 exact 或 checker", prompt)
        self.assertIn("oracle_limits: 给出小规模暴力 oracle 可承受的明确范围", prompt)
        self.assertIn("test_buckets: 给出后续测试生成要覆盖的测试桶", prompt)
        self.assertIn("ambiguity_notes: 集中记录缺失、冲突、无法确定的信息", prompt)
        self.assertIn("revision_context 行动指令", prompt)
        self.assertIn("standard_oracle_mismatch", prompt)
        self.assertIn('"problem_id": "SUM"', prompt)

    def test_build_code_system_prompt_has_role_specific_goals(self) -> None:
        standard_prompt = build_code_system_prompt("StandardSolutionGenerator")
        oracle_prompt = build_code_system_prompt("OracleGenerator")
        tools_prompt = build_code_system_prompt("ToolGenerator")
        weak_prompt = build_code_system_prompt("WeakPlayerGenerator")

        self.assertIn("请先在内部完成约束抽取、算法选择、边界检查和最小自检", standard_prompt)
        self.assertIn("不要输出思维链、推导草稿、候选方案列表", standard_prompt)
        self.assertIn("内部解题流程", standard_prompt)
        self.assertIn("先抽取输入、输出、判题方式与复杂度约束", standard_prompt)
        self.assertIn("选择最简单且能满足约束的正确算法", standard_prompt)
        self.assertIn("实现前做一次边界覆盖检查", standard_prompt)
        self.assertIn("复杂度达标", standard_prompt)
        self.assertIn("先在内部判定合适的暴力空间", oracle_prompt)
        self.assertIn("先在内部拆分三者职责", tools_prompt)
        self.assertIn("先模拟错误理解路径", weak_prompt)
        self.assertNotEqual(standard_prompt, oracle_prompt)

    def test_build_standard_solution_prompt_emphasizes_contract_reasoning_and_revision(self) -> None:
        prompt = build_standard_solution_prompt(self.context, self.spec, self.revision_context)

        self.assertIn("code: 完整可运行的 Python 代码字符串，必须实现 solve(input_str: str) -> str。", prompt)
        self.assertIn("先严格服从 execution_spec，再根据 revision_context 修复已暴露问题", prompt)
        self.assertIn("不要输出伪代码、解释性代码块、Markdown 围栏", prompt)
        self.assertIn("如果 execution_spec.ambiguity_notes 非空，不得私自扩展题意", prompt)
        self.assertIn("先列出真正决定算法的约束", prompt)
        self.assertIn("判断是否存在多解、构造或证书语义", prompt)
        self.assertIn("实现前至少在脑中检查 5 类 测试用例：基础、边界、随机、对抗、性能", prompt)
        self.assertIn("确认 code、algorithm、correctness、time_complexity、space_complexity、notes 彼此一致", prompt)
        self.assertIn("标准解反馈", prompt)

    def test_build_oracle_prompt_emphasizes_scope_and_independence(self) -> None:
        prompt = build_oracle_prompt(self.context, self.spec, self.revision_context)

        self.assertIn("oracle_scope: 清晰描述 oracle 保证正确的小规模范围", prompt)
        self.assertIn("尽量与标准解采用不同推理路径", prompt)
        self.assertIn("禁止使用拍脑袋启发式", prompt)
        self.assertIn("先在内部确定 tiny-scope 的真值生成思路", prompt)
        self.assertIn("宁可慢，不可错；宁可笨，不可与标准解同构到一起错", prompt)
        self.assertIn("确认所有依赖的假设都严格落在 oracle_scope 内", prompt)
        self.assertIn("oracle 反馈", prompt)

    def test_build_tools_prompt_emphasizes_role_boundaries_and_test_planning(self) -> None:
        prompt = build_tools_prompt(self.context, self.spec, self.revision_context)

        self.assertIn("validator 只验证输入是否合法，不做求解", prompt)
        self.assertIn("checker 必须服从 execution_spec.judge_type", prompt)
        self.assertIn("expect_oracle、is_sample、is_large、metadata", prompt)
        self.assertIn("仍存活的错误解：surviving_wrong_1", prompt)
        self.assertIn("不要把题解逻辑塞进 validator 或 checker", prompt)
        self.assertIn("先在内部枚举输入合法性规则，再写 validator", prompt)
        self.assertIn("test_generator 先做覆盖计划，再生成测试列表", prompt)
        self.assertIn("基础测试用例、边界测试用例、随机测试用例、对抗测试用例、性能测试用例逐项判断是否相关", prompt)
        self.assertIn("若 oracle_limits 支持，应显式标注哪些测试 expect_oracle=True", prompt)

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
        self.assertIn("空输出、固定输出、首 token 输出、明显瞎写", prompt)
        self.assertIn("错误解必须有竞争力", prompt)
        self.assertIn("仍存活的错误解：surviving_wrong_1", prompt)


if __name__ == "__main__":
    unittest.main()
