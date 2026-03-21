from __future__ import annotations

import copy
from typing import Any


def expand_transform_space(schema: dict[str, Any]) -> dict[str, Any]:
    normalized_schema = copy.deepcopy(schema or {})
    transform_space = copy.deepcopy(normalized_schema.get("transform_space") or {})
    transform_space.setdefault("numerical_parameters", {})
    transform_space["objective_options"] = _dedupe_strings(
        transform_space.get("objective_options", [])
    )
    transform_space["structural_options"] = _dedupe_strings(
        transform_space.get("structural_options", [])
    )

    input_options = _normalize_input_options(
        transform_space.get("input_structure_options", []),
        normalized_schema,
    )
    invariant_options = _normalize_invariant_options(
        transform_space.get("invariant_options", []),
        normalized_schema,
    )

    transform_space["input_structure_options"] = _merge_named_options(
        input_options,
        _derive_input_options(normalized_schema, transform_space),
    )
    transform_space["invariant_options"] = _merge_named_options(
        invariant_options,
        _derive_invariant_options(normalized_schema, transform_space),
    )
    return transform_space


def _dedupe_strings(values: Any) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    if not isinstance(values, list):
        return results
    for item in values:
        if not isinstance(item, str):
            continue
        value = item.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        results.append(value)
    return results


def _merge_named_options(
    explicit: list[dict[str, Any]],
    derived: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for item in explicit + derived:
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        merged[name] = item
    return list(merged.values())


def _normalize_input_options(
    raw_options: Any,
    schema: dict[str, Any],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if not isinstance(raw_options, list):
        return normalized
    for item in raw_options:
        option = _normalize_input_option(item, schema)
        if option:
            normalized.append(option)
    return normalized


def _normalize_input_option(
    raw_option: Any,
    schema: dict[str, Any],
) -> dict[str, Any] | None:
    if isinstance(raw_option, str):
        return _derive_input_option_from_token(schema, raw_option)

    if not isinstance(raw_option, dict):
        return None

    name = str(raw_option.get("name") or raw_option.get("id") or "").strip()
    if not name:
        return None

    patch = copy.deepcopy(raw_option.get("patch") or raw_option.get("input_patch") or {})
    constraints = _normalize_constraints(raw_option.get("constraints", []))
    if not patch and not constraints:
        fallback = _derive_input_option_from_token(schema, name)
        if fallback:
            fallback["description"] = (
                str(raw_option.get("description") or "").strip()
                or fallback.get("description", "")
            )
        return fallback

    return {
        "name": name,
        "description": str(raw_option.get("description") or name).strip(),
        "patch": patch,
        "constraints": constraints,
    }


def _normalize_invariant_options(
    raw_options: Any,
    schema: dict[str, Any],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if not isinstance(raw_options, list):
        return normalized
    for item in raw_options:
        option = _normalize_invariant_option(item, schema)
        if option:
            normalized.append(option)
    return normalized


def _normalize_invariant_option(
    raw_option: Any,
    schema: dict[str, Any],
) -> dict[str, Any] | None:
    if isinstance(raw_option, str):
        return _derive_invariant_option_from_token(raw_option)

    if not isinstance(raw_option, dict):
        return None

    name = str(raw_option.get("name") or raw_option.get("id") or "").strip()
    if not name:
        return None

    invariants = _normalize_invariants(raw_option.get("invariants", []))
    mode = str(raw_option.get("mode", "append")).strip().lower() or "append"
    drop_names = _dedupe_strings(raw_option.get("drop_names", []))
    if not invariants and not drop_names:
        fallback = _derive_invariant_option_from_token(name)
        if fallback:
            fallback["description"] = (
                str(raw_option.get("description") or "").strip()
                or fallback.get("description", "")
            )
        return fallback

    return {
        "name": name,
        "description": str(raw_option.get("description") or name).strip(),
        "mode": mode,
        "drop_names": drop_names,
        "invariants": invariants,
    }


def _normalize_constraints(raw_constraints: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if not isinstance(raw_constraints, list):
        return normalized
    for item in raw_constraints:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        description = str(item.get("description", "")).strip()
        if not name and not description:
            continue
        normalized.append(
            {
                "name": name,
                "description": description,
            }
        )
    return normalized


def _normalize_invariants(raw_invariants: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if not isinstance(raw_invariants, list):
        return normalized
    for item in raw_invariants:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        description = str(item.get("description", "")).strip()
        if not name and not description:
            continue
        properties = item.get("properties", {})
        if not isinstance(properties, dict):
            properties = {}
        normalized.append(
            {
                "name": name,
                "description": description,
                "properties": copy.deepcopy(properties),
            }
        )
    return normalized


def _derive_input_options(
    schema: dict[str, Any],
    transform_space: dict[str, Any],
) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    for token in transform_space.get("structural_options", []):
        option = _derive_input_option_from_token(schema, token)
        if option:
            options.append(option)
    return options


def _derive_input_option_from_token(
    schema: dict[str, Any],
    token: str,
) -> dict[str, Any] | None:
    lowered = str(token).strip().lower()
    input_structure = schema.get("input_structure", {})
    value_range = input_structure.get("value_range", {}) or {}
    properties = input_structure.get("properties", {}) or {}
    current_min = value_range.get("min")
    current_max = value_range.get("max")
    max_abs = _max_abs(current_min, current_max)

    if "negative" in lowered:
        patch = {
            "value_range": {
                "min": -max_abs,
                "max": max_abs,
            }
        }
        if _input_patch_changes(input_structure, patch):
            return {
                "name": "signed_input_values",
                "description": "输入值域扩展为允许负数，题面需要显式说明可出现负值。",
                "patch": patch,
                "constraints": [
                    {
                        "name": "signed_input_values",
                        "description": "输入值允许为负数。",
                    }
                ],
            }

    if "zero" in lowered:
        patch = {
            "value_range": {
                "min": 0,
            }
        }
        if _input_patch_changes(input_structure, patch):
            return {
                "name": "zero_enabled_values",
                "description": "输入值域下界放宽到 0，使零值成为合法输入。",
                "patch": patch,
                "constraints": [
                    {
                        "name": "zero_enabled_values",
                        "description": "输入中允许出现 0。",
                    }
                ],
            }

    if "duplicate" in lowered or "repeated" in lowered:
        patch = {"properties": {"duplicate_allowed": True}}
        if _input_patch_changes(input_structure, patch):
            return {
                "name": "duplicate_friendly_input",
                "description": "输入对象允许重复出现，题面应明确重复项是合法的。",
                "patch": patch,
                "constraints": [],
            }

    if "sorted" in lowered:
        patch = {"properties": {"sorted_input": True}}
        if _input_patch_changes(input_structure, patch):
            return {
                "name": "sorted_input_view",
                "description": "输入带有显式顺序结构，可利用排序后的扫描性质。",
                "patch": patch,
                "constraints": [],
            }

    if "overlap" in lowered:
        patch = {"properties": {"overlap_allowed": True}}
        if _input_patch_changes(input_structure, patch):
            return {
                "name": "overlap_enabled_segments",
                "description": "输入对象允许重叠，题面需要体现重叠结构是合法的。",
                "patch": patch,
                "constraints": [],
            }

    if "rotation" in lowered:
        patch = {"properties": {"rotation_allowed": True}}
        if _input_patch_changes(input_structure, patch):
            return {
                "name": "rotatable_entities",
                "description": "输入对象允许旋转或方向归一化处理。",
                "patch": patch,
                "constraints": [],
            }

    if "rectangular" in lowered:
        patch = {"properties": {"rectangular_layout": True}}
        if _input_patch_changes(input_structure, patch):
            return {
                "name": "rectangular_layout_input",
                "description": "输入布局显式满足矩形结构。",
                "patch": patch,
                "constraints": [],
            }

    if "coordinate" in lowered:
        patch = {
            "value_range": {
                "min": 0,
            },
            "properties": {
                "non_negative_coordinates": True,
            },
        }
        if _input_patch_changes(input_structure, patch):
            return {
                "name": "non_negative_coordinates",
                "description": "坐标或位置索引限定为非负，题面需要强调边界从 0 开始。",
                "patch": patch,
                "constraints": [],
            }

    if "row_sum" in lowered:
        patch = {"properties": {"row_aggregated_input": True}}
        if _input_patch_changes(input_structure, patch):
            return {
                "name": "row_aggregated_input",
                "description": "输入结构更强调按行聚合的信息组织方式。",
                "patch": patch,
                "constraints": [],
            }

    return None


def _input_patch_changes(input_structure: dict[str, Any], patch: dict[str, Any]) -> bool:
    preview = copy.deepcopy(input_structure or {})
    _deep_merge(preview, patch)
    return preview != (input_structure or {})


def _max_abs(*values: Any) -> int:
    numbers = [abs(int(value)) for value in values if isinstance(value, (int, float))]
    if not numbers:
        return 10**9
    return max(numbers)


def _deep_merge(target: dict[str, Any], patch: dict[str, Any]) -> None:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
            continue
        target[key] = copy.deepcopy(value)


def _derive_invariant_options(
    schema: dict[str, Any],
    transform_space: dict[str, Any],
) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    objective_tokens = transform_space.get("objective_options", [])
    structural_tokens = transform_space.get("structural_options", [])

    for token in objective_tokens + structural_tokens:
        option = _derive_invariant_option_from_token(token)
        if option:
            options.append(option)

    if schema.get("input_structure", {}).get("type") == "array":
        options.append(
            {
                "name": "prefix_scan_invariant",
                "description": "显式引入前缀/分块扫描的不变量，便于同族但非同题的表达。",
                "mode": "append",
                "drop_names": [],
                "invariants": [
                    {
                        "name": "prefix_scan_stability",
                        "description": "前缀或分块扫描过程中，局部状态可以被稳定复用，不需要回看全部历史输入。",
                        "properties": {"scan_style": "prefix_or_block"},
                    }
                ],
            }
        )
    return options


def _derive_invariant_option_from_token(token: str) -> dict[str, Any] | None:
    lowered = str(token).strip().lower()

    if "decision" in lowered:
        return _single_invariant_option(
            "feasibility_monotonicity",
            "当目标转为判定时，可利用可行性关于阈值或步骤的单调变化。",
            "feasibility_monotonicity",
            "可行性会随着阈值、次数或资源上界的变化呈现单调性，可据此二分或逐步推进。",
            {"objective_family": "decision"},
        )

    if "count" in lowered:
        return _single_invariant_option(
            "counting_decomposition",
            "当目标转为计数时，状态可以分解为若干独立计数子结构。",
            "counting_decomposition",
            "总方案数可由若干互不重叠的子状态累积得到，允许使用 DP、容斥或分治计数。",
            {"objective_family": "count"},
        )

    if "minimize" in lowered or "maximize" in lowered:
        return _single_invariant_option(
            "dominance_pruning",
            "优化目标引入支配关系，较差状态可以被更优状态吸收。",
            "dominance_pruning",
            "存在可比较的状态支配关系，保留代表性最优状态即可推进求解。",
            {"objective_family": "optimization"},
        )

    if "negative" in lowered:
        return _single_invariant_option(
            "signed_balance",
            "允许负值后，状态转移依然依赖净贡献或相对差值。",
            "signed_balance",
            "即使输入允许负值，关键状态仍可通过净贡献、偏移或平衡量统一表示。",
            {"supports_negative_values": True},
        )

    if "zero" in lowered:
        return _single_invariant_option(
            "zero_contribution_absorption",
            "零值对象的引入不会破坏主状态，只会带来可吸收的空贡献。",
            "zero_contribution_absorption",
            "零贡献元素可以被安全吸收或跳过，不改变主要状态转移的正确性。",
            {"supports_zero_values": True},
        )

    if "duplicate" in lowered or "repeated" in lowered:
        return _single_invariant_option(
            "frequency_aggregation",
            "重复对象可以被频次聚合处理，而不必逐个区分身份。",
            "frequency_aggregation",
            "对重复输入项，只需维护频次或桶级统计，核心决策仍成立。",
            {"supports_duplicates": True},
        )

    if "sorted" in lowered:
        return _single_invariant_option(
            "ordered_scan",
            "有序输入允许单向扫描或双指针式推进。",
            "ordered_scan",
            "当关键字段有序时，状态可以通过单调扫描维护，不需要回退。",
            {"requires_ordered_input": True},
        )

    if "overlap" in lowered:
        return _single_invariant_option(
            "overlap_conflict_resolution",
            "重叠结构下仍可通过局部冲突消解维持全局正确性。",
            "overlap_conflict_resolution",
            "对象存在重叠时，关键状态只依赖有限的边界冲突信息，可局部消解。",
            {"supports_overlap": True},
        )

    if "rotation" in lowered:
        return _single_invariant_option(
            "orientation_normalization",
            "方向或旋转差异可先归一化，再进入统一状态转移。",
            "orientation_normalization",
            "旋转后的对象可通过标准朝向归一化，主算法只需处理规范化表示。",
            {"supports_rotation": True},
        )

    if "rectangular" in lowered or "row_sum" in lowered:
        return _single_invariant_option(
            "row_column_separability",
            "矩形或按行聚合结构下，行列信息可分离维护。",
            "row_column_separability",
            "局部状态可以按行或按列分离维护，再汇总成全局答案。",
            {"grid_like": True},
        )

    if "same_programs" in lowered:
        return _single_invariant_option(
            "adjacency_state_tracking",
            "相邻冲突约束只需维护上一状态或局部邻接信息。",
            "adjacency_state_tracking",
            "为了避免相邻对象相同，只需额外记录最近一步的类别或邻接状态。",
            {"adjacency_sensitive": True},
        )

    return None


def _single_invariant_option(
    name: str,
    description: str,
    invariant_name: str,
    invariant_description: str,
    properties: dict[str, Any],
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "mode": "append",
        "drop_names": [],
        "invariants": [
            {
                "name": invariant_name,
                "description": invariant_description,
                "properties": properties,
            }
        ],
    }
