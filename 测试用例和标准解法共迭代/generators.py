from __future__ import annotations

import copy
from typing import Any

from execution_spec import normalize_execution_spec
from models import ExecutionSpec, GeneratedCodeArtifact, WrongSolution, to_dict
from prompt_builder import (
    build_checker_prompt,
    build_code_system_prompt,
    build_oracle_prompt,
    build_revision_advisor_system_prompt,
    build_revision_advisor_user_prompt,
    build_schema_aware_wrong_solution_prompt,
    build_schema_mistake_analysis_prompt,
    build_spec_system_prompt,
    build_spec_user_prompt,
    build_standard_solution_prompt,
    build_test_generator_prompt,
    build_validator_prompt,
    build_weak_player_prompt,
)


class RevisionAdvisor:
    def __init__(self, client: Any):
        self.client = client

    def generate(self, failure_packet: dict[str, Any]) -> dict[str, Any]:
        payload = self.client.chat_json(
            system_prompt=build_revision_advisor_system_prompt(),
            user_prompt=build_revision_advisor_user_prompt(failure_packet),
            temperature=0.1,
        )
        return _normalize_advisor_revision(payload, failure_packet)


class SpecExtractor:
    def __init__(self, client: Any):
        self.client = client

    def generate(self, context: dict[str, Any], revision_context: dict[str, Any] | None = None) -> ExecutionSpec:
        payload = self.client.chat_json(
            system_prompt=build_spec_system_prompt(),
            user_prompt=build_spec_user_prompt(context, revision_context),
            temperature=0.1,
        )
        return normalize_execution_spec(payload)


class StandardSolutionGenerator:
    def __init__(self, client: Any, timeout_s: int | None = None):
        self.client = client
        self.timeout_s = timeout_s

    def generate(
        self,
        context: dict[str, Any],
        spec: ExecutionSpec,
        revision_context: dict[str, Any] | None = None,
    ) -> GeneratedCodeArtifact:
        payload = self.client.chat_json(
            system_prompt=build_code_system_prompt("StandardSolutionGenerator"),
            user_prompt=build_standard_solution_prompt(context, to_dict(spec), revision_context),
            temperature=0.15,
            timeout_s=self.timeout_s,
            request_name="standard_solution_generation",
        )
        return GeneratedCodeArtifact(
            name="standard_solution",
            role="standard_solution",
            code=_clean_code(str(payload.get("code", ""))),
            metadata={
                "algorithm": payload.get("algorithm", ""),
                "correctness": payload.get("correctness", ""),
                "time_complexity": payload.get("time_complexity", ""),
                "space_complexity": payload.get("space_complexity", ""),
                "notes": payload.get("notes", ""),
            },
        )


class OracleGenerator:
    def __init__(self, client: Any):
        self.client = client

    def generate(
        self,
        context: dict[str, Any],
        spec: ExecutionSpec,
        revision_context: dict[str, Any] | None = None,
    ) -> GeneratedCodeArtifact:
        payload = self.client.chat_json(
            system_prompt=build_code_system_prompt("OracleGenerator"),
            user_prompt=build_oracle_prompt(context, to_dict(spec), revision_context),
            temperature=0.1,
        )
        return GeneratedCodeArtifact(
            name="oracle_solution",
            role="oracle_solution",
            code=_clean_code(str(payload.get("code", ""))),
            metadata={
                "oracle_scope": payload.get("oracle_scope", {}),
                "method": payload.get("method", ""),
                "notes": payload.get("notes", ""),
            },
        )


class ToolGenerator:
    def __init__(self, client: Any, timeout_s: int | None = None):
        self.client = client
        self.timeout_s = timeout_s

    def generate(
        self,
        context: dict[str, Any],
        spec: ExecutionSpec,
        revision_context: dict[str, Any] | None = None,
    ) -> dict[str, GeneratedCodeArtifact]:
        validator = self.generate_validator(context, spec, revision_context)
        checker = self.generate_checker(context, spec, validator, revision_context)
        test_generator = self.generate_test_generator(context, spec, validator, checker, revision_context)
        return {
            "validator": validator,
            "checker": checker,
            "test_generator": test_generator,
        }

    def generate_validator(
        self,
        context: dict[str, Any],
        spec: ExecutionSpec,
        revision_context: dict[str, Any] | None = None,
    ) -> GeneratedCodeArtifact:
        payload = self.client.chat_json(
            system_prompt=build_code_system_prompt("ValidatorGenerator"),
            user_prompt=build_validator_prompt(context, to_dict(spec), revision_context),
            temperature=0.1,
            timeout_s=self.timeout_s,
            request_name="validator_generation",
        )
        return GeneratedCodeArtifact(
            name="validator",
            role="validator",
            code=_clean_code(str(payload.get("validator_code", ""))),
            metadata={"notes": payload.get("notes", ""), "stage": "validator"},
        )

    def generate_checker(
        self,
        context: dict[str, Any],
        spec: ExecutionSpec,
        validator: GeneratedCodeArtifact,
        revision_context: dict[str, Any] | None = None,
    ) -> GeneratedCodeArtifact:
        payload = self.client.chat_json(
            system_prompt=build_code_system_prompt("CheckerGenerator"),
            user_prompt=build_checker_prompt(context, to_dict(spec), to_dict(validator), revision_context),
            temperature=0.1,
            timeout_s=self.timeout_s,
            request_name="checker_generation",
        )
        return GeneratedCodeArtifact(
            name="checker",
            role="checker",
            code=_clean_code(str(payload.get("checker_code", ""))),
            metadata={"notes": payload.get("notes", ""), "stage": "checker"},
        )

    def generate_test_generator(
        self,
        context: dict[str, Any],
        spec: ExecutionSpec,
        validator: GeneratedCodeArtifact,
        checker: GeneratedCodeArtifact,
        revision_context: dict[str, Any] | None = None,
    ) -> GeneratedCodeArtifact:
        payload = self.client.chat_json(
            system_prompt=build_code_system_prompt("TestGenerator"),
            user_prompt=build_test_generator_prompt(
                context,
                to_dict(spec),
                to_dict(validator),
                to_dict(checker),
                revision_context,
            ),
            temperature=0.1,
            timeout_s=self.timeout_s,
            request_name="test_generator_generation",
        )
        return GeneratedCodeArtifact(
            name="test_generator",
            role="test_generator",
            code=_clean_code(str(payload.get("test_generator_code", ""))),
            metadata={"notes": payload.get("notes", ""), "stage": "test_generator"},
        )


class WeakPlayerGenerator:
    def __init__(self, client: Any):
        self.client = client

    def generate(
        self,
        statement_only_context: dict[str, Any],
        revision_context: dict[str, Any] | None = None,
    ) -> list[WrongSolution]:
        payload = self.client.chat_json(
            system_prompt=build_code_system_prompt("WeakPlayerGenerator"),
            user_prompt=build_weak_player_prompt(statement_only_context, revision_context),
            temperature=0.75,
        )
        return [
            WrongSolution(
                solution_id=str(item.get("solution_id", f"weak_player_{index}")),
                code=_clean_code(str(item.get("code", ""))),
                source=str(item.get("source", "weak_llm_player")),
                bug_type=str(item.get("bug_type", "unknown")),
                expected_failure=str(item.get("expected_failure", "")),
                metadata={"raw": copy.deepcopy(item)},
            )
            for index, item in enumerate(payload.get("wrong_solutions", []), start=1)
            if isinstance(item, dict)
        ]


class SchemaMistakeAnalyzer:
    def __init__(self, client: Any):
        self.client = client

    def generate(
        self,
        context: dict[str, Any],
        spec: ExecutionSpec,
        revision_context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if not context.get("new_schema") or self.client is None:
            return []

        payload = self.client.chat_json(
            system_prompt=build_code_system_prompt("SchemaMistakeAnalyzer"),
            user_prompt=build_schema_mistake_analysis_prompt(context, to_dict(spec), revision_context),
            temperature=0.35,
        )
        mistake_points = payload.get("mistake_points", [])
        if not isinstance(mistake_points, list):
            return []
        return [
            _normalize_mistake_point(item, index)
            for index, item in enumerate(mistake_points, start=1)
            if isinstance(item, dict)
        ]


class SchemaAwareWrongSolutionGenerator:
    def __init__(self, client: Any):
        self.client = client

    def generate(
        self,
        context: dict[str, Any],
        spec: ExecutionSpec,
        mistake_points: list[dict[str, Any]],
        revision_context: dict[str, Any] | None = None,
    ) -> list[WrongSolution]:
        if not context.get("new_schema") or not mistake_points or self.client is None:
            return []

        payload = self.client.chat_json(
            system_prompt=build_code_system_prompt("SchemaAwareWrongSolutionGenerator"),
            user_prompt=build_schema_aware_wrong_solution_prompt(context, to_dict(spec), mistake_points, revision_context),
            temperature=0.65,
        )
        mistake_by_id = {str(item.get("mistake_id", "")).strip(): item for item in mistake_points}
        default_schema_signals = _extract_schema_signal_names(context.get("new_schema"))
        wrong_solutions: list[WrongSolution] = []
        raw_items = payload.get("wrong_solutions", [])
        if not isinstance(raw_items, list):
            return wrong_solutions

        for index, item in enumerate(raw_items, start=1):
            if not isinstance(item, dict):
                continue
            mistake_id = str(item.get("mistake_id", "")).strip()
            mistake_point = mistake_by_id.get(mistake_id, {})
            schema_signals = item.get("schema_signals")
            if not isinstance(schema_signals, list):
                schema_signals = default_schema_signals
            wrong_solutions.append(
                WrongSolution(
                    solution_id=str(item.get("solution_id", f"{spec.problem_id}_schema_wrong_{index}")),
                    code=_clean_code(str(item.get("code", ""))),
                    source="schema_aware_llm_player",
                    bug_type=str(item.get("bug_type", "schema_misread")),
                    expected_failure=str(item.get("expected_failure", "")),
                    metadata={
                        "mistake_id": mistake_id,
                        "mistake_point": copy.deepcopy(mistake_point),
                        "schema_signals": [str(signal) for signal in schema_signals if str(signal).strip()],
                        "raw": copy.deepcopy(item),
                    },
                )
            )
        return wrong_solutions


def _normalize_mistake_point(item: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "mistake_id": str(item.get("mistake_id", f"schema_mistake_{index}")).strip() or f"schema_mistake_{index}",
        "schema_basis": _normalize_string_list(item.get("schema_basis")),
        "player_visible_misread": str(item.get("player_visible_misread", "")).strip(),
        "wrong_strategy": str(item.get("wrong_strategy", "")).strip(),
        "target_failure_bucket": str(item.get("target_failure_bucket", "")).strip(),
        "expected_counterexample_shape": str(item.get("expected_counterexample_shape", "")).strip(),
        "triviality_risk": str(item.get("triviality_risk", "")).strip(),
        "raw": copy.deepcopy(item),
    }


def _extract_schema_signal_names(new_schema: Any) -> list[str]:
    if not isinstance(new_schema, dict):
        return []
    signals: list[str] = []
    objective = new_schema.get("objective", {})
    if isinstance(objective, dict):
        objective_type = str(objective.get("type", "")).strip()
        if objective_type:
            signals.append(f"objective:{objective_type}")

    constraints = new_schema.get("core_constraints", {}).get("constraints", [])
    if isinstance(constraints, list):
        for item in constraints:
            if isinstance(item, dict) and str(item.get("name", "")).strip():
                signals.append(f"constraint:{item['name']}")

    invariants = new_schema.get("invariant", {}).get("invariants", [])
    if isinstance(invariants, list):
        for item in invariants:
            if isinstance(item, dict) and str(item.get("name", "")).strip():
                signals.append(f"invariant:{item['name']}")
    return signals


def _normalize_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _normalize_advisor_revision(payload: dict[str, Any], failure_packet: dict[str, Any]) -> dict[str, Any]:
    diagnostic = failure_packet.get("diagnostic") if isinstance(failure_packet.get("diagnostic"), dict) else {}
    allowed_roles = {str(role) for role in diagnostic.get("target_roles", [])}
    target_roles = [role for role in _normalize_string_list(payload.get("target_roles")) if role in allowed_roles]
    if not target_roles:
        target_roles = sorted(allowed_roles)
    confidence = str(payload.get("confidence", "medium")).strip().lower()
    if confidence not in {"low", "medium", "high"}:
        confidence = "medium"
    return {
        "root_cause": str(payload.get("root_cause", "")).strip(),
        "revision_advice": str(payload.get("revision_advice", "")).strip(),
        "target_roles": target_roles,
        "evidence_used": _normalize_string_list(payload.get("evidence_used")),
        "confidence": confidence,
        "risk_notes": str(payload.get("risk_notes", "")).strip(),
    }


def _clean_code(text: str) -> str:
    cleaned = text.strip()
    if "```" not in cleaned:
        return cleaned
    for block in cleaned.split("```"):
        candidate = block.strip()
        if candidate.startswith("python"):
            return candidate[len("python") :].strip()
        if candidate.startswith("py"):
            return candidate[len("py") :].strip()
        if candidate.startswith("def ") or candidate.startswith("import ") or candidate.startswith("from "):
            return candidate
    return cleaned.replace("```python", "").replace("```", "").strip()
