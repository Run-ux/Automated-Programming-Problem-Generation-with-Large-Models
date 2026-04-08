from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Theme:
    theme_id: str
    name: str
    tone: str
    keywords: list[str]
    mapping_hint: str


@dataclass
class DifferencePlan:
    target_distance_band: dict[str, float]
    changed_axes: list[str]
    same_family_allowed: bool
    forbidden_reuse: list[str]
    rationale: str
    summary: str = ""
    mode: str = "single_seed_extension"


@dataclass
class InstantiatedSchema:
    problem_id: str
    source: str
    input_structure: dict[str, Any]
    core_constraints: dict[str, Any]
    objective: dict[str, Any]
    invariant: dict[str, Any]
    theme: dict[str, Any] = field(default_factory=dict)
    difficulty: str = ""


@dataclass
class AuditTraceEvent:
    stage: str
    rule_id: str
    outcome: str
    reason_code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuleSelectionResult:
    rule_id: str
    handler: str
    accepted: bool
    score: float
    reason_code: str
    selection_reason: str
    risk_tags: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuleValidationOutcome:
    accepted: bool
    errors: list[str] = field(default_factory=list)
    events: list[AuditTraceEvent] = field(default_factory=list)
    reason_code: str = ""
    message: str = ""


@dataclass
class VariantPlan:
    problem_id: str
    variant_index: int
    seed: int
    mode: str
    theme: Theme
    source_problem_ids: list[str]
    objective: dict[str, Any]
    difficulty: str
    rule_selection_reason: str
    input_summary: str
    constraint_summary: list[str]
    invariant_summary: list[str]
    difference_plan: DifferencePlan
    instantiated_schema_snapshot: InstantiatedSchema
    predicted_schema_distance: float
    distance_breakdown: dict[str, Any]
    changed_axes_realized: list[str]
    applied_rule: str
    rejected_candidates: list[dict[str, Any]] = field(default_factory=list)
    algorithmic_delta_claim: dict[str, Any] = field(default_factory=dict)
    planning_status: str = "ok"
    planning_error_reason: str = ""
    planning_feedback: str = ""
    shared_core_summary: str = ""
    shared_core_anchors: dict[str, Any] = field(default_factory=dict)
    seed_contributions: dict[str, Any] = field(default_factory=dict)
    fusion_ablation: dict[str, Any] = field(default_factory=dict)
    applied_helpers: list[dict[str, Any]] = field(default_factory=list)
    rule_version: str = ""
    selection_trace: list[dict[str, Any]] = field(default_factory=list)
    validation_trace: list[dict[str, Any]] = field(default_factory=list)
    candidate_attempts: list[dict[str, Any]] = field(default_factory=list)
    rule_snapshot: dict[str, Any] = field(default_factory=dict)


@dataclass
class GeneratedProblem:
    title: str
    description: str
    input_format: str
    output_format: str
    constraints: list[str]
    samples: list[dict[str, str]] = field(default_factory=list)
    notes: str = ""
    status: str = "ok"
    error_reason: str = ""
    feedback: str = ""
