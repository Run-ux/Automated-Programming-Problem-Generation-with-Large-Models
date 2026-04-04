from __future__ import annotations

import copy
from typing import Any

from models import AuditTraceEvent, GeneratedProblem, RuleSelectionResult, RuleValidationOutcome, VariantPlan
from prompt_builder import build_eligibility_system_prompt, build_eligibility_user_prompt
from qwen_client import QwenClient
from rulebook import normalize_rule_id


def get_rule_handler(rule: dict[str, Any]) -> "RuleHandler":
    handler_id = normalize_rule_id(rule.get("handler", "") or rule.get("id", ""))
    handler_cls = _RULE_HANDLER_REGISTRY.get(handler_id, GenericRuleHandler)
    return handler_cls(rule_id=normalize_rule_id(rule.get("id", "")), handler_name=handler_id)


class RuleHandler:
    def __init__(self, *, rule_id: str, handler_name: str) -> None:
        self.rule_id = normalize_rule_id(rule_id)
        self.handler_name = normalize_rule_id(handler_name or rule_id)

    def check_eligibility(
        self,
        *,
        client: QwenClient,
        mode: str,
        rule: dict[str, Any],
        schema_context: dict[str, Any],
        original_refs: list[dict[str, Any]],
        global_constraints: dict[str, Any],
        global_redlines: list[str],
    ) -> RuleSelectionResult:
        payload = client.chat_json(
            system_prompt=build_eligibility_system_prompt(),
            user_prompt=build_eligibility_user_prompt(
                mode=mode,
                review_role=self.eligibility_role(mode=mode, rule=rule),
                rule=rule,
                schema_context=schema_context,
                original_problem_references=original_refs,
                global_constraints=global_constraints,
                global_redlines=global_redlines,
            ),
            temperature=0.05,
        )
        status = str(payload.get("status", "ineligible")).strip().lower()
        accepted = status == "eligible"
        reason_code = str(payload.get("reason_code", "")).strip() or ("eligible" if accepted else status or "ineligible")
        message = str(payload.get("selection_reason", "")).strip() or str(payload.get("feedback", "")).strip()
        evidence = str(payload.get("evidence", "")).strip()
        risk_tags = [str(item).strip() for item in payload.get("risk_tags", []) if str(item).strip()]
        score = _clamp_score(payload.get("score", 0.0))
        if status == "schema_insufficient":
            accepted = False
        if accepted:
            score += 0.03 * len(rule.get("required_axis_changes", {}).get("must_change", []))
            score += 0.01 * len(rule.get("audit_tags", []))
        return RuleSelectionResult(
            rule_id=self.rule_id,
            handler=self.handler_name,
            accepted=accepted,
            score=round(score, 4),
            reason_code=reason_code,
            selection_reason=message or "资格审查未返回明确理由。",
            risk_tags=risk_tags,
            details={
                "mode": mode,
                "family": str(rule.get("family", "")).strip(),
                "audit_tags": list(rule.get("audit_tags", [])),
                "review_role": self.eligibility_role(mode=mode, rule=rule),
                "llm_status": status,
                "evidence": evidence,
                "feedback": str(payload.get("feedback", "")).strip(),
            },
        )

    def eligibility_role(self, *, mode: str, rule: dict[str, Any]) -> str:
        return "你扮演一名保守的规则资格审查官，只在证据充分时才放行。"

    def validate_plan(
        self,
        *,
        mode: str,
        rule: dict[str, Any],
        payload: dict[str, Any],
        source_schema: dict[str, Any],
        candidate_schema: dict[str, Any],
        changed_axes: list[str],
        global_constraints: dict[str, Any],
    ) -> RuleValidationOutcome:
        errors: list[str] = []
        events: list[AuditTraceEvent] = []

        required_fields = list(rule.get("planner_output_contract", {}).get("required_fields", []))
        missing_fields = [field for field in required_fields if not _payload_has_value(payload, field)]
        if missing_fields:
            errors.append("规划结果缺少规则要求字段：" + ", ".join(missing_fields) + "。")
            events.append(
                _event(
                    stage="plan_validation",
                    rule_id=self.rule_id,
                    outcome="fail",
                    reason_code="missing_required_fields",
                    message="规划结果未满足规则输出合同。",
                    details={"missing_fields": missing_fields},
                )
            )

        auxiliary_moves = [str(item).strip() for item in payload.get("auxiliary_moves", []) if str(item).strip()]
        if auxiliary_moves and not global_constraints.get("allow_helper_moves", True):
            errors.append("全局配置禁止 auxiliary_moves，但规划结果仍输出了辅助动作。")
            events.append(
                _event(
                    stage="plan_validation",
                    rule_id=self.rule_id,
                    outcome="fail",
                    reason_code="helper_moves_disabled",
                    message="辅助动作违反全局配置。",
                    details={"auxiliary_moves": auxiliary_moves},
                )
            )

        allowed_helpers = {str(item).strip() for item in rule.get("allowed_helpers", []) if str(item).strip()}
        forbidden_helpers = {str(item).strip() for item in rule.get("forbidden_helpers", []) if str(item).strip()}
        if allowed_helpers:
            invalid_helpers = sorted(move for move in auxiliary_moves if move not in allowed_helpers)
            if invalid_helpers:
                errors.append("规划结果使用了规则未允许的 auxiliary_moves：" + ", ".join(invalid_helpers) + "。")
                events.append(
                    _event(
                        stage="plan_validation",
                        rule_id=self.rule_id,
                        outcome="fail",
                        reason_code="helper_not_allowed",
                        message="辅助动作不在规则白名单中。",
                        details={"invalid_helpers": invalid_helpers},
                    )
                )
        forbidden_hits = sorted(move for move in auxiliary_moves if move in forbidden_helpers)
        if forbidden_hits:
            errors.append("规划结果命中了规则禁止的 auxiliary_moves：" + ", ".join(forbidden_hits) + "。")
            events.append(
                _event(
                    stage="plan_validation",
                    rule_id=self.rule_id,
                    outcome="fail",
                    reason_code="helper_forbidden",
                    message="辅助动作命中规则黑名单。",
                    details={"forbidden_helpers": forbidden_hits},
                )
            )

        semantic_checks = [
            (
                "new_output_object_missing",
                "规划结果没有形成新的输出对象或新的输出责任。",
                _has_new_output_object(source_schema, candidate_schema),
            ),
            (
                "main_goal_unchanged",
                "规划结果没有改变主求解目标。",
                _has_main_goal_change(source_schema, candidate_schema, payload),
            ),
            (
                "main_state_unchanged",
                "规划结果没有改变主状态演化。",
                _has_main_state_change(source_schema, candidate_schema, changed_axes),
            ),
            (
                "reuse_risk_high",
                "规划结果没有提供足够清晰的原解复用阻断理由。",
                _has_reuse_barrier(payload),
            ),
        ]
        for reason_code, message, passed in semantic_checks:
            outcome = "pass" if passed else "fail"
            events.append(
                _event(
                    stage="plan_validation",
                    rule_id=self.rule_id,
                    outcome=outcome,
                    reason_code=reason_code,
                    message=message if not passed else "语义硬判据通过。",
                )
            )
            if not passed:
                errors.append(message)

        specific = self._validate_specific_plan(
            mode=mode,
            rule=rule,
            payload=payload,
            source_schema=source_schema,
            candidate_schema=candidate_schema,
            changed_axes=changed_axes,
        )
        errors.extend(specific.errors)
        events.extend(specific.events)
        return RuleValidationOutcome(
            accepted=not errors,
            errors=errors,
            events=events,
            reason_code=specific.reason_code,
            message=specific.message,
        )

    def validate_problem(
        self,
        *,
        problem: GeneratedProblem,
        plan: VariantPlan,
    ) -> RuleValidationOutcome:
        return self._validate_specific_problem(problem=problem, plan=plan)

    def _check_specific_eligibility(
        self,
        *,
        mode: str,
        rule: dict[str, Any],
        schema_context: dict[str, Any],
        original_refs: list[dict[str, Any]],
        global_constraints: dict[str, Any],
        global_redlines: list[str],
    ) -> tuple[bool, str, str, list[str], float]:
        return True, "eligible", "规则满足基础资格条件。", [], 0.5

    def _validate_specific_plan(
        self,
        *,
        mode: str,
        rule: dict[str, Any],
        payload: dict[str, Any],
        source_schema: dict[str, Any],
        candidate_schema: dict[str, Any],
        changed_axes: list[str],
    ) -> RuleValidationOutcome:
        return RuleValidationOutcome(accepted=True)

    def _validate_specific_problem(
        self,
        *,
        problem: GeneratedProblem,
        plan: VariantPlan,
    ) -> RuleValidationOutcome:
        return RuleValidationOutcome(accepted=True)


class GenericRuleHandler(RuleHandler):
    pass


class CanonicalWitnessHandler(RuleHandler):
    def eligibility_role(self, *, mode: str, rule: dict[str, Any]) -> str:
        return "你扮演一名规范解审查官，重点判断种子题是否仍有空间升级为带规范性的构造输出。"

    def _check_specific_eligibility(
        self,
        *,
        mode: str,
        rule: dict[str, Any],
        schema_context: dict[str, Any],
        original_refs: list[dict[str, Any]],
        global_constraints: dict[str, Any],
        global_redlines: list[str],
    ) -> tuple[bool, str, str, list[str], float]:
        source_schema = _primary_schema(schema_context)
        objective_text = _objective_text(source_schema)
        output_text = " ".join(str(ref.get("output_summary", "")) for ref in original_refs)
        if _text_has_any(objective_text + " " + output_text, _CONSTRUCT_TOKENS | _WITNESS_TOKENS):
            return False, "already_constructive", "种子题已经带有明显的构造或 witness 输出责任。", ["low_novelty"], 0.0
        return True, "eligible", "种子题仍有把答案升级为规范构造的空间。", ["requires_output_contract"], 0.72

    def _validate_specific_plan(
        self,
        *,
        mode: str,
        rule: dict[str, Any],
        payload: dict[str, Any],
        source_schema: dict[str, Any],
        candidate_schema: dict[str, Any],
        changed_axes: list[str],
    ) -> RuleValidationOutcome:
        combined = _schema_text(candidate_schema) + " " + str(payload.get("anti_shallow_rationale", ""))
        errors: list[str] = []
        if not _text_has_any(combined, {"规范", "canonical", "字典序", "witness", "见证"}):
            errors.append("canonical_witness 缺少规范解或规范性约束定义。")
        return _outcome_from_errors(self.rule_id, "plan_validation", "canonical_witness_missing", errors)

    def _validate_specific_problem(
        self,
        *,
        problem: GeneratedProblem,
        plan: VariantPlan,
    ) -> RuleValidationOutcome:
        combined = _problem_text(problem)
        errors: list[str] = []
        if not _text_has_any(combined, {"规范", "字典序", "canonical", "witness", "见证"}):
            errors.append("题面没有明确说明规范解、witness 或字典序规则。")
        if not _text_has_any(combined, {"输出一个", "构造", "方案"}):
            errors.append("题面没有明确要求输出一个可校验的构造方案。")
        return _outcome_from_errors(self.rule_id, "problem_validation", "canonical_witness_not_materialized", errors)


class ConstructOrObstructionHandler(RuleHandler):
    def eligibility_role(self, *, mode: str, rule: dict[str, Any]) -> str:
        return "你扮演一名冲突证书审查官，重点判断无解情形能否落成可局部检查的阻碍证据。"

    def _check_specific_eligibility(
        self,
        *,
        mode: str,
        rule: dict[str, Any],
        schema_context: dict[str, Any],
        original_refs: list[dict[str, Any]],
        global_constraints: dict[str, Any],
        global_redlines: list[str],
    ) -> tuple[bool, str, str, list[str], float]:
        source_schema = _primary_schema(schema_context)
        if _text_has_any(_objective_text(source_schema), {"count", "计数"}):
            return False, "counting_seed", "计数种子题通常不适合直接扩成 obstruction 证据输出。", ["semantic_mismatch"], 0.0
        return True, "eligible", "种子题仍可引入可局部校验的冲突证据。", ["certificate_design"], 0.69

    def _validate_specific_plan(
        self,
        *,
        mode: str,
        rule: dict[str, Any],
        payload: dict[str, Any],
        source_schema: dict[str, Any],
        candidate_schema: dict[str, Any],
        changed_axes: list[str],
    ) -> RuleValidationOutcome:
        combined = _schema_text(candidate_schema) + " " + str(payload.get("core_transformation_summary", ""))
        errors: list[str] = []
        if not _text_has_any(combined, {"证书", "certificate", "阻碍", "obstruction", "冲突", "conflict"}):
            errors.append("construct_or_obstruction 缺少可局部检查的阻碍证据定义。")
        return _outcome_from_errors(self.rule_id, "plan_validation", "obstruction_missing", errors)

    def _validate_specific_problem(
        self,
        *,
        problem: GeneratedProblem,
        plan: VariantPlan,
    ) -> RuleValidationOutcome:
        combined = _problem_text(problem)
        errors: list[str] = []
        if not _text_has_any(combined, {"无解", "证书", "阻碍", "obstruction", "冲突", "conflict"}):
            errors.append("题面没有明确失败输出或阻碍证据语义。")
        return _outcome_from_errors(self.rule_id, "problem_validation", "obstruction_not_materialized", errors)


class ExistenceToCountingHandler(RuleHandler):
    def eligibility_role(self, *, mode: str, rule: dict[str, Any]) -> str:
        return "你扮演一名计数化审查官，重点判断解空间、去重规则和有限性是否足够清晰。"

    def _check_specific_eligibility(
        self,
        *,
        mode: str,
        rule: dict[str, Any],
        schema_context: dict[str, Any],
        original_refs: list[dict[str, Any]],
        global_constraints: dict[str, Any],
        global_redlines: list[str],
    ) -> tuple[bool, str, str, list[str], float]:
        source_schema = _primary_schema(schema_context)
        if _text_has_any(_objective_text(source_schema), {"count", "计数"}):
            return False, "already_counting", "种子题本身已经是计数目标。", ["low_novelty"], 0.0
        return True, "eligible", "种子题仍可升级为对象明确的计数任务。", ["deduplication_needed"], 0.7

    def _validate_specific_plan(
        self,
        *,
        mode: str,
        rule: dict[str, Any],
        payload: dict[str, Any],
        source_schema: dict[str, Any],
        candidate_schema: dict[str, Any],
        changed_axes: list[str],
    ) -> RuleValidationOutcome:
        objective_text = _objective_text(candidate_schema)
        combined = _schema_text(candidate_schema) + " " + str(payload.get("core_transformation_summary", ""))
        errors: list[str] = []
        if not _text_has_any(objective_text, {"count", "计数", "方案数"}):
            errors.append("existence_to_counting 没有把目标改成计数。")
        if not _text_has_any(combined, {"去重", "distinct", "不同", "等价", "模", "mod", "有限"}):
            errors.append("existence_to_counting 缺少去重规则、有限性说明或取模约定。")
        return _outcome_from_errors(self.rule_id, "plan_validation", "counting_contract_missing", errors)

    def _validate_specific_problem(
        self,
        *,
        problem: GeneratedProblem,
        plan: VariantPlan,
    ) -> RuleValidationOutcome:
        combined = _problem_text(problem)
        errors: list[str] = []
        if not _text_has_any(combined, {"方案数", "个数", "count", "计数"}):
            errors.append("题面没有明确输出计数结果。")
        if not _text_has_any(combined, {"模", "mod", "不同", "distinct", "等价"}):
            errors.append("题面没有明确去重规则或取模约定。")
        return _outcome_from_errors(self.rule_id, "problem_validation", "counting_not_materialized", errors)


class MinimumGuaranteeUnderPerturbationHandler(RuleHandler):
    def eligibility_role(self, *, mode: str, rule: dict[str, Any]) -> str:
        return "你扮演一名保底优化审查官，重点判断原题语义中是否存在可被放大的原生扰动来源。"

    def _check_specific_eligibility(
        self,
        *,
        mode: str,
        rule: dict[str, Any],
        schema_context: dict[str, Any],
        original_refs: list[dict[str, Any]],
        global_constraints: dict[str, Any],
        global_redlines: list[str],
    ) -> tuple[bool, str, str, list[str], float]:
        source_schema = _primary_schema(schema_context)
        source_text = _schema_text(source_schema)
        has_variability = (
            bool(source_schema.get("input_structure", {}).get("properties"))
            or bool(source_schema.get("core_constraints", {}).get("constraints", []))
            or bool(source_schema.get("invariant", {}).get("invariants", []))
            or _text_has_any(
                source_text,
                {"顺序", "资源", "波动", "扰动", "选择", "不确定", "ordered", "resource"},
            )
        )
        if not has_variability:
            return False, "missing_variability_source", "种子题没有足够清晰的原生扰动来源。", ["semantic_mismatch"], 0.0
        return True, "eligible", "种子题存在可以放大的原生扰动来源。", ["worst_case_reasoning"], 0.68

    def _validate_specific_plan(
        self,
        *,
        mode: str,
        rule: dict[str, Any],
        payload: dict[str, Any],
        source_schema: dict[str, Any],
        candidate_schema: dict[str, Any],
        changed_axes: list[str],
    ) -> RuleValidationOutcome:
        objective_text = _objective_text(candidate_schema)
        combined = _schema_text(candidate_schema) + " " + str(payload.get("core_transformation_summary", ""))
        errors: list[str] = []
        if not _text_has_any(objective_text, {"min", "max", "最小", "最大", "保底", "guarantee"}):
            errors.append("minimum_guarantee_under_perturbation 没有把目标改成保底型优化。")
        if not _text_has_any(combined, {"最坏", "任意", "保底", "worst", "guarantee", "扰动"}):
            errors.append("minimum_guarantee_under_perturbation 缺少最坏情形或扰动模型说明。")
        return _outcome_from_errors(self.rule_id, "plan_validation", "guarantee_contract_missing", errors)

    def _validate_specific_problem(
        self,
        *,
        problem: GeneratedProblem,
        plan: VariantPlan,
    ) -> RuleValidationOutcome:
        combined = _problem_text(problem)
        errors: list[str] = []
        if not _text_has_any(combined, {"保证", "最坏", "任意", "保底", "worst", "guarantee"}):
            errors.append("题面没有明确最坏情形或保底语义。")
        return _outcome_from_errors(self.rule_id, "problem_validation", "guarantee_not_materialized", errors)


class InterlockedConstraintsHandler(RuleHandler):
    def eligibility_role(self, *, mode: str, rule: dict[str, Any]) -> str:
        return "你扮演一名共享主核融合审查官，重点判断两题是否真的共享同一个状态核，并能形成互锁约束。"

    def _check_specific_eligibility(
        self,
        *,
        mode: str,
        rule: dict[str, Any],
        schema_context: dict[str, Any],
        original_refs: list[dict[str, Any]],
        global_constraints: dict[str, Any],
        global_redlines: list[str],
    ) -> tuple[bool, str, str, list[str], float]:
        seed_a = schema_context.get("seed_a_schema", {})
        seed_b = schema_context.get("seed_b_schema", {})
        if seed_a.get("input_structure", {}).get("type") != seed_b.get("input_structure", {}).get("type"):
            return False, "shared_core_missing", "两题的输入主核类型不一致，难以形成稳定共享主核。", ["shared_core_risk"], 0.0
        return True, "eligible", "两题在输入主核上具有形成互锁约束的基础。", ["fusion_complexity"], 0.76

    def _validate_specific_plan(
        self,
        *,
        mode: str,
        rule: dict[str, Any],
        payload: dict[str, Any],
        source_schema: dict[str, Any],
        candidate_schema: dict[str, Any],
        changed_axes: list[str],
    ) -> RuleValidationOutcome:
        errors = _same_family_core_errors(payload, changed_axes, required_axes={"C", "V"})
        return _outcome_from_errors(self.rule_id, "plan_validation", "interlocked_constraints_missing", errors)

    def _validate_specific_problem(
        self,
        *,
        problem: GeneratedProblem,
        plan: VariantPlan,
    ) -> RuleValidationOutcome:
        combined = _problem_text(problem)
        errors: list[str] = []
        if not _text_has_any(combined, {"同时", "同一", "互锁", "共享", "同步", "simultaneous", "shared"}):
            errors.append("题面没有明确双义务在同一状态过程中同时起作用。")
        return _outcome_from_errors(self.rule_id, "problem_validation", "interlocked_not_materialized", errors)


class SharedCoreObjectiveUpgradeHandler(RuleHandler):
    def eligibility_role(self, *, mode: str, rule: dict[str, Any]) -> str:
        return "你扮演一名共享主核升级审查官，重点判断共享主核是否足以承担更强的新目标。"

    def _check_specific_eligibility(
        self,
        *,
        mode: str,
        rule: dict[str, Any],
        schema_context: dict[str, Any],
        original_refs: list[dict[str, Any]],
        global_constraints: dict[str, Any],
        global_redlines: list[str],
    ) -> tuple[bool, str, str, list[str], float]:
        seed_a = schema_context.get("seed_a_schema", {})
        seed_b = schema_context.get("seed_b_schema", {})
        if seed_a.get("input_structure", {}).get("type") != seed_b.get("input_structure", {}).get("type"):
            return False, "shared_core_missing", "两题的输入主核类型不一致，无法稳定抬高共享目标。", ["shared_core_risk"], 0.0
        return True, "eligible", "两题拥有可承载更强目标的共享主核。", ["objective_upgrade_risk"], 0.74

    def _validate_specific_plan(
        self,
        *,
        mode: str,
        rule: dict[str, Any],
        payload: dict[str, Any],
        source_schema: dict[str, Any],
        candidate_schema: dict[str, Any],
        changed_axes: list[str],
    ) -> RuleValidationOutcome:
        errors = _same_family_core_errors(payload, changed_axes, required_axes={"O"})
        source_objective = normalize_rule_id(source_schema.get("objective", {}).get("type", ""))
        candidate_objective = normalize_rule_id(candidate_schema.get("objective", {}).get("type", ""))
        if source_objective == candidate_objective:
            errors.append("shared_core_objective_upgrade 没有改变共享主核上的主目标。")
        return _outcome_from_errors(self.rule_id, "plan_validation", "objective_upgrade_missing", errors)

    def _validate_specific_problem(
        self,
        *,
        problem: GeneratedProblem,
        plan: VariantPlan,
    ) -> RuleValidationOutcome:
        combined = _problem_text(problem)
        errors: list[str] = []
        objective_type = str(plan.objective.get("type", "")).lower()
        if "count" in objective_type and not _text_has_any(combined, {"计数", "方案数", "count"}):
            errors.append("题面没有体现升级后的计数目标。")
        if any(token in objective_type for token in ("construct", "witness")) and not _text_has_any(
            combined, {"构造", "规范", "witness", "输出一个"}
        ):
            errors.append("题面没有体现升级后的构造目标。")
        if not _text_has_any(combined, {"共享", "同一", "同时", "shared", "simultaneous"}):
            errors.append("题面没有说明更强目标仍作用在共享主核上。")
        return _outcome_from_errors(self.rule_id, "problem_validation", "objective_upgrade_not_materialized", errors)


def selection_result_to_event(result: RuleSelectionResult) -> AuditTraceEvent:
    return _event(
        stage="eligibility",
        rule_id=result.rule_id,
        outcome="pass" if result.accepted else "fail",
        reason_code=result.reason_code,
        message=result.selection_reason,
        details={
            "handler": result.handler,
            "score": result.score,
            "risk_tags": list(result.risk_tags),
            **copy.deepcopy(result.details),
        },
    )


def _same_family_core_errors(payload: dict[str, Any], changed_axes: list[str], required_axes: set[str]) -> list[str]:
    errors: list[str] = []
    shared_core_summary = str(payload.get("shared_core_summary", "")).strip()
    anchors = payload.get("shared_core_anchors", {})
    fusion_ablation = payload.get("fusion_ablation", {})
    if not shared_core_summary:
        errors.append("same_family 规则缺少 shared_core_summary。")
    if not all(str(anchors.get(key, "")).strip() for key in ("shared_state", "shared_transition", "shared_decision_basis")):
        errors.append("same_family 规则缺少完整的 shared_core_anchors。")
    if not str(payload.get("seed_a_indispensable_obligation", "")).strip():
        errors.append("same_family 规则缺少 seed_a 不可删贡献。")
    if not str(payload.get("seed_b_indispensable_obligation", "")).strip():
        errors.append("same_family 规则缺少 seed_b 不可删贡献。")
    if not str(payload.get("why_not_sequential_composition", "")).strip():
        errors.append("same_family 规则缺少反串联论证。")
    if not str(fusion_ablation.get("without_seed_a", "")).strip():
        errors.append("same_family 规则缺少 without_seed_a 消融论证。")
    if not str(fusion_ablation.get("without_seed_b", "")).strip():
        errors.append("same_family 规则缺少 without_seed_b 消融论证。")
    if not required_axes.issubset(set(changed_axes)):
        errors.append("same_family 规则没有落地所需的核心变化轴。")
    return errors


def _outcome_from_errors(rule_id: str, stage: str, reason_code: str, errors: list[str]) -> RuleValidationOutcome:
    if not errors:
        return RuleValidationOutcome(
            accepted=True,
            events=[
                _event(
                    stage=stage,
                    rule_id=rule_id,
                    outcome="pass",
                    reason_code="ok",
                    message="规则专属校验通过。",
                )
            ],
        )
    return RuleValidationOutcome(
        accepted=False,
        errors=errors,
        events=[
            _event(
                stage=stage,
                rule_id=rule_id,
                outcome="fail",
                reason_code=reason_code,
                message="；".join(errors),
            )
        ],
        reason_code=reason_code,
        message="；".join(errors),
    )


def _event(
    *,
    stage: str,
    rule_id: str,
    outcome: str,
    reason_code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> AuditTraceEvent:
    return AuditTraceEvent(
        stage=stage,
        rule_id=rule_id,
        outcome=outcome,
        reason_code=reason_code,
        message=message,
        details=copy.deepcopy(details or {}),
    )


def _payload_has_value(payload: dict[str, Any], field: str) -> bool:
    value = payload.get(field)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _primary_schema(schema_context: dict[str, Any]) -> dict[str, Any]:
    for key in ("seed_schema", "original_schema", "seed_a_schema"):
        if isinstance(schema_context.get(key), dict):
            return schema_context[key]
    return {}


def _objective_text(schema: dict[str, Any]) -> str:
    objective = schema.get("objective", {})
    return " ".join(str(objective.get(key, "")) for key in ("type", "description"))


def _schema_text(schema: dict[str, Any]) -> str:
    parts = [_objective_text(schema)]
    for item in schema.get("core_constraints", {}).get("constraints", []):
        parts.append(str(item.get("name", "")))
        parts.append(str(item.get("description", "")))
    for item in schema.get("invariant", {}).get("invariants", []):
        parts.append(str(item.get("name", "")))
        parts.append(str(item.get("description", "")))
    return " ".join(parts)


def _problem_text(problem: GeneratedProblem) -> str:
    return "\n".join(
        [
            problem.title,
            problem.description,
            problem.input_format,
            problem.output_format,
            "\n".join(problem.constraints),
            problem.notes,
        ]
    ).lower()


def _text_has_any(text: str, tokens: set[str]) -> bool:
    lowered = str(text).lower()
    return any(token.lower() in lowered for token in tokens)


def _clamp_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, score))


def _constraint_signatures(schema: dict[str, Any]) -> set[str]:
    return {
        str(item.get("name", "")).strip().lower() or str(item.get("description", "")).strip().lower()
        for item in schema.get("core_constraints", {}).get("constraints", [])
        if item
    }


def _invariant_signatures(schema: dict[str, Any]) -> set[str]:
    return {
        str(item.get("name", "")).strip().lower() or str(item.get("description", "")).strip().lower()
        for item in schema.get("invariant", {}).get("invariants", [])
        if item
    }


def _has_new_output_object(source_schema: dict[str, Any], candidate_schema: dict[str, Any]) -> bool:
    source_text = _objective_text(source_schema)
    candidate_text = _objective_text(candidate_schema)
    if normalize_rule_id(source_schema.get("objective", {}).get("type", "")) != normalize_rule_id(
        candidate_schema.get("objective", {}).get("type", "")
    ):
        return True
    signal_tokens = _CONSTRUCT_TOKENS | _WITNESS_TOKENS | {"计数", "count", "证书", "certificate", "保底", "guarantee"}
    return _text_has_any(candidate_text, signal_tokens - {token for token in signal_tokens if token.lower() in source_text.lower()})


def _has_main_goal_change(source_schema: dict[str, Any], candidate_schema: dict[str, Any], payload: dict[str, Any]) -> bool:
    if normalize_rule_id(source_schema.get("objective", {}).get("type", "")) != normalize_rule_id(
        candidate_schema.get("objective", {}).get("type", "")
    ):
        return True
    delta = payload.get("algorithmic_delta_claim", {})
    seed_solver_core = str(delta.get("seed_solver_core", "")).strip().lower()
    new_solver_core = str(delta.get("new_solver_core", "")).strip().lower()
    return bool(seed_solver_core and new_solver_core and seed_solver_core != new_solver_core)


def _has_main_state_change(source_schema: dict[str, Any], candidate_schema: dict[str, Any], changed_axes: list[str]) -> bool:
    if not ({"C", "V"} & set(changed_axes)):
        return False
    if _constraint_signatures(source_schema) != _constraint_signatures(candidate_schema):
        return True
    return _invariant_signatures(source_schema) != _invariant_signatures(candidate_schema)


def _has_reuse_barrier(payload: dict[str, Any]) -> bool:
    delta = payload.get("algorithmic_delta_claim", {})
    reason = str(delta.get("why_direct_reuse_fails", "")).strip()
    seed_solver_core = str(delta.get("seed_solver_core", "")).strip().lower()
    new_solver_core = str(delta.get("new_solver_core", "")).strip().lower()
    return bool(reason and seed_solver_core and new_solver_core and seed_solver_core != new_solver_core)


_CONSTRUCT_TOKENS = {"construct", "构造", "输出一个"}
_WITNESS_TOKENS = {"witness", "见证", "证据", "规范", "canonical", "字典序"}

_RULE_HANDLER_REGISTRY = {
    "canonical_witness": CanonicalWitnessHandler,
    "construct_or_obstruction": ConstructOrObstructionHandler,
    "existence_to_counting": ExistenceToCountingHandler,
    "minimum_guarantee_under_perturbation": MinimumGuaranteeUnderPerturbationHandler,
    "interlocked_constraints": InterlockedConstraintsHandler,
    "shared_core_objective_upgrade": SharedCoreObjectiveUpgradeHandler,
}
