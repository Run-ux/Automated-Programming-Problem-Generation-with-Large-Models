from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "生成题面") not in sys.path:
    sys.path.insert(0, str(ROOT / "生成题面"))
if str(ROOT / "题目质量评价") not in sys.path:
    sys.path.insert(0, str(ROOT / "题目质量评价"))

from finiteness_verification.problem_repository import ProblemRepository
from problem_quality import ProblemEvaluator
from variant_planner import VariantPlanner


class ProblemQualityTests(unittest.TestCase):
    def test_variant_planner_builds_difference_plan_for_cf25e(self) -> None:
        prepared_path = ROOT / "生成题面" / "prepared_schemas" / "CF25E.json"
        prepared = json.loads(prepared_path.read_text(encoding="utf-8"))
        original_problem = ProblemRepository().get_problem(
            source=prepared["source"],
            problem_id=prepared["problem_id"],
        )

        plan = VariantPlanner(seed=20260312).build_plan(
            schema=prepared,
            variant_index=1,
            theme_id="campus_ops",
            original_schema=prepared,
            original_problem=original_problem,
        )

        self.assertGreaterEqual(plan.predicted_schema_distance, 0.35)
        self.assertGreaterEqual(len(plan.changed_axes_realized), 2)
        self.assertIn("O", plan.changed_axes_realized)
        self.assertTrue(plan.difference_plan.forbidden_reuse)

    def test_evaluator_rejects_legacy_cf25e_artifact_as_retheme(self) -> None:
        evaluator = ProblemEvaluator(enable_llm=False)
        report = evaluator.evaluate_problem(
            original_schema_path=ROOT / "生成题面" / "prepared_schemas" / "CF25E.json",
            prepared_schema_path=ROOT / "生成题面" / "prepared_schemas" / "CF25E.json",
            artifact_path=ROOT / "生成题面" / "artifacts" / "CF25E_v1_campus_ops_20260315_233917.json",
        )

        self.assertEqual(report["overall"]["status"], "reject_as_retheme")
        failed_checks = {item["check_id"] for item in report["hard_checks"] if not item["passed"]}
        self.assertIn("input_count_alignment", failed_checks)
        self.assertIn("schema_distance_threshold", failed_checks)

    def test_evaluator_can_separate_divergence_and_quality(self) -> None:
        evaluator = ProblemEvaluator(enable_llm=False)
        original_schema = {
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
                    {"name": "subsequence_constraint", "description": "目标字符串必须包含给定的三个子串"}
                ]
            },
            "objective": {
                "type": "minimize_value",
                "description": "求包含给定三个子串的最短字符串长度",
            },
            "invariant": {
                "invariants": [
                    {"name": "optimal_substructure", "description": "最优子结构"}
                ]
            },
            "transform_space": {
                "numerical_parameters": {
                    "K_Substrings": {"min": 2, "max": 6, "description": "Number of substrings to combine (currently 3)"}
                },
                "objective_options": ["count_minimal_strings"],
                "structural_options": ["must_contain_in_order", "cyclic_string"],
            },
        }
        prepared_schema = original_schema
        original_problem = {
            "problem_id": "CFX",
            "title": "E. Test",
            "description": "给定三个字符串，求最短字符串使其包含全部子串。",
            "input": "输入三行，每行一个字符串。",
            "output": "输出一个整数。",
            "constraints": "time limit per test 2 seconds\nmemory limit per test 256 megabytes",
            "source": "codeforces",
        }
        artifact = {
            "problem_id": "CFX",
            "variant_index": 1,
            "seed": 1,
            "theme": {"id": "campus_ops", "name": "校园运营"},
            "difference_plan": {
                "target_distance_band": {"min": 0.35, "max": 0.60},
                "changed_axes": ["I", "C", "O", "T"],
                "same_family_allowed": True,
                "forbidden_reuse": ["CFX", "E. Test"],
                "rationale": "目标、约束和输入组织均已变化。",
            },
            "predicted_schema_distance": 0.46,
            "changed_axes_realized": ["I", "C", "O", "T"],
            "objective": {
                "type": "count_minimal_strings",
                "description": "统计满足条件的最优结果方案数。",
            },
            "numerical_parameters": {
                "K_Substrings": {"value": 2, "min": 2, "max": 6, "description": "Number of substrings to combine (currently 3)"}
            },
            "structural_options": ["must_contain_in_order", "cyclic_string"],
            "instantiated_schema_snapshot": {
                "problem_id": "CFX",
                "source": "codeforces",
                "input_structure": {
                    "type": "array",
                    "length": {"min": 2, "max": 2},
                    "value_range": {"min": 1, "max": 100000},
                    "properties": {"ordered": True, "cyclic": True, "fixed_item_count": 2},
                },
                "core_constraints": {
                    "constraints": [
                        {"name": "must_contain_in_order", "description": "目标对象需要按给定顺序覆盖所有输入项。"},
                        {"name": "cyclic_string", "description": "结果对象按循环意义处理，允许首尾相接形成匹配。"},
                    ]
                },
                "objective": {
                    "type": "count_minimal_strings",
                    "description": "统计满足条件的最优结果方案数。",
                },
                "invariant": {
                    "invariants": [{"name": "optimal_substructure", "description": "最优子结构"}]
                },
                "instantiated_parameters": {
                    "K_Substrings": {"value": 2, "min": 2, "max": 6, "description": "Number of substrings to combine (currently 3)"}
                },
                "selected_structural_options": ["must_contain_in_order", "cyclic_string"],
                "theme": {"id": "campus_ops", "name": "校园运营"},
                "difficulty": "Medium",
            },
            "generated_problem": {
                "status": "ok",
                "error_reason": "",
                "feedback": "",
                "title": "轮值备份环",
                "description": "学院需要把两个关键备份串按固定顺序嵌入一个环形校验码中。不同的最优环形校验码可能不止一种，请统计方案数。",
                "input_format": "输入共两行，每行一个仅由小写字母组成的字符串。",
                "output_format": "输出一个整数，表示最优环形校验码的方案数。若方案数较大，对 998244353 取模。",
                "constraints": [
                    "每个字符串长度不超过 100000。",
                    "目标环形校验码需要按输入顺序覆盖两个字符串。",
                    "时间限制：2 秒。",
                    "空间限制：256 MB。",
                ],
                "samples": [
                    {
                        "input": "ab\nbc",
                        "output": "1",
                        "explanation": "只有一种最短环形校验码。"
                    },
                    {
                        "input": "aa\naa",
                        "output": "1",
                        "explanation": "两个输入相同，最优方案唯一。"
                    },
                ],
                "notes": "结果按循环意义比较；若多个最优结果存在，需要统计其数量。",
            },
        }

        low_quality_artifact = json.loads(json.dumps(artifact))
        low_quality_artifact["generated_problem"]["samples"] = [
            {
                "input": "ab\nbc",
                "output": "1",
                "explanation": ""
            }
        ]
        low_quality_artifact["generated_problem"]["notes"] = ""

        with tempfile.TemporaryDirectory() as tempdir:
            temp = Path(tempdir)
            original_schema_path = temp / "original.json"
            prepared_schema_path = temp / "prepared.json"
            artifact_path = temp / "artifact.json"
            low_quality_artifact_path = temp / "artifact_low_quality.json"
            original_schema_path.write_text(json.dumps(original_schema, ensure_ascii=False, indent=2), encoding="utf-8")
            prepared_schema_path.write_text(json.dumps(prepared_schema, ensure_ascii=False, indent=2), encoding="utf-8")
            artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
            low_quality_artifact_path.write_text(json.dumps(low_quality_artifact, ensure_ascii=False, indent=2), encoding="utf-8")

            pass_report = evaluator.evaluate_problem(
                original_schema_path=original_schema_path,
                prepared_schema_path=prepared_schema_path,
                artifact_path=artifact_path,
                original_problem_override=original_problem,
            )
            revise_report = evaluator.evaluate_problem(
                original_schema_path=original_schema_path,
                prepared_schema_path=prepared_schema_path,
                artifact_path=low_quality_artifact_path,
                original_problem_override=original_problem,
            )

        self.assertEqual(pass_report["overall"]["status"], "pass")
        self.assertGreaterEqual(pass_report["overall"]["divergence_score"], 70.0)
        self.assertEqual(revise_report["overall"]["status"], "revise_quality")
        self.assertGreaterEqual(revise_report["overall"]["divergence_score"], 70.0)


if __name__ == "__main__":
    unittest.main()
