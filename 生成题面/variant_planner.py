from __future__ import annotations

import copy
import random
from typing import Any

from models import DifferencePlan, InstantiatedSchema, Theme, VariantPlan
from prompt_builder import (
    build_planner_system_prompt,
    build_planner_user_prompt,
    build_rule_selection_system_prompt,
    build_rule_selection_user_prompt,
)
from qwen_client import QwenClient
from rulebook import RuleBook, normalize_mode_name, normalize_rule_id
from schema_tools import build_forbidden_reuse_list, compute_changed_axes, compute_schema_distance


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

class VariantPlanner:
    MIN_DISTANCE = 0.35
    MAX_DISTANCE = 0.60

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
        original_schema: dict[str, Any] | None = None,
        prepared_schema: dict[str, Any] | None = None,
        original_problem: dict[str, Any] | None = None,
        seed_a_schema: dict[str, Any] | None = None,
        seed_b_schema: dict[str, Any] | None = None,
        seed_a_original_schema: dict[str, Any] | None = None,
        seed_b_original_schema: dict[str, Any] | None = None,
        seed_a_problem: dict[str, Any] | None = None,
        seed_b_problem: dict[str, Any] | None = None,
        allowed_rule_ids: set[str] | None = None,
    ) -> VariantPlan:
        if self.client is None:
            raise RuntimeError("未初始化 LLM 客户端，无法执行规则规划。")

        canonical_mode = _canonical_mode(mode)
        rng = random.Random(self.seed + variant_index)
        theme = self._select_theme(rng, theme_id)

        if canonical_mode == "single_seed_extension":
            return self._build_single_plan(
                prepared_schema=prepared_schema or original_schema,
                original_schema=original_schema or prepared_schema or {},
                original_problem=original_problem,
                variant_index=variant_index,
                theme=theme,
                allowed_rule_ids=allowed_rule_ids,
            )
        if canonical_mode == "same_family_fusion":
            if seed_a_schema is None or seed_b_schema is None or seed_a_problem is None or seed_b_problem is None:
                raise ValueError("same_family 模式必须提供两题 schema 和原题文本。")
            return self._build_same_family_plan(
                seed_a_schema=seed_a_schema,
                seed_b_schema=seed_b_schema,
                seed_a_original_schema=seed_a_original_schema,
                seed_b_original_schema=seed_b_original_schema,
                seed_a_problem=seed_a_problem,
                seed_b_problem=seed_b_problem,
                variant_index=variant_index,
                theme=theme,
                allowed_rule_ids=allowed_rule_ids,
            )
        raise ValueError(f"Unsupported mode: {mode}")

    def _build_single_plan(
        self,
        *,
        prepared_schema: dict[str, Any],
        original_schema: dict[str, Any],
        original_problem: dict[str, Any] | None,
        variant_index: int,
        theme: Theme,
        allowed_rule_ids: set[str] | None,
    ) -> VariantPlan:
        rules = self.rulebook.enabled_rules("single_seed_extension", allowed_rule_ids)
        seed_problem_ids = [prepared_schema.get("problem_id", "unknown")]
        theme_payload = self._theme_payload(theme)
        schema_context = {
            "seed_schema": prepared_schema,
            "original_schema": original_schema,
        }
        original_refs = [_build_problem_reference(original_problem)]
        if not rules:
            return self._finalize_plan(
                mode="single_seed_extension",
                source_problem_ids=seed_problem_ids,
                source_schema=original_schema,
                theme=theme,
                variant_index=variant_index,
                selected_plan=None,
                rejected_candidates=[],
                forbidden_reuse=build_forbidden_reuse_list(original_problem),
                rule_selection_reason="",
                planning_status="difference_insufficient",
                planning_error_reason="当前模式下没有可用规则。",
                planning_feedback="请检查规则文件的启用状态，或调整 rule override。",
            )

        selection = self._select_rule(
            mode="single_seed_extension",
            rules=rules,
            schema_context=schema_context,
            original_refs=original_refs,
        )
        if not selection["accepted"]:
            return self._finalize_plan(
                mode="single_seed_extension",
                source_problem_ids=seed_problem_ids,
                source_schema=original_schema,
                theme=theme,
                variant_index=variant_index,
                selected_plan=None,
                rejected_candidates=[],
                forbidden_reuse=build_forbidden_reuse_list(original_problem),
                rule_selection_reason=str(selection.get("selection_reason", "")),
                planning_status=str(selection.get("planning_status", "difference_insufficient")),
                planning_error_reason=str(selection.get("error_reason", "")),
                planning_feedback=str(selection.get("feedback", "")),
            )

        selected_rule = selection["rule"]
        plan_result = self._generate_candidate(
            mode="single_seed_extension",
            rule=selected_rule,
            theme_payload=theme_payload,
            schema_context=schema_context,
            original_refs=original_refs,
            source_schema=original_schema,
            source_problem_ids=seed_problem_ids,
        )
        return self._finalize_plan(
            mode="single_seed_extension",
            source_problem_ids=seed_problem_ids,
            source_schema=original_schema,
            theme=theme,
            variant_index=variant_index,
            selected_plan=plan_result if plan_result["accepted"] else None,
            rejected_candidates=[] if plan_result["accepted"] else [plan_result["summary"]],
            forbidden_reuse=build_forbidden_reuse_list(original_problem),
            rule_selection_reason=str(selection.get("selection_reason", "")),
            planning_status="ok" if plan_result["accepted"] else "difference_insufficient",
            planning_error_reason=""
            if plan_result["accepted"]
            else str(plan_result["summary"].get("reason", "") or "选中的规则未能通过规划校验。"),
            planning_feedback=""
            if plan_result["accepted"]
            else f"已选择规则 {selected_rule.get('id', '')}，但实例化四元组没有通过硬门槛。",
            applied_rule=""
            if plan_result["accepted"]
            else str(selected_rule.get("id", "")),
        )

    def _build_same_family_plan(
        self,
        *,
        seed_a_schema: dict[str, Any],
        seed_b_schema: dict[str, Any],
        seed_a_original_schema: dict[str, Any] | None,
        seed_b_original_schema: dict[str, Any] | None,
        seed_a_problem: dict[str, Any],
        seed_b_problem: dict[str, Any],
        variant_index: int,
        theme: Theme,
        allowed_rule_ids: set[str] | None,
    ) -> VariantPlan:
        rules = self.rulebook.enabled_rules("same_family_fusion", allowed_rule_ids)
        theme_payload = self._theme_payload(theme)
        source_problem_ids = [
            seed_a_schema.get("problem_id", "seed_a"),
            seed_b_schema.get("problem_id", "seed_b"),
        ]
        schema_context = {
            "seed_a_schema": seed_a_schema,
            "seed_b_schema": seed_b_schema,
        }
        if seed_a_original_schema is not None:
            schema_context["seed_a_original_schema"] = seed_a_original_schema
        if seed_b_original_schema is not None:
            schema_context["seed_b_original_schema"] = seed_b_original_schema
        original_refs = [
            _build_problem_reference(seed_a_problem),
            _build_problem_reference(seed_b_problem),
        ]
        source_schema = _merge_seed_schemas(seed_a_schema, seed_b_schema)
        if not rules:
            return self._finalize_plan(
                mode="same_family_fusion",
                source_problem_ids=source_problem_ids,
                source_schema=source_schema,
                theme=theme,
                variant_index=variant_index,
                selected_plan=None,
                rejected_candidates=[],
                forbidden_reuse=_merge_forbidden_reuse(seed_a_problem, seed_b_problem),
                rule_selection_reason="",
                planning_status="difference_insufficient",
                planning_error_reason="当前模式下没有可用规则。",
                planning_feedback="请检查规则文件的启用状态，或调整 rule override。",
            )

        selection = self._select_rule(
            mode="same_family_fusion",
            rules=rules,
            schema_context=schema_context,
            original_refs=original_refs,
        )
        if not selection["accepted"]:
            return self._finalize_plan(
                mode="same_family_fusion",
                source_problem_ids=source_problem_ids,
                source_schema=source_schema,
                theme=theme,
                variant_index=variant_index,
                selected_plan=None,
                rejected_candidates=[],
                forbidden_reuse=_merge_forbidden_reuse(seed_a_problem, seed_b_problem),
                rule_selection_reason=str(selection.get("selection_reason", "")),
                planning_status=str(selection.get("planning_status", "difference_insufficient")),
                planning_error_reason=str(selection.get("error_reason", "")),
                planning_feedback=str(selection.get("feedback", "")),
            )

        selected_rule = selection["rule"]
        plan_result = self._generate_candidate(
            mode="same_family_fusion",
            rule=selected_rule,
            theme_payload=theme_payload,
            schema_context=schema_context,
            original_refs=original_refs,
            source_schema=source_schema,
            source_problem_ids=source_problem_ids,
        )
        return self._finalize_plan(
            mode="same_family_fusion",
            source_problem_ids=source_problem_ids,
            source_schema=source_schema,
            theme=theme,
            variant_index=variant_index,
            selected_plan=plan_result if plan_result["accepted"] else None,
            rejected_candidates=[] if plan_result["accepted"] else [plan_result["summary"]],
            forbidden_reuse=_merge_forbidden_reuse(seed_a_problem, seed_b_problem),
            rule_selection_reason=str(selection.get("selection_reason", "")),
            planning_status="ok" if plan_result["accepted"] else "difference_insufficient",
            planning_error_reason=""
            if plan_result["accepted"]
            else str(plan_result["summary"].get("reason", "") or "选中的规则未能通过规划校验。"),
            planning_feedback=""
            if plan_result["accepted"]
            else f"已选择规则 {selected_rule.get('id', '')}，但实例化四元组没有通过硬门槛。",
            applied_rule=""
            if plan_result["accepted"]
            else str(selected_rule.get("id", "")),
        )

    def _select_rule(
        self,
        *,
        mode: str,
        rules: list[dict[str, Any]],
        schema_context: dict[str, Any],
        original_refs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if len(rules) == 1:
            rule = dict(rules[0])
            return {
                "accepted": True,
                "rule": rule,
                "selection_reason": f"当前仅有一条启用规则 {rule.get('id', '')}，直接采用。",
            }

        payload = self.client.chat_json(
            system_prompt=build_rule_selection_system_prompt(),
            user_prompt=build_rule_selection_user_prompt(
                mode=mode,
                available_rules=rules,
                schema_context=schema_context,
                original_problem_references=original_refs,
                global_constraints=self.rulebook.global_constraints(),
                global_redlines=self.rulebook.global_redlines(),
            ),
            temperature=0.05,
        )
        selection_reason = _summarize_rule_selection(payload)
        status = str(payload.get("status", "difference_insufficient"))
        if status != "ok":
            return {
                "accepted": False,
                "selection_reason": selection_reason,
                "planning_status": status,
                "error_reason": str(payload.get("error_reason", "") or payload.get("feedback", "")),
                "feedback": str(payload.get("feedback", "")),
            }

        selected_rule_id = normalize_rule_id(payload.get("selected_rule_id", ""))
        selected_rule = next(
            (
                dict(rule)
                for rule in rules
                if normalize_rule_id(rule.get("id", "")) == selected_rule_id
            ),
            None,
        )
        if selected_rule is None:
            return {
                "accepted": False,
                "selection_reason": selection_reason,
                "planning_status": "difference_insufficient",
                "error_reason": f"规则选择阶段返回了未知规则：{selected_rule_id or '空'}。",
                "feedback": "请检查规则选择提示词或模型输出。",
            }

        return {
            "accepted": True,
            "rule": selected_rule,
            "selection_reason": selection_reason or f"已选择规则 {selected_rule_id}。",
        }

    def _generate_candidate(
        self,
        *,
        mode: str,
        rule: dict[str, Any],
        theme_payload: dict[str, Any],
        schema_context: dict[str, Any],
        original_refs: list[dict[str, Any]],
        source_schema: dict[str, Any],
        source_problem_ids: list[str],
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
            ),
            temperature=0.15,
        )
        accepted, normalized, rejection_reason = self._validate_candidate(
            mode=mode,
            rule=rule,
            payload=payload,
            source_schema=source_schema,
            source_problem_ids=source_problem_ids,
            theme_payload=theme_payload,
        )
        summary = {
            "rule_id": rule.get("id", ""),
            "status": str(payload.get("status", "difference_insufficient")),
            "reason": rejection_reason
            or str(payload.get("error_reason", "") or payload.get("feedback", "")),
        }
        if accepted:
            normalized["summary"] = summary
            return {"accepted": True, **normalized}
        return {"accepted": False, "summary": summary}

    def _validate_candidate(
        self,
        *,
        mode: str,
        rule: dict[str, Any],
        payload: dict[str, Any],
        source_schema: dict[str, Any],
        source_problem_ids: list[str],
        theme_payload: dict[str, Any],
    ) -> tuple[bool, dict[str, Any], str]:
        status = str(payload.get("status", "difference_insufficient"))
        if status != "ok":
            return False, {}, str(payload.get("error_reason", "") or payload.get("feedback", ""))

        instantiated_schema = _normalize_instantiated_schema(payload.get("instantiated_schema", {}), theme_payload)
        if not instantiated_schema:
            return False, {}, "instantiated_schema 缺失或结构不完整。"

        distance = compute_schema_distance(source_schema, instantiated_schema)
        changed_axes = compute_changed_axes(source_schema, instantiated_schema)
        must_change = set(rule.get("required_axis_changes", {}).get("must_change", []))
        if not must_change.issubset(set(changed_axes)):
            return False, {}, f"规则要求的核心变化轴未完整落地，当前仅有：{', '.join(changed_axes) or '无'}。"
        if mode == "same_family_fusion":
            anchors = payload.get("shared_core_anchors", {})
            if not all(str(anchors.get(key, "")).strip() for key in ("shared_state", "shared_transition", "shared_decision_basis")):
                return False, {}, "same_family_fusion 缺少共享主核锚点。"
            if not str(payload.get("seed_a_indispensable_obligation", "")).strip():
                return False, {}, "same_family_fusion 缺少 seed_a 不可删贡献。"
            if not str(payload.get("seed_b_indispensable_obligation", "")).strip():
                return False, {}, "same_family_fusion 缺少 seed_b 不可删贡献。"
            if not str(payload.get("why_not_sequential_composition", "")).strip():
                return False, {}, "same_family_fusion 缺少反串联论证。"
            fusion_ablation = payload.get("fusion_ablation", {})
            if not str(fusion_ablation.get("without_seed_a", "")).strip():
                return False, {}, "same_family_fusion 缺少 without_seed_a 消融论证。"
            if not str(fusion_ablation.get("without_seed_b", "")).strip():
                return False, {}, "same_family_fusion 缺少 without_seed_b 消融论证。"

        within_band = self.MIN_DISTANCE <= distance["total"] < self.MAX_DISTANCE
        if not within_band or len(changed_axes) < 2:
            return (
                False,
                {},
                "规划结果未达到硬门槛，"
                f"预测距离={distance['total']:.4f}，落地轴={', '.join(changed_axes) or '无'}。",
            )

        plan_problem_id = instantiated_schema.get("problem_id") or "__".join(source_problem_ids)
        difficulty = instantiated_schema.get("difficulty") or _infer_difficulty(instantiated_schema)
        normalized = {
            "problem_id": plan_problem_id,
            "source_problem_ids": list(source_problem_ids),
            "objective": copy.deepcopy(instantiated_schema.get("objective", {})),
            "difficulty": difficulty,
            "input_summary": _summarize_input_structure(instantiated_schema.get("input_structure", {})),
            "constraint_summary": _summarize_constraints(
                instantiated_schema.get("core_constraints", {}).get("constraints", [])
            ),
            "invariant_summary": _summarize_invariants(
                instantiated_schema.get("invariant", {}).get("invariants", [])
            ),
            "instantiated_schema": InstantiatedSchema(**instantiated_schema),
            "distance": distance,
            "changed_axes": changed_axes,
            "difference_rationale": str(payload.get("difference_plan", {}).get("rationale", "")),
            "difference_summary": str(payload.get("difference_plan", {}).get("summary", "")),
            "algorithmic_delta_claim": _normalize_algorithmic_delta(payload.get("algorithmic_delta_claim", {})),
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
            "auxiliary_moves": [str(item) for item in payload.get("auxiliary_moves", []) if str(item).strip()],
        }
        return True, normalized, ""

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
    ) -> VariantPlan:
        if selected_plan is None:
            fallback_schema = InstantiatedSchema(
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
                instantiated_schema_snapshot=fallback_schema,
                predicted_schema_distance=0.0,
                distance_breakdown={"I": 0.0, "C": 0.0, "O": 0.0, "V": 0.0, "T": 0.0, "total": 0.0},
                changed_axes_realized=[],
                applied_rule=applied_rule,
                rejected_candidates=rejected_candidates,
                algorithmic_delta_claim={},
                planning_status=planning_status,
                planning_error_reason=planning_error_reason,
                planning_feedback=planning_feedback,
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
            instantiated_schema_snapshot=selected["instantiated_schema"],
            predicted_schema_distance=selected["distance"]["total"],
            distance_breakdown=selected["distance"],
            changed_axes_realized=selected["changed_axes"],
            applied_rule=selected["applied_rule"],
            rejected_candidates=rejected_candidates,
            algorithmic_delta_claim=selected["algorithmic_delta_claim"],
            shared_core_summary=selected["shared_core_summary"],
            shared_core_anchors=selected["shared_core_anchors"],
            seed_contributions=selected["seed_contributions"],
            fusion_ablation=selected["fusion_ablation"],
            auxiliary_moves=selected["auxiliary_moves"],
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


def _normalize_instantiated_schema(payload: dict[str, Any], theme_payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    required = ("problem_id", "source", "input_structure", "core_constraints", "objective", "invariant")
    if not all(key in payload for key in required):
        return {}
    schema = {
        "problem_id": str(payload.get("problem_id", "")).strip(),
        "source": str(payload.get("source", "")).strip(),
        "input_structure": copy.deepcopy(payload.get("input_structure", {})),
        "core_constraints": copy.deepcopy(payload.get("core_constraints", {"constraints": []})),
        "objective": copy.deepcopy(payload.get("objective", {})),
        "invariant": copy.deepcopy(payload.get("invariant", {"invariants": []})),
        "instantiated_parameters": copy.deepcopy(payload.get("instantiated_parameters", {})),
        "selected_structural_options": [
            str(item).strip()
            for item in payload.get("selected_structural_options", [])
            if str(item).strip()
        ],
        "selected_input_options": [
            str(item).strip()
            for item in payload.get("selected_input_options", [])
            if str(item).strip()
        ],
        "selected_invariant_options": [
            str(item).strip()
            for item in payload.get("selected_invariant_options", [])
            if str(item).strip()
        ],
        "theme": copy.deepcopy(payload.get("theme", theme_payload)) or copy.deepcopy(theme_payload),
        "difficulty": str(payload.get("difficulty", "")).strip() or _infer_difficulty(payload),
    }
    return schema


def _normalize_algorithmic_delta(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "seed_solver_core": str(payload.get("seed_solver_core", "")),
        "reusable_subroutines": str(payload.get("reusable_subroutines", "")),
        "new_solver_core": str(payload.get("new_solver_core", "")),
        "new_proof_obligation": str(payload.get("new_proof_obligation", "")),
        "why_direct_reuse_fails": str(payload.get("why_direct_reuse_fails", "")),
    }


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
