from __future__ import annotations

import copy
import importlib.util
import json
import re
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GEN_DIR = ROOT / "生成题面"
if str(GEN_DIR) not in sys.path:
    sys.path.insert(0, str(GEN_DIR))

from main import _load_batch_problem_ids, _normalize_rule_overrides, _target_problem_ids, _validate_args, build_parser
from models import DifferencePlan, GeneratedProblem, NewSchema, Theme, VariantPlan
from pipeline import GenerationPipeline
from problem_generator import ProblemGenerator
from qwen_client import QwenClient
from rule_handlers import get_rule_handler
from rulebook import RuleBook
from schema_tools import _objective_type_prompt, compute_schema_distance
from variant_planner import VariantPlanner


def _load_upstream_objective_specs() -> dict[str, str]:
    module_path = ROOT / "四元组抽取" / "label_vocab.py"
    spec = importlib.util.spec_from_file_location("test_upstream_label_vocab", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load upstream label vocab: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return {
        str(item.name): str(item.description)
        for item in getattr(module, "OBJECTIVE_SPECS", [])
    }


def _load_rule_helper_specs() -> dict[str, list[dict[str, object]]]:
    payload = json.loads((GEN_DIR / "planning_rules.json").read_text(encoding="utf-8"))
    helper_specs: dict[str, list[dict[str, object]]] = {}
    for mode_config in payload.get("modes", {}).values():
        if not isinstance(mode_config, dict):
            continue
        for rule in mode_config.get("rules", []):
            if not isinstance(rule, dict):
                continue
            rule_id = str(rule.get("id", "")).strip()
            if not rule_id:
                continue
            helper_specs[rule_id] = copy.deepcopy(rule.get("helpers", []))
    return helper_specs


def _schema_change_text(section: str) -> str:
    mapping = {
        "input_structure": "输入结构承担新的主导责任",
        "core_constraints": "核心约束承接新的 helper 义务",
        "objective": "目标定义切换到新的主求解对象",
        "invariant": "不变量需要支撑新的证明责任",
    }
    return mapping.get(section, f"{section} 发生了结构变化")


def make_applied_helpers(rule_id: str) -> list[dict[str, object]]:
    helper_specs = _load_rule_helper_specs()[rule_id]
    return [
        {
            "id": str(helper["id"]),
            "selection_reason": str(helper.get("summary", "")) or f"{helper['id']} 改变了主导义务。",
            "affected_axes": [str(axis) for axis in helper.get("target_axes", []) if str(axis).strip()],
            "schema_changes": [_schema_change_text(str(section)) for section in helper.get("must_realize_in", []) if str(section).strip()],
            "innovation_reason": str(helper.get("innovation_role", "")) or f"{helper['id']} 提高了创新度。",
            "difficulty_reason": str(helper.get("difficulty_role", "")) or f"{helper['id']} 提高了难度。",
        }
        for helper in helper_specs
    ]


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
        self.assertTrue(rulebook.version())
        self.assertEqual(rulebook.enabled_rules("same_family_fusion"), [])
        enabled_ids = {item["id"] for item in rulebook.enabled_rules("single_seed_extension")}
        self.assertNotIn("canonical_witness", enabled_ids)
        self.assertIn("construct_or_obstruction", enabled_ids)
        first_rule = rulebook.enabled_rules("single_seed_extension")[0]
        self.assertNotIn("helpers", rulebook.mode_config("single_seed_extension"))
        self.assertTrue(first_rule["handler"])
        self.assertTrue(first_rule["family"])
        self.assertTrue(first_rule["helpers"])

    def test_rulebook_rejects_duplicate_helper_ids(self) -> None:
        base_payload = json.loads((GEN_DIR / "planning_rules.json").read_text(encoding="utf-8"))
        duplicated = copy.deepcopy(base_payload["modes"]["single_seed_extension"]["rules"][0]["helpers"][0])
        base_payload["modes"]["single_seed_extension"]["rules"][0]["helpers"].append(duplicated)

        with tempfile.TemporaryDirectory() as tempdir:
            rule_path = Path(tempdir) / "rules.json"
            rule_path.write_text(json.dumps(base_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate helper ids"):
                RuleBook.load(rule_path)

    def test_rulebook_rejects_must_change_helper_axis_mismatch(self) -> None:
        base_payload = json.loads((GEN_DIR / "planning_rules.json").read_text(encoding="utf-8"))
        base_payload["modes"]["single_seed_extension"]["rules"][0]["required_axis_changes"]["must_change"] = ["O", "V"]

        with tempfile.TemporaryDirectory() as tempdir:
            rule_path = Path(tempdir) / "rules.json"
            rule_path.write_text(json.dumps(base_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must_change must match helper target axes"):
                RuleBook.load(rule_path)

    def test_rulebook_inherits_mode_level_planner_output_contract(self) -> None:
        rulebook = RuleBook.load(GEN_DIR / "planning_rules.json")

        single_rule = rulebook.rule("single_seed_extension", "canonical_witness")
        self.assertEqual(
            single_rule["planner_output_contract"]["required_fields"],
            [
                "eligibility_reason",
                "core_transformation_summary",
                "difference_plan",
                "new_schema",
                "algorithmic_delta_claim",
                "anti_shallow_rationale",
                "applied_helpers",
            ],
        )

        same_family_rule = rulebook.rule("same_family_fusion", "interlocked_constraints")
        self.assertEqual(
            same_family_rule["planner_output_contract"]["required_fields"],
            [
                "shared_core_summary",
                "shared_core_anchors",
                "seed_a_indispensable_obligation",
                "seed_b_indispensable_obligation",
                "why_not_sequential_composition",
                "fusion_ablation",
                "new_schema",
                "algorithmic_delta_claim",
                "applied_helpers",
            ],
        )

    def test_rulebook_merges_mode_level_and_rule_level_required_fields(self) -> None:
        base_payload = json.loads((GEN_DIR / "planning_rules.json").read_text(encoding="utf-8"))
        base_payload["modes"]["single_seed_extension"]["rules"][0]["planner_output_contract"] = {
            "required_fields": ["custom_field", "new_schema"]
        }

        with tempfile.TemporaryDirectory() as tempdir:
            rule_path = Path(tempdir) / "rules.json"
            rule_path.write_text(json.dumps(base_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            rulebook = RuleBook.load(rule_path)

        self.assertEqual(
            rulebook.rule("single_seed_extension", "canonical_witness")["planner_output_contract"]["required_fields"],
            [
                "eligibility_reason",
                "core_transformation_summary",
                "difference_plan",
                "new_schema",
                "algorithmic_delta_claim",
                "anti_shallow_rationale",
                "applied_helpers",
                "custom_field",
            ],
        )

    def test_rulebook_rejects_missing_required_execution_fields(self) -> None:
        base_payload = json.loads((GEN_DIR / "planning_rules.json").read_text(encoding="utf-8"))
        base_payload["modes"]["single_seed_extension"]["rules"][0]["handler"] = ""

        with tempfile.TemporaryDirectory() as tempdir:
            rule_path = Path(tempdir) / "rules.json"
            rule_path.write_text(json.dumps(base_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing required execution fields"):
                RuleBook.load(rule_path)

class SchemaDistanceTests(unittest.TestCase):
    def test_objective_type_prompt_uses_upstream_objective_specs(self) -> None:
        objective_specs = _load_upstream_objective_specs()

        self.assertEqual(_objective_type_prompt("decision"), f"decision: {objective_specs['decision']}")
        self.assertEqual(_objective_type_prompt("counting"), f"counting: {objective_specs['counting']}")
        self.assertEqual(_objective_type_prompt("construction"), f"construction: {objective_specs['construction']}")
        self.assertEqual(_objective_type_prompt("count"), "count")

    def test_identical_schema_distance_is_zero(self) -> None:
        schema = make_schema(problem_id="IDENTICAL")
        distance = compute_schema_distance(schema, copy.deepcopy(schema), embedding_client=StubEmbeddingClient())

        self.assertEqual(distance["distance_version"], "v2")
        self.assertEqual(distance["backend"], "embedding")
        self.assertAlmostEqual(distance["total"], 0.0, places=4)
        self.assertEqual(distance["axis_scores"], {"I": 0.0, "C": 0.0, "O": 0.0, "V": 0.0})

    def test_semantically_similar_constraint_rewrite_stays_below_jaccard_style_penalty(self) -> None:
        left = make_schema(problem_id="LEFT")
        right = make_schema(problem_id="RIGHT")
        right["core_constraints"]["constraints"] = [
            {"name": "base_constraint", "description": "必须选择一个满足基础条件的候选。"}
        ]
        embedding_client = StubEmbeddingClient(
            {
                "需要满足基础选择约束。": [1.0, 0.0, 0.0],
                "必须选择一个满足基础条件的候选。": [0.96, 0.04, 0.0],
            }
        )

        distance = compute_schema_distance(left, right, embedding_client=embedding_client)

        self.assertLess(distance["axis_scores"]["C"], 0.5)
        self.assertEqual(distance["backend"], "embedding")

    def test_objective_count_shift_is_larger_than_small_description_rewrite(self) -> None:
        base = make_schema(problem_id="BASE")
        count_variant = make_schema(problem_id="COUNT", objective_type="counting")
        count_variant["objective"]["description"] = "统计所有合法方案数。"
        rewrite_variant = make_schema(problem_id="REWRITE")
        rewrite_variant["objective"]["description"] = "判断是否能找到任意合法方案。"
        objective_specs = _load_upstream_objective_specs()

        embedding_client = StubEmbeddingClient(
            {
                "判断是否存在合法方案。": [1.0, 0.0, 0.0],
                "判断是否能找到任意合法方案。": [0.97, 0.03, 0.0],
                "统计所有合法方案数。": [0.1, 0.95, 0.0],
                f"decision: {objective_specs['decision']}": [1.0, 0.0, 0.0],
                f"counting: {objective_specs['counting']}": [0.0, 1.0, 0.0],
            }
        )

        count_distance = compute_schema_distance(base, count_variant, embedding_client=embedding_client)
        rewrite_distance = compute_schema_distance(base, rewrite_variant, embedding_client=embedding_client)

        self.assertGreater(count_distance["axis_scores"]["O"], rewrite_distance["axis_scores"]["O"])

    def test_tree_to_graph_shift_is_smaller_than_array_to_graph(self) -> None:
        base = make_schema(problem_id="BASE")
        tree_variant = copy.deepcopy(base)
        tree_variant["input_structure"]["type"] = "tree"
        graph_variant = copy.deepcopy(base)
        graph_variant["input_structure"]["type"] = "graph"

        embedding_client = StubEmbeddingClient(
            {
                "array": [1.0, 0.0, 0.0],
                "tree": [0.0, 1.0, 0.0],
                "graph": [0.0, 0.85, 0.15],
            }
        )
        tree_to_graph = compute_schema_distance(tree_variant, graph_variant, embedding_client=embedding_client)
        array_to_graph = compute_schema_distance(base, graph_variant, embedding_client=embedding_client)

        self.assertLess(tree_to_graph["axis_scores"]["I"], array_to_graph["axis_scores"]["I"])

    def test_constraint_distance_increases_when_extra_core_constraint_is_added(self) -> None:
        base = make_schema(problem_id="BASE")
        one_extra = copy.deepcopy(base)
        one_extra["core_constraints"]["constraints"].append(
            {"name": "capacity_guard", "description": "总容量不能超过给定上界。"}
        )
        two_extra = copy.deepcopy(one_extra)
        two_extra["core_constraints"]["constraints"].append(
            {"name": "conflict_guard", "description": "任意冲突元素不能同时出现。"}
        )

        embedding_client = StubEmbeddingClient()
        one_extra_distance = compute_schema_distance(base, one_extra, embedding_client=embedding_client)
        two_extra_distance = compute_schema_distance(base, two_extra, embedding_client=embedding_client)

        self.assertGreater(two_extra_distance["axis_scores"]["C"], one_extra_distance["axis_scores"]["C"])

    def test_embedding_failure_raises_runtime_error(self) -> None:
        left = make_schema(problem_id="LEFT")
        right = copy.deepcopy(left)
        right["objective"]["description"] = "判断是否能找到任意合法方案。"

        with self.assertRaisesRegex(RuntimeError, "embedding service unavailable"):
            compute_schema_distance(left, right, embedding_client=FailingEmbeddingClient())

    def test_missing_embedding_client_raises_runtime_error(self) -> None:
        schema = make_schema(problem_id="ONLY")

        with self.assertRaisesRegex(RuntimeError, "embedding client unavailable"):
            compute_schema_distance(schema, copy.deepcopy(schema), embedding_client=None)


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
                    seed_schema=self.source_schema,
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
                    seed_schema=self.source_schema,
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
            seed_schema=self.source_schema,
            original_problem=self.original_problem,
        )

        self.assertEqual(plan.planning_status, "ok")
        self.assertEqual(plan.applied_rule, "construct_or_obstruction")
        self.assertIn("construct_or_obstruction", plan.rule_selection_reason)
        self.assertEqual(
            client.calls,
            ["select", "plan:construct_or_obstruction", "plan_review:construct_or_obstruction"],
        )

    def test_rule_selection_falls_back_to_next_ranked_rule(self) -> None:
        client = FakePlannerClient(
            responses={
                "construct_or_obstruction": {
                    "status": "difference_insufficient",
                    "error_reason": "证书定义不稳定。",
                    "feedback": "当前规则会退化成说明性输出。",
                },
                "existence_to_counting": make_single_payload("existence_to_counting"),
            },
            selection_response={
                **make_rule_selection_payload("construct_or_obstruction"),
                "ranked_rule_ids": ["construct_or_obstruction", "existence_to_counting"],
            },
        )
        planner = VariantPlanner(
            client=client,
            rulebook=self.rulebook,
            seed=31,
        )

        plan = planner.build_plan(
            mode="single_seed_extension",
            variant_index=1,
            theme_id="campus_ops",
            seed_schema=self.source_schema,
            original_problem=self.original_problem,
        )

        self.assertEqual(plan.planning_status, "ok")
        self.assertEqual(plan.applied_rule, "existence_to_counting")
        self.assertEqual(plan.rejected_candidates[0]["rule_id"], "construct_or_obstruction")
        self.assertEqual(
            client.calls,
            [
                "select",
                "plan:construct_or_obstruction",
                "plan:existence_to_counting",
                "plan_review:existence_to_counting",
            ],
        )

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
            seed_schema=self.source_schema,
            original_problem=self.original_problem,
        )

        self.assertEqual(plan.planning_status, "difference_insufficient")
        self.assertEqual(plan.applied_rule, "")
        self.assertIn("所有规则都只能形成浅改", plan.rule_selection_reason)
        self.assertEqual(client.calls, ["select"])

    def test_validate_candidate_rejects_unexpected_new_schema_fields(self) -> None:
        planner = VariantPlanner(
            client=None,
            rulebook=self.rulebook,
            seed=29,
        )
        payload = make_single_payload("canonical_witness")
        payload["new_schema"]["selected_input_options"] = ["legacy_option"]
        rule = next(
            item
            for item in self.rulebook.enabled_rules("single_seed_extension")
            if item["id"] == "canonical_witness"
        )

        accepted, _, reason, _, _ = planner._validate_candidate(
            mode="single_seed_extension",
            rule=rule,
            payload=payload,
            source_schema=self.source_schema,
            source_problem_ids=["SINGLE"],
            theme_payload={"id": "campus_ops", "name": "校园运营"},
        )

        self.assertFalse(accepted)
        self.assertIn("额外字段", reason)
        self.assertIn("selected_input_options", reason)


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
            client=FakePlannerClient(
                responses,
                plan_review_responses={
                    "interlocked_constraints": make_rule_review_payload(
                        status="fail",
                        reason_code="interlocked_constraints_missing",
                        message="共享主核论证不完整。",
                        errors=["缺少反串联论证或消融论证。"],
                        evidence="payload 中 why_not_sequential_composition 为空，fusion_ablation.without_seed_b 为空。",
                    )
                },
            ),
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


class RuleHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rulebook = RuleBook.load(GEN_DIR / "planning_rules.json")

    def test_rule_handlers_can_reject_ineligible_inputs(self) -> None:
        canonical_handler = get_rule_handler({"id": "canonical_witness", "handler": "canonical_witness"})
        canonical_client = FakePlannerClient(
            responses={},
            eligibility_responses={
                "canonical_witness": make_eligibility_payload(
                    "canonical_witness",
                    status="ineligible",
                    score=0.1,
                    reason_code="already_constructive",
                    selection_reason="种子题已经自带构造输出责任。",
                    risk_tags=["low_novelty"],
                    evidence="objective.type 已经是 construction。",
                )
            },
        )
        canonical_result = canonical_handler.check_eligibility(
            client=canonical_client,
            mode="single_seed_extension",
            rule={"id": "canonical_witness", "handler": "canonical_witness", "family": "output_upgrade", "audit_tags": []},
            schema_context={
                "seed_schema": make_schema(problem_id="CW", objective_type="construction"),
            },
            original_refs=[{"output_summary": "输出一个合法构造。"}],
            global_constraints={"allow_helper_moves": True},
            global_redlines=[],
        )
        self.assertFalse(canonical_result.accepted)

        fusion_handler = get_rule_handler({"id": "interlocked_constraints", "handler": "interlocked_constraints"})
        fusion_client = FakePlannerClient(
            responses={},
            eligibility_responses={
                "interlocked_constraints": make_eligibility_payload(
                    "interlocked_constraints",
                    status="ineligible",
                    score=0.2,
                    reason_code="shared_core_missing",
                    selection_reason="两题输入主核类型不一致，无法稳定共享状态核。",
                    risk_tags=["shared_core_risk"],
                    evidence="seed_a.input_structure.type=array, seed_b.input_structure.type=graph。",
                )
            },
        )
        fusion_result = fusion_handler.check_eligibility(
            client=fusion_client,
            mode="same_family_fusion",
            rule={"id": "interlocked_constraints", "handler": "interlocked_constraints", "family": "shared_core_fusion", "audit_tags": []},
            schema_context={
                "seed_a_schema": make_schema(problem_id="A"),
                "seed_b_schema": {
                    **make_schema(problem_id="B"),
                    "input_structure": {
                        "type": "graph",
                        "length": {"min": 3, "max": 3},
                        "value_range": {"min": 1, "max": 9},
                        "properties": {},
                    },
                },
            },
            original_refs=[],
            global_constraints={"allow_helper_moves": True},
            global_redlines=[],
        )
        self.assertFalse(fusion_result.accepted)

    def test_rule_specific_plan_validation_uses_llm_reviews(self) -> None:
        for rule_id in (
            "canonical_witness",
            "construct_or_obstruction",
            "existence_to_counting",
            "minimum_guarantee_under_perturbation",
            "interlocked_constraints",
            "shared_core_objective_upgrade",
        ):
            with self.subTest(rule_id=rule_id):
                mode = "same_family_fusion" if rule_id in {"interlocked_constraints", "shared_core_objective_upgrade"} else "single_seed_extension"
                rule = self.rulebook.rule(mode, rule_id)
                payload = make_same_family_payload(rule_id) if mode == "same_family_fusion" else make_single_payload(rule_id)
                handler = get_rule_handler(rule)
                pass_client = FakePlannerClient(
                    responses={},
                    plan_review_responses={
                        rule_id: make_rule_review_payload(
                            status="pass",
                            reason_code="ok",
                            message=f"{rule_id} 规划专属审查通过。",
                            evidence="规划 payload 已兑现规则专属合同。",
                        )
                    },
                )
                outcome = handler.validate_plan(
                    client=pass_client,
                    mode=mode,
                    rule=rule,
                    payload=payload,
                    source_schema=make_schema(problem_id="SRC"),
                    candidate_schema=payload["new_schema"],
                    changed_axes=payload["difference_plan"]["changed_axes"],
                    global_constraints={"allow_helper_moves": True},
                )
                self.assertTrue(outcome.accepted)
                self.assertIn(f"plan_review:{rule_id}", pass_client.calls)

                fail_client = FakePlannerClient(
                    responses={},
                    plan_review_responses={
                        rule_id: make_rule_review_payload(
                            status="fail",
                            reason_code=f"{rule_id}_contract_missing",
                            message=f"{rule_id} 规划没有兑现专属合同。",
                            errors=[f"{rule_id} 缺少关键规则承诺。"],
                            evidence="规则专属审查发现规划承诺不足。",
                        )
                    },
                )
                failed = handler.validate_plan(
                    client=fail_client,
                    mode=mode,
                    rule=rule,
                    payload=payload,
                    source_schema=make_schema(problem_id="SRC"),
                    candidate_schema=payload["new_schema"],
                    changed_axes=payload["difference_plan"]["changed_axes"],
                    global_constraints={"allow_helper_moves": True},
                )
                self.assertFalse(failed.accepted)
                self.assertEqual(failed.reason_code, f"{rule_id}_contract_missing")
                self.assertIn(f"plan_review:{rule_id}", fail_client.calls)

    def test_rule_specific_plan_validation_short_circuits_before_llm_review(self) -> None:
        rule = self.rulebook.rule("single_seed_extension", "canonical_witness")
        payload = make_single_payload("canonical_witness")
        payload.pop("algorithmic_delta_claim")
        handler = get_rule_handler(rule)
        client = FakePlannerClient(
            responses={},
            plan_review_responses={
                "canonical_witness": make_rule_review_payload(
                    status="pass",
                    evidence="不会被调用。",
                )
            },
        )
        outcome = handler.validate_plan(
            client=client,
            mode="single_seed_extension",
            rule=rule,
            payload=payload,
            source_schema=make_schema(problem_id="SRC"),
            candidate_schema=payload["new_schema"],
            changed_axes=payload["difference_plan"]["changed_axes"],
            global_constraints={"allow_helper_moves": True},
        )
        self.assertFalse(outcome.accepted)
        self.assertNotIn("plan_review:canonical_witness", client.calls)

    def test_interlocked_constraints_plan_validation_allows_objective_axis_to_stay_unchanged(self) -> None:
        rule = self.rulebook.rule("same_family_fusion", "interlocked_constraints")
        payload = make_same_family_payload("interlocked_constraints")
        handler = get_rule_handler(rule)
        client = FakePlannerClient(
            responses={},
            plan_review_responses={
                "interlocked_constraints": make_rule_review_payload(
                    status="pass",
                    reason_code="ok",
                    message="interlocked_constraints 规划专属审查通过。",
                    evidence="共享主核、同步承压与反串联语义已经成立。",
                )
            },
        )
        outcome = handler.validate_plan(
            client=client,
            mode="same_family_fusion",
            rule=rule,
            payload=payload,
            source_schema=make_schema(problem_id="SRC"),
            candidate_schema=payload["new_schema"],
            changed_axes=payload["difference_plan"]["changed_axes"],
            global_constraints={"allow_helper_moves": True},
        )
        self.assertIn("C", payload["difference_plan"]["changed_axes"])
        self.assertIn("V", payload["difference_plan"]["changed_axes"])
        self.assertNotIn("O", payload["difference_plan"]["changed_axes"])
        self.assertEqual(payload["new_schema"]["objective"]["type"], "decision")
        self.assertTrue(outcome.accepted)
        self.assertIn("plan_review:interlocked_constraints", client.calls)

    def test_rule_plan_validation_rejects_missing_or_extra_helpers(self) -> None:
        rule = self.rulebook.rule("single_seed_extension", "canonical_witness")
        handler = get_rule_handler(rule)

        missing_payload = make_single_payload("canonical_witness")
        missing_payload["applied_helpers"] = missing_payload["applied_helpers"][:-1]
        missing_outcome = handler.validate_plan(
            client=FakePlannerClient(responses={}),
            mode="single_seed_extension",
            rule=rule,
            payload=missing_payload,
            source_schema=make_schema(problem_id="SRC"),
            candidate_schema=missing_payload["new_schema"],
            changed_axes=missing_payload["difference_plan"]["changed_axes"],
            global_constraints={"allow_helper_moves": True},
        )
        self.assertFalse(missing_outcome.accepted)
        self.assertEqual(missing_outcome.reason_code, "helper_missing")

        extra_payload = make_single_payload("canonical_witness")
        extra_payload["applied_helpers"] = list(extra_payload["applied_helpers"]) + [
            {
                "id": "unexpected_helper",
                "selection_reason": "无效 helper。",
                "affected_axes": ["C"],
                "schema_changes": ["核心约束被改动。"],
                "innovation_reason": "无效。",
                "difficulty_reason": "无效。",
            }
        ]
        extra_outcome = handler.validate_plan(
            client=FakePlannerClient(responses={}),
            mode="single_seed_extension",
            rule=rule,
            payload=extra_payload,
            source_schema=make_schema(problem_id="SRC"),
            candidate_schema=extra_payload["new_schema"],
            changed_axes=extra_payload["difference_plan"]["changed_axes"],
            global_constraints={"allow_helper_moves": True},
        )
        self.assertFalse(extra_outcome.accepted)
        self.assertEqual(extra_outcome.reason_code, "helper_not_declared")

    def test_rule_plan_validation_rejects_helper_without_realized_schema_sections(self) -> None:
        rule = self.rulebook.rule("single_seed_extension", "canonical_witness")
        handler = get_rule_handler(rule)
        payload = make_single_payload("canonical_witness")
        broken_helper = copy.deepcopy(payload["applied_helpers"][0])
        broken_helper["schema_changes"] = ["只有目标变了。"]
        payload["applied_helpers"][0] = broken_helper
        candidate_schema = copy.deepcopy(payload["new_schema"])
        candidate_schema["invariant"] = copy.deepcopy(make_schema(problem_id="SRC")["invariant"])
        outcome = handler.validate_plan(
            client=FakePlannerClient(responses={}),
            mode="single_seed_extension",
            rule=rule,
            payload=payload,
            source_schema=make_schema(problem_id="SRC"),
            candidate_schema=candidate_schema,
            changed_axes=payload["difference_plan"]["changed_axes"],
            global_constraints={"allow_helper_moves": True},
        )
        self.assertFalse(outcome.accepted)
        self.assertEqual(outcome.reason_code, "helper_realization_missing")

    def test_rule_specific_problem_validation_rejects_missing_commitments(self) -> None:
        base_problem = GeneratedProblem(
            title="题目",
            description="请完成任务。",
            input_format="输入三行。",
            output_format="输出答案。",
            constraints=["时间限制：2 秒。", "空间限制：256 MB。"],
            samples=[{"input": "1\n2\n3", "output": "1", "explanation": "样例。"}, {"input": "3\n2\n1", "output": "1", "explanation": "样例。"}],
            notes="",
        )
        for rule_id in (
            "canonical_witness",
            "construct_or_obstruction",
            "existence_to_counting",
            "minimum_guarantee_under_perturbation",
            "interlocked_constraints",
            "shared_core_objective_upgrade",
        ):
            with self.subTest(rule_id=rule_id):
                client = FakePlannerClient(
                    responses={},
                    problem_review_responses={
                        rule_id: make_rule_review_payload(
                            status="fail",
                            reason_code=f"{rule_id}_not_materialized",
                            message=f"{rule_id} 题面没有兑现专属承诺。",
                            errors=[f"{rule_id} 题面缺少关键规则语义。"],
                            evidence="题面文本没有兑现规划中的规则承诺。",
                        )
                    },
                )
                handler = get_rule_handler({"id": rule_id, "handler": rule_id})
                outcome = handler.validate_problem(client=client, problem=base_problem, plan=make_validation_plan(rule_id))
                self.assertFalse(outcome.accepted)
                self.assertIn(f"problem_review:{rule_id}", client.calls)

    def test_rule_specific_problem_validation_accepts_matching_commitments(self) -> None:
        for rule_id, problem in make_valid_problem_cases().items():
            with self.subTest(rule_id=rule_id):
                client = FakePlannerClient(
                    responses={},
                    problem_review_responses={
                        rule_id: make_rule_review_payload(
                            status="pass",
                            reason_code="ok",
                            message=f"{rule_id} 题面专属审查通过。",
                            evidence="题面文本已经兑现规划中的规则承诺。",
                        )
                    },
                )
                handler = get_rule_handler({"id": rule_id, "handler": rule_id})
                outcome = handler.validate_problem(client=client, problem=problem, plan=make_validation_plan(rule_id))
                self.assertTrue(outcome.accepted)
                self.assertIn(f"problem_review:{rule_id}", client.calls)


class PipelineArtifactTests(unittest.TestCase):
    def test_pipeline_persists_rule_outputs_without_legacy_transform_tracks(self) -> None:
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
        new_schema = NewSchema(
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
            objective={"type": "construction", "description": "输出一个规范构造。"},
            invariant={
                "invariants": [
                    {"name": "shared_core", "description": "共享状态核支撑双义务。"}
                ]
            },
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
            objective={"type": "construction", "description": "输出一个规范构造。"},
            difficulty="Hard",
            rule_selection_reason="共享主核稳定，选择 interlocked_constraints 可以把创新度和难度一起抬高。",
            input_summary="类型=array；长度范围=3..3",
            constraint_summary=["双义务互锁"],
            invariant_summary=["共享状态核"],
            difference_plan=difference_plan,
            new_schema_snapshot=new_schema,
            predicted_schema_distance=0.44,
            distance_breakdown=make_distance_breakdown(i=0.0, c=0.6, o=0.6, v=0.4, total=0.44),
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
            applied_helpers=make_applied_helpers("interlocked_constraints"),
            rule_version="2026-04-rules-v3",
            selection_trace=[{"rule_id": "interlocked_constraints", "accepted": True, "score": 0.88}],
            validation_trace=[{"stage": "plan_validation", "rule_id": "interlocked_constraints", "outcome": "pass", "reason_code": "ok"}],
            candidate_attempts=[{"attempt_index": 1, "rule_id": "interlocked_constraints", "accepted": True, "score": 0.88}],
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
            markdown_path = Path(records[0]["markdown_path"])
            report_path = Path(records[0]["report_path"])
            self.assertEqual(artifact_path.parent.name, "A__B")
            self.assertEqual(markdown_path.parent.name, "A__B")
            self.assertEqual(report_path.parent.name, "A__B")
            self.assertEqual(report_path.name, "A__B.md")
            report_text = Path(records[0]["report_path"]).read_text(encoding="utf-8")

        for key in (
            "difference_plan",
            "predicted_schema_distance",
            "changed_axes_realized",
            "new_schema_snapshot",
            "mode",
            "applied_rule",
            "rule_selection_reason",
            "rejected_candidates",
            "algorithmic_delta_claim",
            "fusion_ablation",
            "applied_helpers",
            "rule_version",
            "selection_trace",
            "validation_trace",
            "candidate_attempts",
        ):
            self.assertIn(key, artifact)
        self.assertEqual(artifact["mode"], "same_family_fusion")
        self.assertEqual(artifact["generated_problem"]["status"], "ok")
        self.assertEqual(
            set(artifact["distance_breakdown"]),
            {"distance_version", "backend", "total", "axis_scores", "components"},
        )
        self.assertEqual(
            set(artifact["distance_breakdown"]["axis_scores"]),
            {"I", "C", "O", "V"},
        )
        self.assertIn("objective_text_distance", artifact["distance_breakdown"]["components"])
        for key in (
            "numerical_parameters",
            "structural_options",
            "input_structure_options",
            "invariant_options",
        ):
            self.assertNotIn(key, artifact)
        for key in (
            "instantiated_parameters",
            "selected_structural_options",
            "selected_input_options",
            "selected_invariant_options",
        ):
            self.assertNotIn(key, artifact["new_schema_snapshot"])
            self.assertNotIn(key, report_text)


class BatchPipelineTests(unittest.TestCase):
    def test_single_run_emits_progress_messages(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            temp = Path(tempdir)
            source_dir = temp / "schemas"
            output_dir = temp / "output"
            artifact_dir = temp / "artifacts"
            report_dir = temp / "reports"
            source_dir.mkdir(parents=True, exist_ok=True)
            (source_dir / "A.json").write_text(
                json.dumps(make_schema(problem_id="A"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            messages: list[str] = []

            pipeline = GenerationPipeline(
                source_dir=source_dir,
                output_dir=output_dir,
                artifact_dir=artifact_dir,
                report_dir=report_dir,
                generator=FakeGenerator(),
                planner=ProblemAwarePlanner(),
                problem_repository=FakeProblemRepository(),
                progress_writer=messages.append,
            )
            pipeline.run(
                mode="single",
                problem_ids=["A"],
                variants=1,
                theme_id="campus_ops",
            )

        joined = "\n".join(messages)
        self.assertIn("[single] 开始生成", joined)
        self.assertIn("[problem] A：读取 schema 与原题信息。", joined)
        self.assertIn("[problem] A：variant 1 进入规划。", joined)
        self.assertIn("[problem] A：variant 1 进入题面生成。", joined)
        self.assertIn("[problem] A：variant 1 写入产物。", joined)
        self.assertIn("[problem] A：完成。report=", joined)

    def test_batch_single_run_writes_summary_outputs_in_sorted_order(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            temp = Path(tempdir)
            source_dir = temp / "schemas"
            output_dir = temp / "output"
            artifact_dir = temp / "artifacts"
            report_dir = temp / "reports"
            source_dir.mkdir(parents=True, exist_ok=True)
            for problem_id in ("B", "A"):
                (source_dir / f"{problem_id}.json").write_text(
                    json.dumps(make_schema(problem_id=problem_id), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

            pipeline = GenerationPipeline(
                source_dir=source_dir,
                output_dir=output_dir,
                artifact_dir=artifact_dir,
                report_dir=report_dir,
                generator=FakeGenerator(),
                planner=ProblemAwarePlanner(),
                problem_repository=FakeProblemRepository(),
            )
            records = pipeline.run(
                mode="single",
                problem_ids=["A", "B"],
                variants=1,
                theme_id="campus_ops",
                batch_source_dir=source_dir,
            )

            batch_artifacts = sorted(artifact_dir.glob("batch_*.json"))
            batch_reports = sorted(report_dir.glob("batch_*.md"))
            self.assertEqual(len(batch_artifacts), 1)
            self.assertEqual(len(batch_reports), 0)
            batch_payload = json.loads(batch_artifacts[0].read_text(encoding="utf-8"))
            for record in records:
                self.assertIn("batch_artifact_path", record)
                self.assertNotIn("batch_report_path", record)
                self.assertTrue(Path(record["batch_artifact_path"]).exists())
                expected_group = "__".join(record["source_problem_ids"])
                self.assertEqual(Path(record["artifact_path"]).parent.name, expected_group)
                self.assertEqual(Path(record["markdown_path"]).parent.name, expected_group)

        self.assertEqual(batch_payload["status"], "completed")
        self.assertEqual(batch_payload["task_order"], ["A", "B"])
        self.assertEqual(batch_payload["completed_count"], 2)
        self.assertEqual([item["problem_id"] for item in batch_payload["items"]], ["A", "B"])

    def test_batch_single_run_continues_after_failure_and_persists_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            temp = Path(tempdir)
            source_dir = temp / "schemas"
            output_dir = temp / "output"
            artifact_dir = temp / "artifacts"
            report_dir = temp / "reports"
            source_dir.mkdir(parents=True, exist_ok=True)
            for problem_id in ("A", "B", "C"):
                (source_dir / f"{problem_id}.json").write_text(
                    json.dumps(make_schema(problem_id=problem_id), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

            pipeline = GenerationPipeline(
                source_dir=source_dir,
                output_dir=output_dir,
                artifact_dir=artifact_dir,
                report_dir=report_dir,
                generator=FailingOnProblemGenerator(fail_problem_id="B"),
                planner=ProblemAwarePlanner(),
                problem_repository=FakeProblemRepository(),
            )
            records = pipeline.run(
                mode="single",
                problem_ids=["A", "B", "C"],
                variants=1,
                theme_id="campus_ops",
                batch_source_dir=source_dir,
            )

            batch_artifacts = sorted(artifact_dir.glob("batch_*.json"))
            batch_reports = sorted(report_dir.glob("batch_*.md"))
            self.assertEqual(len(batch_artifacts), 1)
            self.assertEqual(len(batch_reports), 0)
            batch_payload = json.loads(batch_artifacts[0].read_text(encoding="utf-8"))
            markdown_paths = sorted(path.name for path in output_dir.rglob("*.md"))
            markdown_parent_names = sorted(path.parent.name for path in output_dir.rglob("*.md"))

        self.assertEqual(batch_payload["status"], "failed")
        self.assertEqual(batch_payload["completed_count"], 2)
        self.assertEqual(batch_payload["failed_count"], 1)
        self.assertEqual(batch_payload["failed_problem_id"], "B")
        self.assertEqual([item["problem_id"] for item in batch_payload["items"]], ["A", "B", "C"])
        self.assertEqual([record["source_problem_ids"] for record in records], [["A"], ["C"]])
        self.assertEqual(len(markdown_paths), 2)
        self.assertEqual(markdown_parent_names, ["A", "C"])
        self.assertTrue(markdown_paths[0].startswith("A_v1_campus_ops_"))
        self.assertTrue(markdown_paths[1].startswith("C_v1_campus_ops_"))

    def test_batch_single_run_continues_after_embedding_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            temp = Path(tempdir)
            source_dir = temp / "schemas"
            output_dir = temp / "output"
            artifact_dir = temp / "artifacts"
            report_dir = temp / "reports"
            source_dir.mkdir(parents=True, exist_ok=True)
            for problem_id in ("A", "B", "C"):
                (source_dir / f"{problem_id}.json").write_text(
                    json.dumps(make_schema(problem_id=problem_id), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

            pipeline = GenerationPipeline(
                source_dir=source_dir,
                output_dir=output_dir,
                artifact_dir=artifact_dir,
                report_dir=report_dir,
                generator=FakeGenerator(),
                planner=EmbeddingFailurePlanner(fail_problem_id="B"),
                problem_repository=FakeProblemRepository(),
            )
            records = pipeline.run(
                mode="single",
                problem_ids=["A", "B", "C"],
                variants=1,
                theme_id="campus_ops",
                batch_source_dir=source_dir,
            )

            batch_artifacts = sorted(artifact_dir.glob("batch_*.json"))
            self.assertEqual(len(batch_artifacts), 1)
            batch_payload = json.loads(batch_artifacts[0].read_text(encoding="utf-8"))

        self.assertEqual(batch_payload["status"], "failed")
        self.assertEqual(batch_payload["completed_count"], 2)
        self.assertEqual(batch_payload["failed_count"], 1)
        self.assertEqual(batch_payload["failed_problem_id"], "B")
        self.assertEqual([item["problem_id"] for item in batch_payload["items"]], ["A", "B", "C"])
        failed_item = next(item for item in batch_payload["items"] if item["problem_id"] == "B")
        self.assertEqual(failed_item["status"], "failed")
        self.assertIn("embedding service unavailable", failed_item["error_reason"])
        self.assertEqual([record["source_problem_ids"] for record in records], [["A"], ["C"]])


class QualityIterationPipelineTests(unittest.TestCase):
    def test_quality_iteration_stops_after_first_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            temp = Path(tempdir)
            source_dir = temp / "schemas"
            output_dir = temp / "output"
            artifact_dir = temp / "artifacts"
            report_dir = temp / "reports"
            source_dir.mkdir(parents=True, exist_ok=True)
            (source_dir / "A.json").write_text(
                json.dumps(make_schema(problem_id="A"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            planner = RevisionAwarePlanner()
            generator = RevisionAwareGenerator()
            evaluator = SequencedQualityEvaluator([make_quality_report_payload(overall_status="pass", round_index=1)])

            pipeline = GenerationPipeline(
                source_dir=source_dir,
                output_dir=output_dir,
                artifact_dir=artifact_dir,
                report_dir=report_dir,
                generator=generator,
                planner=planner,
                problem_repository=FakeProblemRepository(),
                quality_evaluator=evaluator,
            )
            records = pipeline.run(
                mode="single",
                problem_ids=["A"],
                variants=1,
                theme_id="campus_ops",
                quality_iterations=2,
            )

            summary_path = Path(records[0]["iteration_summary_path"])
            summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
            quality_json_path = Path(records[0]["quality_report_json_path"])
            quality_md_path = Path(records[0]["quality_report_md_path"])
            quality_json_exists = quality_json_path.exists()
            quality_md_exists = quality_md_path.exists()
            artifact_path = Path(records[0]["artifact_path"])
            markdown_path = Path(records[0]["markdown_path"])

        self.assertEqual(len(planner.calls), 1)
        self.assertEqual(len(generator.calls), 1)
        self.assertEqual(len(evaluator.calls), 1)
        self.assertEqual(records[0]["final_round_index"], 1)
        self.assertTrue(quality_json_exists)
        self.assertTrue(quality_md_exists)
        self.assertEqual(artifact_path.parent.name, "A")
        self.assertEqual(markdown_path.parent.name, "A")
        self.assertEqual(quality_json_path.parent.name, "A")
        self.assertEqual(quality_md_path.parent.name, "A")
        self.assertEqual(summary_path.parent.name, "A")
        self.assertEqual(summary_payload["final_round_index"], 1)
        self.assertEqual(summary_payload["stop_reason"], "pass")
        self.assertEqual(len(summary_payload["rounds"]), 1)
        self.assertTrue(summary_payload["rounds"][0]["artifact_path"].endswith("_round1.json"))
        self.assertEqual(Path(summary_payload["rounds"][0]["artifact_path"]).parent.name, "A")
        self.assertEqual(Path(summary_payload["rounds"][0]["markdown_path"]).parent.name, "A")

    def test_quality_iteration_runs_second_round_for_revise_quality(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            temp = Path(tempdir)
            source_dir = temp / "schemas"
            output_dir = temp / "output"
            artifact_dir = temp / "artifacts"
            report_dir = temp / "reports"
            source_dir.mkdir(parents=True, exist_ok=True)
            (source_dir / "A.json").write_text(
                json.dumps(make_schema(problem_id="A"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            planner = RevisionAwarePlanner()
            generator = RevisionAwareGenerator()
            evaluator = SequencedQualityEvaluator(
                [
                    make_quality_report_payload(
                        overall_status="revise_quality",
                        round_index=1,
                        suggested_revisions=["补齐样例解释。"],
                        strengths=["约束表达稳定"],
                    ),
                    make_quality_report_payload(overall_status="pass", round_index=2),
                ]
            )

            pipeline = GenerationPipeline(
                source_dir=source_dir,
                output_dir=output_dir,
                artifact_dir=artifact_dir,
                report_dir=report_dir,
                generator=generator,
                planner=planner,
                problem_repository=FakeProblemRepository(),
                quality_evaluator=evaluator,
            )
            records = pipeline.run(
                mode="single",
                problem_ids=["A"],
                variants=1,
                theme_id="campus_ops",
                quality_iterations=2,
            )

            summary_path = Path(records[0]["iteration_summary_path"])
            summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
            quality_json_path = Path(records[0]["quality_report_json_path"])
            quality_md_path = Path(records[0]["quality_report_md_path"])
            artifact_path = Path(records[0]["artifact_path"])
            markdown_path = Path(records[0]["markdown_path"])

        self.assertEqual(len(planner.calls), 2)
        self.assertEqual(len(generator.calls), 2)
        self.assertEqual(planner.calls[0]["revision_context"], {})
        self.assertEqual(
            planner.calls[1]["revision_context"]["suggested_revisions"],
            ["补齐样例解释。"],
        )
        self.assertEqual(
            planner.calls[1]["revision_context"]["strengths_to_keep"],
            ["约束表达稳定"],
        )
        self.assertEqual(
            generator.calls[1]["revision_context"]["suggested_revisions"],
            ["补齐样例解释。"],
        )
        self.assertEqual(records[0]["final_round_index"], 2)
        self.assertEqual(artifact_path.parent.name, "A")
        self.assertEqual(markdown_path.parent.name, "A")
        self.assertEqual(quality_json_path.parent.name, "A")
        self.assertEqual(quality_md_path.parent.name, "A")
        self.assertEqual(summary_path.parent.name, "A")
        self.assertEqual(summary_payload["stop_reason"], "pass")
        self.assertEqual(len(summary_payload["rounds"]), 2)
        self.assertTrue(summary_payload["rounds"][1]["artifact_path"].endswith("_round2.json"))
        self.assertTrue(summary_payload["rounds"][1]["quality_report_json_path"].endswith("_round2_quality_report.json"))
        self.assertEqual(Path(summary_payload["rounds"][0]["artifact_path"]).parent.name, "A")
        self.assertEqual(Path(summary_payload["rounds"][1]["artifact_path"]).parent.name, "A")
        self.assertEqual(Path(summary_payload["rounds"][0]["quality_report_json_path"]).parent.name, "A")
        self.assertEqual(Path(summary_payload["rounds"][1]["quality_report_json_path"]).parent.name, "A")

    def test_quality_iteration_can_run_third_round(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            temp = Path(tempdir)
            source_dir = temp / "schemas"
            output_dir = temp / "output"
            artifact_dir = temp / "artifacts"
            report_dir = temp / "reports"
            source_dir.mkdir(parents=True, exist_ok=True)
            (source_dir / "A.json").write_text(
                json.dumps(make_schema(problem_id="A"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            planner = RevisionAwarePlanner()
            generator = RevisionAwareGenerator()
            evaluator = SequencedQualityEvaluator(
                [
                    make_quality_report_payload(
                        overall_status="revise_quality",
                        round_index=1,
                        suggested_revisions=["补齐样例解释。"],
                        strengths=["约束表达稳定"],
                    ),
                    make_quality_report_payload(
                        overall_status="reject_as_retheme",
                        round_index=2,
                        suggested_revisions=["拉开核心任务差异。"],
                        strengths=["样例结构正确"],
                    ),
                    make_quality_report_payload(overall_status="pass", round_index=3),
                ]
            )

            pipeline = GenerationPipeline(
                source_dir=source_dir,
                output_dir=output_dir,
                artifact_dir=artifact_dir,
                report_dir=report_dir,
                generator=generator,
                planner=planner,
                problem_repository=FakeProblemRepository(),
                quality_evaluator=evaluator,
            )
            records = pipeline.run(
                mode="single",
                problem_ids=["A"],
                variants=1,
                theme_id="campus_ops",
                quality_iterations=3,
            )

            summary_path = Path(records[0]["iteration_summary_path"])
            summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
            quality_json_path = Path(records[0]["quality_report_json_path"])
            quality_md_path = Path(records[0]["quality_report_md_path"])
            artifact_path = Path(records[0]["artifact_path"])
            markdown_path = Path(records[0]["markdown_path"])

        self.assertEqual(len(planner.calls), 3)
        self.assertEqual(len(generator.calls), 3)
        self.assertEqual(
            planner.calls[2]["revision_context"]["suggested_revisions"],
            ["拉开核心任务差异。"],
        )
        self.assertEqual(records[0]["final_round_index"], 3)
        self.assertEqual(artifact_path.parent.name, "A")
        self.assertEqual(markdown_path.parent.name, "A")
        self.assertEqual(quality_json_path.parent.name, "A")
        self.assertEqual(quality_md_path.parent.name, "A")
        self.assertEqual(summary_path.parent.name, "A")
        self.assertEqual(summary_payload["stop_reason"], "pass")
        self.assertEqual(len(summary_payload["rounds"]), 3)
        self.assertTrue(summary_payload["rounds"][2]["artifact_path"].endswith("_round3.json"))
        self.assertTrue(summary_payload["rounds"][2]["quality_report_json_path"].endswith("_round3_quality_report.json"))
        self.assertEqual(Path(summary_payload["rounds"][0]["artifact_path"]).parent.name, "A")
        self.assertEqual(Path(summary_payload["rounds"][1]["artifact_path"]).parent.name, "A")
        self.assertEqual(Path(summary_payload["rounds"][2]["artifact_path"]).parent.name, "A")
        self.assertEqual(Path(summary_payload["rounds"][0]["quality_report_json_path"]).parent.name, "A")
        self.assertEqual(Path(summary_payload["rounds"][1]["quality_report_json_path"]).parent.name, "A")
        self.assertEqual(Path(summary_payload["rounds"][2]["quality_report_json_path"]).parent.name, "A")

    def test_quality_iteration_stops_after_difference_insufficient(self) -> None:
        plan = make_validation_plan("canonical_witness")
        plan.problem_id = "A_GEN"
        plan.source_problem_ids = ["A"]
        plan.new_schema_snapshot.problem_id = "A_GEN"
        plan.applied_rule = ""
        plan.planning_status = "difference_insufficient"
        plan.planning_error_reason = "规则规划未达到有效差异门槛。"
        plan.planning_feedback = "建议调整核心任务定义。"

        with tempfile.TemporaryDirectory() as tempdir:
            temp = Path(tempdir)
            source_dir = temp / "schemas"
            output_dir = temp / "output"
            artifact_dir = temp / "artifacts"
            report_dir = temp / "reports"
            source_dir.mkdir(parents=True, exist_ok=True)
            (source_dir / "A.json").write_text(
                json.dumps(make_schema(problem_id="A"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            evaluator = SequencedQualityEvaluator(
                [
                    make_quality_report_payload(
                        overall_status="reject_as_retheme",
                        generated_status="difference_insufficient",
                        round_index=1,
                    )
                ]
            )

            pipeline = GenerationPipeline(
                source_dir=source_dir,
                output_dir=output_dir,
                artifact_dir=artifact_dir,
                report_dir=report_dir,
                generator=StatusGenerator(
                    status="difference_insufficient",
                    error_reason="规则规划未达到有效差异门槛。",
                    feedback="建议调整核心任务定义。",
                ),
                planner=FixedPlanPlanner(plan),
                problem_repository=FakeProblemRepository(),
                quality_evaluator=evaluator,
            )
            records = pipeline.run(
                mode="single",
                problem_ids=["A"],
                variants=1,
                theme_id="campus_ops",
                quality_iterations=2,
            )

            summary_path = Path(records[0]["iteration_summary_path"])
            summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
            artifact_path = Path(records[0]["artifact_path"])
            markdown_path = Path(records[0]["markdown_path"])

        self.assertEqual(records[0]["final_round_index"], 1)
        self.assertEqual(artifact_path.parent.name, "A")
        self.assertEqual(markdown_path.parent.name, "A")
        self.assertEqual(summary_path.parent.name, "A")
        self.assertEqual(summary_payload["stop_reason"], "difference_insufficient")
        self.assertEqual(len(summary_payload["rounds"]), 1)


class ReportRenderingTests(unittest.TestCase):
    def test_single_success_report_uses_quad_compare_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            temp = Path(tempdir)
            source_dir = temp / "schemas"
            output_dir = temp / "output"
            artifact_dir = temp / "artifacts"
            report_dir = temp / "reports"
            source_dir.mkdir(parents=True, exist_ok=True)
            (source_dir / "A.json").write_text(
                json.dumps(make_schema(problem_id="A"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            pipeline = GenerationPipeline(
                source_dir=source_dir,
                output_dir=output_dir,
                artifact_dir=artifact_dir,
                report_dir=report_dir,
                generator=FakeGenerator(),
                planner=ProblemAwarePlanner(),
                problem_repository=FakeProblemRepository(),
            )
            records = pipeline.run(
                mode="single",
                problem_ids=["A"],
                variants=1,
                theme_id="campus_ops",
            )

            report_text = Path(records[0]["report_path"]).read_text(encoding="utf-8")
            report_path = Path(records[0]["report_path"])

        self.assertIn("# A 生成报告", report_text)
        self.assertEqual(report_path.parent.name, "A")
        self.assertEqual(report_path.name, "A.md")
        self.assertIn("### 四元组对比", report_text)
        self.assertIn("| 项目 | 原题 | 新题 | 变化判断 |", report_text)
        self.assertIn("#### 输入结构", report_text)
        self.assertIn("#### 核心约束", report_text)
        self.assertIn("#### 求解目标", report_text)
        self.assertIn("#### 关键不变量", report_text)
        self.assertIn("| 类型 |", report_text)
        self.assertIn("- anti_shallow_rationale: 变化已进入主导义务。", report_text)
        self.assertNotIn("### 审计轨迹", report_text)
        self.assertNotIn("applied_helpers", report_text)
        self.assertNotIn("candidate_attempts", report_text)
        self.assertNotIn("### 实例化四元组", report_text)

    def test_single_failure_report_uses_seed_summary_without_compare_tables(self) -> None:
        plan = make_validation_plan("canonical_witness")
        plan.problem_id = "A_GEN"
        plan.source_problem_ids = ["A"]
        plan.new_schema_snapshot.problem_id = "A_GEN"
        plan.applied_rule = ""
        plan.planning_status = "schema_insufficient"
        plan.predicted_schema_distance = 0.0
        plan.changed_axes_realized = []
        plan.rule_selection_reason = "当前规则难以形成主导义务变化。"
        plan.planning_error_reason = "当前种子缺少足够的结构增量空间。"
        plan.planning_feedback = "建议更换具备多解空间或天然失败语义的种子题。"
        plan.selection_trace = [
            {
                "rule_id": "canonical_witness",
                "accepted": True,
                "reason_code": "eligible",
                "selection_reason": "规范输出会退化成后处理。",
            },
            {
                "rule_id": "existence_to_counting",
                "accepted": False,
                "reason_code": "core_structure_mismatch",
                "selection_reason": "原题没有自然的组合分支。",
            },
        ]

        with tempfile.TemporaryDirectory() as tempdir:
            temp = Path(tempdir)
            source_dir = temp / "schemas"
            output_dir = temp / "output"
            artifact_dir = temp / "artifacts"
            report_dir = temp / "reports"
            source_dir.mkdir(parents=True, exist_ok=True)
            (source_dir / "A.json").write_text(
                json.dumps(make_schema(problem_id="A"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            pipeline = GenerationPipeline(
                source_dir=source_dir,
                output_dir=output_dir,
                artifact_dir=artifact_dir,
                report_dir=report_dir,
                generator=StatusGenerator(
                    status="schema_insufficient",
                    error_reason="当前种子缺少足够的结构增量空间。",
                    feedback="建议更换具备多解空间或天然失败语义的种子题。",
                ),
                planner=FixedPlanPlanner(plan),
                problem_repository=FakeProblemRepository(),
            )
            records = pipeline.run(
                mode="single",
                problem_ids=["A"],
                variants=1,
                theme_id="campus_ops",
            )

            report_text = Path(records[0]["report_path"]).read_text(encoding="utf-8")
            report_path = Path(records[0]["report_path"])

        self.assertIn("### 失败原因", report_text)
        self.assertEqual(report_path.parent.name, "A")
        self.assertEqual(report_path.name, "A.md")
        self.assertIn("### 原题四元组", report_text)
        self.assertIn("### 候选规则结论", report_text)
        self.assertIn("### 建议方向", report_text)
        self.assertIn("canonical_witness", report_text)
        self.assertNotIn("### 四元组对比", report_text)
        self.assertNotIn("| 项目 | 原题 | 新题 | 变化判断 |", report_text)
        self.assertNotIn("### 审计轨迹", report_text)


class CliAndDocumentationTests(unittest.TestCase):
    def test_cli_supports_single_and_same_family_with_rule_override(self) -> None:
        parser = build_parser()

        single_args = parser.parse_args(
            [
                "--mode",
                "single",
                "--problem-ids",
                "CF1",
                "CF2",
                "--timeout",
                "360",
                "--quality-iterations",
                "3",
            ]
        )
        _validate_args(parser, single_args)
        self.assertEqual(single_args.mode, "single")
        self.assertEqual(single_args.problem_ids, ["CF1", "CF2"])
        self.assertEqual(single_args.timeout, 360)
        self.assertEqual(single_args.quality_iterations, 3)

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

    def test_cli_rejects_invalid_quality_iteration_settings(self) -> None:
        parser = build_parser()

        with self.assertRaises(SystemExit):
            args = parser.parse_args(["--mode", "single", "--problem-ids", "CF1", "--quality-iterations", "4"])
            _validate_args(parser, args)

        with self.assertRaises(SystemExit):
            args = parser.parse_args(
                [
                    "--mode",
                    "same_family",
                    "--seed-a",
                    "P1",
                    "--seed-b",
                    "P2",
                    "--quality-iterations",
                    "1",
                ]
            )
            _validate_args(parser, args)

    def test_batch_source_dir_resolves_sorted_problem_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            source_dir = Path(tempdir) / "schemas"
            source_dir.mkdir(parents=True, exist_ok=True)
            for problem_id in ("B", "A"):
                (source_dir / f"{problem_id}.json").write_text(
                    json.dumps(make_schema(problem_id=problem_id), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

            args = build_parser().parse_args(["--mode", "single", "--source-dir", str(source_dir)])
            self.assertEqual(_load_batch_problem_ids(source_dir), ["A", "B"])
            self.assertEqual(_target_problem_ids(args), ["A", "B"])

    def test_batch_source_dir_rejects_empty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            source_dir = Path(tempdir) / "schemas"
            source_dir.mkdir(parents=True, exist_ok=True)

            with self.assertRaisesRegex(ValueError, "没有 schema 文件"):
                _load_batch_problem_ids(source_dir)

    def test_batch_source_dir_rejects_problem_id_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            source_dir = Path(tempdir) / "schemas"
            source_dir.mkdir(parents=True, exist_ok=True)
            (source_dir / "A.json").write_text(
                json.dumps(make_schema(problem_id="WRONG"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "problem_id 与文件名一致"):
                _load_batch_problem_ids(source_dir)

    def test_batch_source_dir_rejects_missing_problem_id(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            source_dir = Path(tempdir) / "schemas"
            source_dir.mkdir(parents=True, exist_ok=True)
            payload = make_schema(problem_id="A")
            payload.pop("problem_id")
            (source_dir / "A.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "显式提供 problem_id"):
                _load_batch_problem_ids(source_dir)

    def test_cli_rejects_non_positive_timeout(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--mode", "single", "--problem-ids", "CF1", "--timeout", "0"])

        with self.assertRaises(SystemExit):
            _validate_args(parser, args)

    def test_readmes_describe_rule_driven_four_tuple_flow(self) -> None:
        generator_readme = (GEN_DIR / "README.md").read_text(encoding="utf-8")
        rules_doc = (GEN_DIR / "RULES.md").read_text(encoding="utf-8")
        root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
        root_generator_section = _extract_readme_section(root_readme, "## 5. `生成题面`", "## 6. `题目质量评价`")

        for text in (generator_readme, root_generator_section):
            self.assertIn("规则", text)
            self.assertIn("single_seed_extension", text)
            self.assertIn("same_family_fusion", text)
            self.assertIn("selection_trace", text)
            self.assertIn("batch_", text)
            self.assertNotIn("distance_breakdown.T", text)
        self.assertNotIn("transform_space", generator_readme)
        self.assertNotIn("instantiated_parameters", generator_readme)
        self.assertNotIn("selected_structural_options", generator_readme)
        self.assertNotIn("schema_preparer.py", generator_readme)
        self.assertNotIn("prepared_schemas", generator_readme)
        self.assertNotIn("--prepared-schema-dir", generator_readme)
        self.assertNotIn("transform_space", root_generator_section)
        self.assertNotIn("instantiated_parameters", root_generator_section)
        self.assertNotIn("selected_structural_options", root_generator_section)
        self.assertNotIn("schema_preparer.py", root_generator_section)
        self.assertNotIn("prepared_schemas", root_generator_section)
        self.assertIn("check_eligibility", rules_doc)
        self.assertIn("validate_plan", rules_doc)
        self.assertIn("validate_problem", rules_doc)


class QwenClientTests(unittest.TestCase):
    def test_chat_json_retries_on_timeout_error(self) -> None:
        client = QwenClient(
            api_key="test-key",
            model="test-model",
            base_url="https://example.com/v1",
            timeout_s=5,
        )

        with mock.patch("qwen_client.time.sleep") as mocked_sleep:
            with mock.patch("qwen_client.urllib.request.urlopen") as mocked_urlopen:
                mocked_response = mock.MagicMock()
                mocked_response.__enter__.return_value.read.return_value = (
                    b'{"choices":[{"message":{"content":"{\\"status\\":\\"ok\\"}"}}]}'
                )
                mocked_urlopen.side_effect = [TimeoutError("timed out"), mocked_response]

                payload = client.chat_json(system_prompt="system", user_prompt="user", max_retries=2)

        self.assertEqual(payload, {"status": "ok"})
        self.assertEqual(mocked_urlopen.call_count, 2)
        mocked_sleep.assert_called_once()


class StubEmbeddingClient:
    def __init__(self, overrides: dict[str, list[float]] | None = None) -> None:
        self.embedding_model = "stub-embedding-v1"
        self.distance_cache_path = None
        self.overrides = {_normalize_embedding_text(key): list(value) for key, value in dict(overrides or {}).items()}

    def embed_texts(
        self,
        texts: list[str],
        model: str | None = None,
        dimensions: int | None = None,
    ) -> list[list[float]]:
        return [self._vector_for_text(text) for text in texts]

    def _vector_for_text(self, text: str) -> list[float]:
        normalized = _normalize_embedding_text(text)
        if normalized in self.overrides:
            return list(self.overrides[normalized])
        return _toy_embedding(normalized)


class FailingEmbeddingClient:
    def __init__(self) -> None:
        self.embedding_model = "failing-embedding-v1"
        self.distance_cache_path = None

    def embed_texts(
        self,
        texts: list[str],
        model: str | None = None,
        dimensions: int | None = None,
    ) -> list[list[float]]:
        raise RuntimeError("embedding service unavailable")


class FakePlannerClient:
    def __init__(
        self,
        responses: dict[str, dict],
        selection_response: dict | None = None,
        eligibility_responses: dict[str, dict] | None = None,
        plan_review_responses: dict[str, dict] | None = None,
        problem_review_responses: dict[str, dict] | None = None,
    ) -> None:
        self.responses = copy.deepcopy(responses)
        self.selection_response = copy.deepcopy(selection_response)
        self.eligibility_responses = copy.deepcopy(eligibility_responses or {})
        self.plan_review_responses = copy.deepcopy(plan_review_responses or {})
        self.problem_review_responses = copy.deepcopy(problem_review_responses or {})
        self.calls: list[str] = []
        self.embedding_model = "stub-embedding-v1"
        self.distance_cache_path = None

    def chat_json(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> dict:
        if '"review_type": "eligibility"' in user_prompt:
            rule_id = _extract_rule_under_review_id(user_prompt)
            if rule_id in self.eligibility_responses:
                return copy.deepcopy(self.eligibility_responses[rule_id])
            if rule_id:
                return make_eligibility_payload(rule_id)
            raise AssertionError(f"无法从资格审查 prompt 中匹配规则。prompt={user_prompt}")

        if '"review_type": "rule_plan_validation"' in user_prompt:
            rule_id = _extract_rule_under_review_id(user_prompt)
            if not rule_id:
                raise AssertionError(f"无法从规划审查 prompt 中匹配规则。prompt={user_prompt}")
            self.calls.append(f"plan_review:{rule_id}")
            if rule_id in self.plan_review_responses:
                return copy.deepcopy(self.plan_review_responses[rule_id])
            return make_rule_review_payload(status="pass", evidence=f"{rule_id} 规划默认通过规则专属审查。")

        if '"review_type": "rule_problem_validation"' in user_prompt:
            rule_id = _extract_rule_under_review_id(user_prompt)
            if not rule_id:
                raise AssertionError(f"无法从题面审查 prompt 中匹配规则。prompt={user_prompt}")
            self.calls.append(f"problem_review:{rule_id}")
            if rule_id in self.problem_review_responses:
                return copy.deepcopy(self.problem_review_responses[rule_id])
            return make_rule_review_payload(status="pass", evidence=f"{rule_id} 题面默认通过规则专属审查。")

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

    def embed_texts(
        self,
        texts: list[str],
        model: str | None = None,
        dimensions: int | None = None,
    ) -> list[list[float]]:
        return [_toy_embedding(_normalize_embedding_text(text)) for text in texts]


class FixedPlanPlanner:
    def __init__(self, plan: VariantPlan) -> None:
        self.plan = plan

    def build_plan(self, **_: dict) -> VariantPlan:
        return copy.deepcopy(self.plan)


class FakeGenerator:
    def generate(
        self,
        schema_context: dict,
        plan: VariantPlan,
        original_problems: list[dict] | None = None,
        revision_context: dict | None = None,
    ) -> GeneratedProblem:
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


class StatusGenerator:
    def __init__(self, *, status: str, title: str = "", error_reason: str = "", feedback: str = "") -> None:
        self.status = status
        self.title = title
        self.error_reason = error_reason
        self.feedback = feedback

    def generate(
        self,
        schema_context: dict,
        plan: VariantPlan,
        original_problems: list[dict] | None = None,
        revision_context: dict | None = None,
    ) -> GeneratedProblem:
        return GeneratedProblem(
            title=self.title,
            description="",
            input_format="",
            output_format="",
            constraints=[],
            samples=[],
            notes="",
            status=self.status,
            error_reason=self.error_reason,
            feedback=self.feedback,
        )


class FailingOnProblemGenerator(FakeGenerator):
    def __init__(self, fail_problem_id: str) -> None:
        self.fail_problem_id = fail_problem_id

    def generate(
        self,
        schema_context: dict,
        plan: VariantPlan,
        original_problems: list[dict] | None = None,
        revision_context: dict | None = None,
    ) -> GeneratedProblem:
        current_problem_id = str(schema_context.get("seed_schema", {}).get("problem_id", ""))
        if current_problem_id == self.fail_problem_id:
            raise RuntimeError(f"{current_problem_id} 生成失败")
        return super().generate(schema_context, plan, original_problems, revision_context)


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


class ProblemAwarePlanner:
    def build_plan(self, **kwargs: dict) -> VariantPlan:
        seed_schema = dict(kwargs.get("seed_schema", {}))
        source_problem_id = str(seed_schema.get("problem_id", "unknown"))
        variant_index = int(kwargs.get("variant_index", 1))
        plan = copy.deepcopy(make_validation_plan("canonical_witness"))
        plan.problem_id = f"{source_problem_id}_GEN"
        plan.variant_index = variant_index
        plan.source_problem_ids = [source_problem_id]
        plan.new_schema_snapshot.problem_id = f"{source_problem_id}_GEN"
        plan.seed = 20260409
        return plan


class RevisionAwarePlanner:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def build_plan(self, **kwargs: dict) -> VariantPlan:
        revision_context = copy.deepcopy(dict(kwargs.get("revision_context") or {}))
        seed_schema = dict(kwargs.get("seed_schema", {}))
        source_problem_id = str(seed_schema.get("problem_id", "unknown"))
        variant_index = int(kwargs.get("variant_index", 1))
        round_index = len(self.calls) + 1
        plan = copy.deepcopy(make_validation_plan("canonical_witness"))
        plan.problem_id = f"{source_problem_id}_GEN_R{round_index}"
        plan.variant_index = variant_index
        plan.source_problem_ids = [source_problem_id]
        plan.new_schema_snapshot.problem_id = f"{source_problem_id}_GEN_R{round_index}"
        plan.seed = 20260409 + round_index
        self.calls.append(
            {
                "round_index": round_index,
                "revision_context": revision_context,
                "problem_id": plan.problem_id,
            }
        )
        return plan


class RevisionAwareGenerator(FakeGenerator):
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate(
        self,
        schema_context: dict,
        plan: VariantPlan,
        original_problems: list[dict] | None = None,
        revision_context: dict | None = None,
    ) -> GeneratedProblem:
        round_index = len(self.calls) + 1
        self.calls.append(
            {
                "round_index": round_index,
                "revision_context": copy.deepcopy(revision_context or {}),
                "plan_problem_id": plan.problem_id,
            }
        )
        return GeneratedProblem(
            title=f"第 {round_index} 轮新题",
            description=f"这是第 {round_index} 轮生成结果。",
            input_format="输入三行，每行一个整数。",
            output_format="输出一个规范构造。",
            constraints=["时间限制：2 秒。", "空间限制：256 MB。"],
            samples=[
                {"input": "1\n2\n3", "output": "3 2 1", "explanation": "样例一。"},
                {"input": "2\n3\n4", "output": "4 3 2", "explanation": "样例二。"},
            ],
            notes="无",
        )


class SequencedQualityEvaluator:
    def __init__(self, reports: list[dict[str, object]]) -> None:
        self.reports = [copy.deepcopy(item) for item in reports]
        self.calls: list[dict[str, object]] = []

    def evaluate_problem(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(dict(kwargs))
        if not self.reports:
            raise AssertionError("unexpected evaluate_problem call")
        return copy.deepcopy(self.reports.pop(0))


class EmbeddingFailurePlanner:
    def __init__(self, fail_problem_id: str) -> None:
        self.fail_problem_id = fail_problem_id

    def build_plan(self, **kwargs: dict) -> VariantPlan:
        seed_schema = copy.deepcopy(dict(kwargs.get("seed_schema", {})))
        source_problem_id = str(seed_schema.get("problem_id", "unknown"))
        if source_problem_id == self.fail_problem_id:
            candidate_schema = copy.deepcopy(seed_schema)
            candidate_schema.setdefault("objective", {})["description"] = "判断是否能找到任意合法方案。"
            compute_schema_distance(seed_schema, candidate_schema, embedding_client=FailingEmbeddingClient())
        return ProblemAwarePlanner().build_plan(**kwargs)


def _extract_readme_section(text: str, start_marker: str, end_marker: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


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
        "ranked_rule_ids": [rule_id],
        "selected_rule_id": rule_id,
        "selection_reason": f"规则 {rule_id} 在当前 schema 上最容易形成主导义务变化。",
        "innovation_reason": "它会改变核心任务而不是只改叙事或输出外壳。",
        "difficulty_reason": "主求解责任会明显抬高，不能沿用原题主框架直接完成。",
        "risk_reason": "需要控制换皮风险，但整体可落地。",
        "error_reason": "",
        "feedback": "",
    }


def make_quality_report_payload(
    *,
    overall_status: str,
    generated_status: str = "ok",
    round_index: int = 1,
    quality_score: float = 91.0,
    divergence_score: float = 82.0,
    suggested_revisions: list[str] | None = None,
    strengths: list[str] | None = None,
) -> dict[str, object]:
    revision_suggestions = list(suggested_revisions or [])
    strengths_to_keep = list(strengths or ["题面基础结构完整"])
    return {
        "overall": {
            "status": overall_status,
            "quality_score": quality_score,
            "divergence_score": divergence_score,
            "schema_distance": 0.42,
            "generated_status": generated_status,
        },
        "quality": {
            "dimension_scores": [],
            "strengths": strengths_to_keep,
        },
        "divergence": {
            "schema_distance_breakdown": {},
            "changed_axes_planned": ["C", "O"],
            "changed_axes_realized": ["C", "O"],
            "semantic_difference": 0.8,
            "solution_transfer_risk": 0.2,
            "surface_retheme_risk": 0.2,
            "verdict": "pass" if overall_status != "reject_as_retheme" else "reject_as_retheme",
            "rationale": "测试用差异说明。",
        },
        "hard_checks": [],
        "issues": [],
        "suggested_revisions": revision_suggestions,
        "revision_brief": {
            "round_index": round_index,
            "overall_status": overall_status,
            "generated_status": generated_status,
            "quality_score": quality_score,
            "divergence_score": divergence_score,
            "failed_hard_checks": [],
            "issues": [],
            "suggested_revisions": revision_suggestions,
            "strengths_to_keep": strengths_to_keep,
        },
        "snapshots": {
            "original_problem": {"title": "Seed A"},
            "difference_plan": {"rationale": "测试"},
        },
    }


def make_eligibility_payload(
    rule_id: str,
    *,
    status: str = "eligible",
    score: float = 0.75,
    reason_code: str = "eligible",
    selection_reason: str | None = None,
    risk_tags: list[str] | None = None,
    evidence: str = "schema 与规则声明之间存在稳定匹配证据。",
    feedback: str = "",
) -> dict:
    default_reason = f"规则 {rule_id} 通过资格审查。"
    return {
        "status": status,
        "score": score,
        "reason_code": reason_code,
        "selection_reason": selection_reason or default_reason,
        "risk_tags": list(risk_tags or []),
        "evidence": evidence,
        "feedback": feedback,
    }


def make_rule_review_payload(
    *,
    status: str = "pass",
    reason_code: str = "ok",
    message: str = "规则专属审查通过。",
    errors: list[str] | None = None,
    evidence: str = "规则专属审查已引用具体证据。",
) -> dict:
    return {
        "status": status,
        "reason_code": reason_code,
        "message": message,
        "errors": list(errors or []),
        "evidence": evidence,
    }


def _extract_rule_under_review_id(user_prompt: str) -> str:
    match = re.search(r'"rule_under_review"\s*:\s*{\s*"id"\s*:\s*"([^"]+)"', user_prompt, re.DOTALL)
    return match.group(1) if match else ""


def _normalize_embedding_text(text: str) -> str:
    return " ".join(str(text).strip().lower().split())


def _toy_embedding(text: str) -> list[float]:
    tokens = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", text)
    features = [
        1.0 if any(token in {"decision", "判断", "存在", "合法"} for token in tokens) else 0.0,
        1.0 if any(token in {"count", "统计", "counting"} for token in tokens) else 0.0,
        1.0 if any(token in {"construct", "construction", "构造", "witness"} for token in tokens) else 0.0,
        1.0 if any(token in {"minimize", "minimum", "最小", "保底"} for token in tokens) else 0.0,
        1.0 if any(token in {"array", "数组"} for token in tokens) else 0.0,
        1.0 if any(token in {"tree", "树"} for token in tokens) else 0.0,
        1.0 if any(token in {"graph", "图"} for token in tokens) else 0.0,
        1.0 if any(token in {"constraint", "约束", "义务"} for token in tokens) else 0.0,
        1.0 if any(token in {"invariant", "不变量"} for token in tokens) else 0.0,
        ((sum(ord(char) for char in text) % 17) + 1) / 100.0,
        ((len(text) % 13) + 1) / 100.0,
    ]
    norm = sum(value * value for value in features) ** 0.5 or 1.0
    return [value / norm for value in features]


def make_distance_breakdown(*, i: float, c: float, o: float, v: float, total: float, backend: str = "embedding") -> dict:
    return {
        "distance_version": "v2",
        "backend": backend,
        "total": total,
        "axis_scores": {"I": i, "C": c, "O": o, "V": v},
        "components": {
            "input_tree_distance": i,
            "constraint_match_distance": c,
            "objective_type_distance": o,
            "objective_text_distance": o,
            "invariant_match_distance": v,
        },
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
        "new_schema": {
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
            "objective": {"type": "construction", "description": "输出一个规范 witness。"},
            "invariant": {
                "invariants": [
                    {"name": "base_invariant", "description": "基础不变量保持成立。"},
                    {"name": f"{rule_id}_invariant", "description": f"{rule_id} 引入新的验证不变量。"}
                ]
            },
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
        "applied_helpers": make_applied_helpers(rule_id),
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
    constraints = base["new_schema"]["core_constraints"]["constraints"]
    invariants = base["new_schema"]["invariant"]["invariants"]
    if rule_id == "construct_or_obstruction":
        base["new_schema"]["objective"] = {"type": "construction", "description": "输出构造或阻碍证书。"}
        constraints.append({"name": "obstruction_certificate", "description": "当无解时，必须输出一个可局部检查的冲突证书。"})
    elif rule_id == "existence_to_counting":
        base["new_schema"]["objective"] = {"type": "counting", "description": "统计所有合法方案数。"}
        constraints.append({"name": "counting_scope", "description": "两个方案只有在选择对象集合不同或等价类不同的情况下才计作不同答案；结果对 998244353 取模。"})
        invariants.append({"name": "finite_counting", "description": "候选对象空间有限，且每个对象都能映射到唯一计数单元。"})
    elif rule_id == "minimum_guarantee_under_perturbation":
        base["new_schema"]["objective"] = {"type": "minimize_value", "description": "求最小保底阈值。"}
        constraints.append({"name": "worst_case_perturbation", "description": "必须在任意合法扰动顺序下都保证目标成立。"})
        invariants.append({"name": "guarantee_invariant", "description": "存在一个保底不变量，使最坏情形仍能维持可行。"})
    else:
        constraints.append({"name": "canonical_order", "description": "所有合法构造需要按统一规范顺序输出。"})
    return base


def make_same_family_payload(rule_id: str, drop_fields: set[str] | None = None) -> dict:
    changed_axes = ["I", "C", "V"] if rule_id == "interlocked_constraints" else ["C", "O", "V"]
    objective = (
        {"type": "decision", "description": "判断是否存在合法方案。"}
        if rule_id == "interlocked_constraints"
        else {"type": "construction", "description": "输出共享主核下的规范构造。"}
    )
    payload = {
        "status": "ok",
        "error_reason": "",
        "feedback": "",
        "eligibility_reason": "两个种子题共享稳定主核。",
        "core_transformation_summary": "共享主核承受更强的新义务。",
        "difference_plan": {
            "changed_axes": changed_axes,
            "rationale": "共享主核上叠加双向不可删义务。",
            "summary": "通过单主核和反串联硬门槛。",
        },
        "new_schema": {
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
            "objective": objective,
            "invariant": {
                "invariants": [
                    {"name": "base_invariant", "description": "基础不变量保持成立。"},
                    {"name": "fusion_invariant", "description": "共享状态核同时维持双重义务。"}
                ]
            },
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
        "applied_helpers": make_applied_helpers(rule_id),
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
        payload["new_schema"]["input_structure"] = {
            "type": "array",
            "length": {"min": 4, "max": 8},
            "value_range": {"min": 0, "max": 50},
            "properties": {"ordered": True, "segmented": True, "capacity_indexed": True},
        }
        payload["new_schema"]["core_constraints"]["constraints"] = [
            {"name": "capacity_lock", "description": "每一步状态转移都必须同时满足共享容量配额。"},
            {"name": "conflict_lock", "description": "同一步转移中被冲突关系绑定的对象不能共同进入合法状态。"},
        ]
        payload["new_schema"]["invariant"]["invariants"] = [
            {"name": "shared_pressure", "description": "任一可达状态都同时承受容量与冲突两类义务。"},
            {"name": "non_sequential_core", "description": "任何合法状态都不能拆成先满足一题再满足另一题的串联过程。"},
        ]
    if drop_fields:
        for field in drop_fields:
            if field == "why_not_sequential_composition":
                payload["why_not_sequential_composition"] = ""
            elif field == "fusion_ablation.without_seed_a":
                payload["fusion_ablation"]["without_seed_a"] = ""
            elif field == "fusion_ablation.without_seed_b":
                payload["fusion_ablation"]["without_seed_b"] = ""
    return payload


def make_validation_plan(rule_id: str) -> VariantPlan:
    theme = Theme(
        theme_id="campus_ops",
        name="校园运营",
        tone="日常规则",
        keywords=["社团"],
        mapping_hint="校园资源调度。",
    )
    new_schema = NewSchema(
        problem_id=f"PLAN_{rule_id}",
        source="codeforces",
        input_structure={
            "type": "array",
            "length": {"min": 3, "max": 3},
            "value_range": {"min": 1, "max": 9},
            "properties": {"ordered": True} if "interlocked" in rule_id or "shared_core" in rule_id else {},
        },
        core_constraints={"constraints": [{"name": "base_constraint", "description": "基础约束。"}]},
        objective={"type": "construction", "description": "输出一个规范构造。"},
        invariant={"invariants": [{"name": "base_invariant", "description": "基础不变量。"}]},
        theme={"id": "campus_ops", "name": "校园运营"},
        difficulty="Hard",
    )
    if rule_id == "interlocked_constraints":
        new_schema.input_structure = {
            "type": "array",
            "length": {"min": 4, "max": 8},
            "value_range": {"min": 0, "max": 50},
            "properties": {"ordered": True, "segmented": True, "capacity_indexed": True},
        }
        new_schema.objective = {"type": "decision", "description": "判断是否存在合法方案。"}
    objective = new_schema.objective
    if rule_id == "existence_to_counting":
        objective = {"type": "counting", "description": "统计所有合法方案数。"}
    elif rule_id == "minimum_guarantee_under_perturbation":
        objective = {"type": "minimize_value", "description": "求最小保底阈值。"}
    elif rule_id == "interlocked_constraints":
        objective = {"type": "decision", "description": "判断是否存在合法方案。"}
    return VariantPlan(
        problem_id=new_schema.problem_id,
        variant_index=1,
        seed=1,
        mode="same_family_fusion" if "interlocked" in rule_id or "shared_core" in rule_id else "single_seed_extension",
        theme=theme,
        source_problem_ids=["A", "B"] if "interlocked" in rule_id or "shared_core" in rule_id else ["A"],
        objective=objective,
        difficulty="Hard",
        rule_selection_reason="测试",
        input_summary="类型=array",
        constraint_summary=["基础约束。"],
        invariant_summary=["基础不变量。"],
        difference_plan=DifferencePlan(
            target_distance_band={"min": 0.35, "max": 0.60},
            changed_axes=["I", "C", "V"] if rule_id == "interlocked_constraints" else ["C", "O", "V"],
            same_family_allowed=True,
            forbidden_reuse=["A"],
            rationale="测试",
            summary="测试",
            mode="same_family_fusion" if "interlocked" in rule_id or "shared_core" in rule_id else "single_seed_extension",
        ),
        new_schema_snapshot=new_schema,
        predicted_schema_distance=0.37 if rule_id == "interlocked_constraints" else 0.45,
        distance_breakdown=make_distance_breakdown(
            i=0.25 if rule_id == "interlocked_constraints" else 0.0,
            c=0.5,
            o=0.0 if rule_id == "interlocked_constraints" else 0.8,
            v=0.4,
            total=0.37 if rule_id == "interlocked_constraints" else 0.45,
        ),
        changed_axes_realized=["I", "C", "V"] if rule_id == "interlocked_constraints" else ["C", "O", "V"],
        applied_rule=rule_id,
        algorithmic_delta_claim={
            "seed_solver_core": "基础判定",
            "reusable_subroutines": "状态预处理",
            "new_solver_core": "承担更强的新义务",
            "new_proof_obligation": "证明新责任成立",
            "why_direct_reuse_fails": "原解缺少新责任的验证链路",
        },
        anti_shallow_rationale="变化已进入主导义务。",
        shared_core_summary="共享主核" if "interlocked" in rule_id or "shared_core" in rule_id else "",
        shared_core_anchors={
            "shared_state": "统一状态",
            "shared_transition": "统一转移",
            "shared_decision_basis": "统一判定",
        }
        if "interlocked" in rule_id or "shared_core" in rule_id
        else {},
        seed_contributions={"seed_a": "容量义务", "seed_b": "冲突义务"}
        if "interlocked" in rule_id or "shared_core" in rule_id
        else {},
        fusion_ablation={"without_seed_a": "退化", "without_seed_b": "退化"}
        if "interlocked" in rule_id or "shared_core" in rule_id
        else {},
        applied_helpers=make_applied_helpers(rule_id),
    )


def make_valid_problem_cases() -> dict[str, GeneratedProblem]:
    return {
        "canonical_witness": GeneratedProblem(
            title="规范构造",
            description="请输出一个满足条件的规范构造，并按字典序最小的 witness 作为答案。",
            input_format="输入三行。",
            output_format="输出一个规范构造。",
            constraints=["时间限制：2 秒。", "空间限制：256 MB。"],
            samples=[{"input": "1\n2\n3", "output": "1 2 3", "explanation": "样例。"}, {"input": "3\n2\n1", "output": "1 2 3", "explanation": "样例。"}],
            notes="若有多种方案，输出 canonical witness。",
        ),
        "construct_or_obstruction": GeneratedProblem(
            title="构造或证书",
            description="若存在合法解，输出一个构造；否则输出一个来自主约束不可兼容关系的可局部检查冲突证书。",
            input_format="输入三行。",
            output_format="输出构造或 obstruction 证书。",
            constraints=["时间限制：2 秒。", "空间限制：256 MB。"],
            samples=[{"input": "1\n2\n3", "output": "OK", "explanation": "样例。"}, {"input": "3\n2\n1", "output": "FAIL", "explanation": "样例。"}],
            notes="无解时必须给出由主约束直接定义的结构化证书。",
        ),
        "existence_to_counting": GeneratedProblem(
            title="计数任务",
            description="统计所有不同合法方案的个数，等价方案不重复计数。",
            input_format="输入三行。",
            output_format="输出方案数。",
            constraints=["时间限制：2 秒。", "空间限制：256 MB。"],
            samples=[{"input": "1\n2\n3", "output": "2", "explanation": "样例。"}, {"input": "3\n2\n1", "output": "4", "explanation": "样例。"}],
            notes="结果对 998244353 取模。",
        ),
        "minimum_guarantee_under_perturbation": GeneratedProblem(
            title="保底阈值",
            description="求最小阈值，使任意合法扰动顺序下都能保证任务完成。",
            input_format="输入三行。",
            output_format="输出最小保底值。",
            constraints=["时间限制：2 秒。", "空间限制：256 MB。"],
            samples=[{"input": "1\n2\n3", "output": "5", "explanation": "样例。"}, {"input": "3\n2\n1", "output": "7", "explanation": "样例。"}],
            notes="需要考虑最坏情况。",
        ),
        "interlocked_constraints": GeneratedProblem(
            title="共享主核互锁",
            description="两个义务在同一共享状态过程中同时起作用，任何一步都必须同步满足容量与冲突要求。",
            input_format="输入三行。",
            output_format="若存在合法状态输出 Yes，否则输出 No。",
            constraints=["时间限制：2 秒。", "空间限制：256 MB。"],
            samples=[{"input": "1\n2\n3", "output": "Yes", "explanation": "样例。"}, {"input": "3\n2\n1", "output": "No", "explanation": "样例。"}],
            notes="双义务必须在同一状态过程中同步承压，不能拆成前后两个子任务。",
        ),
        "shared_core_objective_upgrade": GeneratedProblem(
            title="共享主核升级",
            description="在同一共享状态核上，要求输出一个规范构造，并同时保持双向义务成立。",
            input_format="输入三行。",
            output_format="输出一个共享主核下的规范构造。",
            constraints=["时间限制：2 秒。", "空间限制：256 MB。"],
            samples=[{"input": "1\n2\n3", "output": "1 2 3", "explanation": "样例。"}, {"input": "3\n2\n1", "output": "1 2 3", "explanation": "样例。"}],
            notes="更强目标仍然作用在 shared core 上。",
        ),
    }


if __name__ == "__main__":
    unittest.main()
