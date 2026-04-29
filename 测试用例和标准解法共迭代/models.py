from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ProblemContext:
    problem_id: str
    generated_problem: dict[str, Any]
    schema_snapshot: dict[str, Any]
    judge_type: str
    sample_tests: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class GeneratedCodeArtifact:
    name: str
    role: str
    code: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TestCase:
    input: str
    source: str
    purpose: str
    expect_bruteforce: bool = True
    is_sample: bool = False
    is_large: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WrongSolution:
    solution_id: str
    code: str
    source: str
    bug_type: str
    expected_failure: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    artifact_name: str
    function_name: str
    test_source: str
    status: str
    stdout: str = ""
    stderr: str = ""
    result: Any = None
    elapsed_ms: int = 0
    error_reason: str = ""


@dataclass
class FailureIssue:
    category: str
    severity: str
    title: str
    detail: str
    evidence_refs: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    fix_hint: str = ""


@dataclass
class ValidationReport:
    overall: dict[str, Any]
    issues: list[dict[str, Any]]
    execution_matrix: list[dict[str, Any]]
    wrong_solution_stats: dict[str, Any]
    revision_context: dict[str, Any]
    base_consistency: dict[str, Any] = field(default_factory=dict)
    component_gate_results: dict[str, Any] = field(default_factory=dict)
    regression_results: dict[str, Any] = field(default_factory=dict)
    semantic_gate_issues: list[dict[str, Any]] = field(default_factory=list)
    candidate_package_gate_results: dict[str, Any] = field(default_factory=dict)
    known_good_results: dict[str, Any] = field(default_factory=dict)
    candidate_delta_summary: dict[str, Any] = field(default_factory=dict)


@dataclass
class IterationSummary:
    run_id: str
    problem_id: str
    requested_rounds: int
    final_status: str
    final_round_index: int
    stop_reason: str
    rounds: list[dict[str, Any]]
    active_issue_count: int = 0
    new_issue_count: int = 0
    resolved_issue_count: int = 0
    carried_issue_count: int = 0
    deliverable_dir: str = ""
    last_attempt_dir: str = ""
    semantic_gate_status: str = "not_evaluated"
    prompt_payload_bytes_by_round: list[dict[str, Any]] = field(default_factory=list)
    regression_case_count: int = 0
    known_good_case_count: int = 0
    candidate_gate_rejection_count: int = 0
    regression_prevention_count: int = 0


def to_dict(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, list):
        return [to_dict(item) for item in value]
    if isinstance(value, dict):
        return {key: to_dict(item) for key, item in value.items()}
    return value
