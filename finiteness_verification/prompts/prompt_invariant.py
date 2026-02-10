"""
算法不变量（Invariant, V）维度的 Prompt 模板

用于抽取题目解法中始终成立的结构性条件，包括：
- 双指针左右端点单调前进
- 前缀和可叠加
- DP 状态只依赖子状态
- 贪心选择性质
等。

不变量几乎决定了解法范式，是母题识别的核心依据。

输出 JSON Schema：
{
    "name": "monotonicity | optimal_substructure | greedy_choice | ...",
    "description": "不变量的中文描述",
    "properties": {
        "left_monotonic": true/false,
        "right_monotonic": true/false,
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
    return """你是编程竞赛算法不变量分析专家。

你的任务是识别题目解法中始终成立的结构性条件（算法不变量）。

算法不变量定义：
在算法执行过程中，始终保持成立的性质或条件，是算法正确性的核心保证。

常见不变量类型：
1. 单调性（monotonicity）
   - 双指针：左右端点单调前进
   - 滑动窗口：窗口右端点单调递增
   - 二分搜索：搜索区间单调缩小

2. 最优子结构（optimal_substructure）
   - DP：最优解包含子问题的最优解
   - 分治：大问题的解由子问题的解组合而成

3. 贪心选择性质（greedy_choice）
   - 局部最优选择导致全局最优
   - 每步选择后不需要回溯

4. 状态依赖（state_dependency）
   - DP 状态只依赖有限的前序状态
   - 马尔可夫性质：当前状态只依赖前一状态

5. 区间可合并性（interval_mergeable）
   - 前缀和：区间和可通过端点差值计算
   - 线段树：区间信息可通过子区间合并

输出要求：
- 必须输出严格的 JSON 对象，不要输出任何解释文字
- JSON 必须包含 name, description, properties 字段
- name 必须是简洁的英文标识（如 monotonicity, greedy_choice）
- description 必须清晰描述不变量的含义
- properties 包含具体的性质（可以为空对象 {}）

识别原则：
1. 不变量不是题目要求，而是解法的结构性质
2. 不变量决定了"为什么这个算法成立"
3. 优先识别主流算法范式的典型不变量
4. 如果题目解法不明确，可以根据输入结构和约束推断可能的不变量
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
    return f"""请识别以下题目解法的算法不变量：

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

请输出该题解法的算法不变量 JSON，格式如下：

{{
    "name": "不变量类型（monotonicity, optimal_substructure, greedy_choice, state_dependency, interval_mergeable 等）",
    "description": "不变量的中文描述（如：双指针左右端点单调前进，区间合法性可单调维护）",
    "properties": {{
        "left_monotonic": true/false (双指针专用，可选),
        "right_monotonic": true/false (双指针专用，可选),
        "window_shrinkable": true/false (滑动窗口专用，可选),
        ... (其他性质)
    }}
}}

注意：
1. 不变量是解法的性质，不是题目要求
2. 常见算法范式的不变量：
   - 双指针/滑动窗口 → monotonicity（单调性）
   - 动态规划 → optimal_substructure（最优子结构）
   - 贪心算法 → greedy_choice（贪心选择性质）
   - 前缀和 → interval_mergeable（区间可合并性）
3. 如果题目没有明显的算法不变量，可以根据输入结构和约束推断
4. properties 中只包含明确可识别的性质，不确定的不要填写
5. 优先选择最主要的不变量（如果有多个，选择最核心的一个）
"""


INVARIANT_SCHEMA = {
    "type": "object",
    "required": ["name", "description", "properties"],
    "properties": {
        "name": {
            "type": "string",
            "description": "不变量类型，如 monotonicity, optimal_substructure, greedy_choice"
        },
        "description": {
            "type": "string",
            "description": "不变量的中文描述"
        },
        "properties": {
            "type": "object",
            "description": "具体性质，如 left_monotonic, right_monotonic 等"
        }
    }
}
