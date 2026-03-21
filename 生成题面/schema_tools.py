from __future__ import annotations

import copy
import re
from dataclasses import asdict, is_dataclass
from typing import Any

from models import InstantiatedSchema


DISTANCE_WEIGHTS = {
    "I": 0.15,
    "C": 0.25,
    "O": 0.15,
    "V": 0.35,
    "T": 0.10,
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

STRUCTURAL_OPTION_ALIASES = {
    "must_contain_in_order": {
        "constraint_name": "must_contain_in_order",
        "description": "目标对象需要按给定顺序覆盖所有输入项。",
        "property_key": "ordered",
        "property_value": True,
    },
    "cyclic_string": {
        "constraint_name": "cyclic_string",
        "description": "结果对象按循环意义处理，允许首尾相接形成匹配。",
        "property_key": "cyclic",
        "property_value": True,
    },
}


def build_instantiated_schema(
    schema: dict[str, Any],
    objective: dict[str, Any],
    numerical_parameters: dict[str, Any],
    structural_options: list[str],
    input_options: list[dict[str, Any]],
    invariant_options: list[dict[str, Any]],
    theme: dict[str, Any] | None,
    difficulty: str,
) -> InstantiatedSchema:
    normalized = _normalize_schema(schema)
    input_structure = copy.deepcopy(normalized.get("input_structure", {}))
    core_constraints = copy.deepcopy(normalized.get("core_constraints", {"constraints": []}))
    objective_copy = copy.deepcopy(objective)
    invariant = copy.deepcopy(normalized.get("invariant", {"invariants": []}))

    snapshot = {
        "problem_id": normalized.get("problem_id", "unknown"),
        "source": normalized.get("source", ""),
        "input_structure": input_structure,
        "core_constraints": core_constraints,
        "objective": objective_copy,
        "invariant": invariant,
        "instantiated_parameters": copy.deepcopy(numerical_parameters),
        "selected_structural_options": list(structural_options),
        "selected_input_options": [item.get("name", "") for item in input_options if item.get("name")],
        "selected_invariant_options": [
            item.get("name", "") for item in invariant_options if item.get("name")
        ],
        "theme": copy.deepcopy(theme or {}),
        "difficulty": difficulty,
    }
    _apply_parameter_overrides(snapshot)
    _apply_input_options(snapshot, input_options)
    _apply_structural_options(snapshot)
    _apply_invariant_options(snapshot, invariant_options)
    return InstantiatedSchema(**snapshot)


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
    t_distance = _transform_distance(original, candidate)

    total = (
        DISTANCE_WEIGHTS["I"] * i_distance
        + DISTANCE_WEIGHTS["C"] * c_distance
        + DISTANCE_WEIGHTS["O"] * o_distance
        + DISTANCE_WEIGHTS["V"] * v_distance
        + DISTANCE_WEIGHTS["T"] * t_distance
    )
    return {
        "I": round(i_distance, 4),
        "C": round(c_distance, 4),
        "O": round(o_distance, 4),
        "V": round(v_distance, 4),
        "T": round(t_distance, 4),
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
    if distance["C"] >= 0.25 or _normalize_schema(candidate_schema).get(
        "selected_structural_options"
    ):
        axes.append("C")
    if distance["O"] > 0.0:
        axes.append("O")
    if distance["V"] >= 0.18:
        axes.append("V")
    if distance["T"] >= 0.3 and any(axis in axes for axis in ("I", "C", "O", "V")):
        axes.append("T")
    return axes


def _normalize_schema(raw_schema: dict[str, Any]) -> dict[str, Any]:
    schema = dataclass_to_dict(raw_schema)
    if not isinstance(schema, dict):
        return {}

    if "input_structure" in schema or "instantiated_parameters" in schema:
        schema.setdefault("core_constraints", {"constraints": []})
        schema.setdefault("objective", {})
        schema.setdefault("invariant", {"invariants": []})
        schema.setdefault("selected_structural_options", [])
        schema.setdefault("selected_input_options", [])
        schema.setdefault("selected_invariant_options", [])
        return schema

    normalized = {
        "problem_id": schema.get("problem_id", ""),
        "source": schema.get("source", ""),
        "input_structure": schema.get("input_structure") or schema.get("I") or {},
        "core_constraints": schema.get("core_constraints")
        or {"constraints": schema.get("C", []) if isinstance(schema.get("C"), list) else []},
        "objective": schema.get("objective")
        or schema.get("O")
        or {},
        "invariant": schema.get("invariant")
        or {"invariants": schema.get("V", []) if isinstance(schema.get("V"), list) else []},
        "selected_structural_options": schema.get("selected_structural_options", []),
        "selected_input_options": schema.get("selected_input_options", []),
        "selected_invariant_options": schema.get("selected_invariant_options", []),
        "instantiated_parameters": schema.get("instantiated_parameters", {}),
    }
    if isinstance(normalized["objective"], str):
        normalized["objective"] = {"type": normalized["objective"], "description": normalized["objective"]}
    if isinstance(normalized["core_constraints"], list):
        normalized["core_constraints"] = {"constraints": normalized["core_constraints"]}
    if isinstance(normalized["invariant"], list):
        normalized["invariant"] = {"invariants": normalized["invariant"]}
    normalized.setdefault("transform_space", schema.get("transform_space", {}))
    return normalized


def _apply_parameter_overrides(snapshot: dict[str, Any]) -> None:
    input_structure = snapshot.get("input_structure", {})
    constraints = snapshot.setdefault("core_constraints", {}).setdefault("constraints", [])
    parameters = snapshot.get("instantiated_parameters", {})

    for name, spec in parameters.items():
        value = spec.get("value")
        description = str(spec.get("description", ""))
        if value is None:
            continue

        if _looks_like_count_parameter(name, description) and isinstance(value, int):
            length = input_structure.setdefault("length", {})
            if isinstance(length, dict):
                length["min"] = value
                length["max"] = value
            properties = input_structure.setdefault("properties", {})
            if isinstance(properties, dict):
                properties["fixed_item_count"] = value
            constraints.append(
                _constraint_item(
                    name=f"fixed_{_slugify(name)}",
                    description=f"输入项数量固定为 {value}。",
                )
            )
            _rewrite_count_mentions(constraints, value)
            continue

        if _looks_like_length_limit_parameter(name, description) and isinstance(value, int):
            value_range = input_structure.setdefault("value_range", {})
            if isinstance(value_range, dict):
                value_range["max"] = value
            constraints.append(
                _constraint_item(
                    name=f"materialized_{_slugify(name)}",
                    description=f"{description or name} 固定为不超过 {value}。",
                )
            )


def _apply_input_options(
    snapshot: dict[str, Any],
    input_options: list[dict[str, Any]],
) -> None:
    input_structure = snapshot.setdefault("input_structure", {})
    constraints = snapshot.setdefault("core_constraints", {}).setdefault("constraints", [])

    for option in input_options:
        patch = option.get("patch", {})
        if isinstance(patch, dict):
            _deep_merge_dict(input_structure, patch)

        for item in option.get("constraints", []):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            description = str(item.get("description", "")).strip()
            if not name and not description:
                continue
            constraints.append(
                _constraint_item(
                    name=name or option.get("name", "input_option"),
                    description=description or option.get("description", ""),
                )
            )


def _apply_structural_options(snapshot: dict[str, Any]) -> None:
    input_structure = snapshot.get("input_structure", {})
    constraints = snapshot.setdefault("core_constraints", {}).setdefault("constraints", [])
    properties = input_structure.setdefault("properties", {})
    if not isinstance(properties, dict):
        properties = {}
        input_structure["properties"] = properties

    for option in snapshot.get("selected_structural_options", []):
        meta = STRUCTURAL_OPTION_ALIASES.get(option)
        if meta is None:
            constraints.append(
                _constraint_item(
                    name=option,
                    description=f"启用结构选项：{option}。",
                )
            )
            continue

        properties[meta["property_key"]] = meta["property_value"]
        constraints.append(
            _constraint_item(
                name=meta["constraint_name"],
                description=meta["description"],
            )
        )


def _apply_invariant_options(
    snapshot: dict[str, Any],
    invariant_options: list[dict[str, Any]],
) -> None:
    invariant_bucket = snapshot.setdefault("invariant", {}).setdefault("invariants", [])
    if not isinstance(invariant_bucket, list):
        invariant_bucket = []
        snapshot["invariant"]["invariants"] = invariant_bucket

    for option in invariant_options:
        mode = str(option.get("mode", "append")).strip().lower()
        drop_names = {
            str(name).strip().lower()
            for name in option.get("drop_names", [])
            if str(name).strip()
        }
        if drop_names:
            invariant_bucket[:] = [
                item
                for item in invariant_bucket
                if str(item.get("name", "")).strip().lower() not in drop_names
            ]

        normalized = [
            {
                "name": str(item.get("name", "")).strip(),
                "description": str(item.get("description", "")).strip(),
                "properties": copy.deepcopy(item.get("properties", {}))
                if isinstance(item.get("properties", {}), dict)
                else {},
            }
            for item in option.get("invariants", [])
            if isinstance(item, dict)
            and (str(item.get("name", "")).strip() or str(item.get("description", "")).strip())
        ]
        if not normalized:
            continue

        if mode == "replace":
            invariant_bucket[:] = normalized
            continue

        existing = {_invariant_signature(item) for item in invariant_bucket if item}
        for item in normalized:
            signature = _invariant_signature(item)
            if signature in existing:
                continue
            invariant_bucket.append(item)
            existing.add(signature)


def _constraint_item(name: str, description: str) -> dict[str, str]:
    return {
        "name": name,
        "description": description,
    }


def _rewrite_count_mentions(constraints: list[dict[str, Any]], count: int) -> None:
    replacements = [
        (r"三个", f"{count}个"),
        (r"three", str(count)),
        (r"\b3\b", str(count)),
    ]
    for item in constraints:
        description = str(item.get("description", ""))
        for pattern, replacement in replacements:
            description = re.sub(pattern, replacement, description, flags=re.IGNORECASE)
        item["description"] = description


def _looks_like_count_parameter(name: str, description: str) -> bool:
    text = f"{name} {description}".lower()
    return any(
        keyword in text
        for keyword in (
            "number of",
            "count of",
            "substrings",
            "strings to combine",
            "k_substrings",
            "items",
            "segments",
        )
    )


def _looks_like_length_limit_parameter(name: str, description: str) -> bool:
    text = f"{name} {description}".lower()
    return any(
        keyword in text
        for keyword in (
            "maximum length",
            "length constraint",
            "max length",
            "size limit",
        )
    )


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


def _transform_distance(original: dict[str, Any], candidate: dict[str, Any]) -> float:
    candidate_params = candidate.get("instantiated_parameters", {}) or {}
    candidate_options = list(candidate.get("selected_structural_options", []) or [])
    candidate_input_options = list(candidate.get("selected_input_options", []) or [])
    candidate_invariant_options = list(candidate.get("selected_invariant_options", []) or [])
    all_options = candidate_options + candidate_input_options + candidate_invariant_options
    if not candidate_params and not all_options:
        return 0.0

    scores: list[float] = []
    for name, spec in candidate_params.items():
        value = spec.get("value")
        description = str(spec.get("description", ""))
        minimum = spec.get("min")
        maximum = spec.get("max")
        baseline = _infer_parameter_baseline(original, name, description)

        if isinstance(value, (int, float)) and isinstance(baseline, (int, float)):
            denominator = max(abs(baseline), abs((maximum or value) - (minimum or value)), 1)
            scores.append(min(1.0, abs(value - baseline) / denominator))
            continue

        if all(isinstance(item, (int, float)) for item in (value, minimum, maximum)) and maximum > minimum:
            midpoint = (minimum + maximum) / 2
            scores.append(min(1.0, abs(value - midpoint) / max((maximum - minimum) / 2, 1)))
            continue

        scores.append(0.4)

    if all_options:
        scores.append(min(1.0, 0.5 + 0.15 * len(all_options)))

    return round(sum(scores) / len(scores), 4) if scores else 0.0


def _infer_parameter_baseline(
    original: dict[str, Any],
    name: str,
    description: str,
) -> int | float | None:
    text = f"{name} {description}".lower()
    input_structure = original.get("input_structure", {})
    length = input_structure.get("length", {}) or {}
    value_range = input_structure.get("value_range", {}) or {}

    current_match = re.search(r"currently\s+(\d+)", text)
    if current_match:
        return int(current_match.group(1))

    if any(keyword in text for keyword in ("number of", "count of", "substrings", "items", "segments")):
        fixed_length = _extract_fixed_value(length)
        if fixed_length is not None:
            return fixed_length

    if any(keyword in text for keyword in ("maximum length", "length constraint", "max length", "size limit")):
        if isinstance(value_range.get("max"), (int, float)):
            return value_range["max"]
        if isinstance(length.get("max"), (int, float)):
            return length["max"]

    return None


def _extract_fixed_value(length: dict[str, Any]) -> int | None:
    minimum = length.get("min")
    maximum = length.get("max")
    if isinstance(minimum, int) and minimum == maximum:
        return minimum
    return None


def _jaccard_distance(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 0.0
    union = left | right
    intersection = left & right
    return 1.0 - len(intersection) / len(union)


def _tokenize_text(text: str) -> list[str]:
    lowered = text.lower()
    return re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", lowered)


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower())
    return slug.strip("_") or "field"


def _truncate_text(text: str, limit: int) -> str:
    cleaned = " ".join(str(text).split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def _deep_merge_dict(target: dict[str, Any], patch: dict[str, Any]) -> None:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge_dict(target[key], value)
            continue
        target[key] = copy.deepcopy(value)
