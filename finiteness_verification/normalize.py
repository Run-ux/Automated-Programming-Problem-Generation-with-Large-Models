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


PREDEFINED_LABELS: Dict[str, List[Tuple[str, str]]] = {
    "core_constraints": [
        ("connectivity", "连通性/可达性约束，如连通图或可达要求"),
        ("acyclicity", "无环性约束，如 DAG 或森林结构"),
        ("planarity", "平面性约束，图需可平面嵌入"),
        ("bipartiteness", "二部性约束，图为二部图"),
        ("degree_bound", "度数上下界约束，如节点度限制"),
        ("path_constraint", "路径约束，如路径长度/简单路径限制"),
        ("matching_constraint", "匹配约束，如最大/完美匹配"),
        ("flow_constraint", "流量/容量约束，如守恒或容量限制"),
        ("coloring_constraint", "染色约束，如相邻不同色或色数限制"),
        ("spanning_constraint", "生成结构约束，如生成树/生成子图"),
        ("ordering", "有序性约束，如单调、排序或字典序"),
        ("distinctness", "唯一性约束，如元素互异或去重"),
        ("adjacency_relation", "相邻关系约束，如相等/差值/相邻互斥"),
        ("frequency_bound", "频次约束，如出现次数上界/下界"),
        ("subsequence_constraint", "子序列/子串约束，如包含或排除"),
        ("permutation_constraint", "排列/置换约束，如逆序对或循环结构"),
        ("range_bound", "值域/范围约束，如元素上下界"),
        ("sum_constraint", "和约束，如区间和/前缀和条件"),
        ("divisibility", "整除/同余约束，如 GCD/LCM"),
        ("parity", "奇偶性约束"),
        ("linear_relation", "线性关系约束，如线性方程或不等式"),
        ("modular_arithmetic", "模运算约束，如取模结果限制"),
        ("convexity", "凸性约束，如凸包或凸多边形"),
        ("distance_bound", "距离约束，如曼哈顿/欧氏距离限制"),
        ("intersection", "相交/重叠关系约束"),
        ("orientation", "方向/朝向约束，如顺逆时针"),
        ("subset_constraint", "子集约束，如子集选择或大小限制"),
        ("partition", "划分约束，如分组或等价类划分"),
        ("coverage", "覆盖约束，如区间或集合覆盖"),
        ("exclusion", "互斥/禁止约束"),
        ("inclusion", "包含/必选约束"),
        ("operation_limit", "操作次数限制"),
        ("operation_type", "操作类型限制，如仅交换/翻转/插入"),
        ("state_transition", "状态转移约束，如合法转移"),
        ("concurrency", "并发/同步约束"),
        ("reversibility", "可逆性约束"),
        ("transformation", "变换/替换/映射规则约束"),
        ("palindrome", "回文约束"),
        ("pattern_matching", "模式匹配约束，如通配符"),
        ("alphabet_constraint", "字符集约束，如字母表大小"),
        ("repetition", "重复性/周期性约束"),
        ("turn_based", "回合制约束"),
        ("optimal_play", "最优策略约束"),
        ("query_limit", "询问次数限制"),
        ("probability_distribution", "概率分布约束"),
        ("independence", "独立性约束"),
    ],
    "invariant": [
        ("monotonicity", "单调性不变量，如双指针或二分的单调推进"),
        ("optimal_substructure", "最优子结构不变量，如动态规划的最优解可组合"),
        ("greedy_choice", "贪心选择性质不变量"),
        ("state_transition", "状态转移不变量，如状态机/博弈 DP"),
        ("interval_additivity", "区间可加性不变量，如前缀和"),
        ("interval_mergeable", "区间可合并性不变量，如线段树"),
        ("divide_conquer", "分治不变量，如子问题可合成"),
        ("topological_order", "拓扑序不变量，如 DAG 依赖顺序"),
        ("flow_conservation", "流守恒不变量"),
        ("matroid_exchange", "拟阵交换性质不变量"),
        ("convexity", "凸性不变量，如斜率优化或凸包"),
        ("symmetry", "对称性不变量"),
        ("idempotency", "幂等性不变量，如 RMQ/倍增"),
        ("prefix_decomposability", "前缀可分解性不变量"),
        ("cycle_invariant", "环不变量，如置换环或判圈"),
        ("subproblem_independence", "子问题独立性不变量"),
        ("exchange_argument", "交换论证不变量"),
        ("potential_function", "势函数不变量"),
    ],
    "objective": [
        ("maximize_value", "最大化某个值，如和/积/距离"),
        ("minimize_value", "最小化某个值，如代价/距离/时间"),
        ("maximize_count", "最大化计数，如方案数或匹配数"),
        ("minimize_count", "最小化计数，如操作次数"),
        ("maximize_probability", "最大化概率或期望"),
        ("minimize_probability", "最小化概率或期望"),
        ("min_max", "极小化极大值，如瓶颈路径"),
        ("max_min", "极大化极小值"),
        ("lexicographic_optimize", "字典序优化"),
        ("feasibility", "可行性判定"),
        ("construction", "构造任意或最优方案"),
        ("enumeration", "计数/枚举方案数"),
        ("multi_objective", "多目标优化"),
        ("game_outcome", "博弈结果"),
    ],
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
            invariants = result.get("invariants", [])
            for inv in invariants:
                name = inv.get("name")
                if name:
                    labels.append(str(name))
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
        elif dimension == "invariant":
            invariants = result.get("invariants", [])
            for inv in invariants:
                name = inv.get("name")
                if name:
                    inv["name"] = mapping.get(name, name)
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
            reg.register(name, description)
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
                apply_mapping_to_rounds(rounds, dim, embedding_mapping)

            llm_mapping, _ = normalize_labels_with_llm(
                client=client,
                registry=registries[dim],
                dimension=dim,
                raw_labels=unresolved_labels,
                logger=logger,
            )
            if llm_mapping:
                apply_mapping_to_rounds(rounds, dim, llm_mapping)

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
    logger.info("下一步：运行 vote.py 进行多数投票")


if __name__ == "__main__":
    main()
