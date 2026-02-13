"""
输入结构（Input Structure, I）维度的 Prompt 模板

用于抽取题目的数据组织形式，包括：
- 数据类型（array, graph, tree, string, matrix 等）
- 长度范围（min, max）
- 值域范围（min, max）
- 额外性质（如是否有序、是否连通等）

输出 JSON Schema：
{
    "type": "array | graph | tree | string | matrix | ...",
    "length": {"min": int, "max": int},
    "value_range": {"min": int, "max": int},
    "properties": {
        "ordered": bool,
        "connected": bool,
        "weighted": bool,
        ... (其他性质)
    }
}
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Dict, Any


def build_system_prompt() -> str:
    """构建系统提示词（角色定义与输出格式要求）"""
    return """你是编程竞赛题目输入结构分析专家。

你的任务是从题目描述中抽取输入数据的组织形式，包括：
1. 数据类型（如 array, graph, tree, string, matrix 等）
2. 长度/规模范围（最小值和最大值）
3. 值域范围（元素取值的最小值和最大值）
4. 额外性质（如是否有序、是否连通、是否带权等）

输出要求：
- 必须输出严格的 JSON 对象，不要输出任何解释文字
- JSON 必须包含以下字段：type, length, value_range, properties
- length 和 value_range 必须是包含 min 和 max 的对象
- properties 是包含额外性质的对象（可以为空对象 {}）

分析原则：
- 优先从题面明确给出的范围约束中提取（通常在 Constraints 部分）
- 若题面未明确给出某项约束，请根据题目逻辑合理推断并在 properties 中标注 "inferred": true
- 对于图/树结构，需要识别节点数、边数范围
- 对于字符串，需要识别长度范围和字符集
- 对于数组，需要识别元素个数和元素值域

抽象化要求（CRITICAL）：
- 所有字段值必须是算法/数据结构领域的抽象概括，严禁包含原题目的具体情境词汇
- type 字段必须用通用数据结构名称（如 array, graph, tree, string, matrix），不得使用情境名称
- properties 中的 key 必须是通用的结构性质名称（如 ordered, connected, weighted, directed, bipartite），不得使用情境词
- 反例：题目说"城市之间的公路网" → type 不能写 "city_road_network"，应写 "weighted_undirected_graph"
- 反例：题目说"糖果分配到盒子" → type 不能写 "candy_box"，应写 "array"
- 正例：题目说"朋友关系网络" → type 写 "undirected_graph"，properties 中可标注 "connected": true
"""


def build_user_prompt(problem: Dict[str, Any]) -> str:
    """
    构建用户提示词（题面内容）
    
    Args:
        problem: 题目字典，必须包含以下字段：
            - title: 题目标题
            - description: 题目描述
            - input: 输入格式说明
            - output: 输出格式说明
            - constraints: 约束条件
    
    Returns:
        格式化的用户提示词
    """
    return f"""请分析以下题目的输入结构：

标题：{problem.get('title', 'N/A')}

题目描述：
{problem.get('description', '')}

输入格式：
{problem.get('input', '')}

输出格式：
{problem.get('output', '')}

约束条件：
{problem.get('constraints', '')}

---

请输出该题的输入结构 JSON，格式如下：

{{
    "type": "数据类型（如 array, graph, tree, string, matrix 等）",
    "length": {{"min": 最小长度, "max": 最大长度}},
    "value_range": {{"min": 最小值, "max": 最大值}},
    "properties": {{
        "ordered": true/false（是否有序，可选）,
        "connected": true/false（是否连通，图/树专用，可选）,
        "weighted": true/false（是否带权，图/树专用，可选）,
        ... (其他性质)
    }}
}}

注意：
1. 如果题目有多个输入数据结构，请选择最主要的核心数据结构
2. length 和 value_range 的 min/max 必须是整数（如果题面未明确给出，请合理推断）
3. properties 中只包含明确可识别的性质，不确定的性质不要包含
4. 所有输出必须是数据结构领域的抽象概念，不得包含题目中的具体情境词汇（如人名、动物名、物品名、地名等）
"""


# JSON Schema 定义（用于文档和验证）
INPUT_STRUCTURE_SCHEMA = {
    "type": "object",
    "required": ["type", "length", "value_range", "properties"],
    "properties": {
        "type": {
            "type": "string",
            "description": "数据类型，如 array, graph, tree, string, matrix 等"
        },
        "length": {
            "type": "object",
            "required": ["min", "max"],
            "properties": {
                "min": {"type": "integer"},
                "max": {"type": "integer"}
            }
        },
        "value_range": {
            "type": "object",
            "required": ["min", "max"],
            "properties": {
                "min": {"type": "integer"},
                "max": {"type": "integer"}
            }
        },
        "properties": {
            "type": "object",
            "description": "额外性质，如 ordered, connected, weighted 等"
        }
    }
}
