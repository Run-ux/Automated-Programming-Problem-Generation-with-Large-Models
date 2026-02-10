"""
LLM 归一化层：逐步聚类归一化标签

用法：
    python -m finiteness_verification.normalize \
        --input output/pilot/raw/ \
        --output output/pilot/normalized/

输入：
    raw/{problem_id}_{dimension}_round{N}.json（原始抽取结果）

输出：
    normalized/{problem_id}.json（归一化后的四维结果）
    label_registry/{dimension}.json（动态标签注册表）
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from finiteness_verification.prompts import prompt_normalize
from finiteness_verification.qwen_client import QwenClient, QwenConfig


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

    def register(self, name: str, description: str) -> None:
        if name in self.labels:
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


def extract_raw_labels_for_dimension(
    problem_rounds: List[Dict[str, Any]],
    dimension: str,
) -> List[str]:
    labels: List[str] = []
    for item in problem_rounds:
        if item.get("status") != "success":
            continue
        result = item.get("result", {})
        if dimension == "input_structure":
            label = result.get("type")
            if label:
                labels.append(str(label))
        elif dimension == "objective":
            label = result.get("type")
            if label:
                labels.append(str(label))
        elif dimension == "invariant":
            label = result.get("name")
            if label:
                labels.append(str(label))
        elif dimension == "core_constraints":
            constraints = result.get("constraints", [])
            for c in constraints:
                name = c.get("name")
                if name:
                    labels.append(str(name))
    return labels


def apply_mapping_to_rounds(
    problem_rounds: List[Dict[str, Any]],
    dimension: str,
    mapping: Dict[str, str],
) -> None:
    for item in problem_rounds:
        if item.get("status") != "success":
            continue
        result = item.get("result", {})
        if dimension == "input_structure" and "type" in result:
            result["type"] = mapping.get(result.get("type"), result.get("type"))
        elif dimension == "objective" and "type" in result:
            result["type"] = mapping.get(result.get("type"), result.get("type"))
        elif dimension == "invariant" and "name" in result:
            result["name"] = mapping.get(result.get("name"), result.get("name"))
        elif dimension == "core_constraints":
            constraints = result.get("constraints", [])
            for c in constraints:
                name = c.get("name")
                if name:
                    c["name"] = mapping.get(name, name)
        item["result"] = result


def normalize_labels_with_llm(
    client: QwenClient,
    registry: LabelRegistry,
    dimension: str,
    raw_labels: List[str],
    logger: logging.Logger,
) -> Tuple[Dict[str, str], List[str]]:
    if not raw_labels:
        return {}, []

    unique_labels = sorted(set(raw_labels))
    registry_text = registry.to_prompt_text()
    system_prompt = prompt_normalize.build_system_prompt()
    user_prompt = prompt_normalize.build_user_prompt(
        dimension_name=DIMENSION_DISPLAY[dimension],
        registry_text=registry_text,
        raw_labels=unique_labels,
    )

    result = client.chat_json(system_prompt, user_prompt)
    mappings = result.get("mappings", [])
    new_labels = result.get("new_labels", [])

    mapping_dict: Dict[str, str] = {}
    newly_created: List[str] = []

    for m in mappings:
        original = m.get("original")
        normalized = m.get("normalized")
        is_new = m.get("is_new")
        if not original or not normalized:
            continue
        mapping_dict[original] = normalized
        if is_new:
            newly_created.append(normalized)

    for nl in new_labels:
        name = nl.get("name")
        description = nl.get("description", "")
        if not name:
            continue
        registry.register(name, description)

    for original, normalized in mapping_dict.items():
        if normalized in registry.labels:
            registry.add_alias(normalized, original)

    logger.debug(
        f"{dimension}: 归一化 {len(unique_labels)} 个标签, 新增 {len(new_labels)} 个"
    )

    return mapping_dict, newly_created


def load_raw_files(raw_dir: Path, logger: logging.Logger) -> Dict[str, Dict[str, Any]]:
    raw_files = list(raw_dir.glob("*.json"))
    logger.info(f"找到 {len(raw_files)} 个原始抽取文件")
    problems: Dict[str, Dict[str, Any]] = {}
    for raw_file in raw_files:
        raw_data = json.loads(raw_file.read_text(encoding="utf-8"))
        problem_id = raw_data["problem_id"]
        dimension = raw_data["dimension"]
        round_num = raw_data["round"]
        if problem_id not in problems:
            problems[problem_id] = {
                "problem_id": problem_id,
                "source": raw_data["source"],
                "input_structure": [],
                "core_constraints": [],
                "objective": [],
                "invariant": [],
            }
        problems[problem_id][dimension].append(
            {
                "round": round_num,
                "status": raw_data.get("status"),
                "result": raw_data.get("result", {}),
            }
        )
    return problems


def normalize_all_problems(
    raw_dir: Path,
    normalized_dir: Path,
    registry_dir: Path,
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
        registries[dim] = reg

    try:
        client = QwenClient(QwenConfig(model="qwen-flash"))
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
            rounds = data[dim]
            raw_labels = extract_raw_labels_for_dimension(rounds, dim)
            mapping, _ = normalize_labels_with_llm(
                client=client,
                registry=registries[dim],
                dimension=dim,
                raw_labels=raw_labels,
                logger=logger,
            )
            if mapping:
                apply_mapping_to_rounds(rounds, dim, mapping)

            registry_path = registry_dir / f"{dim}.json"
            registries[dim].save(registry_path)

            time.sleep(0.5)

        output_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
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

    normalize_all_problems(raw_dir, normalized_dir, registry_dir, logger)
    logger.info("下一步：运行 vote.py 进行多数投票")


if __name__ == "__main__":
    main()
