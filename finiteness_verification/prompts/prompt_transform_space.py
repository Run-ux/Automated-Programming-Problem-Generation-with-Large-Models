"""
可变参数空间（Transform Space, T）维度的 Prompt 模板

用于抽取题目中可变形、可调整的参数空间，描述在不改变核心算法（Invariant）的前提下，
可以通过调整哪些“旋钮”来生成不同的题目实例。

包括：
- 数值参数及其范围（如 K, D, 阈值 等）
- 潜在的约束组合（开关项）
- 目标函数的可替换选项（如是否可转为计数、判定）

输出 JSON Schema：
{
    "numerical_parameters": {
        "参数名": {"min": int, "max": int, "description": "描述"},
        ...
    },
    "objective_options": ["max_value", "count", "decision", ...],
    "structural_options": ["multi_constraints", "negative_values", ...]
}
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Dict, Any


def build_system_prompt() -> str:
    """构建系统提示词（角色定义与输出格式要求）"""
    return """你是编程竞赛题目生成与变形专家。

你的任务是分析给定的题目，识别其 "Problem Schema" 的第五维度：**可变参数空间 (Transform Space)**。
可变参数空间定义了在不破坏题目核心算法结构（Invariants）和输入结构（Input Structure）的前提下，可以调整哪些因素来生成新的题目实例。

请分析以下维度：
1. **数值参数 (Numerical Parameters)**：
   - 识别题目中出现的、决定题目具体形态的关键常数或变量（例如："选取 K 个元素" 中的 K，"差值不大于 D" 中的 D）。
   - 识别题目中硬编码的数字，这些数字应当被参数化（例如：题目说"除以3"，则模数 3 可被参数化为 M）。
   - 为这些参数提供合理的数值范围（考虑到算法复杂度，通常对应 $O(N)$, $O(N \log N)$ 或 $O(N^2)$ 等）。

2. **目标函数可变性 (Objective Options)**：
   - 在保持核心约束和算法逻辑不变的情况下，该题目还可以产生哪些类型的目标？
   - 例如：原题求"最大值"，是否可以求"方案数"？是否可以求"是否存在"（判定）？

3. **结构选项 (Structural Options)**：
   - 识别哪些约束是可以"开关"的（例如：是否允许负数？是否允许重复元素？）。
   - 识别是否支持多重约束叠加。

输出要求：
- 必须输出严格的 JSON 对象。
- JSON 必须包含 `numerical_parameters`, `objective_options`, `structural_options` 三个字段。
- `numerical_parameters` 是一个字典，键为参数名（如 "K", "D", "M"），值为包含 `min`, `max`, `description` 的对象。
- `objective_options` 是字符串列表，包含可能的目标类型（如 "maximize", "minimize", "count", "decision"）。
- `structural_options` 是字符串列表，描述可变的可选约束或变种方向。

分析原则：
- **参数化思维**：不要局限于原题的具体数值，要思考"如果我们是出题人，可以用什么变量来替换这个数字"。
- **有限性**：只提取影响题目逻辑的关键参数，忽略输入数据规模本身（如 N, M 通常属于 Input Structure，不需要在这里重复，除非它们作为约束阈值出现）。
"""


def build_user_prompt(problem: Dict[str, Any]) -> str:
    """
    构建用户提示词（题面内容）
    
    Args:
        problem: 题目字典，必须包含 title, description, constraints 等字段
    
    Returns:
        格式化的用户提示词
    """
    return f"""请分析以下题目的可变参数空间（Transform Space）：

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

请输出该题的可变参数空间 JSON，格式如下：

{{
    "numerical_parameters": {{
        "参数名 (如 K, D, Modulo)": {{
            "min": 最小合理值 (int),
            "max": 最大合理值 (int),
            "description": "参数含义描述"
        }},
        ...
    }},
    "objective_options": [
        "当前目标类型 (如 minimize_length)",
        "潜在其他目标 (如 boolean_decision)"
    ],
    "structural_options": [
        "描述可变形的结构选项，如 'allow_negative_weights'",
        "multi_constraints"
    ]
}}

注意：
1. 如果题目中包含具体数字（如"长度为3的子串"），请将其抽象为参数（如 "Length_L"）。
2. min/max 范围应基于常见算法竞赛的时间限制（1秒）和该类算法的通常复杂度估算。
3. 如果没有显著的可变参数，numerical_parameters 可以为空。
"""


# JSON Schema 定义（用于文档和验证）
TRANSFORM_SPACE_SCHEMA = {
    "type": "object",
    "required": ["numerical_parameters", "objective_options", "structural_options"],
    "properties": {
        "numerical_parameters": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "required": ["min", "max", "description"],
                "properties": {
                    "min": {"type": "integer"},
                    "max": {"type": "integer"},
                    "description": {"type": "string"}
                }
            }
        },
        "objective_options": {
            "type": "array",
            "items": {"type": "string"}
        },
        "structural_options": {
            "type": "array",
            "items": {"type": "string"}
        }
    }
}
