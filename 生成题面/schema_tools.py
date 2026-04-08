from __future__ import annotations

import copy
import importlib.util
import json
import math
import re
import sys
from dataclasses import asdict, dataclass, is_dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from config import DEFAULT_DISTANCE_CACHE_DIR, DEFAULT_EMBEDDING_MODEL, PROJECT_ROOT


DISTANCE_VERSION = "v2"
TOTAL_WEIGHTS = {
    "I": 0.25,
    "C": 0.30,
    "O": 0.25,
    "V": 0.20,
}
AXIS_THRESHOLDS = {
    "I": 0.18,
    "C": 0.25,
    "O": 0.18,
    "V": 0.18,
}


@dataclass
class InputTreeNode:
    kind: str
    label: str
    value: Any = None
    children: list["InputTreeNode"] | None = None

    def __post_init__(self) -> None:
        self.children = list(self.children or [])


class SimilarityBackend:
    def __init__(self, embedding_client: Any | None):
        self.embedding_client = embedding_client
        self.embedding_model = str(
            getattr(embedding_client, "embedding_model", "") or DEFAULT_EMBEDDING_MODEL
        )
        self.backend = "embedding" if embedding_client and hasattr(embedding_client, "embed_texts") else "lexical_fallback"
        self._vector_cache: dict[str, list[float]] = {}
        self._cache_dirty = False
        self._file_cache_path = self._resolve_cache_path(embedding_client)
        self._file_cache: dict[str, list[float]] = self._load_file_cache(self._file_cache_path)

    def similarity(self, left: str, right: str) -> float:
        normalized_left = _normalize_text(left)
        normalized_right = _normalize_text(right)
        if not normalized_left and not normalized_right:
            return 1.0
        if normalized_left == normalized_right:
            return 1.0

        if self.backend == "embedding":
            try:
                left_vector = self._get_vector(normalized_left)
                right_vector = self._get_vector(normalized_right)
                return _cosine_similarity(left_vector, right_vector)
            except Exception:
                self.backend = "lexical_fallback"

        return _lexical_similarity(normalized_left, normalized_right)

    def distance(self, left: str, right: str) -> float:
        return round(1.0 - self.similarity(left, right), 4)

    def flush(self) -> None:
        if not self._cache_dirty or self._file_cache_path is None:
            return
        self._file_cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {key: value for key, value in sorted(self._file_cache.items())}
        self._file_cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._cache_dirty = False

    def _get_vector(self, text: str) -> list[float]:
        cache_key = f"{self.embedding_model}|||{text}"
        if cache_key in self._vector_cache:
            return self._vector_cache[cache_key]
        if cache_key in self._file_cache:
            vector = [float(item) for item in self._file_cache[cache_key]]
            self._vector_cache[cache_key] = vector
            return vector
        if not self.embedding_client or not hasattr(self.embedding_client, "embed_texts"):
            raise RuntimeError("embedding client unavailable")
        vectors = self.embedding_client.embed_texts([text], model=self.embedding_model)
        if not vectors or not isinstance(vectors[0], list):
            raise RuntimeError("embedding vector missing")
        vector = [float(item) for item in vectors[0]]
        self._vector_cache[cache_key] = vector
        if self._file_cache_path is not None:
            self._file_cache[cache_key] = vector
            self._cache_dirty = True
        return vector

    def _resolve_cache_path(self, embedding_client: Any | None) -> Path | None:
        if embedding_client is not None and hasattr(embedding_client, "distance_cache_path"):
            value = getattr(embedding_client, "distance_cache_path")
            if value is None:
                return None
            return Path(value)
        return DEFAULT_DISTANCE_CACHE_DIR / "schema_distance_embeddings.json"

    def _load_file_cache(self, cache_path: Path | None) -> dict[str, list[float]]:
        if cache_path is None or not cache_path.exists():
            return {}
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(payload, dict):
            return {}
        normalized: dict[str, list[float]] = {}
        for key, value in payload.items():
            if isinstance(key, str) and isinstance(value, list):
                normalized[key] = [float(item) for item in value]
        return normalized


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
    embedding_client: Any | None = None,
) -> dict[str, Any]:
    original = _normalize_schema(original_schema)
    candidate = _normalize_schema(candidate_schema)
    similarity_backend = SimilarityBackend(embedding_client)

    try:
        i_distance = _input_distance(
            original.get("input_structure", {}),
            candidate.get("input_structure", {}),
            similarity_backend,
        )
        c_distance = _constraint_distance(
            original.get("core_constraints", {}).get("constraints", []),
            candidate.get("core_constraints", {}).get("constraints", []),
            similarity_backend,
        )
        objective_components = _objective_distance(
            original.get("objective", {}),
            candidate.get("objective", {}),
            similarity_backend,
        )
        v_distance = _invariant_distance(
            original.get("invariant", {}).get("invariants", []),
            candidate.get("invariant", {}).get("invariants", []),
            similarity_backend,
        )
    finally:
        similarity_backend.flush()

    o_distance = objective_components["total"]
    axis_scores = {
        "I": round(i_distance, 4),
        "C": round(c_distance, 4),
        "O": round(o_distance, 4),
        "V": round(v_distance, 4),
    }
    total = (
        TOTAL_WEIGHTS["I"] * axis_scores["I"]
        + TOTAL_WEIGHTS["C"] * axis_scores["C"]
        + TOTAL_WEIGHTS["O"] * axis_scores["O"]
        + TOTAL_WEIGHTS["V"] * axis_scores["V"]
    )
    return {
        "distance_version": DISTANCE_VERSION,
        "backend": similarity_backend.backend,
        "total": round(total, 4),
        "axis_scores": axis_scores,
        "components": {
            "input_tree_distance": axis_scores["I"],
            "constraint_match_distance": axis_scores["C"],
            "objective_type_distance": round(objective_components["type"], 4),
            "objective_text_distance": round(objective_components["text"], 4),
            "invariant_match_distance": axis_scores["V"],
        },
    }


def compute_changed_axes(
    original_schema: dict[str, Any],
    candidate_schema: dict[str, Any],
    embedding_client: Any | None = None,
    distance: dict[str, Any] | None = None,
) -> list[str]:
    effective_distance = distance or compute_schema_distance(
        original_schema,
        candidate_schema,
        embedding_client=embedding_client,
    )
    axis_scores = effective_distance.get("axis_scores", {})
    axes: list[str] = []
    for axis in ("I", "C", "O", "V"):
        if float(axis_scores.get(axis, 0.0)) >= AXIS_THRESHOLDS[axis]:
            axes.append(axis)
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


def _normalize_text(text: Any) -> str:
    lowered = str(text or "").strip().lower()
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered


def _embed_similarity(left: str, right: str, similarity_backend: SimilarityBackend) -> float:
    return similarity_backend.similarity(left, right)


def _lexical_similarity(left: str, right: str) -> float:
    left_tokens = set(_tokenize_text(left))
    right_tokens = set(_tokenize_text(right))
    if not left_tokens and not right_tokens:
        return 1.0
    if not left_tokens or not right_tokens:
        return 0.0
    union = left_tokens | right_tokens
    intersection = left_tokens & right_tokens
    return len(intersection) / len(union)


def _input_distance(
    left: dict[str, Any],
    right: dict[str, Any],
    similarity_backend: SimilarityBackend,
) -> float:
    left_tree = _build_input_tree(left)
    right_tree = _build_input_tree(right)
    tree_distance = _tree_edit_distance(left_tree, right_tree, similarity_backend)
    normalizer = max(_tree_size(left_tree) + _tree_size(right_tree), 1)
    return round(min(1.0, tree_distance / normalizer), 4)


def _build_input_tree(input_structure: dict[str, Any]) -> InputTreeNode:
    root = InputTreeNode(kind="root", label="input_structure")
    if not isinstance(input_structure, dict):
        return root

    root.children.append(
        InputTreeNode(
            kind="category",
            label="type",
            value=_normalize_text(input_structure.get("type", "unknown")),
        )
    )
    root.children.append(
        InputTreeNode(
            kind="section",
            label="length",
            children=[
                InputTreeNode(kind="numeric", label="min", value=input_structure.get("length", {}).get("min")),
                InputTreeNode(kind="numeric", label="max", value=input_structure.get("length", {}).get("max")),
            ],
        )
    )
    root.children.append(
        InputTreeNode(
            kind="section",
            label="value_range",
            children=[
                InputTreeNode(kind="numeric", label="min", value=input_structure.get("value_range", {}).get("min")),
                InputTreeNode(kind="numeric", label="max", value=input_structure.get("value_range", {}).get("max")),
            ],
        )
    )

    properties = input_structure.get("properties", {})
    property_children = []
    if isinstance(properties, dict):
        for key in sorted(properties):
            value = properties[key]
            value_kind = "numeric" if isinstance(value, (int, float)) else "text"
            property_children.append(
                InputTreeNode(
                    kind="property",
                    label=str(key),
                    children=[InputTreeNode(kind=value_kind, label="value", value=value)],
                )
            )
    root.children.append(InputTreeNode(kind="section", label="properties", children=property_children))
    return root


def _tree_edit_distance(
    left: InputTreeNode,
    right: InputTreeNode,
    similarity_backend: SimilarityBackend,
) -> float:
    substitution_cost = _node_substitution_cost(left, right, similarity_backend)
    return substitution_cost + _forest_edit_distance(left.children or [], right.children or [], similarity_backend)


# _forest_edit_distance 过程：
# 1) 设 dp[i][j] 为 left 前 i 棵子树与 right 前 j 棵子树的最小编辑代价。
# 2) 边界：空集到非空集仅能通过插入/删除，单步代价为对应子树大小 _tree_size。
# 3) 转移：三选一取最小值（删除、插入、替换），其中替换代价递归调用 _tree_edit_distance。
# 4) 返回 dp[rows][cols]，即两组子树的最小森林编辑距离。
def _forest_edit_distance(
    left_children: list[InputTreeNode],
    right_children: list[InputTreeNode],
    similarity_backend: SimilarityBackend,
) -> float:
    rows = len(left_children)
    cols = len(right_children)
    dp = [[0.0] * (cols + 1) for _ in range(rows + 1)]

    for index in range(1, rows + 1):
        dp[index][0] = dp[index - 1][0] + _tree_size(left_children[index - 1])
    for index in range(1, cols + 1):
        dp[0][index] = dp[0][index - 1] + _tree_size(right_children[index - 1])

    for row in range(1, rows + 1):
        for col in range(1, cols + 1):
            delete_cost = dp[row - 1][col] + _tree_size(left_children[row - 1])
            insert_cost = dp[row][col - 1] + _tree_size(right_children[col - 1])
            replace_cost = dp[row - 1][col - 1] + _tree_edit_distance(
                left_children[row - 1],
                right_children[col - 1],
                similarity_backend,
            )
            dp[row][col] = min(delete_cost, insert_cost, replace_cost)
    return dp[rows][cols]


# _node_substitution_cost 过程：
# 1) kind 不同直接记满代价 1.0；root 与 root 替换代价为 0.0。
# 2) numeric 节点走 _numeric_distance，按数值差异计算。
# 3) section/property 节点采用标签词法距离与值语义距离的加权和（0.6/0.4）。
# 4) 其余节点用 1 - 语义相似度，最终裁剪到 [0, 1] 并保留 4 位小数。
def _node_substitution_cost(
    left: InputTreeNode,
    right: InputTreeNode,
    similarity_backend: SimilarityBackend,
) -> float:
    if left.kind != right.kind:
        return 1.0
    if left.kind == "root":
        return 0.0
    if left.kind == "numeric":
        return _numeric_distance(left.value, right.value)

    left_value = _normalize_text(left.value if left.value is not None else left.label)
    right_value = _normalize_text(right.value if right.value is not None else right.label)
    if left.kind in {"section", "property"}:
        label_distance = 1.0 - _lexical_similarity(left.label, right.label)
        value_distance = 0.0 if left.kind == "section" else 1.0 - _embed_similarity(left_value, right_value, similarity_backend)
        return round(min(1.0, 0.6 * label_distance + 0.4 * value_distance), 4)
    return round(min(1.0, 1.0 - _embed_similarity(left_value, right_value, similarity_backend)), 4)


def _tree_size(node: InputTreeNode) -> int:
    return 1 + sum(_tree_size(child) for child in node.children or [])


def _numeric_distance(left: Any, right: Any) -> float:
    if left is None and right is None:
        return 0.0
    if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
        return 1.0 if left != right else 0.0
    if left == right:
        return 0.0
    return min(1.0, abs(left - right) / max(abs(left), abs(right), 1))


def _constraint_distance(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
    similarity_backend: SimilarityBackend,
) -> float:
    return _match_item_sets(left, right, _constraint_item_cost, similarity_backend)


def _constraint_item_cost(
    left: dict[str, Any],
    right: dict[str, Any],
    similarity_backend: SimilarityBackend,
) -> float:
    left_name = _normalize_text(left.get("name", ""))
    right_name = _normalize_text(right.get("name", ""))
    left_description = _normalize_text(left.get("description", ""))
    right_description = _normalize_text(right.get("description", ""))
    name_distance = similarity_backend.distance(left_name, right_name)
    description_distance = similarity_backend.distance(left_description, right_description)
    return round(min(1.0, 0.35 * name_distance + 0.65 * description_distance), 4)


def _constraint_item_text(item: dict[str, Any]) -> str:
    return " ".join(
        part for part in (_normalize_text(item.get("name", "")), _normalize_text(item.get("description", ""))) if part
    )


def _invariant_distance(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
    similarity_backend: SimilarityBackend,
) -> float:
    return _match_item_sets(left, right, _invariant_item_cost, similarity_backend)


def _invariant_item_cost(
    left: dict[str, Any],
    right: dict[str, Any],
    similarity_backend: SimilarityBackend,
) -> float:
    left_name = _normalize_text(left.get("name", ""))
    right_name = _normalize_text(right.get("name", ""))
    left_description = _normalize_text(left.get("description", ""))
    right_description = _normalize_text(right.get("description", ""))
    name_distance = similarity_backend.distance(left_name, right_name)
    description_distance = similarity_backend.distance(left_description, right_description)
    return round(min(1.0, 0.35 * name_distance + 0.65 * description_distance), 4)


def _invariant_item_text(item: dict[str, Any]) -> str:
    return " ".join(
        part for part in (_normalize_text(item.get("name", "")), _normalize_text(item.get("description", ""))) if part
    )


def _match_item_sets(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
    item_cost: Callable[[dict[str, Any], dict[str, Any], SimilarityBackend], float],
    similarity_backend: SimilarityBackend,
) -> float:
    filtered_left = [item for item in left if item]
    filtered_right = [item for item in right if item]
    if not filtered_left and not filtered_right:
        return 0.0

    size = max(len(filtered_left), len(filtered_right))
    matrix = [[1.0] * size for _ in range(size)]
    for row in range(len(filtered_left)):
        for col in range(len(filtered_right)):
            matrix[row][col] = item_cost(filtered_left[row], filtered_right[col], similarity_backend)
    total_cost = _hungarian_min_cost(matrix)
    return round(min(1.0, total_cost / max(size, 1)), 4)


def _hungarian_min_cost(matrix: list[list[float]]) -> float:
    size = len(matrix)
    if size == 0:
        return 0.0
    u = [0.0] * (size + 1)
    v = [0.0] * (size + 1)
    p = [0] * (size + 1)
    way = [0] * (size + 1)

    for row in range(1, size + 1):
        p[0] = row
        minv = [math.inf] * (size + 1)
        used = [False] * (size + 1)
        col0 = 0
        while True:
            used[col0] = True
            row0 = p[col0]
            delta = math.inf
            col1 = 0
            for col in range(1, size + 1):
                if used[col]:
                    continue
                current = matrix[row0 - 1][col - 1] - u[row0] - v[col]
                if current < minv[col]:
                    minv[col] = current
                    way[col] = col0
                if minv[col] < delta:
                    delta = minv[col]
                    col1 = col
            for col in range(size + 1):
                if used[col]:
                    u[p[col]] += delta
                    v[col] -= delta
                else:
                    minv[col] -= delta
            col0 = col1
            if p[col0] == 0:
                break
        while True:
            col1 = way[col0]
            p[col0] = p[col1]
            col0 = col1
            if col0 == 0:
                break

    assignment = [0] * size
    for col in range(1, size + 1):
        if p[col] > 0:
            assignment[p[col] - 1] = col - 1
    return sum(matrix[row][assignment[row]] for row in range(size))


def _objective_distance(
    left: dict[str, Any],
    right: dict[str, Any],
    similarity_backend: SimilarityBackend,
) -> dict[str, float]:
    left_type_prompt = _objective_type_prompt(left.get("type", ""))
    right_type_prompt = _objective_type_prompt(right.get("type", ""))
    left_text = _normalize_text(left.get("description", ""))
    right_text = _normalize_text(right.get("description", ""))

    type_distance = similarity_backend.distance(left_type_prompt, right_type_prompt)
    text_distance = similarity_backend.distance(left_text, right_text)
    total = 0.6 * type_distance + 0.4 * text_distance
    return {
        "type": round(type_distance, 4),
        "text": round(text_distance, 4),
        "total": round(min(1.0, total), 4),
    }


def _objective_type_prompt(objective_type: Any) -> str:
    objective_type = _normalize_text(objective_type)
    if not objective_type:
        return "unknown objective"

    prompts = _load_objective_type_prompts()
    return prompts.get(objective_type, objective_type)


@lru_cache(maxsize=1)
def _load_objective_type_prompts() -> dict[str, str]:
    label_vocab_path = PROJECT_ROOT / "四元组抽取" / "label_vocab.py"
    if not label_vocab_path.exists():
        return {}

    spec = importlib.util.spec_from_file_location("autoproblemgen_upstream_label_vocab", label_vocab_path)
    if spec is None or spec.loader is None:
        return {}

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    prompts: dict[str, str] = {}
    for objective_spec in getattr(module, "OBJECTIVE_SPECS", []):
        name = _normalize_text(getattr(objective_spec, "name", ""))
        description = str(getattr(objective_spec, "description", "")).strip()
        if name and description:
            prompts[name] = f"{name}: {description}"
    return prompts


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(l_value * r_value for l_value, r_value in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    cosine = numerator / (left_norm * right_norm)
    return max(-1.0, min(1.0, cosine))


def _tokenize_text(text: str) -> list[str]:
    lowered = text.lower()
    return re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", lowered)


def _truncate_text(text: str, limit: int) -> str:
    cleaned = " ".join(str(text).split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."
