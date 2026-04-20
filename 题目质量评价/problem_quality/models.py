from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class HardCheckResult:
    check_id: str
    passed: bool
    severity: str
    category: str
    message: str
    evidence_refs: list[str] = field(default_factory=list)


@dataclass
class DimensionScore:
    dimension: str
    score: float
    rationale: str
    evidence_refs: list[str] = field(default_factory=list)


@dataclass
class Issue:
    issue_type: str
    severity: str
    title: str
    detail: str
    evidence_refs: list[str] = field(default_factory=list)
    fix_hint: str = ""


@dataclass
class DivergenceResult:
    schema_distance: float
    changed_axes_planned: list[str]
    changed_axes_realized: list[str]
    semantic_difference: float
    solution_transfer_risk: float
    surface_retheme_risk: float
    verdict: str
    rationale: str
    evidence_refs: list[str] = field(default_factory=list)


@dataclass
class EvaluationReport:
    overall: dict[str, Any]
    quality: dict[str, Any]
    divergence: dict[str, Any]
    hard_checks: list[dict[str, Any]]
    issues: list[dict[str, Any]]
    suggested_revisions: list[str]
    revision_brief: dict[str, Any]
    snapshots: dict[str, Any]
