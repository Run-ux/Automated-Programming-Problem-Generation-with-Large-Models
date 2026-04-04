"""归一化 Prompt。"""

from __future__ import annotations

import json
from typing import Any, Dict, List


DIMENSION_POLICIES = {
    "input_structure": "强归并。优先映射到现有主类型，常见结构默认不新建标签。",
    "objective": "强归并。优先映射到统一目标词表，常见目标默认不新建标签。",
    "core_constraints": "半开放归并。只有语义缺口明确时才允许新建标签。",
    "invariant": "半开放归并。只有现有不变量词表无法覆盖时才允许新建标签。",
}


def build_system_prompt() -> str:
    return """你是标签归一化专家。

你的任务是将原始条目映射到已有标签体系中，或在确认语义缺口明确时创建新标签。

硬规则：
1. 只输出严格 JSON 对象，不输出任何解释文字。
2. 优先复用已有标签与预置词表，只有在确实无法覆盖时才创建新标签。
3. 不得把题目情境词直接写进 normalized 或 new_labels.name。

归并规则：
1. input_structure 与 objective 采用强归并，常见标签默认不新建。
2. core_constraints 与 invariant 采用半开放归并，只有现有体系无法覆盖时才允许新建。
3. 规范标签名使用小写英文加下划线格式。
4. 同义表达必须归并到同一规范标签，不得分别创建多个新标签。

输出约束：
1. 每个原始条目必须在 mappings 中映射一次。
2. is_new=true 的 normalized 必须同时出现在 new_labels 中。
3. new_labels 不得重复。
4. 不得把同义词拆成多个新标签。
"""


def build_user_prompt(
    dimension_key: str,
    dimension_name: str,
    registry_text: str,
    raw_entries: List[Dict[str, Any]],
) -> str:
    entries_text = json.dumps(raw_entries, ensure_ascii=False, indent=2)
    if not raw_entries:
        entries_text = "[]"
    policy = DIMENSION_POLICIES.get(dimension_key, "优先复用已有标签。")

    return f"""维度键：{dimension_key}
维度名称：{dimension_name}

维度策略：
{policy}

已有标签列表：
{registry_text}

待归一化的原始条目：
{entries_text}

字段说明：
1. mappings[].entry_id 表示原始条目的唯一标识。每个原始条目都必须映射一次时填写；没有对应条目时不出现。常见误填：改写、合并或新造 entry_id。
2. mappings[].original 表示原始条目中的原始标签。存在该映射项时始终填写；没有单独留空场景。常见误填：把 original 改成解释文本或规范标签。
3. mappings[].normalized 表示最终归一化后的规范标签名。已有标签能够覆盖时填写已有标签；只有确实存在语义缺口时才填写新的稳定标签。常见误填：把相似但并非同义的标签强行合并，或把题目情境词写进 normalized。
4. mappings[].is_new 表示 normalized 是否是本轮新建标签。normalized 已存在于已有标签列表时写 false；只有需要新增标签时写 true。常见误填：normalized 和 original 不同就写 true。
5. new_labels 表示本轮真正新增的规范标签定义。至少存在一个 is_new=true 的映射时填写对应新标签；没有新增标签时返回空数组。常见误填：把已有标签重复写进 new_labels，或遗漏 is_new=true 对应的定义。
6. new_labels[].description 表示新标签的简明中文语义。创建新标签时填写；没有新标签时不出现。常见误填：把具体题目实例、数值条件或冗长规则塞进 description。

请输出 JSON：
{{
  "mappings": [
    {{
      "entry_id": "原始条目 id",
      "original": "原始标签",
      "normalized": "规范标签名",
      "is_new": true
    }}
  ],
  "new_labels": [
    {{
      "name": "规范标签名",
      "description": "简明中文描述"
    }}
  ]
}}

要求：
1. 字段说明优先于字段名直觉，不要仅凭命名猜测字段含义。
2. 每个原始条目必须在 mappings 中出现且只出现一次。
3. normalized 优先复用已有标签；只有语义缺口明确时才新建标签。
4. is_new=true 的 normalized 必须同时出现在 new_labels 中。
5. 没有新增标签时返回 "new_labels": []。
"""


NORMALIZE_SCHEMA = {
    "type": "object",
    "required": ["mappings", "new_labels"],
    "additionalProperties": True,
    "properties": {
        "mappings": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["entry_id", "original", "normalized", "is_new"],
                "additionalProperties": True,
                "properties": {
                    "entry_id": {"type": "string"},
                    "original": {"type": "string"},
                    "normalized": {"type": "string"},
                    "is_new": {"type": "boolean"},
                },
            },
        },
        "new_labels": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "description"],
                "additionalProperties": True,
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                },
            },
        },
    },
}
