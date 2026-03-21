from __future__ import annotations

import random
from dataclasses import asdict
from itertools import combinations, product
from typing import Any

from models import DifferencePlan, Theme, VariantPlan
from schema_tools import (
    build_forbidden_reuse_list,
    build_instantiated_schema,
    compute_changed_axes,
    compute_schema_distance,
)
from transform_space_tools import expand_transform_space


THEMES = [
    Theme(
        theme_id="cyber_city",
        name="赛博城市调度",
        tone="冷静、工程化、略带未来感",
        keywords=["节点", "数据流", "权限", "缓存", "链路", "控制台"],
        mapping_hint="把原始结构映射成网络节点、任务包或访问记录。",
    ),
    Theme(
        theme_id="arcane_lab",
        name="奥术实验室",
        tone="神秘、规则驱动、强调仪式感",
        keywords=["符文", "法阵", "共鸣", "晶核", "炼成", "序列"],
        mapping_hint="把状态变化映射成符文叠加、法阵拼接或能量共鸣。",
    ),
    Theme(
        theme_id="interstellar_logistics",
        name="星际物流",
        tone="宏观、任务导向、强调资源与路径",
        keywords=["货舱", "航线", "补给", "跃迁", "殖民地", "调度中心"],
        mapping_hint="把对象映射成货物、航线、站点、任务波次。",
    ),
    Theme(
        theme_id="campus_ops",
        name="校园运营",
        tone="日常、轻松、贴近现实",
        keywords=["社团", "教室", "队伍", "课表", "仓库", "窗口"],
        mapping_hint="把抽象约束映射成排队、分配、排课或借还流程。",
    ),
]


class VariantPlanner:
    MIN_DISTANCE = 0.35
    MAX_DISTANCE = 0.60
    MAX_PARAMETER_CANDIDATES = 6
    MAX_STRUCTURAL_CANDIDATES = 6
    MAX_INPUT_OPTION_CANDIDATES = 4
    MAX_INVARIANT_OPTION_CANDIDATES = 4

    def __init__(self, seed: int | None = None):
        self.seed = seed if seed is not None else random.randrange(1, 10**9)

    def build_plan(
        self,
        schema: dict[str, Any],
        variant_index: int,
        theme_id: str | None = None,
        original_schema: dict[str, Any] | None = None,
        original_problem: dict[str, Any] | None = None,
    ) -> VariantPlan:
        rng = random.Random(self.seed + variant_index)
        theme = self._select_theme(rng, theme_id)
        normalized_schema = dict(schema)
        normalized_schema["transform_space"] = expand_transform_space(schema)
        source_schema = original_schema or schema

        candidate = self._pick_difference_candidate(
            schema=normalized_schema,
            source_schema=source_schema,
            theme=theme,
            rng=rng,
        )
        snapshot = candidate["instantiated_schema"]
        difference_plan = DifferencePlan(
            target_distance_band={"min": self.MIN_DISTANCE, "max": self.MAX_DISTANCE},
            changed_axes=candidate["changed_axes"],
            same_family_allowed=True,
            forbidden_reuse=build_forbidden_reuse_list(original_problem),
            rationale=self._build_difference_rationale(candidate),
        )

        return VariantPlan(
            problem_id=schema.get("problem_id", "unknown"),
            variant_index=variant_index,
            seed=self.seed + variant_index,
            theme=theme,
            objective=candidate["objective"],
            numerical_parameters=candidate["numerical_parameters"],
            structural_options=candidate["structural_options"],
            input_structure_options=candidate["input_structure_options"],
            invariant_options=candidate["invariant_options"],
            difficulty=self._infer_difficulty(schema),
            input_summary=self._summarize_input_structure(snapshot["input_structure"]),
            constraint_summary=self._summarize_constraints(
                snapshot["core_constraints"].get("constraints", [])
            ),
            invariant_summary=self._summarize_invariants(
                snapshot["invariant"].get("invariants", [])
            ),
            difference_plan=difference_plan,
            instantiated_schema_snapshot=candidate["instantiated_schema_object"],
            predicted_schema_distance=candidate["distance"]["total"],
            distance_breakdown=candidate["distance"],
            changed_axes_realized=candidate["changed_axes"],
        )

    def _pick_difference_candidate(
        self,
        schema: dict[str, Any],
        source_schema: dict[str, Any],
        theme: Theme,
        rng: random.Random,
    ) -> dict[str, Any]:
        transform_space = schema.get("transform_space", {})
        objectives = self._objective_candidates(schema, transform_space, rng)
        parameter_sets = self._parameter_candidates(schema, transform_space, rng)
        structural_sets = self._structural_option_candidates(transform_space, rng)
        input_sets = self._input_structure_option_candidates(transform_space, rng)
        invariant_sets = self._invariant_option_candidates(transform_space, rng)
        difficulty = self._infer_difficulty(schema)
        theme_payload = {
            "id": theme.theme_id,
            "name": theme.name,
            "tone": theme.tone,
            "keywords": list(theme.keywords),
            "mapping_hint": theme.mapping_hint,
        }

        best: dict[str, Any] | None = None
        for objective, numerical_parameters, structural_options, input_options, invariant_options in product(
            objectives,
            parameter_sets,
            structural_sets,
            input_sets,
            invariant_sets,
        ):
            instantiated = build_instantiated_schema(
                schema=schema,
                objective=objective,
                numerical_parameters=numerical_parameters,
                structural_options=structural_options,
                input_options=input_options,
                invariant_options=invariant_options,
                theme=theme_payload,
                difficulty=difficulty,
            )
            snapshot = asdict(instantiated)
            distance = compute_schema_distance(source_schema, snapshot)
            changed_axes = compute_changed_axes(source_schema, snapshot)
            candidate = {
                "objective": objective,
                "numerical_parameters": numerical_parameters,
                "structural_options": structural_options,
                "input_structure_options": [
                    item.get("name", "") for item in input_options if item.get("name")
                ],
                "invariant_options": [
                    item.get("name", "") for item in invariant_options if item.get("name")
                ],
                "instantiated_schema": snapshot,
                "instantiated_schema_object": instantiated,
                "distance": distance,
                "changed_axes": changed_axes,
            }
            if best is None or self._is_better_candidate(candidate, best, rng):
                best = candidate

        if best is None:
            fallback_objective = self._current_objective(schema)
            fallback_parameters = {}
            fallback_structural_options: list[str] = []
            fallback_input_options: list[dict[str, Any]] = []
            fallback_invariant_options: list[dict[str, Any]] = []
            instantiated = build_instantiated_schema(
                schema=schema,
                objective=fallback_objective,
                numerical_parameters=fallback_parameters,
                structural_options=fallback_structural_options,
                input_options=fallback_input_options,
                invariant_options=fallback_invariant_options,
                theme=theme_payload,
                difficulty=difficulty,
            )
            snapshot = asdict(instantiated)
            return {
                "objective": fallback_objective,
                "numerical_parameters": fallback_parameters,
                "structural_options": fallback_structural_options,
                "input_structure_options": [],
                "invariant_options": [],
                "instantiated_schema": snapshot,
                "instantiated_schema_object": instantiated,
                "distance": compute_schema_distance(source_schema, snapshot),
                "changed_axes": compute_changed_axes(source_schema, snapshot),
            }
        return best

    def _is_better_candidate(
        self,
        candidate: dict[str, Any],
        current: dict[str, Any],
        rng: random.Random,
    ) -> bool:
        candidate_score = self._candidate_score(candidate)
        current_score = self._candidate_score(current)
        if candidate_score != current_score:
            return candidate_score > current_score
        return rng.random() > 0.5

    def _candidate_score(self, candidate: dict[str, Any]) -> tuple[float, ...]:
        distance = candidate["distance"]["total"]
        core_axes = len(
            [axis for axis in candidate["changed_axes"] if axis in {"I", "C", "O", "V", "T"}]
        )
        within_band = self.MIN_DISTANCE <= distance < self.MAX_DISTANCE
        above_min = distance >= self.MIN_DISTANCE
        target_mid = (self.MIN_DISTANCE + self.MAX_DISTANCE) / 2
        closeness = -abs(distance - target_mid)
        option_count = (
            len(candidate["structural_options"])
            + len(candidate["input_structure_options"])
            + len(candidate["invariant_options"])
        )
        return (
            1.0 if within_band and core_axes >= 2 else 0.0,
            1.0 if above_min and core_axes >= 2 else 0.0,
            float(core_axes),
            closeness,
            distance,
            float(option_count),
        )

    def _select_theme(self, rng: random.Random, theme_id: str | None) -> Theme:
        if theme_id:
            for theme in THEMES:
                if theme.theme_id == theme_id:
                    return theme
            raise ValueError(f"Unknown theme_id: {theme_id}")
        return rng.choice(THEMES)

    def _objective_candidates(
        self,
        schema: dict[str, Any],
        transform_space: dict[str, Any],
        rng: random.Random,
    ) -> list[dict[str, Any]]:
        original = self._current_objective(schema)
        options = transform_space.get("objective_options", [])
        candidates: list[dict[str, Any]] = []
        for option in options:
            if option == original.get("type"):
                continue
            candidates.append(
                {
                    "type": option,
                    "description": self._describe_objective(option, original.get("description", "")),
                }
            )
        if not candidates:
            return [original]
        rng.shuffle(candidates)
        return candidates[:3]

    def _parameter_candidates(
        self,
        schema: dict[str, Any],
        transform_space: dict[str, Any],
        rng: random.Random,
    ) -> list[dict[str, Any]]:
        specs = transform_space.get("numerical_parameters", {})
        if not specs:
            return [{}]

        original_length = schema.get("input_structure", {}).get("length", {})
        fixed_length = (
            original_length.get("min")
            if isinstance(original_length.get("min"), int)
            and original_length.get("min") == original_length.get("max")
            else None
        )
        fields: list[list[tuple[str, dict[str, Any]]]] = []
        for name, spec in specs.items():
            min_value = spec.get("min")
            max_value = spec.get("max")
            description = spec.get("description", "")
            choices: list[Any] = []
            if isinstance(min_value, int) and isinstance(max_value, int):
                candidate_values = {
                    min_value,
                    max_value,
                    (min_value + max_value) // 2,
                    rng.randint(min_value, max_value),
                }
                if fixed_length is not None and any(
                    token in f"{name} {description}".lower()
                    for token in ("number of", "count", "substrings", "items", "segments")
                ):
                    for delta in (-1, 1, -2, 2):
                        value = fixed_length + delta
                        if min_value <= value <= max_value and value != fixed_length:
                            candidate_values.add(value)
                choices = sorted(candidate_values)
            else:
                choices = [spec.get("default", "N/A")]

            fields.append(
                [
                    (
                        name,
                        {
                            "value": value,
                            "min": min_value,
                            "max": max_value,
                            "description": description,
                        },
                    )
                    for value in choices[:5]
                ]
            )

        candidates: list[dict[str, Any]] = []
        for combination in product(*fields):
            candidate = {name: payload for name, payload in combination}
            candidates.append(candidate)
            if len(candidates) >= self.MAX_PARAMETER_CANDIDATES:
                break
        if not candidates:
            return [{}]
        rng.shuffle(candidates)
        return candidates

    def _structural_option_candidates(
        self,
        transform_space: dict[str, Any],
        rng: random.Random,
    ) -> list[list[str]]:
        options = list(transform_space.get("structural_options", []))
        if not options:
            return [[]]

        subsets: list[list[str]] = []
        for size in (1, 2):
            for combo in combinations(options, min(size, len(options))):
                subsets.append(list(combo))
                if len(combo) == len(options):
                    break
        rng.shuffle(subsets)
        return ([[]] + subsets[: self.MAX_STRUCTURAL_CANDIDATES]) or [[]]

    def _input_structure_option_candidates(
        self,
        transform_space: dict[str, Any],
        rng: random.Random,
    ) -> list[list[dict[str, Any]]]:
        return self._option_payload_candidates(
            transform_space.get("input_structure_options", []),
            rng,
            max_sets=self.MAX_INPUT_OPTION_CANDIDATES,
        )

    def _invariant_option_candidates(
        self,
        transform_space: dict[str, Any],
        rng: random.Random,
    ) -> list[list[dict[str, Any]]]:
        return self._option_payload_candidates(
            transform_space.get("invariant_options", []),
            rng,
            max_sets=self.MAX_INVARIANT_OPTION_CANDIDATES,
        )

    def _option_payload_candidates(
        self,
        raw_options: list[dict[str, Any]],
        rng: random.Random,
        max_sets: int,
    ) -> list[list[dict[str, Any]]]:
        options = [item for item in raw_options if isinstance(item, dict) and item.get("name")]
        if not options:
            return [[]]

        subsets: list[list[dict[str, Any]]] = [[]]
        staged: list[list[dict[str, Any]]] = []
        max_size = min(2, len(options))
        for size in range(1, max_size + 1):
            for combo in combinations(options, size):
                staged.append(list(combo))
        rng.shuffle(staged)
        subsets.extend(staged[: max(0, max_sets - 1)])
        return subsets

    def _current_objective(self, schema: dict[str, Any]) -> dict[str, Any]:
        objective = schema.get("objective", {})
        return {
            "type": objective.get("type", "unknown"),
            "description": objective.get("description", ""),
        }

    def _infer_difficulty(self, schema: dict[str, Any]) -> str:
        invariants = schema.get("invariant", {}).get("invariants", [])
        constraints = schema.get("core_constraints", {}).get("constraints", [])
        score = len(invariants) + len(constraints)
        if score <= 2:
            return "Easy"
        if score <= 4:
            return "Medium"
        return "Hard"

    def _summarize_input_structure(self, data: dict[str, Any]) -> str:
        input_type = data.get("type", "unknown")
        length = data.get("length", {})
        value_range = data.get("value_range", {})
        parts = [f"类型={input_type}"]
        if length:
            parts.append(f"长度范围={length.get('min', '?')}..{length.get('max', '?')}")
        if value_range:
            parts.append(
                f"值范围={value_range.get('min', '?')}..{value_range.get('max', '?')}"
            )
        properties = data.get("properties", {})
        if properties:
            props = ", ".join(f"{key}={value}" for key, value in properties.items())
            parts.append(f"属性={props}")
        return "；".join(parts)

    def _summarize_constraints(self, constraints: list[dict[str, Any]]) -> list[str]:
        return [item.get("description", "") for item in constraints if item.get("description")]

    def _summarize_invariants(self, invariants: list[dict[str, Any]]) -> list[str]:
        return [item.get("description", "") for item in invariants if item.get("description")]

    def _build_difference_rationale(self, candidate: dict[str, Any]) -> str:
        distance = candidate["distance"]["total"]
        axes = ", ".join(candidate["changed_axes"]) or "无"
        structural = ", ".join(candidate["structural_options"]) or "无"
        input_options = ", ".join(candidate["input_structure_options"]) or "无"
        invariant_options = ", ".join(candidate["invariant_options"]) or "无"
        objective = candidate["objective"].get("type", "unknown")
        if distance < self.MIN_DISTANCE or len(candidate["changed_axes"]) < 2:
            return (
                "当前 transform_space 无法稳定支撑中等差异目标。"
                f" 已尝试 objective={objective}、structural_options={structural}、"
                f"input_options={input_options}、invariant_options={invariant_options}，"
                f"预测距离={distance:.2f}，落地轴={axes}。"
            )
        return (
            "该方案保持同族算法线索，但通过目标函数、结构选项、输入视角与不变量提示拉开差异。"
            f" objective={objective}，structural_options={structural}，"
            f"input_options={input_options}，invariant_options={invariant_options}，"
            f"预测距离={distance:.2f}，落地轴={axes}。"
        )

    def _describe_objective(self, objective_type: str, fallback: str) -> str:
        mapping = {
            "minimize": "求最小代价或最小长度。",
            "minimize_length": "求满足条件的最短结果。",
            "minimize_value": "求满足条件的最小值。",
            "maximize": "求最大收益或最大可行值。",
            "maximize_value": "求满足条件的最大值。",
            "count": "统计满足条件的方案数。",
            "count_minimal_strings": "统计达到最优结果的方案数。",
            "enumeration": "统计所有满足条件的对象数量。",
            "decision": "判断是否存在满足条件的方案。",
            "boolean_decision": "判断方案是否存在。",
            "lexicographically_first_minimal_string": "求最优结果中字典序最小的构造。",
        }
        return mapping.get(objective_type, fallback or objective_type)
