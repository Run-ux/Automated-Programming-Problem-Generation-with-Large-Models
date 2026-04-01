from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GEN_DIR = ROOT / "生成题面"
if str(GEN_DIR) not in sys.path:
    sys.path.insert(0, str(GEN_DIR))

from main import _normalize_rule_overrides, _validate_args, build_parser
from models import DifferencePlan, GeneratedProblem, InstantiatedSchema, Theme, VariantPlan
from pipeline import GenerationPipeline
from rulebook import RuleBook
from variant_planner import VariantPlanner


class RuleBookTests(unittest.TestCase):
    def test_rulebook_reads_mode_switch_rule_switch_and_redlines(self) -> None:
        base_payload = json.loads((GEN_DIR / "planning_rules.json").read_text(encoding="utf-8"))
        base_payload["modes"]["same_family_fusion"]["enabled"] = False
        base_payload["modes"]["single_seed_extension"]["rules"][0]["enabled"] = False

        with tempfile.TemporaryDirectory() as tempdir:
            rule_path = Path(tempdir) / "rules.json"
            rule_path.write_text(json.dumps(base_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            rulebook = RuleBook.load(rule_path)

        self.assertIn("只换故事背景", rulebook.global_redlines())
        self.assertEqual(rulebook.enabled_rules("same_family_fusion"), [])
        enabled_ids = {item["id"] for item in rulebook.enabled_rules("single_seed_extension")}
        self.assertNotIn("canonical_witness", enabled_ids)
        self.assertIn("construct_or_obstruction", enabled_ids)


class SingleSeedExtensionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rulebook = RuleBook.load(GEN_DIR / "planning_rules.json")
        self.source_schema = make_schema(problem_id="SINGLE")
        self.original_problem = {
            "problem_id": "SINGLE",
            "title": "Seed Title",
            "description": "给定数组，判断是否存在合法方案。",
            "input": "输入三行。",
            "output": "输出 Yes 或 No。",
            "constraints": "time limit per test 2 seconds\nmemory limit per test 256 megabytes",
            "source": "codeforces",
        }

    def test_each_single_rule_can_pass(self) -> None:
        responses = {
            "canonical_witness": make_single_payload("canonical_witness"),
            "construct_or_obstruction": make_single_payload("construct_or_obstruction"),
            "existence_to_counting": make_single_payload("existence_to_counting"),
            "minimum_guarantee_under_perturbation": make_single_payload("minimum_guarantee_under_perturbation"),
        }
        planner = VariantPlanner(
            client=FakePlannerClient(responses),
            rulebook=self.rulebook,
            seed=7,
        )

        for rule_id in responses:
            with self.subTest(rule_id=rule_id):
                plan = planner.build_plan(
                    mode="single_seed_extension",
                    variant_index=1,
                    theme_id="campus_ops",
                    original_schema=self.source_schema,
                    prepared_schema=self.source_schema,
                    original_problem=self.original_problem,
                    allowed_rule_ids={rule_id},
                )
                self.assertEqual(plan.planning_status, "ok")
                self.assertEqual(plan.mode, "single_seed_extension")
                self.assertEqual(plan.applied_rule, rule_id)
                self.assertGreaterEqual(plan.predicted_schema_distance, 0.35)
                self.assertGreaterEqual(len(plan.changed_axes_realized), 2)

    def test_each_single_rule_can_be_explicitly_rejected(self) -> None:
        responses = {
            rule_id: {
                "status": "difference_insufficient",
                "error_reason": f"{rule_id} 不适用",
                "feedback": "浅改风险过高",
            }
            for rule_id in (
                "canonical_witness",
                "construct_or_obstruction",
                "existence_to_counting",
                "minimum_guarantee_under_perturbation",
            )
        }
        planner = VariantPlanner(
            client=FakePlannerClient(responses),
            rulebook=self.rulebook,
            seed=11,
        )

        for rule_id in responses:
            with self.subTest(rule_id=rule_id):
                plan = planner.build_plan(
                    mode="single",
                    variant_index=1,
                    theme_id="campus_ops",
                    original_schema=self.source_schema,
                    prepared_schema=self.source_schema,
                    original_problem=self.original_problem,
                    allowed_rule_ids={rule_id},
                )
                self.assertEqual(plan.planning_status, "difference_insufficient")
                self.assertEqual(plan.mode, "single_seed_extension")
                self.assertEqual(plan.applied_rule, rule_id)
                self.assertEqual(len(plan.rejected_candidates), 1)
                self.assertEqual(plan.rejected_candidates[0]["rule_id"], rule_id)

    def test_rule_selection_runs_before_planning(self) -> None:
        client = FakePlannerClient(
            responses={
                "construct_or_obstruction": make_single_payload("construct_or_obstruction"),
            },
            selection_response=make_rule_selection_payload("construct_or_obstruction"),
        )
        planner = VariantPlanner(
            client=client,
            rulebook=self.rulebook,
            seed=19,
        )

        plan = planner.build_plan(
            mode="single_seed_extension",
            variant_index=1,
            theme_id="campus_ops",
            original_schema=self.source_schema,
            prepared_schema=self.source_schema,
            original_problem=self.original_problem,
        )

        self.assertEqual(plan.planning_status, "ok")
        self.assertEqual(plan.applied_rule, "construct_or_obstruction")
        self.assertIn("construct_or_obstruction", plan.rule_selection_reason)
        self.assertEqual(client.calls, ["select", "plan:construct_or_obstruction"])

    def test_rule_selection_can_fail_before_planning(self) -> None:
        client = FakePlannerClient(
            responses={
                "canonical_witness": make_single_payload("canonical_witness"),
            },
            selection_response={
                "status": "difference_insufficient",
                "selected_rule_id": "",
                "selection_reason": "所有规则都只能形成浅改。",
                "innovation_reason": "",
                "difficulty_reason": "",
                "risk_reason": "直接规划会退化成换皮。",
                "error_reason": "没有足够强的规则适配当前 schema。",
                "feedback": "请更换种子题或缩小规则集。",
            },
        )
        planner = VariantPlanner(
            client=client,
            rulebook=self.rulebook,
            seed=23,
        )

        plan = planner.build_plan(
            mode="single_seed_extension",
            variant_index=1,
            theme_id="campus_ops",
            original_schema=self.source_schema,
            prepared_schema=self.source_schema,
            original_problem=self.original_problem,
        )

        self.assertEqual(plan.planning_status, "difference_insufficient")
        self.assertEqual(plan.applied_rule, "")
        self.assertIn("所有规则都只能形成浅改", plan.rule_selection_reason)
        self.assertEqual(client.calls, ["select"])


class SameFamilyFusionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rulebook = RuleBook.load(GEN_DIR / "planning_rules.json")
        self.seed_a_schema = make_schema(problem_id="A", objective_type="decision")
        self.seed_b_schema = make_schema(problem_id="B", objective_type="decision")
        self.seed_a_problem = {
            "problem_id": "A",
            "title": "Seed A",
            "description": "种子题 A",
            "input": "输入三行。",
            "output": "输出 Yes 或 No。",
            "constraints": "time limit per test 2 seconds\nmemory limit per test 256 megabytes",
            "source": "codeforces",
        }
        self.seed_b_problem = {
            "problem_id": "B",
            "title": "Seed B",
            "description": "种子题 B",
            "input": "输入三行。",
            "output": "输出 Yes 或 No。",
            "constraints": "time limit per test 2 seconds\nmemory limit per test 256 megabytes",
            "source": "codeforces",
        }

    def test_same_family_rules_enforce_shared_core_and_ablation(self) -> None:
        responses = {
            "interlocked_constraints": make_same_family_payload("interlocked_constraints"),
            "shared_core_objective_upgrade": make_same_family_payload("shared_core_objective_upgrade"),
        }
        planner = VariantPlanner(
            client=FakePlannerClient(responses),
            rulebook=self.rulebook,
            seed=13,
        )

        for rule_id in responses:
            with self.subTest(rule_id=rule_id):
                plan = planner.build_plan(
                    mode="same_family_fusion",
                    variant_index=1,
                    theme_id="campus_ops",
                    seed_a_schema=self.seed_a_schema,
                    seed_b_schema=self.seed_b_schema,
                    seed_a_problem=self.seed_a_problem,
                    seed_b_problem=self.seed_b_problem,
                    allowed_rule_ids={rule_id},
                )
                self.assertEqual(plan.planning_status, "ok")
                self.assertEqual(plan.mode, "same_family_fusion")
                self.assertEqual(plan.applied_rule, rule_id)
                self.assertTrue(plan.shared_core_summary)
                self.assertTrue(plan.seed_contributions["seed_a"])
                self.assertTrue(plan.seed_contributions["seed_b"])
                self.assertTrue(plan.fusion_ablation["without_seed_a"])
                self.assertTrue(plan.fusion_ablation["without_seed_b"])

    def test_same_family_rejects_missing_ablation_or_anti_sequential_argument(self) -> None:
        responses = {
            "interlocked_constraints": make_same_family_payload(
                "interlocked_constraints",
                drop_fields={"why_not_sequential_composition", "fusion_ablation.without_seed_b"},
            )
        }
        planner = VariantPlanner(
            client=FakePlannerClient(responses),
            rulebook=self.rulebook,
            seed=17,
        )
        plan = planner.build_plan(
            mode="same_family",
            variant_index=1,
            theme_id="campus_ops",
            seed_a_schema=self.seed_a_schema,
            seed_b_schema=self.seed_b_schema,
            seed_a_problem=self.seed_a_problem,
            seed_b_problem=self.seed_b_problem,
            allowed_rule_ids={"interlocked_constraints"},
        )

        self.assertEqual(plan.planning_status, "difference_insufficient")
        self.assertEqual(plan.mode, "same_family_fusion")
        self.assertEqual(plan.applied_rule, "interlocked_constraints")
        self.assertEqual(plan.rejected_candidates[0]["rule_id"], "interlocked_constraints")


class PipelineArtifactTests(unittest.TestCase):
    def test_pipeline_persists_legacy_shell_and_new_fields(self) -> None:
        theme = Theme(
            theme_id="campus_ops",
            name="校园运营",
            tone="日常规则",
            keywords=["社团", "排课"],
            mapping_hint="把状态映射成校园资源调度。",
        )
        difference_plan = DifferencePlan(
            target_distance_band={"min": 0.35, "max": 0.60},
            changed_axes=["C", "O", "V"],
            same_family_allowed=True,
            forbidden_reuse=["A", "B"],
            rationale="共享主核下引入新目标与新验证义务。",
            summary="双向对等融合通过硬门槛。",
            mode="same_family_fusion",
        )
        instantiated_schema = InstantiatedSchema(
            problem_id="A__B_FUSED",
            source="codeforces+codeforces",
            input_structure={
                "type": "array",
                "length": {"min": 3, "max": 3},
                "value_range": {"min": 1, "max": 9},
                "properties": {"ordered": True},
            },
            core_constraints={
                "constraints": [
                    {"name": "dual_lock", "description": "两个种子义务在同一状态过程里互锁。"}
                ]
            },
            objective={"type": "construct_witness", "description": "输出一个规范构造。"},
            invariant={
                "invariants": [
                    {"name": "shared_core", "description": "共享状态核支撑双义务。"}
                ]
            },
            selected_structural_options=["must_contain_in_order"],
            theme={"id": "campus_ops", "name": "校园运营"},
            difficulty="Hard",
        )
        plan = VariantPlan(
            problem_id="A__B_FUSED",
            variant_index=1,
            seed=99,
            mode="same_family_fusion",
            theme=theme,
            source_problem_ids=["A", "B"],
            objective={"type": "construct_witness", "description": "输出一个规范构造。"},
            difficulty="Hard",
            rule_selection_reason="共享主核稳定，选择 interlocked_constraints 可以把创新度和难度一起抬高。",
            input_summary="类型=array；长度范围=3..3",
            constraint_summary=["双义务互锁"],
            invariant_summary=["共享状态核"],
            difference_plan=difference_plan,
            instantiated_schema_snapshot=instantiated_schema,
            predicted_schema_distance=0.44,
            distance_breakdown={"I": 0.0, "C": 0.6, "O": 0.6, "V": 0.4, "T": 0.0, "total": 0.44},
            changed_axes_realized=["C", "O", "V"],
            applied_rule="interlocked_constraints",
            rejected_candidates=[{"rule_id": "shared_core_objective_upgrade", "status": "difference_insufficient", "reason": "新目标退化为后处理。"}],
            algorithmic_delta_claim={
                "seed_solver_core": "共享状态转移",
                "reusable_subroutines": "状态压缩与合法性检查",
                "new_solver_core": "在共享状态上同步满足双义务",
                "new_proof_obligation": "证明规范构造与互锁约束同时成立",
                "why_direct_reuse_fails": "原解无法同时承担双向互锁验证责任",
            },
            shared_core_summary="两个种子共享同一状态核。",
            shared_core_anchors={
                "shared_state": "统一状态数组",
                "shared_transition": "一次转移同时检查两类义务",
                "shared_decision_basis": "以共享状态上的可达性与规范性判定",
            },
            seed_contributions={"seed_a": "容量义务", "seed_b": "冲突义务"},
            fusion_ablation={"without_seed_a": "容量义务缺失后主核退化。", "without_seed_b": "冲突义务缺失后主核退化。"},
            auxiliary_moves=["规范输出"],
        )

        with tempfile.TemporaryDirectory() as tempdir:
            temp = Path(tempdir)
            source_dir = temp / "schemas"
            output_dir = temp / "output"
            artifact_dir = temp / "artifacts"
            report_dir = temp / "reports"
            source_dir.mkdir(parents=True, exist_ok=True)
            for problem_id in ("A", "B"):
                (source_dir / f"{problem_id}.json").write_text(
                    json.dumps(make_schema(problem_id=problem_id), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

            pipeline = GenerationPipeline(
                raw_source_dir=source_dir,
                source_dir=source_dir,
                output_dir=output_dir,
                artifact_dir=artifact_dir,
                report_dir=report_dir,
                generator=FakeGenerator(),
                planner=FixedPlanPlanner(plan),
                problem_repository=FakeProblemRepository(),
            )
            records = pipeline.run(
                mode="same_family",
                problem_ids=[],
                variants=1,
                theme_id="campus_ops",
                seed_a="A",
                seed_b="B",
            )

            artifact_path = Path(records[0]["artifact_path"])
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))

        for key in (
            "difference_plan",
            "predicted_schema_distance",
            "changed_axes_realized",
            "instantiated_schema_snapshot",
            "mode",
            "applied_rule",
            "rule_selection_reason",
            "rejected_candidates",
            "algorithmic_delta_claim",
            "fusion_ablation",
        ):
            self.assertIn(key, artifact)
        self.assertEqual(artifact["mode"], "same_family_fusion")
        self.assertEqual(artifact["distance_breakdown"]["T"], 0.0)
        self.assertEqual(artifact["generated_problem"]["status"], "ok")


class CliAndDocumentationTests(unittest.TestCase):
    def test_cli_supports_single_and_same_family_with_rule_override(self) -> None:
        parser = build_parser()

        single_args = parser.parse_args(["--mode", "single", "--problem-ids", "CF1", "CF2"])
        _validate_args(parser, single_args)
        self.assertEqual(single_args.mode, "single")
        self.assertEqual(single_args.problem_ids, ["CF1", "CF2"])

        same_family_args = parser.parse_args(
            [
                "--mode",
                "same_family",
                "--seed-a",
                "P1",
                "--seed-b",
                "P2",
                "--rule-override",
                "interlocked_constraints,shared_core_objective_upgrade",
            ]
        )
        _validate_args(parser, same_family_args)
        self.assertEqual(same_family_args.seed_a, "P1")
        self.assertEqual(same_family_args.seed_b, "P2")
        self.assertEqual(
            _normalize_rule_overrides(same_family_args.rule_override),
            {"interlocked_constraints", "shared_core_objective_upgrade"},
        )

    def test_readmes_describe_rule_driven_four_tuple_flow(self) -> None:
        generator_readme = (GEN_DIR / "README.md").read_text(encoding="utf-8")
        root_readme = (ROOT / "README.md").read_text(encoding="utf-8")

        for text in (generator_readme, root_readme):
            self.assertIn("规则", text)
            self.assertIn("single_seed_extension", text)
            self.assertIn("same_family_fusion", text)
            self.assertNotIn("先补全 transform_space 再生成", text)
            self.assertNotIn("transform_space 是生成主驱动", text)


class FakePlannerClient:
    def __init__(self, responses: dict[str, dict], selection_response: dict | None = None) -> None:
        self.responses = copy.deepcopy(responses)
        self.selection_response = copy.deepcopy(selection_response)
        self.calls: list[str] = []

    def chat_json(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> dict:
        if '"available_rules"' in user_prompt:
            self.calls.append("select")
            if self.selection_response is not None:
                return copy.deepcopy(self.selection_response)
            matched_rule_ids = [
                rule_id for rule_id in self.responses if f'"id": "{rule_id}"' in user_prompt
            ]
            if len(matched_rule_ids) == 1:
                return make_rule_selection_payload(matched_rule_ids[0])
            raise AssertionError(f"无法从规则选择 prompt 中确定唯一规则。prompt={user_prompt}")

        for rule_id, payload in self.responses.items():
            if f'"id": "{rule_id}"' in user_prompt:
                self.calls.append(f"plan:{rule_id}")
                return copy.deepcopy(payload)
        raise AssertionError(f"无法从 prompt 中匹配规则。prompt={user_prompt}")


class FixedPlanPlanner:
    def __init__(self, plan: VariantPlan) -> None:
        self.plan = plan

    def build_plan(self, **_: dict) -> VariantPlan:
        return copy.deepcopy(self.plan)


class FakeGenerator:
    def generate(self, schema_context: dict, plan: VariantPlan, original_problems: list[dict] | None = None) -> GeneratedProblem:
        return GeneratedProblem(
            title="融合后的新题",
            description="这是一道规则驱动生成的新题。",
            input_format="输入三行，每行一个整数。",
            output_format="输出一个规范构造。",
            constraints=["时间限制：2 秒。", "空间限制：256 MB。"],
            samples=[
                {"input": "1\n2\n3", "output": "3 2 1", "explanation": "样例一。"},
                {"input": "2\n3\n4", "output": "4 3 2", "explanation": "样例二。"},
            ],
            notes="无",
        )


class FakeProblemRepository:
    def get_problem(self, source: str, problem_id: str) -> dict:
        return {
            "problem_id": problem_id,
            "title": f"Seed {problem_id}",
            "description": f"{problem_id} 描述",
            "input": "输入三行。",
            "output": "输出一个答案。",
            "constraints": "time limit per test 2 seconds\nmemory limit per test 256 megabytes",
            "source": source or "codeforces",
            "tags": ["dp"],
            "difficulty": "Medium",
        }


def make_schema(problem_id: str, objective_type: str = "decision") -> dict:
    return {
        "problem_id": problem_id,
        "source": "codeforces",
        "input_structure": {
            "type": "array",
            "length": {"min": 3, "max": 3},
            "value_range": {"min": 1, "max": 9},
            "properties": {},
        },
        "core_constraints": {
            "constraints": [
                {"name": "base_constraint", "description": "需要满足基础选择约束。"}
            ]
        },
        "objective": {
            "type": objective_type,
            "description": "判断是否存在合法方案。",
        },
        "invariant": {
            "invariants": [
                {"name": "base_invariant", "description": "基础不变量保持成立。"}
            ]
        },
    }


def make_rule_selection_payload(rule_id: str) -> dict:
    return {
        "status": "ok",
        "selected_rule_id": rule_id,
        "selection_reason": f"规则 {rule_id} 在当前 schema 上最容易形成主导义务变化。",
        "innovation_reason": "它会改变核心任务而不是只改叙事或输出外壳。",
        "difficulty_reason": "主求解责任会明显抬高，不能沿用原题主框架直接完成。",
        "risk_reason": "需要控制换皮风险，但整体可落地。",
        "error_reason": "",
        "feedback": "",
    }


def make_single_payload(rule_id: str) -> dict:
    base = {
        "status": "ok",
        "error_reason": "",
        "feedback": "",
        "eligibility_reason": "种子题具备稳定可扩展性。",
        "core_transformation_summary": "在四元组层面引入新义务。",
        "difference_plan": {
            "changed_axes": ["C", "O", "V"],
            "rationale": "新规则改变主导求解义务。",
            "summary": "通过硬门槛并可追溯到规则。",
        },
        "instantiated_schema": {
            "problem_id": f"SINGLE_{rule_id}",
            "source": "codeforces",
            "input_structure": {
                "type": "array",
                "length": {"min": 3, "max": 3},
                "value_range": {"min": 1, "max": 9},
                "properties": {},
            },
            "core_constraints": {
                "constraints": [
                    {"name": "base_constraint", "description": "需要满足基础选择约束。"},
                    {"name": f"{rule_id}_constraint", "description": f"{rule_id} 引入新的核心约束。"}
                ]
            },
            "objective": {"type": "construct_witness", "description": "输出一个规范 witness。"},
            "invariant": {
                "invariants": [
                    {"name": "base_invariant", "description": "基础不变量保持成立。"},
                    {"name": f"{rule_id}_invariant", "description": f"{rule_id} 引入新的验证不变量。"}
                ]
            },
            "instantiated_parameters": {},
            "selected_structural_options": [],
            "selected_input_options": [],
            "selected_invariant_options": [],
            "difficulty": "Medium",
        },
        "algorithmic_delta_claim": {
            "seed_solver_core": "基础判定过程",
            "reusable_subroutines": "状态预处理",
            "new_solver_core": "需要输出并验证新的结构",
            "new_proof_obligation": "必须证明构造满足新约束",
            "why_direct_reuse_fails": "原解缺少对新义务的验证链路",
        },
        "anti_shallow_rationale": "变化已进入主导义务。",
        "auxiliary_moves": ["规范输出"],
        "shared_core_summary": "",
        "shared_core_anchors": {
            "shared_state": "",
            "shared_transition": "",
            "shared_decision_basis": "",
        },
        "seed_a_indispensable_obligation": "",
        "seed_b_indispensable_obligation": "",
        "why_not_sequential_composition": "",
        "fusion_ablation": {
            "without_seed_a": "",
            "without_seed_b": "",
        },
    }
    if rule_id == "construct_or_obstruction":
        base["instantiated_schema"]["objective"] = {"type": "construct_or_obstruction", "description": "输出构造或阻碍证书。"}
    elif rule_id == "existence_to_counting":
        base["instantiated_schema"]["objective"] = {"type": "count", "description": "统计所有合法方案数。"}
    elif rule_id == "minimum_guarantee_under_perturbation":
        base["instantiated_schema"]["objective"] = {"type": "minimize_value", "description": "求最小保底阈值。"}
    return base


def make_same_family_payload(rule_id: str, drop_fields: set[str] | None = None) -> dict:
    payload = {
        "status": "ok",
        "error_reason": "",
        "feedback": "",
        "eligibility_reason": "两个种子题共享稳定主核。",
        "core_transformation_summary": "共享主核承受更强的新义务。",
        "difference_plan": {
            "changed_axes": ["C", "O", "V"],
            "rationale": "共享主核上叠加双向不可删义务。",
            "summary": "通过单主核和反串联硬门槛。",
        },
        "instantiated_schema": {
            "problem_id": f"FUSED_{rule_id}",
            "source": "codeforces+codeforces",
            "input_structure": {
                "type": "array",
                "length": {"min": 3, "max": 3},
                "value_range": {"min": 1, "max": 9},
                "properties": {"ordered": True},
            },
            "core_constraints": {
                "constraints": [
                    {"name": "base_constraint", "description": "需要满足基础选择约束。"},
                    {"name": f"{rule_id}_constraint", "description": f"{rule_id} 让双义务在同一状态过程中互锁。"}
                ]
            },
            "objective": {"type": "construct_witness", "description": "输出共享主核下的规范构造。"},
            "invariant": {
                "invariants": [
                    {"name": "base_invariant", "description": "基础不变量保持成立。"},
                    {"name": "fusion_invariant", "description": "共享状态核同时维持双重义务。"}
                ]
            },
            "instantiated_parameters": {},
            "selected_structural_options": [],
            "selected_input_options": [],
            "selected_invariant_options": [],
            "difficulty": "Hard",
        },
        "algorithmic_delta_claim": {
            "seed_solver_core": "共享状态压缩",
            "reusable_subroutines": "基础合法性检查",
            "new_solver_core": "在共享主核上同步满足双义务",
            "new_proof_obligation": "证明规范构造与互锁约束同时成立",
            "why_direct_reuse_fails": "任一单题原解都缺少另一题的不可删义务",
        },
        "anti_shallow_rationale": "融合义务已进入核心状态演化。",
        "auxiliary_moves": ["规范输出"],
        "shared_core_summary": "两个种子题共享同一状态核。",
        "shared_core_anchors": {
            "shared_state": "统一状态数组",
            "shared_transition": "一次转移同时检查两题义务",
            "shared_decision_basis": "基于共享状态上的可达性与规范性判定",
        },
        "seed_a_indispensable_obligation": "保留 seed_a 的容量义务。",
        "seed_b_indispensable_obligation": "保留 seed_b 的冲突义务。",
        "why_not_sequential_composition": "任何串联拆分都会破坏同一状态过程上的同步承压。",
        "fusion_ablation": {
            "without_seed_a": "去掉 seed_a 后只剩表层冲突约束。",
            "without_seed_b": "去掉 seed_b 后只剩单边容量过滤。",
        },
    }
    if rule_id == "interlocked_constraints":
        payload["instantiated_schema"]["objective"] = {"type": "count", "description": "统计共享主核下的合法方案数。"}
    if drop_fields:
        for field in drop_fields:
            if field == "why_not_sequential_composition":
                payload["why_not_sequential_composition"] = ""
            elif field == "fusion_ablation.without_seed_a":
                payload["fusion_ablation"]["without_seed_a"] = ""
            elif field == "fusion_ablation.without_seed_b":
                payload["fusion_ablation"]["without_seed_b"] = ""
    return payload


if __name__ == "__main__":
    unittest.main()
