"""核心约束维度 Prompt。"""

from __future__ import annotations

from typing import TYPE_CHECKING

try:
    from ..label_vocab import (
        CONSTRAINT_SOURCE_SECTIONS,
        CORE_CONSTRAINT_LABELS,
    )
    from ..problem_schema import prepare_problem_record
    from .prompt_sections import build_problem_context
except ImportError:
    from label_vocab import (
        CONSTRAINT_SOURCE_SECTIONS,
        CORE_CONSTRAINT_LABELS,
    )
    from problem_schema import prepare_problem_record
    from prompts.prompt_sections import build_problem_context

if TYPE_CHECKING:
    from typing import Any, Dict


CORE_CONSTRAINT_NAMES = [name for name, _ in CORE_CONSTRAINT_LABELS]


def build_system_prompt() -> str:
    preferred_names = ", ".join(CORE_CONSTRAINT_NAMES)
    return f"""你是编程竞赛题目约束条件分析专家。

你的任务是从题目全文中抽取核心语义约束。

科研定义：
- 核心约束指对合法对象、合法操作、合法状态或合法解集合产生语义作用的限制。
- 该维度只记录会改变可行性、转移合法性、可选解集合或目标定义的约束。
- 纯输入规模上界、时间限制与内存限制不属于该维度。

硬规则：
1. 只输出严格 JSON 对象，不输出任何解释文字。
2. name 必须优先复用规范约束词表：{preferred_names}。
3. 若现有词表无法准确覆盖当前题目的约束语义，允许创建新的抽象标签。
4. 新标签必须使用小写英文加下划线格式，并保持算法术语风格。
5. 不得把题目情境词直接写进 name 或 source_sections。

证据优先级：
1. 题面全文中的任务描述
2. Input 分节
3. Output 分节
4. Constraints 分节
5. 标题

边界规则：
- 排除纯输入规模边界，例如 1 ≤ n ≤ 10^5。
- 排除时间限制与内存限制。
- 保留具有语义作用的范围约束，例如度数上界、操作次数上界、字符集限制、容量上限、可用步数上限。
- 同一语义约束只保留一条；若多个句子共同支撑同一约束，合并到同一条 description。
- name 不得使用 distinct_leq_k、max_min_diff_leq_d 这类实例化标签，具体数值与场景写入 description 或 formal。
- source_sections 只允许使用 description、input、output、constraints。
- 题面没有可确认的核心语义约束时，返回 {{"constraints": []}}。

判别边界：
- range_bound 只用于具有语义作用的范围限制，不用于 n、m、q 或 a_i 的普通输入范围。
- operation_limit 用于操作步数、修改次数或资源配额上界。
- operation_type 用于允许哪些操作或禁止哪些操作。
- state_transition 用于状态之间的合法转移规则，而非普通过程描述。
- order_constraint 用于顺序、相对位置、单调排列等语义限制。
- distinctness 用于互异性要求；排列特有约束优先归入 permutation_constraint。
- 对抗式轮流行动与策略最优性，统一优先归入 optimal_play。
"""


def build_user_prompt(problem: Dict[str, Any]) -> str:
    problem = prepare_problem_record(problem)
    context = build_problem_context(problem)
    preferred_names = ", ".join(CORE_CONSTRAINT_NAMES)
    return f"""请根据下列题目信息抽取核心约束。

{context}

字段说明：
1. constraints[].name 表示约束的抽象标签。现有词表能够覆盖时填写规范标签；只有明确存在语义缺口时才新建标签；没有约束项时不出现。常见误填：把具体数值、题目名词或整句限制直接写进 name。
2. constraints[].description 表示该题中这条约束的具体语义内容。存在该约束项时始终填写；只有整条约束不存在时才不出现。常见误填：只写标签释义，不写当前题目的具体限制。
3. constraints[].formal 表示便于归一化的形式化表达。题面存在清晰公式、逻辑式或边界表达时填写；没有必要时留空。常见误填：把自然语言 description 原样重复到 formal。
4. constraints[].source_sections 表示证据出现在题面哪个分节。需要追溯证据位置时填写；无法明确定位时留空。常见误填：把推理来源、代码来源或不在允许集合中的值写进去。

请输出 JSON：
{{
  "constraints": [
    {{
      "name": "优先复用规范标签，例如 {preferred_names}",
      "description": "该题中的具体约束描述",
      "formal": "形式化表达，可留空",
      "source_sections": ["description", "input"]
    }}
  ]
}}

要求：
1. 字段说明优先于字段名直觉，不要仅凭命名猜测字段含义。
2. name 优先对齐现有规范标签；若词表无法准确覆盖当前约束，允许新建一个抽象标签。
3. 新标签保持小写英文加下划线格式，不创建实例化标签。
4. description 负责表达该题中的具体限制条件。
5. formal 可选，source_sections 可选，且元素只能来自 description、input、output、constraints。
6. 纯输入规模边界与时间内存限制不要抽取。
7. 多句支撑同一约束时合并为一条。
8. 没有可确认约束时返回 {{"constraints": []}}。
"""


CONSTRAINTS_SCHEMA = {
    "type": "object",
    "required": ["constraints"],
    "additionalProperties": True,
    "properties": {
        "constraints": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "description"],
                "additionalProperties": True,
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "formal": {"type": "string"},
                    "source_sections": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": CONSTRAINT_SOURCE_SECTIONS,
                        },
                    },
                },
            },
        }
    },
}
