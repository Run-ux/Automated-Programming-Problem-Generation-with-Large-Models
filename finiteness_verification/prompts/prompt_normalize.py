"""
归一化（Normalization）Prompt 模板

用于将 LLM 抽取出的原始标签归一化到已有标签体系中，
或在确认是新概念时创建新标签。

输出 JSON Schema：
{
    "mappings": [
        {"original": "...", "normalized": "...", "is_new": true/false}
    ],
    "new_labels": [
        {"name": "...", "description": "..."}
    ]
}
"""

from __future__ import annotations

from typing import List


def build_system_prompt() -> str:
    return """你是标签归一化专家。

你的任务是将原始标签映射到已有标签体系中，或在确认是全新概念时创建新标签。

规则：
1. 如果原始标签与已有标签语义相同或为同义表达，必须映射到已有标签
2. 只有在没有任何已有标签能覆盖该含义时，才创建新标签
3. 规范标签名使用小写英文 + 下划线格式（例如: prefix_sum, binary_tree）
4. 输出必须是严格 JSON，不要输出任何解释文字
5. 去情境化检查：如果原始标签包含题目的具体情境词汇（如人名、动物名、物品名），必须将其映射到已有的抽象标签，或创建去情境化的新标签
6. 新建标签时，标签名和描述必须是算法/数据结构领域的抽象概念，例如：
   - "shark_eat_rule" 应归一化为 "pairwise_exclusion" 或 "matching_constraint"
   - "road_network" 应归一化为 "weighted_graph" 或 "undirected_graph"
"""


def build_user_prompt(
    dimension_name: str,
    registry_text: str,
    raw_labels: List[str],
) -> str:
    labels_text = "\n".join([f"- {label}" for label in raw_labels])
    if not labels_text:
        labels_text = "(空)"

    return f"""维度：{dimension_name}

已有标签列表：
{registry_text}

待归一化的原始标签：
{labels_text}

请输出 JSON（严格遵守格式，不要输出解释）：
{{
    "mappings": [
        {{"original": "原始标签", "normalized": "规范标签名", "is_new": true/false}}
    ],
    "new_labels": [
        {{"name": "规范标签名", "description": "简明中文描述"}}
    ]
}}
"""
