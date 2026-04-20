from __future__ import annotations

import json
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "生成题面") not in sys.path:
    sys.path.insert(0, str(ROOT / "生成题面"))
if str(ROOT / "题目质量评价") not in sys.path:
    sys.path.insert(0, str(ROOT / "题目质量评价"))

from problem_quality import ProblemEvaluator

PROJECT_DIR = ROOT / "题目质量评价"
MAIN_SPEC = importlib.util.spec_from_file_location("problem_quality_main", PROJECT_DIR / "main.py")
if MAIN_SPEC is None or MAIN_SPEC.loader is None:
    raise RuntimeError("无法加载题目质量评价 main.py")
main = importlib.util.module_from_spec(MAIN_SPEC)
MAIN_SPEC.loader.exec_module(main)
from problem_quality.report_renderer import render_report_markdown


class FakeJudgeClient:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def chat_json(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("unexpected chat_json call")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if not isinstance(response, dict):
            raise AssertionError("fake response must be dict or exception")
        return response


class ProblemQualityTests(unittest.TestCase):
    def test_evaluator_passes_new_schema_and_review_context_to_judges(self) -> None:
        client = FakeJudgeClient(
            [self._quality_response(score=5), self._divergence_response(verdict="pass")]
        )
        evaluator = ProblemEvaluator(judge_client=client)

        report = self._evaluate(
            evaluator=evaluator,
            source_schema=self._source_schema(),
            artifact=self._artifact(),
            original_problem=self._original_problem(),
        )

        self.assertEqual(len(client.calls), 2)
        quality_prompt = json.loads(str(client.calls[0]["user_prompt"]))
        divergence_prompt = json.loads(str(client.calls[1]["user_prompt"]))

        self.assertIn("new_schema", quality_prompt)
        self.assertIn("review_context", quality_prompt)
        self.assertNotIn("instantiated_schema", quality_prompt)
        self.assertIn("new_schema", divergence_prompt)
        self.assertIn("review_context", divergence_prompt)
        self.assertNotIn("instantiated_schema", divergence_prompt)
        self.assertIn("new_schema", report["snapshots"])
        self.assertIn("review_context", report["snapshots"])

    def test_review_context_contains_only_allowed_structured_fields(self) -> None:
        client = FakeJudgeClient(
            [self._quality_response(score=5), self._divergence_response(verdict="pass")]
        )
        evaluator = ProblemEvaluator(judge_client=client)

        self._evaluate(
            evaluator=evaluator,
            source_schema=self._source_schema(),
            artifact=self._artifact(),
            original_problem=self._original_problem(),
        )

        quality_prompt = json.loads(str(client.calls[0]["user_prompt"]))
        review_context = quality_prompt["review_context"]
        self.assertIn("distance_breakdown", review_context)
        self.assertIn("changed_axes_realized", review_context)
        self.assertIn("algorithmic_delta_claim", review_context)
        self.assertIn("applied_helpers", review_context)
        self.assertNotIn("selection_trace", review_context)
        self.assertNotIn("validation_trace", review_context)
        self.assertNotIn("candidate_attempts", review_context)
        self.assertNotIn("rule_selection_reason", review_context)

    def test_evaluator_uses_artifact_distance_payload_and_maps_planning_status(self) -> None:
        evaluator = ProblemEvaluator(
            judge_client=FakeJudgeClient(
                [self._quality_response(score=5), self._divergence_response(verdict="pass")]
            )
        )
        source_schema = self._source_schema()
        original_problem = self._original_problem()
        artifact = self._artifact()
        artifact["generated_problem"].pop("status", None)
        artifact["planning_status"] = "ok"

        report = self._evaluate(
            evaluator=evaluator,
            source_schema=source_schema,
            artifact=artifact,
            original_problem=original_problem,
        )

        self.assertEqual(report["overall"]["status"], "pass")
        self.assertEqual(report["overall"]["generated_status"], "ok")
        self.assertEqual(report["overall"]["schema_distance"], artifact["predicted_schema_distance"])
        self.assertEqual(report["divergence"]["schema_distance_breakdown"], artifact["distance_breakdown"])
        self.assertEqual(report["divergence"]["changed_axes_realized"], artifact["changed_axes_realized"])
        self.assertEqual(report["revision_brief"]["round_index"], 1)
        self.assertEqual(report["revision_brief"]["overall_status"], "pass")
        self.assertEqual(report["revision_brief"]["generated_status"], "ok")
        self.assertEqual(report["revision_brief"]["strengths_to_keep"], ["题面基础结构完整"])

    def test_evaluator_can_separate_divergence_and_quality(self) -> None:
        evaluator = ProblemEvaluator(
            judge_client=FakeJudgeClient(
                [self._quality_response(score=3), self._divergence_response(verdict="pass")]
            )
        )

        report = self._evaluate(
            evaluator=evaluator,
            source_schema=self._source_schema(),
            artifact=self._artifact(),
            original_problem=self._original_problem(),
        )

        self.assertEqual(report["overall"]["status"], "revise_quality")
        self.assertGreaterEqual(report["overall"]["divergence_score"], 70.0)

    def test_evaluator_exposes_revision_brief_with_failed_checks_and_issues(self) -> None:
        evaluator = ProblemEvaluator(
            judge_client=FakeJudgeClient(
                [self._quality_response(score=5), self._divergence_response(verdict="pass")]
            )
        )
        artifact = self._artifact()
        artifact["generated_problem"]["samples"] = artifact["generated_problem"]["samples"][:1]

        report = self._evaluate(
            evaluator=evaluator,
            source_schema=self._source_schema(),
            artifact=artifact,
            original_problem=self._original_problem(),
        )

        self.assertEqual(report["overall"]["status"], "revise_quality")
        self.assertTrue(any(item["check_id"] == "sample_count" for item in report["revision_brief"]["failed_hard_checks"]))
        self.assertEqual(report["revision_brief"]["issues"], report["issues"])
        self.assertEqual(report["revision_brief"]["suggested_revisions"], report["suggested_revisions"])

    def test_render_report_markdown_includes_revision_brief_section(self) -> None:
        evaluator = ProblemEvaluator(
            judge_client=FakeJudgeClient(
                [self._quality_response(score=5), self._divergence_response(verdict="pass")]
            )
        )
        report = self._evaluate(
            evaluator=evaluator,
            source_schema=self._source_schema(),
            artifact=self._artifact(),
            original_problem=self._original_problem(),
        )

        markdown = render_report_markdown(report)

        self.assertIn("## 回流摘要", markdown)
        self.assertIn("- round_index: 1", markdown)
        self.assertIn("- overall_status: pass", markdown)

    def test_evaluator_maps_difference_insufficient_to_retheme(self) -> None:
        evaluator = ProblemEvaluator(
            judge_client=FakeJudgeClient(
                [self._quality_response(score=5), self._divergence_response(verdict="reject_as_retheme")]
            )
        )
        artifact = self._artifact()
        artifact["generated_problem"].pop("status", None)
        artifact["planning_status"] = "difference_insufficient"
        artifact["planning_error_reason"] = "规则规划失败。"

        report = self._evaluate(
            evaluator=evaluator,
            source_schema=self._source_schema(),
            artifact=artifact,
            original_problem=self._original_problem(),
        )

        self.assertEqual(report["overall"]["status"], "reject_as_retheme")
        self.assertEqual(report["overall"]["generated_status"], "difference_insufficient")

    def test_evaluator_accepts_artifact_with_new_schema_field(self) -> None:
        evaluator = ProblemEvaluator(
            judge_client=FakeJudgeClient(
                [self._quality_response(score=5), self._divergence_response(verdict="pass")]
            )
        )
        artifact = self._artifact()
        artifact["new_schema"] = artifact.pop("new_schema_snapshot")

        report = self._evaluate(
            evaluator=evaluator,
            source_schema=self._source_schema(),
            artifact=artifact,
            original_problem=self._original_problem(),
        )

        self.assertEqual(report["overall"]["status"], "pass")
        self.assertTrue(any(item["check_id"] == "new_schema_present" and item["passed"] for item in report["hard_checks"]))

    def test_evaluator_rejects_artifact_without_any_schema_field(self) -> None:
        evaluator = ProblemEvaluator(
            judge_client=FakeJudgeClient(
                [self._quality_response(score=5), self._divergence_response(verdict="pass")]
            )
        )
        artifact = self._artifact()
        artifact.pop("new_schema_snapshot")

        report = self._evaluate(
            evaluator=evaluator,
            source_schema=self._source_schema(),
            artifact=artifact,
            original_problem=self._original_problem(),
        )

        self.assertEqual(report["overall"]["status"], "reject_invalid")
        failed_checks = {item["check_id"] for item in report["hard_checks"] if not item["passed"]}
        self.assertIn("new_schema_present", failed_checks)

    def test_evaluator_rejects_artifact_without_predicted_schema_distance(self) -> None:
        report = self._evaluate_missing_distance_field("predicted_schema_distance")

        self.assertEqual(report["overall"]["status"], "reject_invalid")
        failed_checks = {item["check_id"] for item in report["hard_checks"] if not item["passed"]}
        self.assertIn("predicted_schema_distance_present", failed_checks)

    def test_evaluator_rejects_artifact_without_distance_breakdown(self) -> None:
        report = self._evaluate_missing_distance_field("distance_breakdown")

        self.assertEqual(report["overall"]["status"], "reject_invalid")
        failed_checks = {item["check_id"] for item in report["hard_checks"] if not item["passed"]}
        self.assertIn("distance_breakdown_present", failed_checks)

    def test_evaluator_rejects_artifact_without_changed_axes_realized(self) -> None:
        report = self._evaluate_missing_distance_field("changed_axes_realized")

        self.assertEqual(report["overall"]["status"], "reject_invalid")
        failed_checks = {item["check_id"] for item in report["hard_checks"] if not item["passed"]}
        self.assertIn("changed_axes_realized_present", failed_checks)

    def test_evaluator_requires_judge_client(self) -> None:
        with mock.patch("problem_quality.evaluator.DEFAULT_API_KEY", ""):
            with self.assertRaisesRegex(RuntimeError, "LLM Judge"):
                ProblemEvaluator()

    def test_evaluator_raises_when_quality_judge_fails(self) -> None:
        evaluator = ProblemEvaluator(judge_client=FakeJudgeClient([RuntimeError("quality failed")]))

        with self.assertRaisesRegex(RuntimeError, "quality failed"):
            self._evaluate(
                evaluator=evaluator,
                source_schema=self._source_schema(),
                artifact=self._artifact(),
                original_problem=self._original_problem(),
            )

    def test_evaluator_raises_when_divergence_judge_fails(self) -> None:
        evaluator = ProblemEvaluator(
            judge_client=FakeJudgeClient([self._quality_response(score=5), RuntimeError("divergence failed")])
        )

        with self.assertRaisesRegex(RuntimeError, "divergence failed"):
            self._evaluate(
                evaluator=evaluator,
                source_schema=self._source_schema(),
                artifact=self._artifact(),
                original_problem=self._original_problem(),
            )

    def test_evaluator_raises_on_invalid_quality_payload(self) -> None:
        evaluator = ProblemEvaluator(judge_client=FakeJudgeClient([{"scores": {}}]))

        with self.assertRaisesRegex(ValueError, "quality score variant_fidelity"):
            self._evaluate(
                evaluator=evaluator,
                source_schema=self._source_schema(),
                artifact=self._artifact(),
                original_problem=self._original_problem(),
            )

    def test_evaluator_raises_on_invalid_divergence_payload(self) -> None:
        evaluator = ProblemEvaluator(
            judge_client=FakeJudgeClient([self._quality_response(score=5), {"verdict": "pass"}])
        )

        with self.assertRaisesRegex(ValueError, "semantic_difference"):
            self._evaluate(
                evaluator=evaluator,
                source_schema=self._source_schema(),
                artifact=self._artifact(),
                original_problem=self._original_problem(),
            )

    def test_parser_rejects_disable_llm(self) -> None:
        parser = main.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["--schema", "a.json", "--artifact", "b.json", "--disable-llm"])

    def test_parser_allows_missing_original_problem(self) -> None:
        parser = main.build_parser()
        args = parser.parse_args(["--schema", "a.json", "--artifact", "b.json"])

        self.assertIsNone(args.original_problem)

    def test_parser_accepts_original_problem(self) -> None:
        parser = main.build_parser()
        args = parser.parse_args(
            ["--schema", "a.json", "--artifact", "b.json", "--original-problem", "c.json"]
        )

        self.assertEqual(args.original_problem, "c.json")

    def test_evaluator_loads_original_problem_from_json_path(self) -> None:
        evaluator = ProblemEvaluator(
            judge_client=FakeJudgeClient(
                [self._quality_response(score=5), self._divergence_response(verdict="pass")]
            )
        )
        with tempfile.TemporaryDirectory() as tempdir:
            temp = Path(tempdir)
            schema_path = temp / "schema.json"
            artifact_path = temp / "artifact.json"
            original_problem_path = temp / "original_problem.json"
            schema_path.write_text(
                json.dumps(self._source_schema(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            artifact_path.write_text(
                json.dumps(self._artifact(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            original_problem_path.write_text(
                json.dumps(self._original_problem(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            report = evaluator.evaluate_problem(
                schema_path=schema_path,
                artifact_path=artifact_path,
                original_problem_override=original_problem_path,
            )

        self.assertEqual(report["overall"]["status"], "pass")
        self.assertEqual(report["snapshots"]["original_problem"]["title"], "E. Seed Bridge")

    def test_evaluator_auto_loads_original_problem_from_index(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            output_dir = Path(tempdir) / "output"
            self._write_platform_index(
                output_dir=output_dir,
                platform="codeforces",
                records=[self._catalog_problem(problem_id="CFX", title="Auto From Index")],
            )
            evaluator = ProblemEvaluator(
                judge_client=FakeJudgeClient(
                    [self._quality_response(score=5), self._divergence_response(verdict="pass")]
                ),
                original_problem_output_dir=output_dir,
            )

            report = self._evaluate(
                evaluator=evaluator,
                source_schema=self._source_schema(),
                artifact=self._artifact(),
            )

        self.assertEqual(report["overall"]["status"], "pass")
        self.assertEqual(report["snapshots"]["original_problem"]["title"], "Auto From Index")

    def test_evaluator_auto_loads_original_problem_from_imandra_jsons(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            output_dir = Path(tempdir) / "output"
            self._write_platform_index(output_dir=output_dir, platform="codeforces", records=[])
            imandra_dir = output_dir / "imandra_curated_schema_inputs"
            imandra_dir.mkdir(parents=True, exist_ok=True)
            (imandra_dir / "manifest.json").write_text(
                json.dumps({"meta": "ignore"}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (imandra_dir / "sample.json").write_text(
                json.dumps(self._catalog_problem(problem_id="CFX", title="Auto From Imandra"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            evaluator = ProblemEvaluator(
                judge_client=FakeJudgeClient(
                    [self._quality_response(score=5), self._divergence_response(verdict="pass")]
                ),
                original_problem_output_dir=output_dir,
            )

            report = self._evaluate(
                evaluator=evaluator,
                source_schema=self._source_schema(),
                artifact=self._artifact(),
            )

        self.assertEqual(report["overall"]["status"], "pass")
        self.assertEqual(report["snapshots"]["original_problem"]["title"], "Auto From Imandra")

    def test_evaluator_marks_invalid_when_original_problem_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            output_dir = Path(tempdir) / "output"
            self._write_platform_index(output_dir=output_dir, platform="codeforces", records=[])
            evaluator = ProblemEvaluator(
                judge_client=FakeJudgeClient(
                    [self._quality_response(score=5), self._divergence_response(verdict="pass")]
                ),
                original_problem_output_dir=output_dir,
            )

            report = self._evaluate(
                evaluator=evaluator,
                source_schema=self._source_schema(),
                artifact=self._artifact(),
            )

        self.assertEqual(report["overall"]["status"], "reject_invalid")
        source_resolved_checks = [
            item for item in report["hard_checks"] if item["check_id"] == "source_problem_resolved"
        ]
        self.assertEqual(len(source_resolved_checks), 1)
        self.assertFalse(source_resolved_checks[0]["passed"])

    def test_evaluator_prefers_override_over_auto_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            output_dir = Path(tempdir) / "output"
            self._write_platform_index(
                output_dir=output_dir,
                platform="codeforces",
                records=[self._catalog_problem(problem_id="CFX", title="Auto From Index")],
            )
            evaluator = ProblemEvaluator(
                judge_client=FakeJudgeClient(
                    [self._quality_response(score=5), self._divergence_response(verdict="pass")]
                ),
                original_problem_output_dir=output_dir,
            )

            report = self._evaluate(
                evaluator=evaluator,
                source_schema=self._source_schema(),
                artifact=self._artifact(),
                original_problem=self._catalog_problem(problem_id="CFX", title="Manual Override"),
            )

        self.assertEqual(report["overall"]["status"], "pass")
        self.assertEqual(report["snapshots"]["original_problem"]["title"], "Manual Override")

    def test_evaluator_uses_source_problem_ids_before_schema_problem_id(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            output_dir = Path(tempdir) / "output"
            self._write_platform_index(
                output_dir=output_dir,
                platform="codeforces",
                records=[
                    self._catalog_problem(problem_id="CFX", title="From Source Problem IDs"),
                    self._catalog_problem(problem_id="OTHER", title="From Schema Problem ID"),
                ],
            )
            evaluator = ProblemEvaluator(
                judge_client=FakeJudgeClient(
                    [self._quality_response(score=5), self._divergence_response(verdict="pass")]
                ),
                original_problem_output_dir=output_dir,
            )
            schema = self._source_schema()
            schema["problem_id"] = "OTHER"

            report = self._evaluate(
                evaluator=evaluator,
                source_schema=schema,
                artifact=self._artifact(),
            )

        self.assertEqual(report["snapshots"]["original_problem"]["title"], "From Source Problem IDs")

    def _evaluate_missing_distance_field(self, field_name: str) -> dict[str, object]:
        evaluator = ProblemEvaluator(
            judge_client=FakeJudgeClient(
                [self._quality_response(score=5), self._divergence_response(verdict="pass")]
            )
        )
        artifact = self._artifact()
        artifact.pop(field_name)
        return self._evaluate(
            evaluator=evaluator,
            source_schema=self._source_schema(),
            artifact=artifact,
            original_problem=self._original_problem(),
        )

    def _evaluate(
        self,
        evaluator: ProblemEvaluator,
        source_schema: dict[str, object],
        artifact: dict[str, object],
        original_problem: dict[str, object] | None = None,
    ) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as tempdir:
            temp = Path(tempdir)
            schema_path = temp / "schema.json"
            artifact_path = temp / "artifact.json"
            schema_path.write_text(json.dumps(source_schema, ensure_ascii=False, indent=2), encoding="utf-8")
            artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
            return evaluator.evaluate_problem(
                schema_path=schema_path,
                artifact_path=artifact_path,
                original_problem_override=original_problem,
            )

    def _write_platform_index(
        self,
        output_dir: Path,
        platform: str,
        records: list[dict[str, object]],
    ) -> None:
        platform_dir = output_dir / platform
        platform_dir.mkdir(parents=True, exist_ok=True)
        (platform_dir / "index.json").write_text(
            json.dumps(records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _catalog_problem(self, problem_id: str, title: str) -> dict[str, object]:
        return {
            "problem_id": problem_id,
            "title": title,
            "description": "catalog description",
            "input": "catalog input",
            "output": "catalog output",
            "constraints": "catalog constraints",
            "source": "catalog",
        }

    def _source_schema(self) -> dict[str, object]:
        return {
            "problem_id": "CFX",
            "source": "codeforces",
            "input_structure": {
                "type": "array",
                "length": {"min": 3, "max": 3},
                "value_range": {"min": 1, "max": 100000},
                "properties": {"ordered": False},
            },
            "core_constraints": {
                "constraints": [
                    {"name": "subsequence_constraint", "description": "目标串必须覆盖三个片段"}
                ]
            },
            "objective": {
                "type": "minimize_value",
                "description": "求覆盖全部片段的最短长度",
            },
            "invariant": {
                "invariants": [
                    {"name": "optimal_substructure", "description": "最优子结构"}
                ]
            },
        }

    def _original_problem(self) -> dict[str, object]:
        return {
            "problem_id": "CFX",
            "title": "E. Seed Bridge",
            "description": "给定三个片段，求最短覆盖对象。",
            "input": "输入三行，每行一个片段。",
            "output": "输出一个整数。",
            "constraints": "time limit per test 2 seconds\nmemory limit per test 256 megabytes",
            "source": "codeforces",
        }

    def _artifact(self) -> dict[str, object]:
        return {
            "problem_id": "CampusOps_MST_Count",
            "source_problem_ids": ["CFX"],
            "variant_index": 1,
            "seed": 1,
            "mode": "single_seed_extension",
            "rule_version": "2026-04-rules-v3",
            "theme": {"id": "campus_ops", "name": "校园运营"},
            "difference_plan": {
                "target_distance_band": {"min": 0.35, "max": 0.60},
                "changed_axes": ["C", "O", "V"],
                "same_family_allowed": True,
                "forbidden_reuse": ["CFX", "E. Seed Bridge"],
                "rationale": "目标改为模计数，约束与不变量同步重构。",
                "summary": "以计数化改造最小生成树任务",
                "mode": "single_seed_extension",
            },
            "planning_status": "ok",
            "planning_error_reason": "",
            "planning_feedback": "",
            "predicted_schema_distance": 0.4247,
            "distance_breakdown": {
                "distance_version": "v2",
                "backend": "embedding",
                "total": 0.4247,
                "axis_scores": {
                    "I": 0.0833,
                    "C": 0.631,
                    "O": 0.5226,
                    "V": 0.4198,
                },
                "components": {
                    "input_tree_distance": 0.0833,
                    "constraint_match_distance": 0.631,
                    "objective_type_distance": 0.6638,
                    "objective_text_distance": 0.3107,
                    "invariant_match_distance": 0.4198,
                },
            },
            "changed_axes_realized": ["C", "O", "V"],
            "new_schema_snapshot": {
                "problem_id": "CampusOps_MST_Count",
                "source": "CFX_extended",
                "input_structure": {
                    "type": "composite",
                    "length": {"min": None, "max": None},
                    "value_range": {"min": None, "max": None},
                    "properties": {"multiple_test_cases": True, "counting_enabled": True},
                    "components": [
                        {
                            "role": "parameters",
                            "role_description": "n, p, M",
                            "type": "tuple",
                            "length": {"min": 3, "max": 3},
                            "value_range": {"min": 1, "max": 1000000007},
                            "properties": {},
                        },
                        {
                            "role": "room_levels",
                            "role_description": "活动室活跃度序列",
                            "type": "array",
                            "length": {"min": 2, "max": 200000},
                            "value_range": {"min": 1, "max": 1000000000},
                            "properties": {"ordered": True},
                        },
                    ],
                },
                "core_constraints": {
                    "constraints": [
                        {
                            "name": "connectivity_rule",
                            "description": "图的连边由整除区间规则与固定走廊共同决定。",
                        },
                        {
                            "name": "counting_unit_def",
                            "description": "不同方案由边集差异唯一确定。",
                        },
                        {
                            "name": "cut_independence",
                            "description": "全局答案可以按相邻割拆分后相乘。",
                        },
                    ]
                },
                "objective": {
                    "type": "count_modulo",
                    "description": "计算所有不同最小生成树边集的数量，结果对 M 取模。",
                    "target": "mst_count_mod_M",
                    "requires_solution": True,
                },
                "invariant": {
                    "invariants": [
                        {
                            "name": "multiplicative_decomposition",
                            "description": "全局最小生成树数量等于各相邻割最小权边数量的乘积。",
                        },
                        {
                            "name": "monotonic_counting_sweep",
                            "description": "可以在线性扫描中维护每个割的候选边计数。",
                        },
                    ]
                },
                "theme": {"id": "campus_ops", "name": "校园运营"},
                "difficulty": "Hard",
            },
            "applied_rule": "existence_to_counting",
            "rule_selection_reason": "上游排序后选择计数化规则。",
            "algorithmic_delta_claim": {
                "seed_solver_core": "按结构求单个最优值。",
                "new_solver_core": "统计满足最优条件的全部边集数量。",
            },
            "anti_shallow_rationale": "不能只保留原题求值逻辑再附加后处理计数。",
            "applied_helpers": [
                {
                    "id": "counting_unit_definition",
                    "selection_reason": "先定义去重口径。",
                }
            ],
            "selection_trace": [{"rule_id": "existence_to_counting"}],
            "validation_trace": [{"stage": "problem_validation"}],
            "candidate_attempts": [{"rule_id": "existence_to_counting", "status": "ok"}],
            "generated_problem": {
                "status": "ok",
                "title": "社团活动室的走廊规划",
                "description": "大学后勤部需要连通所有活动室。若多种总成本最小的走廊边集同时成立，需要统计它们的数量。",
                "input_format": "第一行输入 t。每个测试用例第一行输入 n, p, M，第二行输入 n 个正整数。",
                "output_format": "每个测试用例输出一个整数，表示最小生成树边集数量对 M 取模后的结果。",
                "constraints": [
                    "1 <= t <= 10000",
                    "2 <= n <= 200000",
                    "1 <= p, M <= 1000000007",
                    "所有测试用例的 n 之和不超过 200000",
                ],
                "samples": [
                    {
                        "input": "1\n3 5 1000000007\n2 4 6",
                        "output": "2",
                        "explanation": "两条不同的最小权边集都可成立。",
                    },
                    {
                        "input": "1\n4 100 1000\n1 2 4 8",
                        "output": "6",
                        "explanation": "各相邻割的可选最小权边数量乘积为 6。",
                    },
                ],
                "notes": "不同方案由边集是否相同决定。全局答案按相邻割的最小权边数量乘积计算。",
                "error_reason": "",
                "feedback": "",
            },
        }

    def _quality_response(self, score: int) -> dict[str, object]:
        return {
            "scores": {
                "variant_fidelity": self._quality_score_payload(score),
                "spec_completeness": self._quality_score_payload(score),
                "cross_section_consistency": self._quality_score_payload(score),
                "sample_quality": self._quality_score_payload(score),
                "oj_readability": self._quality_score_payload(score),
            },
            "issues": [],
            "strengths": ["题面基础结构完整"],
            "suggested_revisions": [],
        }

    def _quality_score_payload(self, score: int) -> dict[str, object]:
        return {
            "score": score,
            "rationale": "结构与字段落地一致。",
            "evidence_refs": ["snapshots.generated_problem"],
        }

    def _divergence_response(self, verdict: str) -> dict[str, object]:
        return {
            "semantic_difference": 0.85 if verdict == "pass" else 0.25,
            "solution_transfer_risk": 0.20 if verdict == "pass" else 0.90,
            "surface_retheme_risk": 0.15 if verdict == "pass" else 0.88,
            "verdict": verdict,
            "rationale": "差异轴已经真实落地，原题解法不能直接迁移。"
            if verdict == "pass"
            else "核心任务仍然高度可迁移。",
            "evidence_refs": [
                "snapshots.original_problem",
                "snapshots.generated_problem",
                "snapshots.new_schema",
            ],
        }


if __name__ == "__main__":
    unittest.main()
