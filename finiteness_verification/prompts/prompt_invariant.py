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
    "invariants": [
        {
            "name": "monotonicity | optimal_substructure | greedy_choice | ...",
            "description": "不变量的中文描述",
            "properties": {
                "left_monotonic": true/false,
                "right_monotonic": true/false,
                ... (其他性质)
            }
        }
    ]
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

常见不变量类型（优先从中选择，但允许必要时新增）：
1. monotonicity（单调性）
   - 双指针：左右端点单调前进
   - 滑动窗口：窗口右端点单调递增
   - 二分搜索：搜索区间单调缩小

2. optimal_substructure（最优子结构）
   - DP：最优解包含子问题的最优解

3. greedy_choice（贪心选择性质）
   - 局部最优选择导致全局最优

4. state_transition（状态转移不变量）
   - 状态机 DP、博弈 DP 的转移一致性

5. interval_additivity（区间可加性）
   - 前缀和：区间和可通过端点差值计算

6. interval_mergeable（区间可合并性）
   - 线段树：区间信息可通过子区间合并

7. divide_conquer（分治不变量）
   - 大问题的解由子问题解合成

8. topological_order（拓扑序不变量）
   - DAG 上的顺序依赖

9. flow_conservation（流守恒）
   - 网络流中的守恒性质

10. matroid_exchange（拟阵交换性）
    - 最小生成树等贪心正确性基础

11. convexity（凸性不变量）
    - 凸壳、斜率优化中的凸性结构

12. symmetry（对称性）
    - 对称变换不改变问题结构

13. idempotency（幂等性）
    - RMQ/倍增等可重复合并

14. prefix_decomposability（前缀可分解性）
    - KMP/Z 函数的前缀结构

15. cycle_invariant（环不变量）
    - 置换环、判圈性质

16. subproblem_independence（子问题独立性）
    - 分治或 DP 中子问题相互独立

17. exchange_argument（交换论证）
    - 邻项交换贪心证明

18. potential_function（势函数）
    - 均摊分析中的势函数不变量

输出要求：
- 必须输出严格的 JSON 对象，不要输出任何解释文字
- JSON 必须包含 invariants 数组字段
- 每个不变量必须包含 name, description, properties 字段
- name 必须是简洁的英文标识（如 monotonicity, greedy_choice）
- description 必须清晰描述不变量的含义
- properties 包含具体的性质（可以为空对象 {}）
- 如果推荐清单中没有合适类型，必须自由新增更准确的不变量类型，不要为了套用而强行归类
- 如果存在多个关键不变量，必须全部输出，不要只选一个

识别原则：
1. 不变量不是题目要求，而是解法的结构性质
2. 不变量决定了"为什么这个算法成立"
3. 优先识别主流算法范式的典型不变量
4. 如果题目解法不明确，可以根据输入结构和约束推断可能的不变量

抽象化要求（CRITICAL）：
- name、description 和 properties 的 key 必须用算法领域的抽象术语，严禁包含原题目的具体情境词汇
- 不变量描述的是算法的结构性质，不是题目故事的叙述
- 反例：题目说"机器人每次只能向右或向下走" → description 不能写 "机器人移动方向限制"，应写 "状态转移方向受限（仅向右/向下），满足 DAG 上的最优子结构"
- 反例：题目说"每轮拍卖价格递增" → name 不能写 "auction_price_increase"，应写 "monotonicity"
- 正例：题目说"蚂蚁在树上爬行相遇会掉头" → name 写 "symmetry"，description 写 "对称性：碰撞等价于穿越，可消除个体差异"
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
    "invariants": [
        {{
            "name": "不变量类型（monotonicity, optimal_substructure, greedy_choice, state_transition, interval_additivity, interval_mergeable 等）",
            "description": "不变量的中文描述（如：双指针左右端点单调前进，区间合法性可单调维护）",
            "properties": {{
                "left_monotonic": true/false (双指针专用，可选),
                "right_monotonic": true/false (双指针专用，可选),
                "window_shrinkable": true/false (滑动窗口专用，可选),
                ... (其他性质)
            }}
        }}
    ]
}}

注意：
1. 不变量是解法的性质，不是题目要求
2. 常见算法范式的不变量：
   - 双指针/滑动窗口 → monotonicity（单调性）
   - 动态规划 → optimal_substructure（最优子结构）
   - 贪心算法 → greedy_choice（贪心选择性质）
   - 前缀和 → interval_additivity（区间可加性）
   - 线段树/ST 表 → interval_mergeable（区间可合并性）
3. 如果题目没有明显的算法不变量，可以根据输入结构和约束推断
4. properties 中只包含明确可识别的性质，不确定的不要填写
5. 如果存在多个关键不变量，必须全部输出，不要只选一个
6. 所有输出必须是算法领域的抽象概括，不得包含题目的具体情境词汇（如角色名、物品名等），需要从算法结构性质的角度进行描述
7. 如果推荐清单中没有合适类型，必须自由新增更准确的不变量类型，不要为了套用而强行归类
"""


INVARIANT_SCHEMA = {
    "type": "object",
    "required": ["invariants"],
    "properties": {
        "invariants": {
            "type": "array",
            "items": {
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
        }
    }
}
