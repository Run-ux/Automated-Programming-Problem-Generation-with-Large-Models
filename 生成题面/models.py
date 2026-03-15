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
