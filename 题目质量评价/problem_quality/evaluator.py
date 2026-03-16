from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GENERATION_DIR = PROJECT_ROOT / "生成题面"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(GENERATION_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATION_DIR))

from finiteness_verification.problem_repository import ProblemRepository
from config import DEFAULT_API_KEY, DEFAULT_BASE_URL, DEFAULT_MODEL
from qwen_client import QwenClient
from schema_tools import (
    build_instantiated_schema,
    compute_changed_axes,
    compute_schema_distance,
    dataclass_to_dict,
)

from .judges import ProblemQualityJudge, SourceDivergenceJudge
from .models import DivergenceResult, EvaluationReport, HardCheckResult, Issue


class ProblemEvaluator:
    def __init__(self, client: Any | None = None, enable_llm: bool = True):
        self.client = client or self._build_client(enable_llm)
        self.problem_repository = ProblemRepository()
        self.quality_judge = ProblemQualityJudge(client=self.client)
        self.divergence_judge = SourceDivergenceJudge(client=self.client)

    def evaluate_problem(
        self,
        original_schema_path: str | Path,
        prepared_schema_path: str | Path,
        artifact_path: str | Path,
        markdown_path: str | Path | None = None,
        original_problem_override: dict[str, Any] | str | Path | None = None,
    ) -> dict[str, Any]:
        original_schema = self._load_json(original_schema_path)
        prepared_schema = self._load_json(prepared_schema_path)
        artifact = self._load_json(artifact_path)
        generated_problem = artifact.get("generated_problem", {})

        original_problem = self._resolve_original_problem(
            prepared_schema=prepared_schema,
            original_problem_override=original_problem_override,
        )
        instantiated_schema, difference_plan, legacy_warnings = self._normalize_artifact(
            prepared_schema=prepared_schema,
            original_schema=original_schema,
            artifact=artifact,
        )

        schema_distance_breakdown = compute_schema_distance(original_schema, instantiated_schema)
        changed_axes_realized = compute_changed_axes(original_schema, instantiated_schema)
        if not difference_plan.get("changed_axes"):
            difference_plan["changed_axes"] = changed_axes_realized

        hard_checks = self._run_hard_checks(
            original_problem=original_problem,
            original_schema=original_schema,
            instantiated_schema=instantiated_schema,
            difference_plan=difference_plan,
            generated_problem=generated_problem,
            schema_distance_breakdown=schema_distance_breakdown,
            changed_axes_realized=changed_axes_realized,
            legacy_warnings=legacy_warnings,
        )
        hard_check_dicts = [asdict(item) for item in hard_checks]

        quality_result = self.quality_judge.evaluate(
            instantiated_schema=instantiated_schema,
            generated_problem=generated_problem,
            hard_checks=hard_check_dicts,
        )
        divergence_result = self._evaluate_divergence(
            original_problem=original_problem,
            original_schema=original_schema,
            instantiated_schema=instantiated_schema,
            generated_problem=generated_problem,
            hard_checks=hard_check_dicts,
            difference_plan=difference_plan,
            schema_distance=schema_distance_breakdown["total"],
            changed_axes_realized=changed_axes_realized,
        )

        quality_score = self._calculate_quality_score(quality_result)
        divergence_score = self._calculate_divergence_score(
            schema_distance=schema_distance_breakdown["total"],
            semantic_difference=divergence_result["semantic_difference"],
            solution_transfer_risk=divergence_result["solution_transfer_risk"],
        )

        issues = self._collect_issues(
            hard_checks=hard_checks,
            quality_result=quality_result,
            divergence_result=divergence_result,
        )
        status = self._determine_status(
            original_problem=original_problem,
            generated_problem=generated_problem,
            hard_checks=hard_checks,
            quality_score=quality_score,
            divergence_score=divergence_score,
            divergence_result=divergence_result,
        )
        suggested_revisions = self._collect_suggestions(issues, quality_result, divergence_result)

        report = EvaluationReport(
            overall={
                "status": status,
                "quality_score": quality_score,
                "divergence_score": divergence_score,
                "schema_distance": schema_distance_breakdown["total"],
                "generated_status": generated_problem.get("status", "ok"),
            },
            quality={
                "dimension_scores": quality_result.get("dimension_scores", []),
                "strengths": quality_result.get("strengths", []),
            },
            divergence={
                "schema_distance_breakdown": schema_distance_breakdown,
                **divergence_result,
            },
            hard_checks=hard_check_dicts,
            issues=[asdict(item) if hasattr(item, "__dataclass_fields__") else item for item in issues],
            suggested_revisions=suggested_revisions,
            snapshots={
                "paths": {
                    "original_schema_path": str(Path(original_schema_path)),
                    "prepared_schema_path": str(Path(prepared_schema_path)),
                    "artifact_path": str(Path(artifact_path)),
                    "markdown_path": str(Path(markdown_path)) if markdown_path else "",
                },
                "original_problem": original_problem or {},
                "difference_plan": difference_plan,
                "instantiated_schema": instantiated_schema,
                "generated_problem": generated_problem,
                "legacy_warnings": legacy_warnings,
            },
        )
        return asdict(report)

    def _build_client(self, enable_llm: bool) -> Any | None:
        if not enable_llm or not DEFAULT_API_KEY:
            return None
        return QwenClient(
            api_key=DEFAULT_API_KEY,
            model=DEFAULT_MODEL,
            base_url=DEFAULT_BASE_URL,
        )

    def _load_json(self, path: str | Path) -> dict[str, Any]:
        target = Path(path)
        with target.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _resolve_original_problem(
        self,
        prepared_schema: dict[str, Any],
        original_problem_override: dict[str, Any] | str | Path | None,
    ) -> dict[str, Any] | None:
        if isinstance(original_problem_override, dict):
            return original_problem_override
        if isinstance(original_problem_override, (str, Path)):
            return self._load_json(original_problem_override)

        try:
            return self.problem_repository.get_problem(
                source=prepared_schema.get("source", ""),
                problem_id=prepared_schema.get("problem_id", ""),
            )
        except Exception:
            return None

    def _normalize_artifact(
        self,
        prepared_schema: dict[str, Any],
        original_schema: dict[str, Any],
        artifact: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
        warnings: list[str] = []
        instantiated_schema = artifact.get("instantiated_schema_snapshot")
        if not instantiated_schema:
            warnings.append("artifact 缺少 instantiated_schema_snapshot，已按 legacy 规则回填。")
            instantiated_schema = dataclass_to_dict(
                build_instantiated_schema(
                    schema=prepared_schema,
                    objective=artifact.get("objective", prepared_schema.get("objective", {})),
                    numerical_parameters=artifact.get("numerical_parameters", {}),
                    structural_options=artifact.get("structural_options", []),
                    theme=artifact.get("theme", {}),
                    difficulty=artifact.get("difficulty", ""),
                )
            )

        difference_plan = artifact.get("difference_plan")
        if not difference_plan:
            warnings.append("artifact 缺少 difference_plan，已按 legacy 规则推断。")
            difference_plan = {
                "target_distance_band": {"min": 0.35, "max": 0.60},
                "changed_axes": compute_changed_axes(original_schema, instantiated_schema),
                "same_family_allowed": True,
                "forbidden_reuse": [],
                "rationale": "Legacy artifact without persisted difference_plan.",
            }
        return instantiated_schema, difference_plan, warnings

    def _run_hard_checks(
        self,
        original_problem: dict[str, Any] | None,
        original_schema: dict[str, Any],
        instantiated_schema: dict[str, Any],
        difference_plan: dict[str, Any],
        generated_problem: dict[str, Any],
        schema_distance_breakdown: dict[str, float],
        changed_axes_realized: list[str],
        legacy_warnings: list[str],
    ) -> list[HardCheckResult]:
        checks: list[HardCheckResult] = []
        generated_status = generated_problem.get("status", "ok")
        checks.append(
            HardCheckResult(
                check_id="source_problem_resolved",
                passed=original_problem is not None,
                severity="blocker",
                category="invalid",
                message="已成功加载原题文本。" if original_problem else "无法加载原题文本，不能进行反换皮判定。",
                evidence_refs=["snapshots.original_problem"],
            )
        )
        checks.append(
            HardCheckResult(
                check_id="generated_status_ok",
                passed=generated_status == "ok",
                severity="blocker",
                category="retheme_issue" if generated_status == "difference_insufficient" else "invalid",
                message="生成状态正常。"
                if generated_status == "ok"
                else f"生成产物状态为 {generated_status}：{generated_problem.get('error_reason', '')}",
                evidence_refs=["snapshots.generated_problem.status"],
            )
        )
        checks.append(
            HardCheckResult(
                check_id="difference_plan_present",
                passed=not legacy_warnings or "difference_plan" not in " ".join(legacy_warnings),
                severity="major",
                category="retheme_issue",
                message="artifact 已持久化 difference_plan。"
                if not legacy_warnings or "difference_plan" not in " ".join(legacy_warnings)
                else "artifact 缺少 difference_plan，只能按 legacy 规则推断。",
                evidence_refs=["snapshots.difference_plan"],
            )
        )

        schema_distance = schema_distance_breakdown["total"]
        distance_passed = schema_distance >= 0.35
        checks.append(
            HardCheckResult(
                check_id="schema_distance_threshold",
                passed=distance_passed,
                severity="blocker",
                category="retheme_issue",
                message=(
                    f"schema_distance={schema_distance:.2f}，达到中等差异阈值。"
                    if distance_passed
                    else (
                        f"schema_distance={schema_distance:.2f}，低于 0.35。"
                        + (" 已接近同母题换皮（<0.25）。" if schema_distance < 0.25 else "")
                    )
                ),
                evidence_refs=["divergence.schema_distance_breakdown"],
            )
        )
        checks.append(
            HardCheckResult(
                check_id="changed_axes_threshold",
                passed=len(changed_axes_realized) >= 2,
                severity="blocker",
                category="retheme_issue",
                message=(
                    f"已落地核心差异轴：{', '.join(changed_axes_realized)}。"
                    if len(changed_axes_realized) >= 2
                    else f"仅落地了 {len(changed_axes_realized)} 个核心差异轴：{', '.join(changed_axes_realized) or '无'}。"
                ),
                evidence_refs=["snapshots.difference_plan", "snapshots.instantiated_schema"],
            )
        )

        checks.append(self._check_source_leakage(original_problem, generated_problem))
        checks.append(self._check_title_overlap(original_problem, generated_problem))
        checks.append(self._check_sample_count(generated_problem))
        checks.append(self._check_sample_line_alignment(instantiated_schema, generated_problem))
        checks.append(self._check_input_count_alignment(instantiated_schema, generated_problem))
        checks.append(self._check_objective_alignment(instantiated_schema, generated_problem))
        checks.append(self._check_structural_option_alignment(instantiated_schema, generated_problem))
        return checks

    def _check_source_leakage(
        self,
        original_problem: dict[str, Any] | None,
        generated_problem: dict[str, Any],
    ) -> HardCheckResult:
        if not original_problem:
            return HardCheckResult(
                check_id="source_leakage",
                passed=True,
                severity="blocker",
                category="retheme_issue",
                message="无原题文本，跳过泄露检查。",
                evidence_refs=[],
            )

        combined = "\n".join(
            [
                str(generated_problem.get("title", "")),
                str(generated_problem.get("description", "")),
                str(generated_problem.get("input_format", "")),
                str(generated_problem.get("output_format", "")),
                str(generated_problem.get("notes", "")),
            ]
        ).lower()
        forbidden = [
            str(original_problem.get("problem_id", "")).lower(),
            str(original_problem.get("source", "")).lower(),
            str(original_problem.get("title", "")).lower(),
        ]
        matched = next((token for token in forbidden if token and token in combined), "")
        return HardCheckResult(
            check_id="source_leakage",
            passed=not matched,
            severity="blocker",
            category="retheme_issue",
            message="未发现原题标题/题源泄露。"
            if not matched
            else f"检测到原题标识或标题片段泄露：{matched}",
            evidence_refs=["snapshots.original_problem", "snapshots.generated_problem"],
        )

    def _check_title_overlap(
        self,
        original_problem: dict[str, Any] | None,
        generated_problem: dict[str, Any],
    ) -> HardCheckResult:
        overlap = _text_overlap(
            str(original_problem.get("title", "")) if original_problem else "",
            str(generated_problem.get("title", "")),
        )
        return HardCheckResult(
            check_id="title_overlap",
            passed=overlap < 0.55,
            severity="major",
            category="retheme_issue",
            message=f"标题重合度={overlap:.2f}。" + (" 偏高，疑似换皮。" if overlap >= 0.55 else ""),
            evidence_refs=["snapshots.original_problem.title", "snapshots.generated_problem.title"],
        )

    def _check_sample_count(self, generated_problem: dict[str, Any]) -> HardCheckResult:
        count = len(generated_problem.get("samples", []))
        return HardCheckResult(
            check_id="sample_count",
            passed=count >= 2,
            severity="major",
            category="quality_issue",
            message=f"样例数量={count}。" + (" 少于 2 组。" if count < 2 else ""),
            evidence_refs=["snapshots.generated_problem.samples"],
        )

    def _check_sample_line_alignment(
        self,
        instantiated_schema: dict[str, Any],
        generated_problem: dict[str, Any],
    ) -> HardCheckResult:
        expected_lines = _infer_expected_sample_lines(instantiated_schema)
        if expected_lines is None:
            return HardCheckResult(
                check_id="sample_line_alignment",
                passed=True,
                severity="major",
                category="quality_issue",
                message="输入结构不是固定小数组，跳过样例行数检查。",
                evidence_refs=[],
            )

        bad_index = None
        for index, sample in enumerate(generated_problem.get("samples", []), start=1):
            actual = len([line for line in str(sample.get("input", "")).splitlines() if line.strip()])
            if actual != expected_lines:
                bad_index = index
                break
        return HardCheckResult(
            check_id="sample_line_alignment",
            passed=bad_index is None,
            severity="major",
            category="quality_issue",
            message="样例输入行数与实例化 schema 一致。"
            if bad_index is None
            else f"样例 {bad_index} 的输入行数与实例化 schema 不一致。",
            evidence_refs=["snapshots.generated_problem.samples", "snapshots.instantiated_schema.input_structure"],
        )

    def _check_input_count_alignment(
        self,
        instantiated_schema: dict[str, Any],
        generated_problem: dict[str, Any],
    ) -> HardCheckResult:
        expected_lines = _infer_expected_sample_lines(instantiated_schema)
        if expected_lines is None:
            return HardCheckResult(
                check_id="input_count_alignment",
                passed=True,
                severity="blocker",
                category="quality_issue",
                message="输入结构不是固定小数组，跳过输入项数量声明检查。",
                evidence_refs=[],
            )
        declared = _extract_declared_line_count(
            "\n".join(
                [
                    str(generated_problem.get("description", "")),
                    str(generated_problem.get("input_format", "")),
                    str(generated_problem.get("notes", "")),
                ]
            )
        )
        passed = declared is None or declared == expected_lines
        return HardCheckResult(
            check_id="input_count_alignment",
            passed=passed,
            severity="blocker",
            category="quality_issue",
            message="题面中的输入项数量声明与实例化 schema 一致。"
            if passed
            else f"题面声明输入项数量为 {declared}，但实例化 schema 要求为 {expected_lines}。",
            evidence_refs=["snapshots.generated_problem.input_format", "snapshots.instantiated_schema.input_structure"],
        )

    def _check_objective_alignment(
        self,
        instantiated_schema: dict[str, Any],
        generated_problem: dict[str, Any],
    ) -> HardCheckResult:
        objective_type = str(instantiated_schema.get("objective", {}).get("type", ""))
        combined = "\n".join(
            [
                str(generated_problem.get("description", "")),
                str(generated_problem.get("output_format", "")),
                str(generated_problem.get("notes", "")),
            ]
        ).lower()
        passed = True
        message = "目标函数已经在题面中落地。"
        if objective_type == "count_minimal_strings":
            passed = any(token in combined for token in ("方案数", "个数", "count", "模", "mod"))
            message = "计数目标未在题面中明确表达。" if not passed else message
        elif objective_type == "decision":
            passed = any(token in combined for token in ("yes", "no", "是否", "存在"))
            message = "判定目标未在题面中明确表达。" if not passed else message
        elif objective_type == "lexicographically_first_minimal_string":
            passed = any(token in combined for token in ("字典序", "lexicographical", "lexicographically"))
            message = "字典序 tie-break 未在题面中明确表达。" if not passed else message
        return HardCheckResult(
            check_id="objective_alignment",
            passed=passed,
            severity="blocker",
            category="quality_issue",
            message=message,
            evidence_refs=["snapshots.instantiated_schema.objective", "snapshots.generated_problem.output_format"],
        )

    def _check_structural_option_alignment(
        self,
        instantiated_schema: dict[str, Any],
        generated_problem: dict[str, Any],
    ) -> HardCheckResult:
        options = list(instantiated_schema.get("selected_structural_options", []))
        combined = "\n".join(
            [
                str(generated_problem.get("description", "")),
                str(generated_problem.get("notes", "")),
                "\n".join(str(item) for item in generated_problem.get("constraints", [])),
            ]
        ).lower()
        missing: list[str] = []
        if "must_contain_in_order" in options and not any(
            token in combined for token in ("顺序", "依次", "in order")
        ):
            missing.append("must_contain_in_order")
        if "cyclic_string" in options and not any(
            token in combined for token in ("循环", "首尾相接", "环", "cyclic")
        ):
            missing.append("cyclic_string")
        return HardCheckResult(
            check_id="structural_option_alignment",
            passed=not missing,
            severity="blocker",
            category="quality_issue",
            message="结构选项已在题面中落地。"
            if not missing
            else f"以下结构选项未在题面中体现：{', '.join(missing)}。",
            evidence_refs=["snapshots.instantiated_schema.selected_structural_options", "snapshots.generated_problem"],
        )

    def _evaluate_divergence(
        self,
        original_problem: dict[str, Any] | None,
        original_schema: dict[str, Any],
        instantiated_schema: dict[str, Any],
        generated_problem: dict[str, Any],
        hard_checks: list[dict[str, Any]],
        difference_plan: dict[str, Any],
        schema_distance: float,
        changed_axes_realized: list[str],
    ) -> dict[str, Any]:
        if not original_problem:
            result = DivergenceResult(
                schema_distance=schema_distance,
                changed_axes_planned=list(difference_plan.get("changed_axes", [])),
                changed_axes_realized=changed_axes_realized,
                semantic_difference=0.0,
                solution_transfer_risk=1.0,
                surface_retheme_risk=1.0,
                verdict="reject_as_retheme",
                rationale="缺少原题文本，无法完成反换皮判定。",
                evidence_refs=["snapshots.original_problem"],
            )
            return asdict(result)

        judge_result = self.divergence_judge.evaluate(
            original_problem=original_problem,
            original_schema=original_schema,
            instantiated_schema=instantiated_schema,
            generated_problem=generated_problem,
            hard_checks=hard_checks,
            schema_distance=schema_distance,
        )
        result = DivergenceResult(
            schema_distance=schema_distance,
            changed_axes_planned=list(difference_plan.get("changed_axes", [])),
            changed_axes_realized=changed_axes_realized,
            semantic_difference=judge_result["semantic_difference"],
            solution_transfer_risk=judge_result["solution_transfer_risk"],
            surface_retheme_risk=judge_result["surface_retheme_risk"],
            verdict=judge_result["verdict"],
            rationale=judge_result["rationale"],
            evidence_refs=judge_result.get("evidence_refs", []),
        )
        return asdict(result)

    def _calculate_quality_score(self, quality_result: dict[str, Any]) -> float:
        weights = {
            "variant_fidelity": 0.30,
            "spec_completeness": 0.25,
            "cross_section_consistency": 0.20,
            "sample_quality": 0.15,
            "oj_readability": 0.10,
        }
        total = 0.0
        for item in quality_result.get("dimension_scores", []):
            total += weights.get(item["dimension"], 0.0) * (float(item["score"]) / 5.0 * 100.0)
        return round(total, 1)

    def _calculate_divergence_score(
        self,
        schema_distance: float,
        semantic_difference: float,
        solution_transfer_risk: float,
    ) -> float:
        schema_distance_component = min(1.0, max(0.0, schema_distance / 0.60))
        score = (
            schema_distance_component * 45.0
            + semantic_difference * 30.0
            + (1.0 - solution_transfer_risk) * 25.0
        )
        return round(score, 1)

    def _collect_issues(
        self,
        hard_checks: list[HardCheckResult],
        quality_result: dict[str, Any],
        divergence_result: dict[str, Any],
    ) -> list[Issue]:
        issues: list[Issue] = []
        for check in hard_checks:
            if check.passed:
                continue
            title = check.check_id.replace("_", " ")
            issues.append(
                Issue(
                    issue_type=check.category,
                    severity=check.severity,
                    title=title,
                    detail=check.message,
                    evidence_refs=check.evidence_refs,
                    fix_hint=self._default_fix_hint(check),
                )
            )
        for raw_issue in quality_result.get("issues", []):
            issues.append(Issue(**raw_issue))
        if divergence_result["verdict"] == "reject_as_retheme":
            issues.append(
                Issue(
                    issue_type="retheme_issue",
                    severity="blocker",
                    title="solution transfer risk too high",
                    detail=divergence_result["rationale"],
                    evidence_refs=divergence_result.get("evidence_refs", []),
                    fix_hint="增加输入/约束/目标的实质变化，降低原题解法的直接迁移性。",
                )
            )
        return issues

    def _default_fix_hint(self, check: HardCheckResult) -> str:
        mapping = {
            "source_problem_resolved": "补齐原题来源信息，确保能从题库索引中读取原题文本。",
            "generated_status_ok": "先修复生成阶段的 schema/difference 不足，再重新生成题面。",
            "difference_plan_present": "在生成 artifact 中持久化 difference_plan，避免评估时回推。",
            "schema_distance_threshold": "提高输入/约束/目标的结构差异，避免停留在同母题换皮。",
            "changed_axes_threshold": "至少让 I/C/O/T 中两个核心轴发生实质变化。",
            "source_leakage": "删除原题编号、题源、标题和明显句式复用。",
            "title_overlap": "重写标题，不要保留原题标题语义骨架。",
            "sample_count": "至少补齐两组可验证样例。",
            "sample_line_alignment": "按实例化 schema 重写样例输入的行数与组织方式。",
            "input_count_alignment": "按实例化 schema 重写输入格式和描述中的项数。",
            "objective_alignment": "在 output_format 和 notes 中明确真实目标函数与 tie-break。",
            "structural_option_alignment": "把结构变化显式写入规则定义和说明部分。",
        }
        return mapping.get(check.check_id, "")

    def _collect_suggestions(
        self,
        issues: list[Issue],
        quality_result: dict[str, Any],
        divergence_result: dict[str, Any],
    ) -> list[str]:
        suggestions = [issue.fix_hint for issue in issues if issue.fix_hint]
        suggestions.extend(quality_result.get("suggested_revisions", []))
        if divergence_result["verdict"] == "reject_as_retheme":
            suggestions.append("优先改写核心任务定义，而不是继续替换故事背景。")
        deduped: list[str] = []
        for item in suggestions:
            if item and item not in deduped:
                deduped.append(item)
        return deduped

    def _determine_status(
        self,
        original_problem: dict[str, Any] | None,
        generated_problem: dict[str, Any],
        hard_checks: list[HardCheckResult],
        quality_score: float,
        divergence_score: float,
        divergence_result: dict[str, Any],
    ) -> str:
        generated_status = generated_problem.get("status", "ok")
        if original_problem is None or generated_status == "schema_insufficient":
            return "reject_invalid"
        if generated_status == "difference_insufficient":
            return "reject_as_retheme"

        failed = [check for check in hard_checks if not check.passed]
        if any(check.category == "invalid" and check.severity == "blocker" for check in failed):
            return "reject_invalid"
        if (
            divergence_score < 70.0
            or divergence_result["verdict"] == "reject_as_retheme"
            or any(check.category == "retheme_issue" and check.severity == "blocker" for check in failed)
        ):
            return "reject_as_retheme"
        if quality_score < 80.0 or any(
            check.category == "quality_issue" and not check.passed for check in failed
        ):
            return "revise_quality"
        return "pass"


def _infer_expected_sample_lines(schema: dict[str, Any]) -> int | None:
    input_structure = schema.get("input_structure", {})
    if input_structure.get("type") != "array":
        return None
    length = input_structure.get("length", {})
    minimum = length.get("min")
    maximum = length.get("max")
    if not isinstance(minimum, int) or minimum != maximum:
        return None
    if minimum <= 0 or minimum > 10:
        return None
    return minimum


def _extract_declared_line_count(text: str) -> int | None:
    import re

    patterns = [
        r"输入共\s*(\d+)\s*行",
        r"恰好\s*(\d+)\s*行",
        r"exactly\s*(\d+)\s*lines",
        r"(\d+)\s*行",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))

    chinese_digits = {
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }
    match = re.search(r"输入共([一二两三四五六七八九十])行", text)
    if match:
        return chinese_digits.get(match.group(1))
    return None


def _text_overlap(left: str, right: str) -> float:
    import re

    left_tokens = set(re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", left.lower()))
    right_tokens = set(re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", right.lower()))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
