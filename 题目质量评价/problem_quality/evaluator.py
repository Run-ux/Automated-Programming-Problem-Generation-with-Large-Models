from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

GENERATION_DIR = Path(__file__).resolve().parents[2] / "生成题面"
if str(GENERATION_DIR) not in sys.path:
    sys.path.append(str(GENERATION_DIR))

from config import DEFAULT_API_KEY, DEFAULT_BASE_URL, DEFAULT_MODEL, DEFAULT_TIMEOUT_S
from qwen_client import QwenClient

from .judges import ProblemQualityJudge, SourceDivergenceJudge
from .models import DivergenceResult, EvaluationReport, HardCheckResult, Issue
from .original_problem_catalog import OriginalProblemCatalog


class ProblemEvaluator:
    def __init__(
        self,
        client: Any | None = None,
        judge_client: Any | None = None,
        original_problem_catalog: OriginalProblemCatalog | None = None,
        original_problem_output_dir: str | Path | None = None,
    ):
        shared_client = judge_client or client or self._build_default_client()
        if shared_client is None:
            raise RuntimeError(
                "当前版本的题目质量评价需要可用的 LLM Judge 接口。"
                "请配置 QWEN_API_KEY 或 DASHSCOPE_API_KEY，或显式传入 judge_client。"
            )
        self.judge_client = shared_client
        self.quality_judge = ProblemQualityJudge(client=self.judge_client)
        self.divergence_judge = SourceDivergenceJudge(client=self.judge_client)
        self.original_problem_catalog = original_problem_catalog or OriginalProblemCatalog(
            output_dir=original_problem_output_dir
        )

    def evaluate_problem(
        self,
        schema_path: str | Path,
        artifact_path: str | Path,
        original_problem_override: dict[str, Any] | str | Path | None = None,
        markdown_path: str | Path | None = None,
        round_index: int = 1,
    ) -> dict[str, Any]:
        source_schema = self._load_json(schema_path)
        artifact = self._load_json(artifact_path)

        original_problem = self._resolve_original_problem(
            original_problem_override=original_problem_override,
            source_schema=source_schema,
            artifact=artifact,
        )
        generated_problem, generated_problem_present = self._normalize_generated_problem(artifact)
        (
            new_schema,
            difference_plan,
            artifact_contract,
            schema_distance,
            schema_distance_breakdown,
            changed_axes_realized,
        ) = self._normalize_artifact(artifact)
        artifact_contract["generated_problem_present"] = generated_problem_present
        review_context = self._build_review_context(
            artifact=artifact,
            difference_plan=difference_plan,
            schema_distance_breakdown=schema_distance_breakdown,
            changed_axes_realized=changed_axes_realized,
        )

        hard_checks = self._run_hard_checks(
            original_problem=original_problem,
            new_schema=new_schema,
            difference_plan=difference_plan,
            generated_problem=generated_problem,
            schema_distance=schema_distance,
            schema_distance_breakdown=schema_distance_breakdown,
            changed_axes_realized=changed_axes_realized,
            artifact_contract=artifact_contract,
        )
        hard_check_dicts = [asdict(item) for item in hard_checks]

        effective_schema = new_schema or {}
        quality_result = self.quality_judge.evaluate(
            new_schema=effective_schema,
            generated_problem=generated_problem,
            hard_checks=hard_check_dicts,
            review_context=review_context,
        )
        divergence_result = self._evaluate_divergence(
            original_problem=original_problem,
            original_schema=source_schema,
            new_schema=effective_schema,
            generated_problem=generated_problem,
            hard_checks=hard_check_dicts,
            difference_plan=difference_plan,
            schema_distance=schema_distance,
            changed_axes_realized=changed_axes_realized,
            review_context=review_context,
        )

        quality_score = self._calculate_quality_score(quality_result)
        divergence_score = self._calculate_divergence_score(
            schema_distance=schema_distance,
            semantic_difference=divergence_result["semantic_difference"],
            solution_transfer_risk=divergence_result["solution_transfer_risk"],
        )

        issues = self._collect_issues(
            hard_checks=hard_checks,
            quality_result=quality_result,
            divergence_result=divergence_result,
        )
        issue_dicts = [asdict(item) if hasattr(item, "__dataclass_fields__") else item for item in issues]
        status = self._determine_status(
            original_problem=original_problem,
            generated_problem=generated_problem,
            hard_checks=hard_checks,
            quality_score=quality_score,
            divergence_score=divergence_score,
            divergence_result=divergence_result,
        )
        suggested_revisions = self._collect_suggestions(issues, quality_result, divergence_result)
        revision_brief = self._build_revision_brief(
            round_index=round_index,
            status=status,
            generated_status=generated_problem.get("status", "ok"),
            quality_score=quality_score,
            divergence_score=divergence_score,
            hard_checks=hard_checks,
            issues=issue_dicts,
            suggested_revisions=suggested_revisions,
            strengths=quality_result.get("strengths", []),
        )

        report = EvaluationReport(
            overall={
                "status": status,
                "quality_score": quality_score,
                "divergence_score": divergence_score,
                "schema_distance": schema_distance,
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
            issues=issue_dicts,
            suggested_revisions=suggested_revisions,
            revision_brief=revision_brief,
            snapshots={
                "paths": {
                    "schema_path": str(Path(schema_path)),
                    "artifact_path": str(Path(artifact_path)),
                    "markdown_path": str(Path(markdown_path)) if markdown_path else "",
                },
                "original_problem": original_problem or {},
                "difference_plan": difference_plan,
                "new_schema": effective_schema,
                "generated_problem": generated_problem,
                "artifact_contract": artifact_contract,
                "review_context": review_context,
            },
        )
        return asdict(report)

    def _build_revision_brief(
        self,
        *,
        round_index: int,
        status: str,
        generated_status: str,
        quality_score: float,
        divergence_score: float,
        hard_checks: list[dict[str, Any]],
        issues: list[dict[str, Any]],
        suggested_revisions: list[str],
        strengths: list[str],
    ) -> dict[str, Any]:
        failed_hard_checks: list[dict[str, Any]] = []
        for item in hard_checks:
            if hasattr(item, "__dataclass_fields__"):
                raw_item = asdict(item)
            else:
                raw_item = dict(item)
            if raw_item.get("passed"):
                continue
            failed_hard_checks.append(
                {
                    "check_id": str(raw_item.get("check_id", "")),
                    "severity": str(raw_item.get("severity", "")),
                    "category": str(raw_item.get("category", "")),
                    "message": str(raw_item.get("message", "")),
                    "evidence_refs": list(raw_item.get("evidence_refs", [])),
                }
            )
        return {
            "round_index": round_index,
            "overall_status": status,
            "generated_status": generated_status,
            "quality_score": quality_score,
            "divergence_score": divergence_score,
            "failed_hard_checks": failed_hard_checks,
            "issues": json.loads(json.dumps(issues, ensure_ascii=False)),
            "suggested_revisions": list(suggested_revisions),
            "strengths_to_keep": [str(item) for item in strengths],
        }

    def _build_default_client(self) -> Any | None:
        if not DEFAULT_API_KEY:
            return None
        return QwenClient(
            api_key=DEFAULT_API_KEY,
            model=DEFAULT_MODEL,
            base_url=DEFAULT_BASE_URL,
            timeout_s=DEFAULT_TIMEOUT_S,
        )

    def _load_json(self, path: str | Path) -> dict[str, Any]:
        target = Path(path)
        with target.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _resolve_original_problem(
        self,
        original_problem_override: dict[str, Any] | str | Path | None,
        source_schema: dict[str, Any],
        artifact: dict[str, Any],
    ) -> dict[str, Any] | None:
        if isinstance(original_problem_override, dict):
            return original_problem_override
        if isinstance(original_problem_override, (str, Path)):
            return self._load_json(original_problem_override)
        if original_problem_override is not None:
            raise TypeError("original_problem_override 必须是原题字典、原题 JSON 路径或 None。")

        for problem_id in self._extract_problem_id_candidates(source_schema=source_schema, artifact=artifact):
            match = self.original_problem_catalog.get_by_problem_id(problem_id)
            if match is not None:
                return match
        return None

    def _extract_problem_id_candidates(
        self,
        source_schema: dict[str, Any],
        artifact: dict[str, Any],
    ) -> list[str]:
        candidates: list[str] = []
        source_problem_ids = artifact.get("source_problem_ids")
        if isinstance(source_problem_ids, list) and source_problem_ids:
            head = source_problem_ids[0]
            if isinstance(head, str) and head.strip():
                candidates.append(head.strip())
        schema_problem_id = source_schema.get("problem_id")
        if isinstance(schema_problem_id, str) and schema_problem_id.strip():
            schema_id = schema_problem_id.strip()
            if schema_id not in candidates:
                candidates.append(schema_id)
        return candidates

    def _normalize_generated_problem(
        self,
        artifact: dict[str, Any],
    ) -> tuple[dict[str, Any], bool]:
        raw_problem = artifact.get("generated_problem")
        generated_problem_present = isinstance(raw_problem, dict)
        payload = raw_problem if generated_problem_present else {}

        samples: list[dict[str, str]] = []
        for item in payload.get("samples", []):
            if not isinstance(item, dict):
                continue
            samples.append(
                {
                    "input": str(item.get("input", "")),
                    "output": str(item.get("output", "")),
                    "explanation": str(item.get("explanation", "")),
                }
            )

        constraints = payload.get("constraints", [])
        if not isinstance(constraints, list):
            constraints = []

        normalized = {
            "title": str(payload.get("title", "")),
            "description": str(payload.get("description", "")),
            "input_format": str(payload.get("input_format", "")),
            "output_format": str(payload.get("output_format", "")),
            "constraints": [str(item) for item in constraints],
            "samples": samples,
            "notes": str(payload.get("notes", "")),
            "status": _resolve_generated_status(artifact, payload, generated_problem_present),
            "error_reason": str(payload.get("error_reason") or artifact.get("planning_error_reason", "")),
            "feedback": str(payload.get("feedback") or artifact.get("planning_feedback", "")),
        }
        return normalized, generated_problem_present

    def _normalize_artifact(
        self,
        artifact: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, dict[str, Any], dict[str, bool], float, dict[str, Any], list[str]]:
        raw_new_schema = artifact.get("new_schema")
        has_new_schema = isinstance(raw_new_schema, dict) and bool(raw_new_schema)
        raw_new_schema_snapshot = artifact.get("new_schema_snapshot")
        has_new_schema_snapshot = isinstance(raw_new_schema_snapshot, dict) and bool(raw_new_schema_snapshot)
        selected_schema = raw_new_schema if has_new_schema else raw_new_schema_snapshot
        has_schema = isinstance(selected_schema, dict) and bool(selected_schema)
        normalized_schema = (
            json.loads(json.dumps(selected_schema, ensure_ascii=False))
            if has_schema
            else None
        )

        difference_plan = artifact.get("difference_plan")
        has_difference_plan = isinstance(difference_plan, dict) and bool(difference_plan)
        normalized_difference_plan = (
            json.loads(json.dumps(difference_plan, ensure_ascii=False))
            if has_difference_plan
            else {
                "target_distance_band": {},
                "changed_axes": [],
                "same_family_allowed": True,
                "forbidden_reuse": [],
                "rationale": "",
                "summary": "",
                "mode": "",
            }
        )

        predicted_schema_distance = artifact.get("predicted_schema_distance")
        has_predicted_schema_distance = (
            isinstance(predicted_schema_distance, (int, float))
            and not isinstance(predicted_schema_distance, bool)
        )
        normalized_schema_distance = float(predicted_schema_distance) if has_predicted_schema_distance else 0.0

        distance_breakdown = artifact.get("distance_breakdown")
        has_distance_breakdown = isinstance(distance_breakdown, dict) and bool(distance_breakdown)
        normalized_distance_breakdown = (
            json.loads(json.dumps(distance_breakdown, ensure_ascii=False))
            if has_distance_breakdown
            else {}
        )

        changed_axes_realized = artifact.get("changed_axes_realized")
        has_changed_axes_realized = isinstance(changed_axes_realized, list)
        normalized_changed_axes_realized = (
            [str(item) for item in changed_axes_realized]
            if has_changed_axes_realized
            else []
        )

        return normalized_schema, normalized_difference_plan, {
            "new_schema_present": has_schema,
            "new_schema_field_present": has_new_schema,
            "new_schema_snapshot_field_present": has_new_schema_snapshot,
            "difference_plan_present": has_difference_plan,
            "predicted_schema_distance_present": has_predicted_schema_distance,
            "distance_breakdown_present": has_distance_breakdown,
            "changed_axes_realized_present": has_changed_axes_realized,
        }, normalized_schema_distance, normalized_distance_breakdown, normalized_changed_axes_realized

    def _build_review_context(
        self,
        artifact: dict[str, Any],
        difference_plan: dict[str, Any],
        schema_distance_breakdown: dict[str, Any],
        changed_axes_realized: list[str],
    ) -> dict[str, Any]:
        applied_helpers = artifact.get("applied_helpers", [])
        if not isinstance(applied_helpers, list):
            applied_helpers = []
        algorithmic_delta_claim = artifact.get("algorithmic_delta_claim", {})
        if not isinstance(algorithmic_delta_claim, dict):
            algorithmic_delta_claim = {}

        return {
            "difference_plan": {
                "summary": str(difference_plan.get("summary", "")),
                "mode": str(difference_plan.get("mode", "")),
                "changed_axes": [str(item) for item in difference_plan.get("changed_axes", [])],
            },
            "changed_axes_realized": list(changed_axes_realized),
            "distance_breakdown": json.loads(json.dumps(schema_distance_breakdown, ensure_ascii=False)),
            "applied_rule": str(artifact.get("applied_rule", "")),
            "applied_helpers": json.loads(json.dumps(applied_helpers, ensure_ascii=False)),
            "algorithmic_delta_claim": json.loads(json.dumps(algorithmic_delta_claim, ensure_ascii=False)),
            "anti_shallow_rationale": str(artifact.get("anti_shallow_rationale", "")),
        }

    def _run_hard_checks(
        self,
        original_problem: dict[str, Any] | None,
        new_schema: dict[str, Any] | None,
        difference_plan: dict[str, Any],
        generated_problem: dict[str, Any],
        schema_distance: float,
        schema_distance_breakdown: dict[str, Any],
        changed_axes_realized: list[str],
        artifact_contract: dict[str, bool],
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
                check_id="generated_problem_present",
                passed=artifact_contract.get("generated_problem_present", False),
                severity="blocker",
                category="invalid",
                message="artifact 已包含 generated_problem。"
                if artifact_contract.get("generated_problem_present", False)
                else "artifact 缺少 generated_problem。",
                evidence_refs=["snapshots.generated_problem"],
            )
        )
        checks.append(
            HardCheckResult(
                check_id="new_schema_present",
                passed=artifact_contract.get("new_schema_present", False),
                severity="blocker",
                category="invalid",
                message="artifact 已包含 new_schema 或兼容字段 new_schema_snapshot。"
                if artifact_contract.get("new_schema_present", False)
                else "artifact 缺少 new_schema 且缺少兼容字段 new_schema_snapshot。",
                evidence_refs=["snapshots.new_schema"],
            )
        )
        checks.append(
            HardCheckResult(
                check_id="difference_plan_present",
                passed=artifact_contract.get("difference_plan_present", False),
                severity="blocker",
                category="invalid",
                message="artifact 已持久化 difference_plan。"
                if artifact_contract.get("difference_plan_present", False)
                else "artifact 缺少 difference_plan。",
                evidence_refs=["snapshots.difference_plan"],
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
                check_id="predicted_schema_distance_present",
                passed=artifact_contract.get("predicted_schema_distance_present", False),
                severity="blocker",
                category="invalid",
                message="artifact 已包含 predicted_schema_distance。"
                if artifact_contract.get("predicted_schema_distance_present", False)
                else "artifact 缺少 predicted_schema_distance。",
                evidence_refs=["divergence.schema_distance_breakdown", "snapshots.artifact_contract"],
            )
        )
        checks.append(
            HardCheckResult(
                check_id="distance_breakdown_present",
                passed=artifact_contract.get("distance_breakdown_present", False),
                severity="blocker",
                category="invalid",
                message="artifact 已包含 distance_breakdown。"
                if artifact_contract.get("distance_breakdown_present", False)
                else "artifact 缺少 distance_breakdown。",
                evidence_refs=["divergence.schema_distance_breakdown", "snapshots.artifact_contract"],
            )
        )
        checks.append(
            HardCheckResult(
                check_id="changed_axes_realized_present",
                passed=artifact_contract.get("changed_axes_realized_present", False),
                severity="blocker",
                category="invalid",
                message="artifact 已包含 changed_axes_realized。"
                if artifact_contract.get("changed_axes_realized_present", False)
                else "artifact 缺少 changed_axes_realized。",
                evidence_refs=["snapshots.difference_plan", "snapshots.artifact_contract"],
            )
        )
        checks.append(
            HardCheckResult(
                check_id="schema_distance_threshold",
                passed=artifact_contract.get("predicted_schema_distance_present", False) and schema_distance >= 0.35,
                severity="blocker",
                category="retheme_issue"
                if artifact_contract.get("predicted_schema_distance_present", False)
                else "invalid",
                message=(
                    f"schema_distance={schema_distance:.2f}，达到中等差异阈值。"
                    if artifact_contract.get("predicted_schema_distance_present", False) and schema_distance >= 0.35
                    else (
                        f"schema_distance={schema_distance:.2f}，低于 0.35。"
                        + (" 已接近同母题换皮（<0.25）。" if schema_distance < 0.25 else "")
                    )
                    if artifact_contract.get("predicted_schema_distance_present", False)
                    else "缺少 predicted_schema_distance，无法完成差异阈值检查。"
                ),
                evidence_refs=["divergence.schema_distance_breakdown"],
            )
        )
        checks.append(
            HardCheckResult(
                check_id="changed_axes_threshold",
                passed=artifact_contract.get("changed_axes_realized_present", False) and len(changed_axes_realized) >= 2,
                severity="blocker",
                category="retheme_issue"
                if artifact_contract.get("changed_axes_realized_present", False)
                else "invalid",
                message=(
                    f"已落地核心差异轴：{', '.join(changed_axes_realized)}。"
                    if artifact_contract.get("changed_axes_realized_present", False) and len(changed_axes_realized) >= 2
                    else f"仅落地了 {len(changed_axes_realized)} 个核心差异轴：{', '.join(changed_axes_realized) or '无'}。"
                    if artifact_contract.get("changed_axes_realized_present", False)
                    else "缺少 changed_axes_realized，无法确认核心差异轴是否落地。"
                ),
                evidence_refs=["snapshots.difference_plan", "snapshots.new_schema"],
            )
        )

        checks.append(self._check_source_leakage(original_problem, generated_problem))
        checks.append(self._check_title_overlap(original_problem, generated_problem))
        checks.append(self._check_sample_count(generated_problem))

        if new_schema is not None:
            checks.append(self._check_sample_line_alignment(new_schema, generated_problem))
            checks.append(self._check_input_count_alignment(new_schema, generated_problem))
            checks.append(self._check_objective_alignment(new_schema, generated_problem))
            checks.append(self._check_structural_option_alignment(new_schema, generated_problem))
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
            message="未发现原题标题或题源泄露。"
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
        new_schema: dict[str, Any],
        generated_problem: dict[str, Any],
    ) -> HardCheckResult:
        expected_lines = _infer_expected_sample_lines(new_schema)
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
            message="样例输入行数与 new_schema 一致。"
            if bad_index is None
            else f"样例 {bad_index} 的输入行数与 new_schema 不一致。",
            evidence_refs=["snapshots.generated_problem.samples", "snapshots.new_schema.input_structure"],
        )

    def _check_input_count_alignment(
        self,
        new_schema: dict[str, Any],
        generated_problem: dict[str, Any],
    ) -> HardCheckResult:
        expected_lines = _infer_expected_sample_lines(new_schema)
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
            message="题面中的输入项数量声明与 new_schema 一致。"
            if passed
            else f"题面声明输入项数量为 {declared}，但 new_schema 要求为 {expected_lines}。",
            evidence_refs=["snapshots.generated_problem.input_format", "snapshots.new_schema.input_structure"],
        )

    def _check_objective_alignment(
        self,
        new_schema: dict[str, Any],
        generated_problem: dict[str, Any],
    ) -> HardCheckResult:
        objective_type = str(new_schema.get("objective", {}).get("type", ""))
        combined = "\n".join(
            [
                str(generated_problem.get("description", "")),
                str(generated_problem.get("output_format", "")),
                str(generated_problem.get("notes", "")),
            ]
        ).lower()
        passed = True
        message = "目标函数已经在题面中落地。"
        if objective_type in {"count_minimal_strings", "count", "count_modulo"}:
            passed = any(token in combined for token in ("方案数", "个数", "count", "数量", "模", "mod"))
            message = "计数目标未在题面中明确表达。" if not passed else message
        elif objective_type == "decision":
            passed = any(token in combined for token in ("yes", "no", "是否", "存在"))
            message = "判定目标未在题面中明确表达。" if not passed else message
        elif objective_type == "lexicographically_first_minimal_string":
            passed = any(token in combined for token in ("字典序", "lexicographical", "lexicographically"))
            message = "字典序 tie-break 未在题面中明确表达。" if not passed else message
        elif objective_type in {"minimize_value", "value_computation"}:
            passed = any(token in combined for token in ("输出", "整数", "最小", "最优", "minimum"))
            message = "数值目标未在题面中明确表达。" if not passed else message
        return HardCheckResult(
            check_id="objective_alignment",
            passed=passed,
            severity="blocker",
            category="quality_issue",
            message=message,
            evidence_refs=["snapshots.new_schema.objective", "snapshots.generated_problem.output_format"],
        )

    def _check_structural_option_alignment(
        self,
        new_schema: dict[str, Any],
        generated_problem: dict[str, Any],
    ) -> HardCheckResult:
        options = list(new_schema.get("selected_structural_options", []))
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
            evidence_refs=["snapshots.new_schema.selected_structural_options", "snapshots.generated_problem"],
        )

    def _evaluate_divergence(
        self,
        original_problem: dict[str, Any] | None,
        original_schema: dict[str, Any],
        new_schema: dict[str, Any],
        generated_problem: dict[str, Any],
        hard_checks: list[dict[str, Any]],
        difference_plan: dict[str, Any],
        schema_distance: float,
        changed_axes_realized: list[str],
        review_context: dict[str, Any],
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
            new_schema=new_schema,
            generated_problem=generated_problem,
            hard_checks=hard_checks,
            schema_distance=schema_distance,
            review_context=review_context,
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
                    fix_hint="增加输入、约束与目标的实质变化，降低原题解法的直接迁移性。",
                )
            )
        return issues

    def _default_fix_hint(self, check: HardCheckResult) -> str:
        mapping = {
            "source_problem_resolved": "显式提供可读取的原题 JSON，确保评测阶段能够加载原题文本。",
            "generated_problem_present": "确认上游 artifact 已输出 generated_problem。",
            "new_schema_present": "确认上游 artifact 已输出 new_schema，或兼容输出 new_schema_snapshot。",
            "generated_status_ok": "先修复生成阶段的 schema 或 difference 问题，再重新生成题面。",
            "difference_plan_present": "确认上游 artifact 已持久化 difference_plan。",
            "predicted_schema_distance_present": "确认上游 artifact 已输出 predicted_schema_distance。",
            "distance_breakdown_present": "确认上游 artifact 已输出 distance_breakdown。",
            "changed_axes_realized_present": "确认上游 artifact 已输出 changed_axes_realized。",
            "schema_distance_threshold": "提高输入、约束与目标的结构差异，避免停留在同母题换皮。",
            "changed_axes_threshold": "至少让 I、C、O、V 中两个核心轴发生实质变化。",
            "source_leakage": "删除原题编号、题源、标题和明显句式复用。",
            "title_overlap": "重写标题，不要保留原题标题语义骨架。",
            "sample_count": "至少补齐两组可验证样例。",
            "sample_line_alignment": "按 new_schema 重写样例输入的行数与组织方式。",
            "input_count_alignment": "按 new_schema 重写输入格式和描述中的项数。",
            "objective_alignment": "在 output_format 和 notes 中明确真实目标函数与必要的 tie-break。",
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


def _resolve_generated_status(
    artifact: dict[str, Any],
    generated_problem: dict[str, Any],
    generated_problem_present: bool,
) -> str:
    status = str(generated_problem.get("status", "")).strip()
    if status:
        return status

    planning_status = str(artifact.get("planning_status", "")).strip()
    if planning_status:
        return planning_status

    return "artifact_invalid" if not generated_problem_present else "ok"


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
