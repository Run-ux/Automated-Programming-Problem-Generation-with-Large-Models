from __future__ import annotations

import copy
import re
from dataclasses import asdict, is_dataclass
from typing import Any


DISTANCE_WEIGHTS = {
    "I": 0.20,
    "C": 0.35,
    "O": 0.25,
    "V": 0.20,
}

OBJECTIVE_DISTANCE = {
    ("minimize", "maximize"): 1.0,
    ("minimize_value", "maximize_value"): 1.0,
    ("minimize_value", "minimize_length"): 0.35,
    ("minimize_length", "count_minimal_strings"): 0.7,
    ("minimize_length", "lexicographically_first_minimal_string"): 0.55,
    ("minimize_value", "lexicographically_first_minimal_string"): 0.7,
    ("count", "decision"): 0.7,
    ("count_minimal_strings", "lexicographically_first_minimal_string"): 0.8,
    ("count_minimal_strings", "minimize_value"): 0.8,
    ("count_minimal_strings", "minimize_length"): 0.7,
    ("lexicographically_first_minimal_string", "maximize_value"): 1.0,
}

INPUT_TYPE_DISTANCE = {
    ("array", "array"): 0.0,
    ("string", "string"): 0.0,
    ("tree", "tree"): 0.0,
    ("graph", "graph"): 0.0,
    ("tree", "graph"): 0.3,
    ("graph", "tree"): 0.3,
    ("array", "string"): 0.7,
    ("string", "array"): 0.7,
    ("array", "graph"): 1.0,
    ("graph", "array"): 1.0,
    ("string", "graph"): 1.0,
    ("graph", "string"): 1.0,
    ("tree", "array"): 1.0,
    ("array", "tree"): 1.0,
}


def dataclass_to_dict(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        return asdict(value)
    return copy.deepcopy(value)


def build_forbidden_reuse_list(original_problem: dict[str, Any] | None) -> list[str]:
    if not original_problem:
        return [
            "不要暴露原题编号、出处或链接。",
            "不要复写原题的叙事结构、输入输出关系或任务定义。",
        ]

    summary = _truncate_text(original_problem.get("description", ""), 220)
    items = [
        str(original_problem.get("problem_id", "")).strip(),
        str(original_problem.get("title", "")).strip(),
        str(original_problem.get("source", "")).strip(),
        str(original_problem.get("url", "")).strip(),
    ]
    if summary:
        items.append(summary)
    items.extend(
        [
            "不要复写原题的叙事结构、任务定义或样例套路。",
            "不要只替换实体名称后保留同样的输入输出关系。",
        ]
    )
    return [item for item in items if item]


def compute_schema_distance(
    original_schema: dict[str, Any],
    candidate_schema: dict[str, Any],
) -> dict[str, float]:
    original = _normalize_schema(original_schema)
    candidate = _normalize_schema(candidate_schema)

    i_distance = _input_distance(
        original.get("input_structure", {}),
        candidate.get("input_structure", {}),
    )
    c_distance = _constraint_distance(
        original.get("core_constraints", {}).get("constraints", []),
        candidate.get("core_constraints", {}).get("constraints", []),
    )
    o_distance = _objective_distance(
        original.get("objective", {}),
        candidate.get("objective", {}),
    )
    v_distance = _invariant_distance(
        original.get("invariant", {}).get("invariants", []),
        candidate.get("invariant", {}).get("invariants", []),
    )

    total = (
        DISTANCE_WEIGHTS["I"] * i_distance
        + DISTANCE_WEIGHTS["C"] * c_distance
        + DISTANCE_WEIGHTS["O"] * o_distance
        + DISTANCE_WEIGHTS["V"] * v_distance
    )
    return {
        "I": round(i_distance, 4),
        "C": round(c_distance, 4),
        "O": round(o_distance, 4),
        "V": round(v_distance, 4),
        "total": round(total, 4),
    }


def compute_changed_axes(
    original_schema: dict[str, Any],
    candidate_schema: dict[str, Any],
) -> list[str]:
    distance = compute_schema_distance(original_schema, candidate_schema)
    axes: list[str] = []
    if distance["I"] >= 0.18:
        axes.append("I")
    if distance["C"] >= 0.25:
        axes.append("C")
    if distance["O"] > 0.0:
        axes.append("O")
    if distance["V"] >= 0.18:
        axes.append("V")
    return axes


def _normalize_schema(raw_schema: dict[str, Any]) -> dict[str, Any]:
    schema = dataclass_to_dict(raw_schema)
    if not isinstance(schema, dict):
        return {}

    if any(key in schema for key in ("input_structure", "core_constraints", "objective", "invariant")):
        schema.setdefault("core_constraints", {"constraints": []})
        schema.setdefault("objective", {})
        schema.setdefault("invariant", {"invariants": []})
        return schema

    normalized = {
        "problem_id": schema.get("problem_id", ""),
        "source": schema.get("source", ""),
        "input_structure": schema.get("input_structure") or schema.get("I") or {},
        "core_constraints": schema.get("core_constraints")
        or {"constraints": schema.get("C", []) if isinstance(schema.get("C"), list) else []},
        "objective": schema.get("objective") or schema.get("O") or {},
        "invariant": schema.get("invariant")
        or {"invariants": schema.get("V", []) if isinstance(schema.get("V"), list) else []},
    }
    if isinstance(normalized["objective"], str):
        normalized["objective"] = {"type": normalized["objective"], "description": normalized["objective"]}
    if isinstance(normalized["core_constraints"], list):
        normalized["core_constraints"] = {"constraints": normalized["core_constraints"]}
    if isinstance(normalized["invariant"], list):
        normalized["invariant"] = {"invariants": normalized["invariant"]}
    return normalized


def _input_distance(left: dict[str, Any], right: dict[str, Any]) -> float:
    if not left and not right:
        return 0.0
    left_type = str(left.get("type", "unknown")).lower()
    right_type = str(right.get("type", "unknown")).lower()
    type_distance = INPUT_TYPE_DISTANCE.get((left_type, right_type), 0.5 if left_type == right_type else 1.0)

    pieces = [type_distance]
    pieces.extend(_range_piece(left.get("length"), right.get("length")))
    pieces.extend(_range_piece(left.get("value_range"), right.get("value_range")))
    pieces.append(_property_distance(left.get("properties", {}), right.get("properties", {})))
    return round(sum(pieces) / len(pieces), 4)


def _range_piece(left: Any, right: Any) -> list[float]:
    if not isinstance(left, dict) and not isinstance(right, dict):
        return [0.0]
    left = left or {}
    right = right or {}
    pieces: list[float] = []
    for key in ("min", "max"):
        pieces.append(_numeric_distance(left.get(key), right.get(key)))
    return pieces


def _numeric_distance(left: Any, right: Any) -> float:
    if left is None and right is None:
        return 0.0
    if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
        return 1.0 if left != right else 0.0
    if left == right:
        return 0.0
    return min(1.0, abs(left - right) / max(abs(left), abs(right), 1))


def _property_distance(left: Any, right: Any) -> float:
    left_tokens = _property_tokens(left)
    right_tokens = _property_tokens(right)
    return _jaccard_distance(left_tokens, right_tokens)


def _property_tokens(value: Any) -> set[str]:
    if not isinstance(value, dict):
        return set()
    return {f"{key}={value[key]}" for key in sorted(value)}


def _constraint_distance(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> float:
    left_tokens = {_constraint_signature(item) for item in left if item}
    right_tokens = {_constraint_signature(item) for item in right if item}
    return _jaccard_distance(left_tokens, right_tokens)


def _constraint_signature(item: dict[str, Any]) -> str:
    name = str(item.get("name", "")).strip().lower()
    description = " ".join(_tokenize_text(str(item.get("description", ""))))
    return name or description


def _objective_distance(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_type = str(left.get("type", "")).strip().lower()
    right_type = str(right.get("type", "")).strip().lower()
    if left_type == right_type:
        return 0.0
    if (left_type, right_type) in OBJECTIVE_DISTANCE:
        return OBJECTIVE_DISTANCE[(left_type, right_type)]
    if (right_type, left_type) in OBJECTIVE_DISTANCE:
        return OBJECTIVE_DISTANCE[(right_type, left_type)]
    if not left_type or not right_type:
        return 0.5
    if any(key in {left_type, right_type} for key in ("count", "decision")):
        return 0.8
    return 0.6


def _invariant_distance(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> float:
    left_tokens = {_invariant_signature(item) for item in left if item}
    right_tokens = {_invariant_signature(item) for item in right if item}
    return _jaccard_distance(left_tokens, right_tokens)


def _invariant_signature(item: dict[str, Any]) -> str:
    name = str(item.get("name", "")).strip().lower()
    description = " ".join(_tokenize_text(str(item.get("description", ""))))
    return name or description


def _jaccard_distance(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 0.0
    union = left | right
    intersection = left & right
    return 1.0 - len(intersection) / len(union)


def _tokenize_text(text: str) -> list[str]:
    lowered = text.lower()
    return re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", lowered)


def _truncate_text(text: str, limit: int) -> str:
    cleaned = " ".join(str(text).split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."
