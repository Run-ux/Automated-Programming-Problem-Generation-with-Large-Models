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


@dataclass
class InstantiatedSchema:
    problem_id: str
    source: str
    input_structure: dict[str, Any]
    core_constraints: dict[str, Any]
    objective: dict[str, Any]
    invariant: dict[str, Any]
    instantiated_parameters: dict[str, Any]
    selected_structural_options: list[str]
    theme: dict[str, Any]
    difficulty: str


@dataclass
class VariantPlan:
    problem_id: str
    variant_index: int
    seed: int
    theme: Theme
    objective: dict[str, Any]
    numerical_parameters: dict[str, Any]
    structural_options: list[str]
    difficulty: str
    input_summary: str
    constraint_summary: list[str]
    invariant_summary: list[str]
    difference_plan: DifferencePlan
    instantiated_schema_snapshot: InstantiatedSchema
    predicted_schema_distance: float
    distance_breakdown: dict[str, float]
    changed_axes_realized: list[str]


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
