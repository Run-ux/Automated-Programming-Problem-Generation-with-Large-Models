from __future__ import annotations

import copy
import json
import re
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
from problem_generator import ProblemGenerator
from rule_handlers import get_rule_handler
from rulebook import RuleBook
from schema_preparer import SchemaPreparer
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
        self.assertTrue(rulebook.version())
        self.assertEqual(rulebook.enabled_rules("same_family_fusion"), [])
        enabled_ids = {item["id"] for item in rulebook.enabled_rules("single_seed_extension")}
        self.assertNotIn("canonical_witness", enabled_ids)
        self.assertIn("construct_or_obstruction", enabled_ids)
        first_rule = rulebook.enabled_rules("single_seed_extension")[0]
        self.assertTrue(first_rule["handler"])
        self.assertTrue(first_rule["family"])


class SchemaPreparerTests(unittest.TestCase):
    def test_schema_preparer_drops_transform_space_from_prepared_schema(self) -> None:
        raw_schema = {
            **make_schema(problem_id="SCHEMA"),
            "transform_space": {
                "objective_options": ["count"],
            },
        }

        with tempfile.TemporaryDirectory() as tempdir:
            source_dir = Path(tempdir) / "source"
            cache_dir = Path(tempdir) / "cache"
            source_dir.mkdir(parents=True, exist_ok=True)
            (source_dir / "SCHEMA.json").write_text(
                json.dumps(raw_schema, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            prepared_dir = SchemaPreparer(source_dir=source_dir, cache_dir=cache_dir).prepare(["SCHEMA"])
            prepared = json.loads((prepared_dir / "SCHEMA.json").read_text(encoding="utf-8"))

        self.assertNotIn("transform_space", prepared)
        self.assertEqual(
            set(prepared),
            {"problem_id", "source", "input_structure", "core_constraints", "objective", "invariant"},
        )


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
            original_schema=self.source_schema,
            prepared_schema=self.source_schema,
            original_problem=self.original_problem,
        )

        self.assertEqual(plan.planning_status, "ok")
        self.assertEqual(plan.applied_rule, "existence_to_counting")
        self.assertEqual(plan.rejected_candidates[0]["rule_id"], "construct_or_obstruction")
        self.assertEqual(client.calls, ["select", "plan:construct_or_obstruction", "plan:existence_to_counting"])

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

    def test_validate_candidate_rejects_unexpected_instantiated_schema_fields(self) -> None:
        planner = VariantPlanner(
            client=None,
            rulebook=self.rulebook,
            seed=29,
        )
        payload = make_single_payload("canonical_witness")
        payload["instantiated_schema"]["selected_input_options"] = ["legacy_option"]
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


class RuleHandlerTests(unittest.TestCase):
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
                    evidence="objective.type 已经是 construct_witness。",
                )
            },
        )
        canonical_result = canonical_handler.check_eligibility(
            client=canonical_client,
            mode="single_seed_extension",
            rule={"id": "canonical_witness", "handler": "canonical_witness", "family": "output_upgrade", "audit_tags": []},
            schema_context={
                "seed_schema": make_schema(problem_id="CW", objective_type="construct_witness"),
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
                handler = get_rule_handler({"id": rule_id, "handler": rule_id})
                outcome = handler.validate_problem(problem=base_problem, plan=make_validation_plan(rule_id))
                self.assertFalse(outcome.accepted)

    def test_rule_specific_problem_validation_accepts_matching_commitments(self) -> None:
        for rule_id, problem in make_valid_problem_cases().items():
            with self.subTest(rule_id=rule_id):
                handler = get_rule_handler({"id": rule_id, "handler": rule_id})
                outcome = handler.validate_problem(problem=problem, plan=make_validation_plan(rule_id))
                self.assertTrue(outcome.accepted)


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
            distance_breakdown={"I": 0.0, "C": 0.6, "O": 0.6, "V": 0.4, "total": 0.44},
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
            rule_version="2026-04-rules-v2",
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
            report_text = Path(records[0]["report_path"]).read_text(encoding="utf-8")

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
            {"I", "C", "O", "V", "total"},
        )
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
            self.assertNotIn(key, artifact["instantiated_schema_snapshot"])
            self.assertNotIn(key, report_text)


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
        rules_doc = (GEN_DIR / "RULES.md").read_text(encoding="utf-8")
        root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
        root_generator_section = _extract_readme_section(root_readme, "## 5. `生成题面`", "## 6. `题目质量评价`")

        for text in (generator_readme, root_generator_section):
            self.assertIn("规则", text)
            self.assertIn("single_seed_extension", text)
            self.assertIn("same_family_fusion", text)
            self.assertIn("selection_trace", text)
            self.assertNotIn("distance_breakdown.T", text)
        self.assertNotIn("transform_space", generator_readme)
        self.assertNotIn("instantiated_parameters", generator_readme)
        self.assertNotIn("selected_structural_options", generator_readme)
        self.assertNotIn("transform_space", root_generator_section)
        self.assertNotIn("instantiated_parameters", root_generator_section)
        self.assertNotIn("selected_structural_options", root_generator_section)
        self.assertIn("check_eligibility", rules_doc)
        self.assertIn("validate_plan", rules_doc)
        self.assertIn("validate_problem", rules_doc)


class FakePlannerClient:
    def __init__(
        self,
        responses: dict[str, dict],
        selection_response: dict | None = None,
        eligibility_responses: dict[str, dict] | None = None,
    ) -> None:
        self.responses = copy.deepcopy(responses)
        self.selection_response = copy.deepcopy(selection_response)
        self.eligibility_responses = copy.deepcopy(eligibility_responses or {})
        self.calls: list[str] = []

    def chat_json(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> dict:
        if '"review_type": "eligibility"' in user_prompt:
            rule_id = _extract_rule_under_review_id(user_prompt)
            if rule_id in self.eligibility_responses:
                return copy.deepcopy(self.eligibility_responses[rule_id])
            if rule_id:
                return make_eligibility_payload(rule_id)
            raise AssertionError(f"无法从资格审查 prompt 中匹配规则。prompt={user_prompt}")

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


def _extract_rule_under_review_id(user_prompt: str) -> str:
    match = re.search(r'"rule_under_review"\s*:\s*{\s*"id"\s*:\s*"([^"]+)"', user_prompt, re.DOTALL)
    return match.group(1) if match else ""


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
    constraints = base["instantiated_schema"]["core_constraints"]["constraints"]
    invariants = base["instantiated_schema"]["invariant"]["invariants"]
    if rule_id == "construct_or_obstruction":
        base["instantiated_schema"]["objective"] = {"type": "construct_or_obstruction", "description": "输出构造或阻碍证书。"}
        base["auxiliary_moves"] = ["局部附加条件"]
        constraints.append({"name": "obstruction_certificate", "description": "当无解时，必须输出一个可局部检查的冲突证书。"})
    elif rule_id == "existence_to_counting":
        base["instantiated_schema"]["objective"] = {"type": "count", "description": "统计所有合法方案数。"}
        constraints.append({"name": "counting_scope", "description": "两个方案只有在选择对象集合不同或等价类不同的情况下才计作不同答案；结果对 998244353 取模。"})
        invariants.append({"name": "finite_counting", "description": "候选对象空间有限，且每个对象都能映射到唯一计数单元。"})
    elif rule_id == "minimum_guarantee_under_perturbation":
        base["instantiated_schema"]["objective"] = {"type": "minimize_value", "description": "求最小保底阈值。"}
        base["auxiliary_moves"] = ["局部附加条件"]
        constraints.append({"name": "worst_case_perturbation", "description": "必须在任意合法扰动顺序下都保证目标成立。"})
        invariants.append({"name": "guarantee_invariant", "description": "存在一个保底不变量，使最坏情形仍能维持可行。"})
    else:
        constraints.append({"name": "canonical_order", "description": "所有合法构造需要按统一规范顺序输出。"})
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


def make_validation_plan(rule_id: str) -> VariantPlan:
    theme = Theme(
        theme_id="campus_ops",
        name="校园运营",
        tone="日常规则",
        keywords=["社团"],
        mapping_hint="校园资源调度。",
    )
    instantiated_schema = InstantiatedSchema(
        problem_id=f"PLAN_{rule_id}",
        source="codeforces",
        input_structure={
            "type": "array",
            "length": {"min": 3, "max": 3},
            "value_range": {"min": 1, "max": 9},
            "properties": {"ordered": True} if "interlocked" in rule_id or "shared_core" in rule_id else {},
        },
        core_constraints={"constraints": [{"name": "base_constraint", "description": "基础约束。"}]},
        objective={"type": "construct_witness", "description": "输出一个规范构造。"},
        invariant={"invariants": [{"name": "base_invariant", "description": "基础不变量。"}]},
        theme={"id": "campus_ops", "name": "校园运营"},
        difficulty="Hard",
    )
    objective = instantiated_schema.objective
    if rule_id == "existence_to_counting":
        objective = {"type": "count", "description": "统计所有合法方案数。"}
    elif rule_id == "minimum_guarantee_under_perturbation":
        objective = {"type": "minimize_value", "description": "求最小保底阈值。"}
    return VariantPlan(
        problem_id=instantiated_schema.problem_id,
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
            changed_axes=["C", "O", "V"],
            same_family_allowed=True,
            forbidden_reuse=["A"],
            rationale="测试",
            summary="测试",
            mode="same_family_fusion" if "interlocked" in rule_id or "shared_core" in rule_id else "single_seed_extension",
        ),
        instantiated_schema_snapshot=instantiated_schema,
        predicted_schema_distance=0.45,
        distance_breakdown={"I": 0.0, "C": 0.5, "O": 0.8, "V": 0.4, "total": 0.45},
        changed_axes_realized=["C", "O", "V"],
        applied_rule=rule_id,
        algorithmic_delta_claim={
            "seed_solver_core": "基础判定",
            "reusable_subroutines": "状态预处理",
            "new_solver_core": "承担更强的新义务",
            "new_proof_obligation": "证明新责任成立",
            "why_direct_reuse_fails": "原解缺少新责任的验证链路",
        },
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
            description="若存在合法解，输出一个构造；否则输出一个可局部检查的冲突证书。",
            input_format="输入三行。",
            output_format="输出构造或 obstruction 证书。",
            constraints=["时间限制：2 秒。", "空间限制：256 MB。"],
            samples=[{"input": "1\n2\n3", "output": "OK", "explanation": "样例。"}, {"input": "3\n2\n1", "output": "FAIL", "explanation": "样例。"}],
            notes="无解时必须给出证书。",
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
            output_format="输出合法方案数。",
            constraints=["时间限制：2 秒。", "空间限制：256 MB。"],
            samples=[{"input": "1\n2\n3", "output": "2", "explanation": "样例。"}, {"input": "3\n2\n1", "output": "1", "explanation": "样例。"}],
            notes="这是一个共享主核上的 simultaneous 约束问题。",
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
