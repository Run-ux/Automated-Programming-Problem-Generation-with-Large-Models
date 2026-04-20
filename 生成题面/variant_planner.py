from __future__ import annotations

import copy
import random
from typing import Any

from models import AuditTraceEvent, DifferencePlan, NewSchema, RuleSelectionResult, Theme, VariantPlan
from prompt_builder import (
    build_planner_system_prompt,
    build_planner_user_prompt,
    build_rule_selection_system_prompt,
    build_rule_selection_user_prompt,
)
from qwen_client import QwenClient
from rule_handlers import get_rule_handler, selection_result_to_event
from rulebook import RuleBook, normalize_mode_name, normalize_rule_id
from schema_tools import build_forbidden_reuse_list, compute_changed_axes, compute_schema_distance, dataclass_to_dict


THEMES = [
    Theme(
        theme_id="cyber_city",
        name="赛博城市调度",
        tone="冷静、工程化、略带未来感",
        keywords=["节点", "数据流", "权限", "缓存", "链路", "控制台"],
        mapping_hint="把原始结构映射成网络节点、任务包或访问记录。",
    ),
    Theme(
        theme_id="arcane_lab",
        name="奥术实验室",
        tone="神秘、规则驱动、强调仪式感",
        keywords=["符文", "法阵", "共鸣", "晶核", "炼成", "序列"],
        mapping_hint="把状态变化映射成符文叠加、法阵拼接或能量共鸣。",
    ),
    Theme(
        theme_id="interstellar_logistics",
        name="星际物流",
        tone="宏观、任务导向、强调资源与路径",
        keywords=["货舱", "航线", "补给", "跃迁", "殖民地", "调度中心"],
        mapping_hint="把对象映射成货物、航线、站点、任务波次。",
    ),
    Theme(
        theme_id="campus_ops",
        name="校园运营",
        tone="日常、轻松、贴近现实",
        keywords=["社团", "教室", "队伍", "课表", "仓库", "窗口"],
        mapping_hint="把抽象约束映射成排队、分配、排课或借还流程。",
    ),
]

REQUIRED_NEW_SCHEMA_FIELDS = (
    "problem_id",
    "source",
    "input_structure",
    "core_constraints",
    "objective",
    "invariant",
)

ALLOWED_NEW_SCHEMA_FIELDS = REQUIRED_NEW_SCHEMA_FIELDS + (
    "theme",
    "difficulty",
)


class VariantPlanner:
    MIN_DISTANCE = 0.35
    MAX_DISTANCE = 0.60
    MAX_RULE_ATTEMPTS = 3

    def __init__(
        self,
        client: QwenClient | None,
        rulebook: RuleBook,
        seed: int | None = None,
    ):
        self.client = client
        self.rulebook = rulebook
        self.seed = seed if seed is not None else random.randrange(1, 10**9)

    def build_plan(
        self,
        *,
        mode: str,
        variant_index: int,
        theme_id: str | None,
        seed_schema: dict[str, Any] | None = None,
        original_problem: dict[str, Any] | None = None,
        seed_a_schema: dict[str, Any] | None = None,
        seed_b_schema: dict[str, Any] | None = None,
        seed_a_problem: dict[str, Any] | None = None,
        seed_b_problem: dict[str, Any] | None = None,
        allowed_rule_ids: set[str] | None = None,
        revision_context: dict[str, Any] | None = None,
    ) -> VariantPlan:
        if self.client is None:
            raise RuntimeError("未初始化 LLM 客户端，无法执行规则规划。")

        canonical_mode = _canonical_mode(mode)
        rng = random.Random(self.seed + variant_index)
        theme = self._select_theme(rng, theme_id)

        if canonical_mode == "single_seed_extension":
            return self._build_single_plan(
                seed_schema=seed_schema or {},
                original_problem=original_problem,
                variant_index=variant_index,
                theme=theme,
                allowed_rule_ids=allowed_rule_ids,
                revision_context=revision_context,
            )
        if canonical_mode == "same_family_fusion":
            if seed_a_schema is None or seed_b_schema is None or seed_a_problem is None or seed_b_problem is None:
                raise ValueError("same_family 模式必须提供两题 schema 和原题文本。")
            return self._build_same_family_plan(
                seed_a_schema=seed_a_schema,
                seed_b_schema=seed_b_schema,
                seed_a_problem=seed_a_problem,
                seed_b_problem=seed_b_problem,
                variant_index=variant_index,
                theme=theme,
                allowed_rule_ids=allowed_rule_ids,
                revision_context=revision_context,
            )
        raise ValueError(f"Unsupported mode: {mode}")

    def _build_single_plan(
        self,
        *,
        seed_schema: dict[str, Any],
        original_problem: dict[str, Any] | None,
        variant_index: int,
        theme: Theme,
        allowed_rule_ids: set[str] | None,
        revision_context: dict[str, Any] | None,
    ) -> VariantPlan:
        return self._build_mode_plan(
            mode="single_seed_extension",
            rules=self.rulebook.enabled_rules("single_seed_extension", allowed_rule_ids),
            source_schema=seed_schema,
            source_problem_ids=[seed_schema.get("problem_id", "unknown")],
            schema_context={
                "seed_schema": seed_schema,
            },
            original_refs=[_build_problem_reference(original_problem)],
            theme=theme,
            variant_index=variant_index,
            forbidden_reuse=build_forbidden_reuse_list(original_problem),
            revision_context=revision_context,
        )

    def _build_same_family_plan(
        self,
        *,
        seed_a_schema: dict[str, Any],
        seed_b_schema: dict[str, Any],
        seed_a_problem: dict[str, Any],
        seed_b_problem: dict[str, Any],
        variant_index: int,
        theme: Theme,
        allowed_rule_ids: set[str] | None,
        revision_context: dict[str, Any] | None,
    ) -> VariantPlan:
        schema_context = {
            "seed_a_schema": seed_a_schema,
            "seed_b_schema": seed_b_schema,
        }
        return self._build_mode_plan(
            mode="same_family_fusion",
            rules=self.rulebook.enabled_rules("same_family_fusion", allowed_rule_ids),
            source_schema=_merge_seed_schemas(seed_a_schema, seed_b_schema),
            source_problem_ids=[
                seed_a_schema.get("problem_id", "seed_a"),
                seed_b_schema.get("problem_id", "seed_b"),
            ],
            schema_context=schema_context,
            original_refs=[
                _build_problem_reference(seed_a_problem),
                _build_problem_reference(seed_b_problem),
            ],
            theme=theme,
            variant_index=variant_index,
            forbidden_reuse=_merge_forbidden_reuse(seed_a_problem, seed_b_problem),
            revision_context=revision_context,
        )

    def _build_mode_plan(
        self,
        *,
        mode: str,
        rules: list[dict[str, Any]],
        source_schema: dict[str, Any],
        source_problem_ids: list[str],
        schema_context: dict[str, Any],
        original_refs: list[dict[str, Any]],
        theme: Theme,
        variant_index: int,
        forbidden_reuse: list[str],
        revision_context: dict[str, Any] | None,
    ) -> VariantPlan:
        theme_payload = self._theme_payload(theme)
        if not rules:
            return self._finalize_plan(
                mode=mode,
                source_problem_ids=source_problem_ids,
                source_schema=source_schema,
                theme=theme,
                variant_index=variant_index,
                selected_plan=None,
                rejected_candidates=[],
                forbidden_reuse=forbidden_reuse,
                rule_selection_reason="",
                planning_status="difference_insufficient",
                planning_error_reason="当前模式下没有可用规则。",
                planning_feedback="请检查规则文件的启用状态，或调整 rule override。",
                rule_version=self.rulebook.version(),
            )

        selection = self._select_rule_candidates(
            mode=mode,
            rules=rules,
            schema_context=schema_context,
            original_refs=original_refs,
            revision_context=revision_context,
        )
        if not selection["accepted"]:
            return self._finalize_plan(
                mode=mode,
                source_problem_ids=source_problem_ids,
                source_schema=source_schema,
                theme=theme,
                variant_index=variant_index,
                selected_plan=None,
                rejected_candidates=[],
                forbidden_reuse=forbidden_reuse,
                rule_selection_reason=str(selection.get("selection_reason", "")),
                planning_status=str(selection.get("planning_status", "difference_insufficient")),
                planning_error_reason=str(selection.get("error_reason", "")),
                planning_feedback=str(selection.get("feedback", "")),
                rule_version=self.rulebook.version(),
                selection_trace=selection.get("selection_trace", []),
                validation_trace=selection.get("validation_trace", []),
            )

        rejected_candidates: list[dict[str, Any]] = []
        candidate_attempts: list[dict[str, Any]] = []
        validation_trace: list[dict[str, Any]] = list(selection.get("validation_trace", []))
        ranked_candidates = list(selection.get("ranked_rules", []))[: self.MAX_RULE_ATTEMPTS]

        for attempt_index, candidate in enumerate(ranked_candidates, start=1):
            plan_result = self._generate_candidate(
                mode=mode,
                rule=candidate["rule"],
                selection_result=candidate["selection"],
                theme_payload=theme_payload,
                schema_context=schema_context,
                original_refs=original_refs,
                source_schema=source_schema,
                source_problem_ids=source_problem_ids,
                revision_context=revision_context,
            )
            attempt = dict(plan_result["attempt"])
            attempt["attempt_index"] = attempt_index
            candidate_attempts.append(attempt)
            validation_trace.extend(plan_result["validation_trace"])
            if plan_result["accepted"]:
                return self._finalize_plan(
                    mode=mode,
                    source_problem_ids=source_problem_ids,
                    source_schema=source_schema,
                    theme=theme,
                    variant_index=variant_index,
                    selected_plan=plan_result,
                    rejected_candidates=rejected_candidates,
                    forbidden_reuse=forbidden_reuse,
                    rule_selection_reason=str(selection.get("selection_reason", "")),
                    planning_status="ok",
                    planning_error_reason="",
                    planning_feedback="",
                    rule_version=self.rulebook.version(),
                    selection_trace=selection.get("selection_trace", []),
                    validation_trace=validation_trace,
                    candidate_attempts=candidate_attempts,
                )
            rejected_candidates.append(plan_result["summary"])

        planning_feedback = (
            f"已尝试 {len(candidate_attempts)} 条候选规则，均未通过规划校验。"
            if candidate_attempts
            else str(selection.get("feedback", "没有可尝试的候选规则。"))
        )
        applied_rule = str(candidate_attempts[0].get("rule_id", "")) if candidate_attempts else ""
        planning_error_reason = (
            str(rejected_candidates[0].get("reason", ""))
            if rejected_candidates
            else str(selection.get("error_reason", "没有规则通过资格与排序阶段。"))
        )
        return self._finalize_plan(
            mode=mode,
            source_problem_ids=source_problem_ids,
            source_schema=source_schema,
            theme=theme,
            variant_index=variant_index,
            selected_plan=None,
            rejected_candidates=rejected_candidates,
            forbidden_reuse=forbidden_reuse,
            rule_selection_reason=str(selection.get("selection_reason", "")),
            planning_status="difference_insufficient",
            planning_error_reason=planning_error_reason,
            planning_feedback=planning_feedback,
            applied_rule=applied_rule,
            rule_version=self.rulebook.version(),
            selection_trace=selection.get("selection_trace", []),
            validation_trace=validation_trace,
            candidate_attempts=candidate_attempts,
        )

    def _select_rule_candidates(
        self,
        *,
        mode: str,
        rules: list[dict[str, Any]],
        schema_context: dict[str, Any],
        original_refs: list[dict[str, Any]],
        revision_context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        selection_results: list[RuleSelectionResult] = []
        for rule in rules:
            handler = get_rule_handler(rule)
            result = handler.check_eligibility(
                client=self.client,
                mode=mode,
                rule=rule,
                schema_context=schema_context,
                original_refs=original_refs,
                global_constraints=self.rulebook.global_constraints(),
                global_redlines=self.rulebook.global_redlines(),
            )
            selection_results.append(result)

        eligible_results = [result for result in selection_results if result.accepted]
        selection_trace = _serialize_selection_trace(selection_results)
        validation_trace = _serialize_events(selection_result_to_event(result) for result in selection_results)
        if not eligible_results:
            return {
                "accepted": False,
                "selection_reason": "所有启用规则都被资格校验拒绝。",
                "planning_status": "difference_insufficient",
                "error_reason": "没有规则通过资格校验。",
                "feedback": "请更换种子题，或调整规则集合。",
                "selection_trace": selection_trace,
                "validation_trace": validation_trace,
            }

        ranked_results = sorted(eligible_results, key=lambda item: item.score, reverse=True)
        selection_reason = (
            "；".join(
                f"{item.rule_id}:{item.selection_reason}"
                for item in ranked_results[: min(3, len(ranked_results))]
            )
            if len(ranked_results) == 1
            else ""
        )
        if len(ranked_results) > 1:
            payload = self.client.chat_json(
                system_prompt=build_rule_selection_system_prompt(),
                user_prompt=build_rule_selection_user_prompt(
                    mode=mode,
                    available_rules=[
                        rule
                        for rule in rules
                        if any(normalize_rule_id(rule.get("id", "")) == result.rule_id for result in ranked_results)
                    ],
                    schema_context=schema_context,
                    original_problem_references=original_refs,
                    global_constraints=self.rulebook.global_constraints(),
                    global_redlines=self.rulebook.global_redlines(),
                    revision_context=revision_context,
                ),
                temperature=0.05,
            )
            status = str(payload.get("status", "difference_insufficient"))
            if status != "ok":
                return {
                    "accepted": False,
                    "selection_reason": _summarize_rule_selection(payload),
                    "planning_status": status,
                    "error_reason": str(payload.get("error_reason", "") or payload.get("feedback", "")),
                    "feedback": str(payload.get("feedback", "")),
                    "selection_trace": selection_trace,
                    "validation_trace": validation_trace,
                }
            ranked_rule_ids = _extract_ranked_rule_ids(payload, ranked_results)
            ranked_results = _reorder_selection_results(ranked_results, ranked_rule_ids)
            selection_reason = _summarize_rule_selection(payload) or selection_reason

        top_results = ranked_results[: self.MAX_RULE_ATTEMPTS]
        result_by_id = {result.rule_id: result for result in top_results}
        ranked_rules = []
        for rule in rules:
            rule_id = normalize_rule_id(rule.get("id", ""))
            if rule_id in result_by_id:
                ranked_rules.append({"rule": dict(rule), "selection": result_by_id[rule_id]})
        ranked_rules.sort(
            key=lambda item: next(
                index for index, result in enumerate(top_results) if result.rule_id == item["selection"].rule_id
            )
        )
        selection_trace = _mark_selection_trace(selection_trace, top_results)
        return {
            "accepted": True,
            "ranked_rules": ranked_rules,
            "selection_reason": selection_reason or f"按资格分与排序结果优先尝试 {top_results[0].rule_id}。",
            "selection_trace": selection_trace,
            "validation_trace": validation_trace,
        }

    def _generate_candidate(
        self,
        *,
        mode: str,
        rule: dict[str, Any],
        selection_result: RuleSelectionResult,
        theme_payload: dict[str, Any],
        schema_context: dict[str, Any],
        original_refs: list[dict[str, Any]],
        source_schema: dict[str, Any],
        source_problem_ids: list[str],
        revision_context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        payload = self.client.chat_json(
            system_prompt=build_planner_system_prompt(),
            user_prompt=build_planner_user_prompt(
                mode=mode,
                rule=rule,
                theme=theme_payload,
                schema_context=schema_context,
                original_problem_references=original_refs,
                global_constraints=self.rulebook.global_constraints(),
                global_redlines=self.rulebook.global_redlines(),
                revision_context=revision_context,
            ),
            temperature=0.15,
        )
        accepted, normalized, rejection_reason, validation_trace, reason_code = self._validate_candidate(
            mode=mode,
            rule=rule,
            payload=payload,
            source_schema=source_schema,
            source_problem_ids=source_problem_ids,
            theme_payload=theme_payload,
        )
        summary = {
            "rule_id": rule.get("id", ""),
            "handler": rule.get("handler", rule.get("id", "")),
            "status": str(payload.get("status", "difference_insufficient")),
            "reason_code": reason_code or ("planner_rejected" if str(payload.get("status", "ok")) != "ok" else "plan_validation_failed"),
            "reason": rejection_reason or str(payload.get("error_reason", "") or payload.get("feedback", "")),
        }
        attempt = {
            "rule_id": rule.get("id", ""),
            "handler": rule.get("handler", rule.get("id", "")),
            "score": selection_result.score,
            "accepted": accepted,
            "risk_tags": list(selection_result.risk_tags),
            "status": summary["status"],
            "reason_code": summary["reason_code"],
            "reason": summary["reason"],
        }
        if accepted:
            normalized["summary"] = summary
            return {
                "accepted": True,
                **normalized,
                "validation_trace": validation_trace,
                "attempt": attempt,
            }
        return {
            "accepted": False,
            "summary": summary,
            "validation_trace": validation_trace,
            "attempt": attempt,
        }

    def _validate_candidate(
        self,
        *,
        mode: str,
        rule: dict[str, Any],
        payload: dict[str, Any],
        source_schema: dict[str, Any],
        source_problem_ids: list[str],
        theme_payload: dict[str, Any],
    ) -> tuple[bool, dict[str, Any], str, list[dict[str, Any]], str]:
        trace: list[AuditTraceEvent] = []
        status = str(payload.get("status", "difference_insufficient"))
        if status != "ok":
            trace.append(
                AuditTraceEvent(
                    stage="plan_validation",
                    rule_id=str(rule.get("id", "")),
                    outcome="fail",
                    reason_code="planner_rejected",
                    message=str(payload.get("error_reason", "") or payload.get("feedback", "")),
                    details={"planner_status": status},
                )
            )
            return (
                False,
                {},
                str(payload.get("error_reason", "") or payload.get("feedback", "")),
                _serialize_events(trace),
                "planner_rejected",
            )

        unexpected_fields = _find_unexpected_new_schema_fields(payload.get("new_schema", {}))
        if unexpected_fields:
            trace.append(
                AuditTraceEvent(
                    stage="plan_validation",
                    rule_id=str(rule.get("id", "")),
                    outcome="fail",
                    reason_code="unexpected_schema_fields",
                    message="new_schema 包含额外字段。",
                    details={"unexpected_fields": unexpected_fields},
                )
            )
            return (
                False,
                {},
                "new_schema 只能包含约定字段，检测到额外字段：" + ", ".join(unexpected_fields) + "。",
                _serialize_events(trace),
                "unexpected_schema_fields",
            )

        new_schema = _normalize_new_schema(payload.get("new_schema", {}), theme_payload)
        if not new_schema:
            trace.append(
                AuditTraceEvent(
                    stage="plan_validation",
                    rule_id=str(rule.get("id", "")),
                    outcome="fail",
                    reason_code="schema_incomplete",
                    message="new_schema 缺失或结构不完整。",
                )
            )
            return False, {}, "new_schema 缺失或结构不完整。", _serialize_events(trace), "schema_incomplete"

        distance = compute_schema_distance(source_schema, new_schema, embedding_client=self.client)
        changed_axes = compute_changed_axes(
            source_schema,
            new_schema,
            embedding_client=self.client,
            distance=distance,
        )
        declared_axes = {str(item) for item in payload.get("difference_plan", {}).get("changed_axes", []) if str(item).strip()}
        if declared_axes and declared_axes != set(changed_axes):
            trace.append(
                AuditTraceEvent(
                    stage="plan_validation",
                    rule_id=str(rule.get("id", "")),
                    outcome="fail",
                    reason_code="declared_axes_mismatch",
                    message="difference_plan.changed_axes 与实际变化轴不一致。",
                    details={"declared_axes": sorted(declared_axes), "realized_axes": list(changed_axes)},
                )
            )
            return (
                False,
                {},
                "difference_plan.changed_axes 与 new_schema 的真实变化不一致。",
                _serialize_events(trace),
                "declared_axes_mismatch",
            )

        must_change = set(rule.get("required_axis_changes", {}).get("must_change", []))
        if not must_change.issubset(set(changed_axes)):
            trace.append(
                AuditTraceEvent(
                    stage="plan_validation",
                    rule_id=str(rule.get("id", "")),
                    outcome="fail",
                    reason_code="required_axes_missing",
                    message="规则要求的核心变化轴未完整落地。",
                    details={"required_axes": sorted(must_change), "realized_axes": list(changed_axes)},
                )
            )
            return (
                False,
                {},
                f"规则要求的核心变化轴未完整落地，当前仅有：{', '.join(changed_axes) or '无'}。",
                _serialize_events(trace),
                "required_axes_missing",
            )

        within_band = self.MIN_DISTANCE <= distance["total"] < self.MAX_DISTANCE
        if not within_band or len(changed_axes) < 2:
            trace.append(
                AuditTraceEvent(
                    stage="plan_validation",
                    rule_id=str(rule.get("id", "")),
                    outcome="fail",
                    reason_code="distance_gate_failed",
                    message="规划结果未达到差异度或变化轴硬门槛。",
                    details={"distance": distance, "changed_axes": list(changed_axes)},
                )
            )
            return (
                False,
                {},
                "规划结果未达到硬门槛，"
                f"预测距离={distance['total']:.4f}，落地轴={', '.join(changed_axes) or '无'}。",
                _serialize_events(trace),
                "distance_gate_failed",
            )

        handler = get_rule_handler(rule)
        # 通用门槛通过后，再把规划结果交给规则专属 validate_plan 做语义合同校验。
        outcome = handler.validate_plan(
            client=self.client,
            mode=mode,
            rule=rule,
            payload=payload,
            source_schema=source_schema,
            candidate_schema=new_schema,
            changed_axes=changed_axes,
            global_constraints=self.rulebook.global_constraints(),
        )
        trace.extend(outcome.events)
        if not outcome.accepted:
            return (
                False,
                {},
                "；".join(outcome.errors),
                _serialize_events(trace),
                outcome.reason_code or "rule_plan_validation_failed",
            )

        plan_problem_id = new_schema.get("problem_id") or "__".join(source_problem_ids)
        difficulty = new_schema.get("difficulty") or _infer_difficulty(new_schema)
        normalized = {
            "problem_id": plan_problem_id,
            "source_problem_ids": list(source_problem_ids),
            "objective": copy.deepcopy(new_schema.get("objective", {})),
            "difficulty": difficulty,
            "input_summary": _summarize_input_structure(new_schema.get("input_structure", {})),
            "constraint_summary": _summarize_constraints(new_schema.get("core_constraints", {}).get("constraints", [])),
            "invariant_summary": _summarize_invariants(new_schema.get("invariant", {}).get("invariants", [])),
            "new_schema": NewSchema(**new_schema),
            "distance": distance,
            "changed_axes": changed_axes,
            "difference_rationale": str(payload.get("difference_plan", {}).get("rationale", "")),
            "difference_summary": str(payload.get("difference_plan", {}).get("summary", "")),
            "algorithmic_delta_claim": _normalize_algorithmic_delta(payload.get("algorithmic_delta_claim", {})),
            "anti_shallow_rationale": str(payload.get("anti_shallow_rationale", "")),
            "applied_rule": str(rule.get("id", "")),
            "shared_core_summary": str(payload.get("shared_core_summary", "")),
            "shared_core_anchors": {
                "shared_state": str(payload.get("shared_core_anchors", {}).get("shared_state", "")),
                "shared_transition": str(payload.get("shared_core_anchors", {}).get("shared_transition", "")),
                "shared_decision_basis": str(payload.get("shared_core_anchors", {}).get("shared_decision_basis", "")),
            },
            "seed_contributions": {
                "seed_a": str(payload.get("seed_a_indispensable_obligation", "")),
                "seed_b": str(payload.get("seed_b_indispensable_obligation", "")),
            },
            "fusion_ablation": {
                "without_seed_a": str(payload.get("fusion_ablation", {}).get("without_seed_a", "")),
                "without_seed_b": str(payload.get("fusion_ablation", {}).get("without_seed_b", "")),
            },
            "applied_helpers": _normalize_applied_helpers(payload.get("applied_helpers", [])),
            "rule_snapshot": copy.deepcopy(rule),
        }
        return True, normalized, "", _serialize_events(trace), ""

    def _finalize_plan(
        self,
        *,
        mode: str,
        source_problem_ids: list[str],
        source_schema: dict[str, Any],
        theme: Theme,
        variant_index: int,
        selected_plan: dict[str, Any] | None,
        rejected_candidates: list[dict[str, Any]],
        forbidden_reuse: list[str],
        rule_selection_reason: str,
        planning_status: str,
        planning_error_reason: str,
        planning_feedback: str,
        applied_rule: str = "",
        rule_version: str = "",
        selection_trace: list[dict[str, Any]] | None = None,
        validation_trace: list[dict[str, Any]] | None = None,
        candidate_attempts: list[dict[str, Any]] | None = None,
    ) -> VariantPlan:
        if selected_plan is None:
            fallback_schema = NewSchema(
                problem_id="__".join(source_problem_ids),
                source=str(source_schema.get("source", "")),
                input_structure=copy.deepcopy(source_schema.get("input_structure", {})),
                core_constraints=copy.deepcopy(source_schema.get("core_constraints", {"constraints": []})),
                objective=copy.deepcopy(source_schema.get("objective", {})),
                invariant=copy.deepcopy(source_schema.get("invariant", {"invariants": []})),
                theme=self._theme_payload(theme),
                difficulty=_infer_difficulty(source_schema),
            )
            difference_plan = DifferencePlan(
                target_distance_band={"min": self.MIN_DISTANCE, "max": self.MAX_DISTANCE},
                changed_axes=[],
                same_family_allowed=True,
                forbidden_reuse=forbidden_reuse,
                rationale=planning_error_reason or "规则规划失败，已显式放弃生成。",
                summary="规则规划失败" if not applied_rule else "选中的规则未能稳定落地",
                mode=mode,
            )
            return VariantPlan(
                problem_id="__".join(source_problem_ids),
                variant_index=variant_index,
                seed=self.seed + variant_index,
                mode=mode,
                theme=theme,
                source_problem_ids=source_problem_ids,
                objective=copy.deepcopy(source_schema.get("objective", {})),
                difficulty=_infer_difficulty(source_schema),
                rule_selection_reason=rule_selection_reason,
                input_summary=_summarize_input_structure(source_schema.get("input_structure", {})),
                constraint_summary=_summarize_constraints(source_schema.get("core_constraints", {}).get("constraints", [])),
                invariant_summary=_summarize_invariants(source_schema.get("invariant", {}).get("invariants", [])),
                difference_plan=difference_plan,
                new_schema_snapshot=fallback_schema,
                predicted_schema_distance=0.0,
                distance_breakdown={
                    "distance_version": "v2",
                    "backend": "embedding",
                    "total": 0.0,
                    "axis_scores": {"I": 0.0, "C": 0.0, "O": 0.0, "V": 0.0},
                    "components": {
                        "input_tree_distance": 0.0,
                        "constraint_match_distance": 0.0,
                        "objective_type_distance": 0.0,
                        "objective_text_distance": 0.0,
                        "invariant_match_distance": 0.0,
                    },
                },
                changed_axes_realized=[],
                applied_rule=applied_rule,
                rejected_candidates=rejected_candidates,
                algorithmic_delta_claim={},
                anti_shallow_rationale="",
                planning_status=planning_status,
                planning_error_reason=planning_error_reason,
                planning_feedback=planning_feedback,
                rule_version=rule_version,
                selection_trace=list(selection_trace or []),
                validation_trace=list(validation_trace or []),
                candidate_attempts=list(candidate_attempts or []),
                applied_helpers=[],
                rule_snapshot={},
            )

        selected = selected_plan
        difference_plan = DifferencePlan(
            target_distance_band={"min": self.MIN_DISTANCE, "max": self.MAX_DISTANCE},
            changed_axes=selected["changed_axes"],
            same_family_allowed=True,
            forbidden_reuse=forbidden_reuse,
            rationale=selected["difference_rationale"] or selected["algorithmic_delta_claim"].get("why_direct_reuse_fails", ""),
            summary=selected["difference_summary"],
            mode=mode,
        )
        return VariantPlan(
            problem_id=selected["problem_id"],
            variant_index=variant_index,
            seed=self.seed + variant_index,
            mode=mode,
            theme=theme,
            source_problem_ids=source_problem_ids,
            objective=selected["objective"],
            difficulty=selected["difficulty"],
            rule_selection_reason=rule_selection_reason,
            input_summary=selected["input_summary"],
            constraint_summary=selected["constraint_summary"],
            invariant_summary=selected["invariant_summary"],
            difference_plan=difference_plan,
            new_schema_snapshot=selected["new_schema"],
            predicted_schema_distance=selected["distance"]["total"],
            distance_breakdown=selected["distance"],
            changed_axes_realized=selected["changed_axes"],
            applied_rule=selected["applied_rule"],
            rejected_candidates=rejected_candidates,
            algorithmic_delta_claim=selected["algorithmic_delta_claim"],
            anti_shallow_rationale=selected.get("anti_shallow_rationale", ""),
            shared_core_summary=selected["shared_core_summary"],
            shared_core_anchors=selected["shared_core_anchors"],
            seed_contributions=selected["seed_contributions"],
            fusion_ablation=selected["fusion_ablation"],
            applied_helpers=selected["applied_helpers"],
            rule_version=rule_version,
            selection_trace=list(selection_trace or []),
            validation_trace=list(validation_trace or []),
            candidate_attempts=list(candidate_attempts or []),
            rule_snapshot=copy.deepcopy(selected.get("rule_snapshot", {})),
        )

    def _select_theme(self, rng: random.Random, theme_id: str | None) -> Theme:
        if theme_id:
            for theme in THEMES:
                if theme.theme_id == theme_id:
                    return theme
            raise ValueError(f"Unknown theme_id: {theme_id}")
        return rng.choice(THEMES)

    def _theme_payload(self, theme: Theme) -> dict[str, Any]:
        return {
            "id": theme.theme_id,
            "name": theme.name,
            "tone": theme.tone,
            "keywords": list(theme.keywords),
            "mapping_hint": theme.mapping_hint,
        }


def _canonical_mode(mode: str) -> str:
    return normalize_mode_name(mode)


def _normalize_new_schema(payload: dict[str, Any], theme_payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    if not all(key in payload for key in REQUIRED_NEW_SCHEMA_FIELDS):
        return {}
    return {
        "problem_id": str(payload.get("problem_id", "")).strip(),
        "source": str(payload.get("source", "")).strip(),
        "input_structure": copy.deepcopy(payload.get("input_structure", {})),
        "core_constraints": copy.deepcopy(payload.get("core_constraints", {"constraints": []})),
        "objective": copy.deepcopy(payload.get("objective", {})),
        "invariant": copy.deepcopy(payload.get("invariant", {"invariants": []})),
        "theme": copy.deepcopy(payload.get("theme", theme_payload)) or copy.deepcopy(theme_payload),
        "difficulty": str(payload.get("difficulty", "")).strip() or _infer_difficulty(payload),
    }


def _find_unexpected_new_schema_fields(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    return sorted(str(field) for field in payload if str(field) not in ALLOWED_NEW_SCHEMA_FIELDS)


def _normalize_algorithmic_delta(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "seed_solver_core": str(payload.get("seed_solver_core", "")),
        "reusable_subroutines": str(payload.get("reusable_subroutines", "")),
        "new_solver_core": str(payload.get("new_solver_core", "")),
        "new_proof_obligation": str(payload.get("new_proof_obligation", "")),
        "why_direct_reuse_fails": str(payload.get("why_direct_reuse_fails", "")),
    }


def _normalize_applied_helpers(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        helper_id = str(item.get("id", "")).strip()
        if not helper_id:
            continue
        normalized.append(
            {
                "id": helper_id,
                "selection_reason": str(item.get("selection_reason", "")).strip(),
                "affected_axes": [str(axis).strip() for axis in item.get("affected_axes", []) if str(axis).strip()],
                "schema_changes": [str(change).strip() for change in item.get("schema_changes", []) if str(change).strip()],
                "innovation_reason": str(item.get("innovation_reason", "")).strip(),
                "difficulty_reason": str(item.get("difficulty_reason", "")).strip(),
            }
        )
    return normalized


def _summarize_rule_selection(payload: dict[str, Any]) -> str:
    parts = [
        str(payload.get("selection_reason", "")).strip(),
        (
            f"创新度判断：{str(payload.get('innovation_reason', '')).strip()}"
            if str(payload.get("innovation_reason", "")).strip()
            else ""
        ),
        (
            f"难度判断：{str(payload.get('difficulty_reason', '')).strip()}"
            if str(payload.get("difficulty_reason", "")).strip()
            else ""
        ),
        (
            f"风险判断：{str(payload.get('risk_reason', '')).strip()}"
            if str(payload.get("risk_reason", "")).strip()
            else ""
        ),
    ]
    return "；".join(item for item in parts if item)


def _extract_ranked_rule_ids(payload: dict[str, Any], ranked_results: list[RuleSelectionResult]) -> list[str]:
    ranked_rule_ids = [
        normalize_rule_id(item)
        for item in payload.get("ranked_rule_ids", [])
        if normalize_rule_id(item)
    ]
    if not ranked_rule_ids:
        selected_rule_id = normalize_rule_id(payload.get("selected_rule_id", ""))
        if selected_rule_id:
            ranked_rule_ids.append(selected_rule_id)
    if not ranked_rule_ids:
        return [result.rule_id for result in ranked_results]
    known_ids = {result.rule_id for result in ranked_results}
    filtered_ids = [rule_id for rule_id in ranked_rule_ids if rule_id in known_ids]
    remainder = [result.rule_id for result in ranked_results if result.rule_id not in filtered_ids]
    return filtered_ids + remainder


def _reorder_selection_results(
    ranked_results: list[RuleSelectionResult],
    ranked_rule_ids: list[str],
) -> list[RuleSelectionResult]:
    position = {rule_id: index for index, rule_id in enumerate(ranked_rule_ids)}
    return sorted(
        ranked_results,
        key=lambda item: (position.get(item.rule_id, len(ranked_results)), -item.score),
    )


def _serialize_selection_trace(results: list[RuleSelectionResult]) -> list[dict[str, Any]]:
    return [dataclass_to_dict(result) for result in results]


def _mark_selection_trace(selection_trace: list[dict[str, Any]], top_results: list[RuleSelectionResult]) -> list[dict[str, Any]]:
    selected_order = {result.rule_id: index + 1 for index, result in enumerate(top_results)}
    marked: list[dict[str, Any]] = []
    for item in selection_trace:
        enriched = dict(item)
        rule_id = normalize_rule_id(enriched.get("rule_id", ""))
        if rule_id in selected_order:
            enriched["selected_for_attempt"] = True
            enriched["attempt_rank"] = selected_order[rule_id]
        else:
            enriched["selected_for_attempt"] = False
        marked.append(enriched)
    return marked


def _serialize_events(events: Any) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []
    for event in events:
        serialized.append(dataclass_to_dict(event))
    return serialized


def _build_problem_reference(problem: dict[str, Any] | None) -> dict[str, Any]:
    if not problem:
        return {}
    return {
        "problem_id": problem.get("problem_id", ""),
        "title": problem.get("title", ""),
        "description_summary": _truncate_text(problem.get("description", ""), 420),
        "input_summary": _truncate_text(problem.get("input", ""), 200),
        "output_summary": _truncate_text(problem.get("output", ""), 200),
        "constraints_summary": _truncate_text(problem.get("constraints", ""), 200),
        "tags": list(problem.get("tags", [])),
    }


def _truncate_text(text: str, limit: int) -> str:
    cleaned = " ".join(str(text).split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def _merge_seed_schemas(seed_a_schema: dict[str, Any], seed_b_schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "problem_id": f"{seed_a_schema.get('problem_id', 'seed_a')}__{seed_b_schema.get('problem_id', 'seed_b')}",
        "source": f"{seed_a_schema.get('source', '')}+{seed_b_schema.get('source', '')}",
        "input_structure": copy.deepcopy(seed_a_schema.get("input_structure", {})),
        "core_constraints": {"constraints": list(seed_a_schema.get("core_constraints", {}).get("constraints", []))},
        "objective": copy.deepcopy(seed_a_schema.get("objective", {})),
        "invariant": {"invariants": list(seed_a_schema.get("invariant", {}).get("invariants", []))},
    }


def _merge_forbidden_reuse(seed_a_problem: dict[str, Any], seed_b_problem: dict[str, Any]) -> list[str]:
    merged: list[str] = []
    for problem in (seed_a_problem, seed_b_problem):
        for item in build_forbidden_reuse_list(problem):
            if item not in merged:
                merged.append(item)
    return merged


def _summarize_input_structure(data: dict[str, Any]) -> str:
    input_type = data.get("type", "unknown")
    length = data.get("length", {})
    value_range = data.get("value_range", {})
    parts = [f"类型={input_type}"]
    if length:
        parts.append(f"长度范围={length.get('min', '?')}..{length.get('max', '?')}")
    if value_range:
        parts.append(f"值范围={value_range.get('min', '?')}..{value_range.get('max', '?')}")
    properties = data.get("properties", {})
    if properties:
        parts.append("属性=" + ", ".join(f"{key}={value}" for key, value in properties.items()))
    return "；".join(parts)


def _summarize_constraints(constraints: list[dict[str, Any]]) -> list[str]:
    return [str(item.get("description", "")) for item in constraints if str(item.get("description", "")).strip()]


def _summarize_invariants(invariants: list[dict[str, Any]]) -> list[str]:
    return [str(item.get("description", "")) for item in invariants if str(item.get("description", "")).strip()]


def _infer_difficulty(schema: dict[str, Any]) -> str:
    invariants = schema.get("invariant", {}).get("invariants", [])
    constraints = schema.get("core_constraints", {}).get("constraints", [])
    score = len(invariants) + len(constraints)
    if score <= 2:
        return "Easy"
    if score <= 4:
        return "Medium"
    return "Hard"
