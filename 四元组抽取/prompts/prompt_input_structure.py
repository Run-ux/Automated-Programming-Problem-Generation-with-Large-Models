"""输入结构维度 Prompt。"""

from __future__ import annotations

from typing import TYPE_CHECKING

try:
    from ..label_vocab import (
        INPUT_STRUCTURE_PROPERTY_SPECS,
        INPUT_STRUCTURE_PROPERTY_KEYS,
        INPUT_STRUCTURE_TYPE_SPECS,
        INPUT_STRUCTURE_TYPE_LABELS,
        build_label_reference,
    )
    from ..problem_schema import prepare_problem_record
    from .prompt_sections import build_problem_context
except ImportError:
    from label_vocab import (
        INPUT_STRUCTURE_PROPERTY_SPECS,
        INPUT_STRUCTURE_PROPERTY_KEYS,
        INPUT_STRUCTURE_TYPE_SPECS,
        INPUT_STRUCTURE_TYPE_LABELS,
        build_label_reference,
    )
    from problem_schema import prepare_problem_record
    from prompts.prompt_sections import build_problem_context

if TYPE_CHECKING:
    from typing import Any, Dict


MAIN_TYPES = [name for name, _ in INPUT_STRUCTURE_TYPE_LABELS]


def build_system_prompt() -> str:
    controlled_types = ", ".join(MAIN_TYPES)
    property_keys = ", ".join(INPUT_STRUCTURE_PROPERTY_KEYS)
    type_reference = build_label_reference(INPUT_STRUCTURE_TYPE_SPECS)
    property_reference = build_label_reference(INPUT_STRUCTURE_PROPERTY_SPECS)
    return f"""你是编程竞赛题目输入结构分析专家。

你的任务是抽取题目的主输入结构、长度范围、值域范围和稳定性质，并在需要时补充 components。

科研定义：
- 输入结构表示题目输入在计算开始前的抽象组织形态，只描述输入如何承载信息，不描述题目情境、输出形式或求解过程中产生的中间结构。
- 该维度关注主输入载体及其稳定结构属性，包括主类型、长度范围、值域范围与可直接从题面确认的结构性质。
- 存在单一主输入载体时只标主类型。多个关键输入载体并列且不存在单一主载体时，使用 composite，并在 components 中展开。

硬规则：
1. 只输出严格 JSON 对象，不输出任何解释文字。
2. type 必须优先复用规范主类型词表：{controlled_types}。
3. 不得把题目情境词直接写进 type、properties 的键名或 components 的 role、role_description 与 type。

规范标签说明：
{type_reference}

性质键说明：
{property_reference}

证据优先级：
1. Input 分节
2. Constraints 分节
3. 题面全文
4. Output 分节
5. 标题

抽取规则：
- type 只写主结构类名，不承载 weighted_undirected_graph 这类复合标签。
- 标量输入也是合法主结构。单个 int、long long 这类整数标量统一写 integer；单个 double、float 这类实数标量统一写 float；单个字符写 char；明确的布尔标记写 boolean。
- 固定位置、固定 arity 的 pair 或 tuple 统一写 tuple。
- directed、weighted、connected、rooted、simple、acyclic、ordered、sorted、distinct、permutation、multiple_test_cases、online_queries 这类修饰信息写入 properties。
- 推荐复用的 properties 键为：{property_keys}。
- 题面没有明确证据时，length.min、length.max、value_range.min、value_range.max 写 null。
- 未识别到的性质不要补写。
- 多个关键输入结构同时出现时，写入 components；每个组件包含 role、role_description、type、length、value_range、properties。
- role_description 用简洁英文短语或短句说明该组件承载的信息职责，不重复 type。
- 顶层字段始终镜像主组件，保持旧流程兼容。
- 只有在不存在单一主结构时才使用 composite；所有已知类型都不适配时使用 other。

判别边界：
- array 用于以线性下标访问为主的输入载体。
- integer 用于单个整数或离散数值标量输入。
- float 用于单个浮点数或实数标量输入。
- char 只用于单个字符。字符序列、模式串、文本串统一写 string。
- boolean 只在题面明确给出 true、false 或等价逻辑标记输入时使用；0、1 这类数值输入仍按 integer 处理。
- tuple 用于固定位置、固定长度的元组或记录。pair 统一视为长度为 2 的 tuple。
- 普通序列、排列、集合元素列表、多重集合元素列表与查询列表，若都以线性条目形式给出，主类型统一写 array。
- set 不单列为主类型。若输入本质上是按线性条目给出的集合或多重集合，仍写 array，再用 ordered=false 与 distinct=true 或 false 表达语义。
- 题面明确要求输入是排列时，写 properties.permutation=true。
- 题面明确说明无重边、无自环或 simple graph 时，写 properties.simple=true。
- 题面明确说明不存在环时，写 properties.acyclic=true。
- 题面明确强调无序成员关系时，写 ordered=false，并用 distinct=true 或 false 区分集合与多重集合语义。
- 查询流若只是附属组件，放入 components；若题目依赖在线处理，补写 online_queries=true。
"""


def build_user_prompt(problem: Dict[str, Any]) -> str:
    problem = prepare_problem_record(problem)
    context = build_problem_context(problem)
    type_list = ", ".join(MAIN_TYPES)
    property_keys = ", ".join(INPUT_STRUCTURE_PROPERTY_KEYS)
    return f"""请根据下列题目信息抽取输入结构。

{context}

字段说明：
1. type 表示主输入载体的抽象类型。有单一主结构时填写该类型；多个关键结构并列且没有单一主载体时写 composite；所有已知类型都不适配时写 other。单个整数标量统一写 integer，单个浮点标量统一写 float，单个字符写 char，pair 和固定长度 tuple 统一写 tuple。集合型输入若按线性条目给出，仍写 array。常见误填：把 weighted_tree、query_array 这类复合语义直接写进 type。
2. length 表示主输入载体或组件的条目数量范围。有明确条目数或可由题面直接换算时填写；标量类型通常写 null；证据不足时 min 和 max 都写 null。常见误填：把值域上界写进 length，或把同一个 n 机械复制给所有组件。
3. value_range 表示单个输入值的取值范围。有明确数值边界时填写；对象不是数值载体或题面没有明确边界时写 null。常见误填：把长度范围写进 value_range，或把目标值范围当作输入值域。
4. properties 表示稳定结构性质。题面明确给出 directed、weighted、distinct 这类性质时填写；没有明确证据时写空对象。常见误填：把题目情境词、算法方法或目标要求写进 properties。
5. components 表示多个关键输入组件并列时的逐项展开。存在多个关键组件且单看顶层不足以表达时填写；只有单一主结构时可省略。常见误填：把 test case 数量、输出对象或求解过程中的中间结构写进 components。
6. components.role 表示组件角色的抽象英文名。只有 components 中的单项需要区分角色时填写；没有 components 时不出现。常见误填：把具体题意名词、整句描述或与 type 重复的复合标签写进 role。
7. components.role_description 表示组件角色的英文职责说明。只在 components 中出现，使用简洁英文短语或短句描述该组件承载的信息，不要重复 role 或 type。常见误填：留空、照抄题面整句，或把算法动作写进 role_description。

请输出 JSON：
{{
  "type": "从 {type_list} 中选择的主结构类型",
  "length": {{"min": null, "max": null}},
  "value_range": {{"min": null, "max": null}},
  "properties": {{}},
  "components": [
    {{
      "role": "组件角色英文名",
      "role_description": "组件职责英文说明",
      "type": "从 {type_list} 中选择的组件类型",
      "length": {{"min": null, "max": null}},
      "value_range": {{"min": null, "max": null}},
      "properties": {{}}
    }}
  ]
}}

要求：
1. 优先读取 Input 分节与 Constraints 分节。
2. 字段说明优先于字段名直觉，不要仅凭命名猜测字段含义。
3. type 只写主结构类名，修饰信息写入 properties。
4. 允许复用的 properties 键包括：{property_keys}。
5. 多个关键输入结构时写入 components，顶层继续镜像主组件。
6. length 与 value_range 在缺少明确证据时写 null，不要补整数。
7. 标签与键名只用抽象数据结构术语，不写题目情境词。
8. 顶层 type 为 composite 时，每个组件都必须填写非空 role 与 role_description。
"""


INPUT_STRUCTURE_SCHEMA = {
    "type": "object",
    "required": ["type", "length", "value_range", "properties"],
    "additionalProperties": True,
    "properties": {
        "type": {
            "type": "string",
            "enum": MAIN_TYPES,
            "description": "主结构类型，只允许受控词表中的主类型名称",
        },
        "length": {
            "type": "object",
            "required": ["min", "max"],
            "additionalProperties": True,
            "properties": {
                "min": {"type": ["integer", "null"]},
                "max": {"type": ["integer", "null"]},
            },
        },
        "value_range": {
            "type": "object",
            "required": ["min", "max"],
            "additionalProperties": True,
            "properties": {
                "min": {"type": ["integer", "null"]},
                "max": {"type": ["integer", "null"]},
            },
        },
        "properties": {
            "type": "object",
            "description": "稳定性质，推荐复用 directed、weighted、connected、rooted、simple、acyclic、ordered、sorted、distinct、permutation、multiple_test_cases、online_queries",
            "properties": {
                key: {"type": "boolean"}
                for key in INPUT_STRUCTURE_PROPERTY_KEYS
            },
            "additionalProperties": True,
        },
        "components": {
            "type": "array",
            "description": "可选扩展字段。存在多个关键输入组件时逐项列出",
            "items": {
                "type": "object",
                "required": ["role", "role_description", "type", "length", "value_range", "properties"],
                "additionalProperties": True,
                "properties": {
                    "role": {"type": "string"},
                    "role_description": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": MAIN_TYPES,
                    },
                    "length": {
                        "type": "object",
                        "required": ["min", "max"],
                        "additionalProperties": True,
                        "properties": {
                            "min": {"type": ["integer", "null"]},
                            "max": {"type": ["integer", "null"]},
                        },
                    },
                    "value_range": {
                        "type": "object",
                        "required": ["min", "max"],
                        "additionalProperties": True,
                        "properties": {
                            "min": {"type": ["integer", "null"]},
                            "max": {"type": ["integer", "null"]},
                        },
                    },
                    "properties": {
                        "type": "object",
                        "additionalProperties": True,
                    },
                },
            },
        },
    },
}
