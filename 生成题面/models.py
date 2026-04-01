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
    instantiated_parameters: dict[str, Any] = field(default_factory=dict)
    selected_structural_options: list[str] = field(default_factory=list)
    selected_input_options: list[str] = field(default_factory=list)
    selected_invariant_options: list[str] = field(default_factory=list)
    theme: dict[str, Any] = field(default_factory=dict)
    difficulty: str = ""


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
    distance_breakdown: dict[str, float]
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
    auxiliary_moves: list[str] = field(default_factory=list)
    numerical_parameters: dict[str, Any] = field(default_factory=dict)
    structural_options: list[str] = field(default_factory=list)
    input_structure_options: list[str] = field(default_factory=list)
    invariant_options: list[str] = field(default_factory=list)


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
