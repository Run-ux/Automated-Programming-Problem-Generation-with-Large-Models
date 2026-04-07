"""
LLM 归一化层：逐步聚类归一化标签，并直接输出最终结果。

用法：
    python normalize.py \
        --input output/pilot/raw/ \
        --output output/pilot/normalized/

输入：
    raw/{problem_id}_{dimension}.json（单轮原始抽取结果）

输出：
    normalized/{problem_id}.json（归一化后的最终四维结果）
    label_registry/{dimension}.json（动态标签注册表）
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    from .label_vocab import (
        CORE_CONSTRAINT_LABELS,
        INPUT_STRUCTURE_TYPE_LABELS,
        INVARIANT_LABELS,
        OBJECTIVE_LABELS,
    )
    from .prompts import prompt_normalize
    from .qwen_client import QwenClient, QwenConfig
except ImportError:
    from label_vocab import (
        CORE_CONSTRAINT_LABELS,
        INPUT_STRUCTURE_TYPE_LABELS,
        INVARIANT_LABELS,
        OBJECTIVE_LABELS,
    )
    from prompts import prompt_normalize
    from qwen_client import QwenClient, QwenConfig


DIMENSIONS = [
    "input_structure",
    "core_constraints",
    "objective",
    "invariant",
]


DIMENSION_DISPLAY = {
    "input_structure": "输入结构（Input Structure）",
    "core_constraints": "核心约束（Core Constraints）",
    "objective": "优化目标（Objective）",
    "invariant": "算法不变量（Invariant）",
}


PREDEFINED_LABELS: Dict[str, List[Tuple[str, str]]] = {
    "input_structure": INPUT_STRUCTURE_TYPE_LABELS,
    "core_constraints": CORE_CONSTRAINT_LABELS,
    "objective": OBJECTIVE_LABELS,
    "invariant": INVARIANT_LABELS,
}


@dataclass
class LabelEntry:
    name: str
    description: str
    aliases: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)


class LabelRegistry:
    def __init__(self, dimension: str):
        self.dimension = dimension
        self.labels: Dict[str, LabelEntry] = {}

    def to_prompt_text(self) -> str:
        if not self.labels:
            return "(当前无已有标签)"
        lines = []
        for name in sorted(self.labels.keys()):
            entry = self.labels[name]
            aliases = ", ".join(entry.aliases) if entry.aliases else "-"
            lines.append(
                f"- {entry.name}: {entry.description} (aliases: {aliases})"
            )
        return "\n".join(lines)

    def build_canonical_texts(self) -> List[str]:
        """返回用于 embedding 比较的文本列表。
        
        只使用纯英文标签名（不附带中文描述），因为 raw label 也是
        英文短词，同语言比较时 embedding 相似度显著更高。
        """
        return [name for name in sorted(self.labels.keys())]

    def get_canonical_names(self) -> List[str]:
        return sorted(self.labels.keys())

    def register(
        self,
        name: str,
        description: str,
        overwrite_description: bool = False,
    ) -> None:
        if name in self.labels:
            if overwrite_description:
                self.labels[name].description = description
            return
        self.labels[name] = LabelEntry(name=name, description=description)

    def add_alias(self, canonical: str, alias: str) -> None:
        if canonical not in self.labels:
            return
        entry = self.labels[canonical]
        if alias not in entry.aliases and alias != canonical:
            entry.aliases.append(alias)

    def save(self, path: Path) -> None:
        data = {
            name: {
                "name": entry.name,
                "description": entry.description,
                "aliases": entry.aliases,
                "examples": entry.examples,
            }
            for name, entry in self.labels.items()
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self, path: Path) -> None:
        if not path.exists():
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        for name, item in data.items():
            self.labels[name] = LabelEntry(
                name=item.get("name", name),
                description=item.get("description", ""),
                aliases=item.get("aliases", []),
                examples=item.get("examples", []),
            )


def _compact_json(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _build_input_structure_description(result: Dict[str, Any]) -> str:
    parts: List[str] = []
    length = result.get("length", {})
    value_range = result.get("value_range", {})
    properties = result.get("properties", {})
    components = result.get("components", [])

    if isinstance(length, dict):
        parts.append(
            f"length={_compact_json({'min': length.get('min'), 'max': length.get('max')})}"
        )
    if isinstance(value_range, dict):
        parts.append(
            "value_range="
            + _compact_json(
                {"min": value_range.get("min"), "max": value_range.get("max")}
            )
        )
    if isinstance(properties, dict) and properties:
        parts.append(f"properties={_compact_json(properties)}")
    if isinstance(components, list) and components:
        parts.append(f"components={_compact_json(components)}")
    return "; ".join(part for part in parts if part)


def _build_objective_description(result: Dict[str, Any]) -> str:
    parts: List[str] = []
    description = result.get("description")
    target = result.get("target")
    requires_solution = result.get("requires_solution")

    if isinstance(description, str) and description.strip():
        parts.append(description.strip())
    if isinstance(target, str) and target.strip():
        parts.append(f"target={target.strip()}")
    if isinstance(requires_solution, bool):
        parts.append(f"requires_solution={str(requires_solution).lower()}")
    return "; ".join(parts)


def extract_raw_entries_for_dimension(
    problem_dimension: Dict[str, Any],
    dimension: str,
) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    if problem_dimension.get("status") != "success":
        return entries

    result = problem_dimension.get("result", {})

    if dimension == "input_structure":
        label = result.get("type")
        if label:
            entries.append(
                {
                    "entry_id": "input_structure",
                    "name": str(label),
                    "description": _build_input_structure_description(result),
                }
            )
    elif dimension == "objective":
        label = result.get("type")
        if label:
            entries.append(
                {
                    "entry_id": "objective",
                    "name": str(label),
                    "description": _build_objective_description(result),
                }
            )
    elif dimension == "invariant":
        invariants = result.get("invariants", [])
        for index, inv in enumerate(invariants, start=1):
            name = inv.get("name")
            if not name:
                continue
            entry = {
                "entry_id": f"invariant_{index}",
                "name": str(name),
                "description": str(inv.get("description", "")).strip(),
            }
            properties = inv.get("properties")
            if isinstance(properties, dict) and properties:
                entry["properties"] = properties
            evidence_source = inv.get("evidence_source")
            if isinstance(evidence_source, str) and evidence_source.strip():
                entry["evidence_source"] = evidence_source.strip()
            entries.append(entry)
    elif dimension == "core_constraints":
        constraints = result.get("constraints", [])
        for index, constraint in enumerate(constraints, start=1):
            name = constraint.get("name")
            if not name:
                continue
            entry = {
                "entry_id": f"constraint_{index}",
                "name": str(name),
                "description": str(constraint.get("description", "")).strip(),
            }
            formal = constraint.get("formal")
            if isinstance(formal, str) and formal.strip():
                entry["formal"] = formal.strip()
            entries.append(entry)
    return entries


def extract_label_names(raw_entries: List[Dict[str, Any]]) -> List[str]:
    labels: List[str] = []
    for entry in raw_entries:
        name = entry.get("name")
        if isinstance(name, str) and name.strip():
            labels.append(name.strip())
    return labels


def apply_mapping_to_result(
    problem_dimension: Dict[str, Any],
    dimension: str,
    mapping: Dict[str, str],
) -> None:
    if problem_dimension.get("status") != "success":
        return

    result = problem_dimension.get("result", {})
    if dimension == "input_structure" and "type" in result:
        result["type"] = mapping.get(result.get("type"), result.get("type"))
    elif dimension == "objective" and "type" in result:
        result["type"] = mapping.get(result.get("type"), result.get("type"))
    elif dimension == "invariant":
        invariants = result.get("invariants", [])
        for inv in invariants:
            name = inv.get("name")
            if name:
                inv["name"] = mapping.get(name, name)
    elif dimension == "core_constraints":
        constraints = result.get("constraints", [])
        for constraint in constraints:
            name = constraint.get("name")
            if name:
                constraint["name"] = mapping.get(name, name)
    problem_dimension["result"] = result


def _build_default_dimension_result(dimension: str) -> Dict[str, Any]:
    if dimension == "input_structure":
        return {"type": None}
    if dimension == "objective":
        return {"type": None}
    if dimension == "core_constraints":
        return {"constraints": []}
    if dimension == "invariant":
        return {"invariants": []}
    return {}


def _build_final_dimension_result(
    problem_dimension: Dict[str, Any],
    dimension: str,
) -> Dict[str, Any]:
    if problem_dimension.get("status") != "success":
        return _build_default_dimension_result(dimension)

    raw_result = problem_dimension.get("result", {})
    if not isinstance(raw_result, dict):
        return _build_default_dimension_result(dimension)

    result = deepcopy(raw_result)
    if dimension == "input_structure":
        result.setdefault("type", None)
        return result
    if dimension == "objective":
        result.setdefault("type", None)
        return result
    if dimension == "core_constraints":
        constraints = result.get("constraints")
        return {"constraints": constraints if isinstance(constraints, list) else []}
    if dimension == "invariant":
        invariants = result.get("invariants")
        return {"invariants": invariants if isinstance(invariants, list) else []}
    return result


def build_final_problem_output(problem_data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "problem_id": problem_data["problem_id"],
        "source": problem_data["source"],
        "input_structure": _build_final_dimension_result(
            problem_data["input_structure"], "input_structure"
        ),
        "core_constraints": _build_final_dimension_result(
            problem_data["core_constraints"], "core_constraints"
        ),
        "objective": _build_final_dimension_result(
            problem_data["objective"], "objective"
        ),
        "invariant": _build_final_dimension_result(
            problem_data["invariant"], "invariant"
        ),
    }


def normalize_labels_with_llm(
    client: QwenClient,
    registry: LabelRegistry,
    dimension: str,
    raw_entries: List[Dict[str, Any]],
    logger: logging.Logger,
) -> Tuple[Dict[str, str], List[str]]:
    if not raw_entries:
        return {}, []

    expected_entry_ids = {
        str(entry["entry_id"])
        for entry in raw_entries
        if isinstance(entry.get("entry_id"), str) and entry["entry_id"]
    }
    registry_text = registry.to_prompt_text()
    system_prompt = prompt_normalize.build_system_prompt()
    user_prompt = prompt_normalize.build_user_prompt(
        dimension_key=dimension,
        dimension_name=DIMENSION_DISPLAY[dimension],
        registry_text=registry_text,
        raw_entries=raw_entries,
    )

    result = client.chat_json(system_prompt, user_prompt)
    mappings = result.get("mappings", [])
    new_labels = result.get("new_labels", [])

    entry_counts: Counter[str] = Counter()
    original_candidates: Dict[str, Counter[str]] = {}
    newly_created: set[str] = set()
    returned_new_labels: Dict[str, str] = {}

    for m in mappings:
        entry_id = m.get("entry_id")
        original = m.get("original")
        normalized = m.get("normalized")
        is_new = m.get("is_new")
        if not entry_id or not original or not normalized:
            continue
        entry_counts[str(entry_id)] += 1
        original_key = str(original)
        normalized_name = str(normalized)
        original_candidates.setdefault(original_key, Counter())[normalized_name] += 1
        if is_new:
            newly_created.add(normalized_name)

    for nl in new_labels:
        name = nl.get("name")
        description = nl.get("description", "")
        if not name:
            continue
        name_str = str(name)
        if name_str in returned_new_labels:
            logger.warning("重复的新标签定义：%s", name_str)
            continue
        returned_new_labels[name_str] = str(description)

    missing_entries = expected_entry_ids - set(entry_counts.keys())
    duplicate_entries = sorted(
        entry_id for entry_id, count in entry_counts.items() if count != 1
    )
    if missing_entries:
        logger.warning("LLM 归一化缺少 %s 个条目映射：%s", len(missing_entries), sorted(missing_entries))
    if duplicate_entries:
        logger.warning("LLM 归一化存在重复条目映射：%s", duplicate_entries)

    for name in sorted(newly_created):
        if name not in returned_new_labels:
            logger.warning("is_new=true 的标签缺少 new_labels 定义：%s", name)
            returned_new_labels[name] = ""

    for name, description in returned_new_labels.items():
        registry.register(name, description)

    mapping_dict: Dict[str, str] = {}
    for original, candidate_counter in original_candidates.items():
        normalized_name, count = candidate_counter.most_common(1)[0]
        if len(candidate_counter) > 1:
            logger.warning(
                "原始标签 %s 出现多种归一化结果 %s，采用多数结果 %s",
                original,
                dict(candidate_counter),
                normalized_name,
            )
        mapping_dict[original] = normalized_name

    for original, normalized in mapping_dict.items():
        if normalized in registry.labels:
            registry.add_alias(normalized, original)

    logger.debug(
        "%s: 归一化 %s 个条目, 新增 %s 个标签",
        dimension,
        len(raw_entries),
        len(returned_new_labels),
    )

    return mapping_dict, sorted(newly_created)


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    if not vec_a or not vec_b:
        return 0.0
    if len(vec_a) != len(vec_b):
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for a, b in zip(vec_a, vec_b):
        dot += a * b
        norm_a += a * a
        norm_b += b * b
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / ((norm_a ** 0.5) * (norm_b ** 0.5))


def normalize_labels_with_embedding(
    client: QwenClient,
    registry: LabelRegistry,
    raw_labels: List[str],
    similarity_threshold: float,
    logger: logging.Logger,
) -> Tuple[Dict[str, str], List[str]]:
    if not raw_labels:
        return {}, []

    unique_labels = sorted(set(raw_labels))
    canonical_names = registry.get_canonical_names()
    if not canonical_names:
        return {}, unique_labels

    canonical_texts = registry.build_canonical_texts()
    raw_texts = unique_labels

    try:
        embeddings = client.embed_texts(canonical_texts + raw_texts)
    except Exception as e:
        logger.warning("Embedding 调用失败，跳过向量归一化：%s", e)
        return {}, unique_labels
    if len(embeddings) != len(canonical_texts) + len(raw_texts):
        logger.warning("Embedding 返回数量异常，跳过向量归一化")
        return {}, unique_labels

    canonical_embeddings = embeddings[: len(canonical_texts)]
    raw_embeddings = embeddings[len(canonical_texts) :]

    mapping: Dict[str, str] = {}
    unresolved: List[str] = []

    for raw_label, raw_vec in zip(unique_labels, raw_embeddings):
        best_idx = -1
        best_score = -1.0
        for idx, canon_vec in enumerate(canonical_embeddings):
            score = _cosine_similarity(raw_vec, canon_vec)
            if score > best_score:
                best_score = score
                best_idx = idx
        if best_idx >= 0 and best_score >= similarity_threshold:
            mapping[raw_label] = canonical_names[best_idx]
        else:
            unresolved.append(raw_label)

    logger.debug(
        "Embedding 归一化命中 %s/%s (阈值 %.2f)",
        len(mapping),
        len(unique_labels),
        similarity_threshold,
    )

    return mapping, unresolved


def load_raw_files(raw_dir: Path, logger: logging.Logger) -> Dict[str, Dict[str, Any]]:
    raw_files = sorted(raw_dir.glob("*.json"))
    logger.info(f"找到 {len(raw_files)} 个原始抽取文件")
    problems: Dict[str, Dict[str, Any]] = {}
    for raw_file in raw_files:
        raw_data = json.loads(raw_file.read_text(encoding="utf-8"))
        problem_id = raw_data["problem_id"]
        dimension = raw_data["dimension"]
        if problem_id not in problems:
            problems[problem_id] = {
                "problem_id": problem_id,
                "source": raw_data["source"],
                "input_structure": {"status": "failed", "result": {}},
                "core_constraints": {"status": "failed", "result": {}},
                "objective": {"status": "failed", "result": {}},
                "invariant": {"status": "failed", "result": {}},
            }

        if dimension not in DIMENSIONS:
            logger.warning("跳过未知维度文件：%s", raw_file.name)
            continue

        current_dimension = problems[problem_id][dimension]
        if current_dimension.get("_loaded"):
            logger.warning(
                "题目 %s 的维度 %s 存在重复原始文件，保留首个文件并跳过 %s",
                problem_id,
                dimension,
                raw_file.name,
            )
            continue

        problems[problem_id][dimension] = {
            "_loaded": True,
            "status": raw_data.get("status"),
            "result": raw_data.get("result", {}),
        }

    for data in problems.values():
        for dimension in DIMENSIONS:
            data[dimension].pop("_loaded", None)
    return problems


def normalize_all_problems(
    raw_dir: Path,
    normalized_dir: Path,
    registry_dir: Path,
    embedding_threshold: float,
    logger: logging.Logger,
) -> None:
    normalized_dir.mkdir(parents=True, exist_ok=True)
    registry_dir.mkdir(parents=True, exist_ok=True)

    problems = load_raw_files(raw_dir, logger)

    registries: Dict[str, LabelRegistry] = {}
    for dim in DIMENSIONS:
        registry_path = registry_dir / f"{dim}.json"
        reg = LabelRegistry(dim)
        reg.load(registry_path)
        for name, description in PREDEFINED_LABELS.get(dim, []):
            reg.register(name, description, overwrite_description=True)
        registries[dim] = reg

    try:
        client = QwenClient(QwenConfig(stage="normalize"))
    except RuntimeError as e:
        logger.error(f"Qwen 客户端初始化失败：{e}")
        return

    processed = 0
    skipped = 0

    for problem_id, data in problems.items():
        output_file = normalized_dir / f"{problem_id}.json"
        if output_file.exists():
            skipped += 1
            continue

        for dim in DIMENSIONS:
            problem_dimension = data[dim]
            raw_entries = extract_raw_entries_for_dimension(problem_dimension, dim)
            raw_labels = extract_label_names(raw_entries)
            embedding_mapping: Dict[str, str] = {}
            unresolved_labels = raw_labels
            if raw_labels:
                embedding_mapping, unresolved_labels = normalize_labels_with_embedding(
                    client=client,
                    registry=registries[dim],
                    raw_labels=raw_labels,
                    similarity_threshold=embedding_threshold,
                    logger=logger,
                )

            if embedding_mapping:
                apply_mapping_to_result(problem_dimension, dim, embedding_mapping)

            unresolved_label_set = set(unresolved_labels)
            unresolved_entries = [
                entry
                for entry in raw_entries
                if entry.get("name") in unresolved_label_set
            ]
            llm_mapping, _ = normalize_labels_with_llm(
                client=client,
                registry=registries[dim],
                dimension=dim,
                raw_entries=unresolved_entries,
                logger=logger,
            )
            if llm_mapping:
                apply_mapping_to_result(problem_dimension, dim, llm_mapping)

            registry_path = registry_dir / f"{dim}.json"
            registries[dim].save(registry_path)

            time.sleep(0.5)

        output_data = build_final_problem_output(data)
        output_file.write_text(
            json.dumps(output_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        processed += 1

        if processed % 10 == 0:
            logger.info(f"归一化进度: {processed}/{len(problems)} (跳过 {skipped})")

    logger.info(f"归一化完成：{processed} 题，跳过 {skipped} 题")


def main():
    parser = argparse.ArgumentParser(description="LLM 归一化（逐步聚类）")
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="原始抽取结果目录（如 output/pilot/raw/）",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="归一化输出目录（如 output/pilot/normalized/）",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别",
    )
    parser.add_argument(
        "--embedding-threshold",
        type=float,
        default=0.85,
        help="向量相似度阈值（默认 0.85）",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    logger = logging.getLogger(__name__)

    raw_dir = Path(args.input)
    normalized_dir = Path(args.output)
    registry_dir = normalized_dir.parent / "label_registry"

    if not raw_dir.exists():
        logger.error(f"输入目录不存在：{raw_dir}")
        return

    normalize_all_problems(
        raw_dir=raw_dir,
        normalized_dir=normalized_dir,
        registry_dir=registry_dir,
        embedding_threshold=args.embedding_threshold,
        logger=logger,
    )
    logger.info("归一化完成，normalized/ 目录中的文件已可直接作为最终结果使用")


if __name__ == "__main__":
    main()
