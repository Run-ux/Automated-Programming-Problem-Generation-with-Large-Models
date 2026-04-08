from __future__ import annotations

import copy
from typing import Any

from models import AuditTraceEvent, GeneratedProblem, RuleSelectionResult, RuleValidationOutcome, VariantPlan
from prompt_builder import (
    build_eligibility_system_prompt,
    build_eligibility_user_prompt,
    build_rule_plan_validation_system_prompt,
    build_rule_plan_validation_user_prompt,
    build_rule_problem_validation_system_prompt,
    build_rule_problem_validation_user_prompt,
)
from qwen_client import QwenClient
from rulebook import normalize_rule_id
from schema_tools import dataclass_to_dict


def get_rule_handler(rule: dict[str, Any]) -> "RuleHandler":
    handler_id = normalize_rule_id(rule.get("handler", "") or rule.get("id", ""))
    handler_cls = _RULE_HANDLER_REGISTRY.get(handler_id, GenericRuleHandler)
    return handler_cls(
        rule_id=normalize_rule_id(rule.get("id", "")),
        handler_name=handler_id,
        rule=rule,
    )


class RuleHandler:
    _REVIEW_KEYS = {"status", "reason_code", "message", "errors", "evidence"}

    def __init__(self, *, rule_id: str, handler_name: str, rule: dict[str, Any] | None = None) -> None:
        self.rule_id = normalize_rule_id(rule_id)
        self.handler_name = normalize_rule_id(handler_name or rule_id)
        self.rule = copy.deepcopy(rule or {})

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

    def plan_review_role(self, *, mode: str, rule: dict[str, Any]) -> str:
        return "你扮演一名规则规划审查官，重点判断规划是否真正兑现该规则的专属语义合同。"

    def plan_review_brief(self, *, mode: str, rule: dict[str, Any]) -> str:
        return "检查规划是否把规则要求的新输出责任、失败语义与主求解义务写进实例化后的四元组。"

    def problem_review_role(self, *, plan: VariantPlan, rule: dict[str, Any]) -> str:
        return "你扮演一名题面规则审查官，重点判断题面是否兑现该规则的专属语义合同。"

    def problem_review_brief(self, *, plan: VariantPlan, rule: dict[str, Any]) -> str:
        return "检查题面是否把规则要求的新输出责任、失败语义与核心承诺清楚写出。"

    def validate_plan(
        self,
        *,
        client: QwenClient,
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

        # 先检查规则声明的输出合同，避免缺字段时把问题误判成更抽象的语义失败。
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

        expected_helpers = _normalize_rule_helpers(rule.get("helpers", []))
        applied_helpers = _normalize_applied_helpers(payload.get("applied_helpers", []))
        if expected_helpers and not global_constraints.get("allow_helper_moves", True):
            errors.append("全局配置禁止 applied_helpers，但当前规则要求 helper 全量应用。")
            events.append(
                _event(
                    stage="plan_validation",
                    rule_id=self.rule_id,
                    outcome="fail",
                    reason_code="helper_moves_disabled",
                    message="helper 应用违反全局配置。",
                    details={"expected_helper_ids": [helper["id"] for helper in expected_helpers]},
                )
            )
        duplicate_helper_ids = sorted(
            {helper["id"] for helper in applied_helpers if [item["id"] for item in applied_helpers].count(helper["id"]) > 1}
        )
        if duplicate_helper_ids:
            errors.append("规划结果重复声明了 applied_helpers：" + ", ".join(duplicate_helper_ids) + "。")
            events.append(
                _event(
                    stage="plan_validation",
                    rule_id=self.rule_id,
                    outcome="fail",
                    reason_code="helper_duplicate",
                    message="规划结果重复声明 helper。",
                    details={"duplicate_helper_ids": duplicate_helper_ids},
                )
            )

        expected_helper_ids = {helper["id"] for helper in expected_helpers}
        applied_helper_ids = {helper["id"] for helper in applied_helpers}
        missing_helper_ids = sorted(expected_helper_ids - applied_helper_ids)
        unexpected_helper_ids = sorted(applied_helper_ids - expected_helper_ids)
        if missing_helper_ids:
            errors.append("规划结果缺少规则要求的 applied_helpers：" + ", ".join(missing_helper_ids) + "。")
            events.append(
                _event(
                    stage="plan_validation",
                    rule_id=self.rule_id,
                    outcome="fail",
                    reason_code="helper_missing",
                    message="规划结果没有全量应用规则 helper。",
                    details={"missing_helper_ids": missing_helper_ids},
                )
            )
        if unexpected_helper_ids:
            errors.append("规划结果声明了未定义的 applied_helpers：" + ", ".join(unexpected_helper_ids) + "。")
            events.append(
                _event(
                    stage="plan_validation",
                    rule_id=self.rule_id,
                    outcome="fail",
                    reason_code="helper_not_declared",
                    message="规划结果使用了规则未声明的 helper。",
                    details={"unexpected_helper_ids": unexpected_helper_ids},
                )
            )

        actual_changed_sections = _changed_schema_sections(source_schema, candidate_schema)
        helper_by_id = {helper["id"]: helper for helper in applied_helpers}
        for helper_spec in expected_helpers:
            helper_id = helper_spec["id"]
            applied_helper = helper_by_id.get(helper_id)
            if not applied_helper:
                continue
            missing_text_fields = [
                field
                for field in ("selection_reason", "innovation_reason", "difficulty_reason")
                if not str(applied_helper.get(field, "")).strip()
            ]
            if missing_text_fields:
                errors.append(f"helper `{helper_id}` 缺少必要说明字段：" + ", ".join(missing_text_fields) + "。")
                events.append(
                    _event(
                        stage="plan_validation",
                        rule_id=self.rule_id,
                        outcome="fail",
                        reason_code="helper_fields_missing",
                        message="helper 缺少必要说明字段。",
                        details={"helper_id": helper_id, "missing_fields": missing_text_fields},
                    )
                )
            if not applied_helper.get("schema_changes"):
                errors.append(f"helper `{helper_id}` 没有给出 schema_changes。")
                events.append(
                    _event(
                        stage="plan_validation",
                        rule_id=self.rule_id,
                        outcome="fail",
                        reason_code="helper_schema_changes_missing",
                        message="helper 没有说明落到哪些 schema 变化。",
                        details={"helper_id": helper_id},
                    )
                )
            target_axes = {str(axis).strip() for axis in helper_spec.get("target_axes", []) if str(axis).strip()}
            affected_axes = {str(axis).strip() for axis in applied_helper.get("affected_axes", []) if str(axis).strip()}
            missing_axes = sorted(target_axes - affected_axes)
            if missing_axes:
                errors.append(f"helper `{helper_id}` 没有覆盖目标变化轴：" + ", ".join(missing_axes) + "。")
                events.append(
                    _event(
                        stage="plan_validation",
                        rule_id=self.rule_id,
                        outcome="fail",
                        reason_code="helper_target_axes_missing",
                        message="helper 没有覆盖声明的目标变化轴。",
                        details={"helper_id": helper_id, "missing_axes": missing_axes},
                    )
                )
            missing_sections = sorted(
                section
                for section in helper_spec.get("must_realize_in", [])
                if str(section).strip() and str(section).strip() not in actual_changed_sections
            )
            if missing_sections:
                errors.append(f"helper `{helper_id}` 没有在必需 schema 部分落地：" + ", ".join(missing_sections) + "。")
                events.append(
                    _event(
                        stage="plan_validation",
                        rule_id=self.rule_id,
                        outcome="fail",
                        reason_code="helper_realization_missing",
                        message="helper 没有在声明的 schema 部分落地。",
                        details={"helper_id": helper_id, "missing_sections": missing_sections},
                    )
                )
            helper_text = " ".join(
                [
                    str(applied_helper.get("selection_reason", "")),
                    str(applied_helper.get("innovation_reason", "")),
                    str(applied_helper.get("difficulty_reason", "")),
                    " ".join(applied_helper.get("schema_changes", [])),
                ]
            ).lower()
            redline_hits = [
                redline
                for redline in helper_spec.get("redlines", [])
                if str(redline).strip() and str(redline).strip().lower() in helper_text
            ]
            if redline_hits:
                errors.append(f"helper `{helper_id}` 命中了自身 redlines：" + "；".join(redline_hits) + "。")
                events.append(
                    _event(
                        stage="plan_validation",
                        rule_id=self.rule_id,
                        outcome="fail",
                        reason_code="helper_redline_hit",
                        message="helper 命中 redline。",
                        details={"helper_id": helper_id, "redline_hits": redline_hits},
                    )
                )

        # 这组硬判据负责拦住浅改规划：没有新输出责任、主目标没变、主状态没变、
        # 或者仍然可以直接套用原解的候选都会在这里被拒绝。
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
            events.append(
                _event(
                    stage="plan_validation",
                    rule_id=self.rule_id,
                    outcome="pass" if passed else "fail",
                    reason_code=reason_code,
                    message="语义硬判据通过。" if passed else message,
                )
            )
            if not passed:
                errors.append(message)

        if errors:
            reason_code = _first_failure_reason_code(events) or "rule_plan_validation_failed"
            return RuleValidationOutcome(
                accepted=False,
                errors=errors,
                events=events,
                reason_code=reason_code,
                message="；".join(errors),
            )

        return self._validate_specific_plan(
            client=client,
            mode=mode,
            rule=rule,
            payload=payload,
            source_schema=source_schema,
            candidate_schema=candidate_schema,
            changed_axes=changed_axes,
        )

    def validate_problem(
        self,
        *,
        client: QwenClient,
        problem: GeneratedProblem,
        plan: VariantPlan,
    ) -> RuleValidationOutcome:
        rule = copy.deepcopy(self.rule) if self.rule else {"id": self.rule_id, "handler": self.handler_name}
        return self._validate_specific_problem(client=client, problem=problem, plan=plan, rule=rule)

    def _validate_specific_plan(
        self,
        *,
        client: QwenClient,
        mode: str,
        rule: dict[str, Any],
        payload: dict[str, Any],
        source_schema: dict[str, Any],
        candidate_schema: dict[str, Any],
        changed_axes: list[str],
    ) -> RuleValidationOutcome:
        review_role = self.plan_review_role(mode=mode, rule=rule)
        review_brief = self.plan_review_brief(mode=mode, rule=rule)
        return self._run_validation_review(
            client=client,
            stage="plan_validation",
            review_role=review_role,
            review_brief=review_brief,
            default_reason_code=f"{self.rule_id}_plan_review_failed",
            system_prompt=build_rule_plan_validation_system_prompt(),
            user_prompt=build_rule_plan_validation_user_prompt(
                mode=mode,
                review_role=review_role,
                review_brief=review_brief,
                rule=rule,
                source_schema=source_schema,
                candidate_schema=candidate_schema,
                changed_axes=changed_axes,
                planner_payload=payload,
            ),
        )

    def _validate_specific_problem(
        self,
        *,
        client: QwenClient,
        problem: GeneratedProblem,
        plan: VariantPlan,
        rule: dict[str, Any],
    ) -> RuleValidationOutcome:
        review_role = self.problem_review_role(plan=plan, rule=rule)
        review_brief = self.problem_review_brief(plan=plan, rule=rule)
        plan_context = {
            "mode": plan.mode,
            "applied_rule": plan.applied_rule,
            "objective": copy.deepcopy(plan.objective),
            "difference_plan": dataclass_to_dict(plan.difference_plan),
            "algorithmic_delta_claim": copy.deepcopy(plan.algorithmic_delta_claim),
            "shared_core_summary": plan.shared_core_summary,
            "shared_core_anchors": copy.deepcopy(plan.shared_core_anchors),
            "seed_contributions": copy.deepcopy(plan.seed_contributions),
            "fusion_ablation": copy.deepcopy(plan.fusion_ablation),
            "applied_helpers": copy.deepcopy(plan.applied_helpers),
            "instantiated_schema": dataclass_to_dict(plan.instantiated_schema_snapshot),
        }
        return self._run_validation_review(
            client=client,
            stage="problem_validation",
            review_role=review_role,
            review_brief=review_brief,
            default_reason_code=f"{self.rule_id}_problem_review_failed",
            system_prompt=build_rule_problem_validation_system_prompt(),
            user_prompt=build_rule_problem_validation_user_prompt(
                mode=plan.mode,
                review_role=review_role,
                review_brief=review_brief,
                rule=rule,
                plan_context=plan_context,
                generated_problem=dataclass_to_dict(problem),
            ),
        )

    def _run_validation_review(
        self,
        *,
        client: QwenClient,
        stage: str,
        review_role: str,
        review_brief: str,
        default_reason_code: str,
        system_prompt: str,
        user_prompt: str,
    ) -> RuleValidationOutcome:
        payload = client.chat_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.05,
        )
        return self._review_payload_to_outcome(
            stage=stage,
            payload=payload,
            review_role=review_role,
            review_brief=review_brief,
            default_reason_code=default_reason_code,
        )

    def _review_payload_to_outcome(
        self,
        *,
        stage: str,
        payload: dict[str, Any],
        review_role: str,
        review_brief: str,
        default_reason_code: str,
    ) -> RuleValidationOutcome:
        unexpected_keys = sorted(key for key in payload if key not in self._REVIEW_KEYS)
        if unexpected_keys:
            return self._invalid_review_outcome(
                stage=stage,
                review_role=review_role,
                review_brief=review_brief,
                message="规则专属审查返回了未声明字段：" + ", ".join(unexpected_keys) + "。",
                payload=payload,
            )

        missing_keys = sorted(key for key in self._REVIEW_KEYS if key not in payload)
        if missing_keys:
            return self._invalid_review_outcome(
                stage=stage,
                review_role=review_role,
                review_brief=review_brief,
                message="规则专属审查缺少必要字段：" + ", ".join(missing_keys) + "。",
                payload=payload,
            )

        status = str(payload.get("status", "")).strip().lower()
        reason_code = str(payload.get("reason_code", "")).strip()
        message = str(payload.get("message", "")).strip()
        evidence = str(payload.get("evidence", "")).strip()
        errors_raw = payload.get("errors", [])
        if not isinstance(errors_raw, list):
            return self._invalid_review_outcome(
                stage=stage,
                review_role=review_role,
                review_brief=review_brief,
                message="规则专属审查的 errors 字段不是字符串数组。",
                payload=payload,
            )
        errors = [str(item).strip() for item in errors_raw if str(item).strip()]

        if status == "pass":
            if errors:
                return self._invalid_review_outcome(
                    stage=stage,
                    review_role=review_role,
                    review_brief=review_brief,
                    message="规则专属审查同时返回了 pass 状态和错误列表。",
                    payload=payload,
                )
            return RuleValidationOutcome(
                accepted=True,
                events=[
                    _event(
                        stage=stage,
                        rule_id=self.rule_id,
                        outcome="pass",
                        reason_code=reason_code or "ok",
                        message=message or "规则专属 LLM 审查通过。",
                        details={
                            "review_role": review_role,
                            "review_brief": review_brief,
                            "evidence": evidence,
                        },
                    )
                ],
                reason_code=reason_code or "ok",
                message=message or "规则专属 LLM 审查通过。",
            )

        if status != "fail":
            return self._invalid_review_outcome(
                stage=stage,
                review_role=review_role,
                review_brief=review_brief,
                message="规则专属审查返回了无效状态：" + (status or "<empty>") + "。",
                payload=payload,
            )

        if not errors and not message:
            return self._invalid_review_outcome(
                stage=stage,
                review_role=review_role,
                review_brief=review_brief,
                message="规则专属审查返回 fail，但没有给出可读原因。",
                payload=payload,
            )

        final_errors = errors or [message]
        final_message = message or "；".join(final_errors)
        final_reason_code = reason_code or default_reason_code
        return RuleValidationOutcome(
            accepted=False,
            errors=final_errors,
            events=[
                _event(
                    stage=stage,
                    rule_id=self.rule_id,
                    outcome="fail",
                    reason_code=final_reason_code,
                    message=final_message,
                    details={
                        "review_role": review_role,
                        "review_brief": review_brief,
                        "evidence": evidence,
                    },
                )
            ],
            reason_code=final_reason_code,
            message=final_message,
        )

    def _invalid_review_outcome(
        self,
        *,
        stage: str,
        review_role: str,
        review_brief: str,
        message: str,
        payload: dict[str, Any],
    ) -> RuleValidationOutcome:
        return RuleValidationOutcome(
            accepted=False,
            errors=[message],
            events=[
                _event(
                    stage=stage,
                    rule_id=self.rule_id,
                    outcome="fail",
                    reason_code="llm_review_invalid",
                    message=message,
                    details={
                        "review_role": review_role,
                        "review_brief": review_brief,
                        "raw_payload": copy.deepcopy(payload),
                    },
                )
            ],
            reason_code="llm_review_invalid",
            message=message,
        )


class GenericRuleHandler(RuleHandler):
    pass


class CanonicalWitnessHandler(RuleHandler):
    def eligibility_role(self, *, mode: str, rule: dict[str, Any]) -> str:
        return "你扮演一名规范解审查官，重点判断种子题是否仍有空间升级为带规范性的构造输出。"

    def plan_review_role(self, *, mode: str, rule: dict[str, Any]) -> str:
        return "你扮演一名规范解规划审查官，重点确认规划是否真正把输出责任升级为可比较、可校验的规范解。"

    def plan_review_brief(self, *, mode: str, rule: dict[str, Any]) -> str:
        return "确认规划是否明确了规范解的定义、比较口径与校验方式，并且规范性会改变主要求解责任。"

    def problem_review_role(self, *, plan: VariantPlan, rule: dict[str, Any]) -> str:
        return "你扮演一名规范解题面审查官，重点确认题面是否要求输出一个规范且可检查的构造。"

    def problem_review_brief(self, *, plan: VariantPlan, rule: dict[str, Any]) -> str:
        return "确认题面是否写清规范解、字典序或统一比较规则，并要求输出一个可校验的构造方案。"


class ConstructOrObstructionHandler(RuleHandler):
    def eligibility_role(self, *, mode: str, rule: dict[str, Any]) -> str:
        return "你扮演一名冲突证书审查官，重点判断无解情形能否落成可局部检查的阻碍证据。"

    def plan_review_role(self, *, mode: str, rule: dict[str, Any]) -> str:
        return "你扮演一名阻碍证据规划审查官，重点确认规划是否同时定义了解分支和可局部检查的失败证据。"

    def plan_review_brief(self, *, mode: str, rule: dict[str, Any]) -> str:
        return "确认规划是否把无解分支写成可直接检查的局部阻碍证据，而不是解释性说明。"

    def problem_review_role(self, *, plan: VariantPlan, rule: dict[str, Any]) -> str:
        return "你扮演一名阻碍证据题面审查官，重点确认题面是否写清失败输出和证据的检查语义。"

    def problem_review_brief(self, *, plan: VariantPlan, rule: dict[str, Any]) -> str:
        return "确认题面是否要求在无解时输出一个可局部检查的冲突证据，而不是仅仅解释为什么无解。"


class ExistenceToCountingHandler(RuleHandler):
    def eligibility_role(self, *, mode: str, rule: dict[str, Any]) -> str:
        return "你扮演一名计数化审查官，重点判断解空间、去重规则和有限性是否足够清晰。"

    def plan_review_role(self, *, mode: str, rule: dict[str, Any]) -> str:
        return "你扮演一名计数规划审查官，重点确认规划是否真正把目标升级为对象明确的计数任务。"

    def plan_review_brief(self, *, mode: str, rule: dict[str, Any]) -> str:
        return "确认规划是否定义了计数对象、去重口径、有限性来源，以及需要时的取模约定。"

    def problem_review_role(self, *, plan: VariantPlan, rule: dict[str, Any]) -> str:
        return "你扮演一名计数题面审查官，重点确认题面是否完整兑现计数目标与去重规则。"

    def problem_review_brief(self, *, plan: VariantPlan, rule: dict[str, Any]) -> str:
        return "确认题面是否明确写出统计对象、等价关系、不同答案的判定口径，以及必要的模数约定。"


class MinimumGuaranteeUnderPerturbationHandler(RuleHandler):
    def eligibility_role(self, *, mode: str, rule: dict[str, Any]) -> str:
        return "你扮演一名保底优化审查官，重点判断原题语义中是否存在可被放大的原生扰动来源。"

    def plan_review_role(self, *, mode: str, rule: dict[str, Any]) -> str:
        return "你扮演一名保底优化规划审查官，重点确认规划是否把目标升级为真实的最坏情形保底优化。"

    def plan_review_brief(self, *, mode: str, rule: dict[str, Any]) -> str:
        return "确认规划是否给出了来源于原题语义的扰动模型，并把保底目标和强化不变量写进四元组。"

    def problem_review_role(self, *, plan: VariantPlan, rule: dict[str, Any]) -> str:
        return "你扮演一名保底优化题面审查官，重点确认题面是否清楚表达最坏情形或任意扰动下的保底语义。"

    def problem_review_brief(self, *, plan: VariantPlan, rule: dict[str, Any]) -> str:
        return "确认题面是否写清扰动来源、最坏情况语义，以及要求求出最小保底值或等价的鲁棒目标。"


class InterlockedConstraintsHandler(RuleHandler):
    def eligibility_role(self, *, mode: str, rule: dict[str, Any]) -> str:
        return "你扮演一名共享主核融合审查官，重点判断两题是否真的共享同一个状态核，并能形成互锁约束。"

    def plan_review_role(self, *, mode: str, rule: dict[str, Any]) -> str:
        return "你扮演一名互锁融合规划审查官，重点确认规划是否让两题义务在同一共享主核上同步承压。"

    def plan_review_brief(self, *, mode: str, rule: dict[str, Any]) -> str:
        return "确认规划是否明确共享主核、双向不可删贡献、反串联论证与消融论证，而且互锁约束进入核心求解过程。"

    def problem_review_role(self, *, plan: VariantPlan, rule: dict[str, Any]) -> str:
        return "你扮演一名互锁融合题面审查官，重点确认题面是否写清双义务在同一状态过程中同时生效。"

    def problem_review_brief(self, *, plan: VariantPlan, rule: dict[str, Any]) -> str:
        return "确认题面是否体现共享主核、同步承压和不可拆分的双重义务，而不是前后串联两个子任务。"


class SharedCoreObjectiveUpgradeHandler(RuleHandler):
    def eligibility_role(self, *, mode: str, rule: dict[str, Any]) -> str:
        return "你扮演一名共享主核升级审查官，重点判断共享主核是否足以承担更强的新目标。"

    def plan_review_role(self, *, mode: str, rule: dict[str, Any]) -> str:
        return "你扮演一名共享主核升级规划审查官，重点确认规划是否在共享主核上承载了更强的新目标。"

    def plan_review_brief(self, *, mode: str, rule: dict[str, Any]) -> str:
        return "确认规划是否保留共享主核与双向不可删贡献，同时把主目标升级到更强层级，而不是保留原目标后附加包装。"

    def problem_review_role(self, *, plan: VariantPlan, rule: dict[str, Any]) -> str:
        return "你扮演一名共享主核升级题面审查官，重点确认题面是否兑现了共享主核上的升级目标。"

    def problem_review_brief(self, *, plan: VariantPlan, rule: dict[str, Any]) -> str:
        objective_type = str(plan.objective.get("type", "")).strip() or "unknown"
        return (
            "确认题面是否明确写出升级后的主目标，"
            f"当前规划目标类型为 {objective_type}，并且该目标仍然作用在同一共享状态核上。"
        )


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


def _first_failure_reason_code(events: list[AuditTraceEvent]) -> str:
    for event in events:
        if event.outcome == "fail" and event.reason_code:
            return event.reason_code
    return ""


def _normalize_rule_helpers(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        helper_id = normalize_rule_id(item.get("id", ""))
        if not helper_id:
            continue
        normalized.append(
            {
                "id": helper_id,
                "must_realize_in": [str(section).strip() for section in item.get("must_realize_in", []) if str(section).strip()],
                "target_axes": [str(axis).strip() for axis in item.get("target_axes", []) if str(axis).strip()],
                "redlines": [str(redline).strip() for redline in item.get("redlines", []) if str(redline).strip()],
            }
        )
    return normalized


def _normalize_applied_helpers(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        helper_id = normalize_rule_id(item.get("id", ""))
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


def _changed_schema_sections(source_schema: dict[str, Any], candidate_schema: dict[str, Any]) -> set[str]:
    changed_sections: set[str] = set()
    for section in ("input_structure", "core_constraints", "objective", "invariant"):
        if copy.deepcopy(source_schema.get(section)) != copy.deepcopy(candidate_schema.get(section)):
            changed_sections.add(section)
    return changed_sections


def _objective_text(schema: dict[str, Any]) -> str:
    objective = schema.get("objective", {})
    return " ".join(str(objective.get(key, "")) for key in ("type", "description"))


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
    return _text_has_any(
        candidate_text,
        signal_tokens - {token for token in signal_tokens if token.lower() in source_text.lower()},
    )


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

# 与 planning_rules.json 的 handler 字段保持一一对应。
_RULE_HANDLER_REGISTRY = {
    "canonical_witness": CanonicalWitnessHandler,
    "construct_or_obstruction": ConstructOrObstructionHandler,
    "existence_to_counting": ExistenceToCountingHandler,
    "minimum_guarantee_under_perturbation": MinimumGuaranteeUnderPerturbationHandler,
    "interlocked_constraints": InterlockedConstraintsHandler,
    "shared_core_objective_upgrade": SharedCoreObjectiveUpgradeHandler,
}
