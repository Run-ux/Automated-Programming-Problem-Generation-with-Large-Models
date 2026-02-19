"""
目标函数（Objective, O）维度的 Prompt 模板

用于抽取题目要求求解的目标类型，包括：
- 最大值 / 最小值（如最长子数组、最短路径）
- 计数（如满足条件的区间数量）
- 判定（是否存在合法解）
- 构造（输出一个满足条件的方案）

输出 JSON Schema：
{
    "type": "max_length | min_cost | count | decision | construction | ...",
    "description": "目标函数的中文描述"
}
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Dict, Any


def build_system_prompt() -> str:
    """构建系统提示词（角色定义与输出格式要求）"""
    return """你是编程竞赛题目目标函数分析专家。

你的任务是识别题目要求求解的目标类型。

常见目标类型（优先从中选择，但允许必要时新增）：
1. maximize_value（最大化值）：最大和、最大积、最大距离、最大面积
2. minimize_value（最小化值）：最小代价、最短路径、最小距离
3. maximize_count（最大化计数）：最大匹配数、最大方案数
4. minimize_count（最小化计数）：最少操作次数、最少删除数
5. maximize_probability（最大化概率/期望）：最大期望收益
6. minimize_probability（最小化概率/期望）：最小期望代价
7. min_max（极小化极大）：瓶颈路径、最小化最大值
8. max_min（极大化极小）：最大化最小值
9. lexicographic_optimize（字典序优化）：最小/最大字典序
10. feasibility（可行性判定）：是否存在解
11. construction（构造）：输出任意/最优方案
12. enumeration（计数/枚举）：求方案数（常取模）
13. multi_objective（多目标优化）：同时优化多个指标
14. game_outcome（博弈结果）：先手胜/后手胜/平局

输出要求：
- 必须输出严格的 JSON 对象，不要输出任何解释文字
- JSON 必须包含 type 和 description 字段
- type 必须是简洁的英文标识（如 max_length, count, decision）
- description 必须清晰描述目标函数的含义
- 如果推荐清单中没有合适类型，必须自由新增更准确的目标类型，不要为了套用而强行归类

识别原则：
1. 优先从题目标题和输出要求中识别
2. 关键词识别：
   - "最长"、"最大" → max_*
   - "最短"、"最小" → min_*
   - "有多少"、"计数" → count
   - "是否存在"、"能否" → decision
   - "输出任意"、"构造一个" → construction
3. 如果题目有多个子问题，选择主要目标

抽象化要求（CRITICAL）：
- type 和 description 必须用算法领域的抽象术语，严禁包含原题目的具体情境词汇
- 必须将题目情境翻译为通用的算法优化目标
- 反例：题目说"求鲨鱼能吃到的最多鱿鱼数" → type 不能写 "max_squid"，应写 "max_matching" 或 "max_count"
- 反例：题目说"求从家到学校的最短路" → description 不能写 "求从家到学校的最短路"，应写 "求两点间最短路径长度"
- 正例：题目说"收集最多金币" → type 写 "max_sum"，description 写 "最大化路径上的权值和"
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
    return f"""请识别以下题目的目标函数：

标题：{problem.get('title', 'N/A')}

题目描述：
{problem.get('description', '')}

输入格式：
{problem.get('input', '')}

输出格式（重点关注）：
{problem.get('output', '')}

约束条件：
{problem.get('constraints', '')}

---

请输出该题的目标函数 JSON，格式如下：

{{
    "type": "目标类型（maximize_value, minimize_value, maximize_count, feasibility, construction 等）",
    "description": "目标函数的中文描述（如：求满足条件的最长子数组长度）"
}}

注意：
1. type 必须简洁且符合常见分类（maximize_*, minimize_*, count, feasibility, construction 等）
2. description 必须完整描述题目要求输出什么
3. 如果题目要求输出多个值，选择主要目标（通常是第一个或最重要的）
4. 常见模式：
   - 求"最长"、"最大" → maximize_value
   - 求"最短"、"最小" → minimize_value
   - 求"有多少个" → enumeration 或 maximize_count
   - 判断"是否存在" → feasibility
   - 要求"输出方案" → construction
5. 所有输出必须是算法领域的抽象概括，不得包含题目中的具体情境词汇（如角色名、物品名等），需翻译为通用的算法术语
6. 如果推荐清单中没有合适类型，必须自由新增更准确的目标类型，不要为了套用而强行归类
"""


OBJECTIVE_SCHEMA = {
    "type": "object",
    "required": ["type", "description"],
    "properties": {
        "type": {
            "type": "string",
        "description": "目标类型，如 maximize_value, minimize_value, maximize_count, feasibility, construction"
        },
        "description": {
            "type": "string",
            "description": "目标函数的中文描述"
        }
    }
}
