"""
核心约束集合（Core Constraints, C）维度的 Prompt 模板

用于从题目描述中抽取必须满足的限制条件，包括：
- 区间内不同元素个数 ≤ K
- 最大值 − 最小值 ≤ D
- 路径长度限制
- 状态转移合法性条件
等。

CRITICAL: 约束必须从题面全文提取（description + input + output + constraints），
因为 CF/ICPC 的 constraints 字段通常只包含时间/内存限制，而真正的业务约束
散布在题目描述、输入输出格式说明中。

输出 JSON Schema：
{
    "constraints": [
        {
            "name": "约束名称（如 distinct_leq_k）",
            "description": "约束描述（如：区间内不同元素数量不超过 K）",
            "formal": "形式化表达（可选，如：|distinct(A[l:r])| <= K）"
        },
        ...
    ]
}
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Dict, Any


def build_system_prompt() -> str:
    """构建系统提示词（角色定义与输出格式要求）"""
    return """你是编程竞赛题目约束条件分析专家。

你的任务是从题目描述的全文中抽取所有核心约束条件。

约束来源（按优先级）：
1. 题目描述（Description）- 通常包含问题的业务逻辑约束
2. 输入格式（Input）- 可能包含输入数据的合法性约束
3. 输出格式（Output）- 可能包含输出结果的约束条件
4. 约束条件（Constraints）- 通常只包含时间/内存限制，但也可能包含数值范围约束

CRITICAL WARNING:
- 不要只看 Constraints 字段！大部分业务约束在 Description 和 Input/Output 中！
- Constraints 字段通常只写"1 ≤ n ≤ 10^5"和"Time Limit: 2s"这种，真正的约束在题面里！

输出要求：
- 必须输出严格的 JSON 对象，不要输出任何解释文字
- JSON 必须包含 constraints 数组字段
- 每个约束必须包含 name 和 description 字段
- formal 字段可选（形式化表达，如数学公式或伪代码）
- 如果推荐清单中没有合适标签，必须自由新增更准确的标签，不要为了套用而强行归类

约束识别原则：
1. 识别限制条件：如"区间内不同元素个数不超过 K"、"路径长度不超过 L"
2. 识别关系约束：如"最大值减最小值不超过 D"、"相邻元素差值不超过 1"
3. 识别结构约束：如"图必须连通"、"数组必须非递减"
4. 识别逻辑约束：如"选择的元素不能重复"、"每个节点最多访问一次"
5. 排除纯粹的数值范围：如"1 ≤ n ≤ 10^5"不算核心约束，只是输入规模
6. 排除时间/内存限制：如"Time Limit: 2s"不算业务约束

抽象化要求（CRITICAL）：
- 约束的 name 和 description 必须用算法/数据结构领域的抽象术语，严禁包含原题目的具体情境词汇
- 必须将题目情境翻译为算法领域的通用概念
- 反例：题目说"鲨鱼不能吃同种鱿鱼" → name 不能写 "shark_eat_squid_limit"，应写 "pairwise_exclusion" 或 "matching_constraint"
- 反例：题目说"每个城市最多修建3条公路" → name 不能写 "city_road_limit"，应写 "degree_upper_bound"
- 正例：题目说"相邻房间不能涂相同颜色" → name 写 "adjacent_difference"，description 写 "相邻节点取值不同（图着色约束）"
- 正例：题目说"背包重量不超过W" → name 写 "capacity_constraint"，description 写 "选取元素权重和不超过容量上限"

推荐的约束类型清单（优先从中选择，但允许必要时新增）：
图论约束：
- connectivity（连通性）
- acyclicity（无环性）
- planarity（平面性）
- bipartiteness（二部性）
- degree_bound（度数约束）
- path_constraint（路径约束）
- matching_constraint（匹配约束）
- flow_constraint（流量/容量约束）
- coloring_constraint（染色约束）
- spanning_constraint（生成结构约束）

序列/数组约束：
- ordering（有序性）
- distinctness（唯一性/去重）
- adjacency_relation（相邻关系）
- frequency_bound（频次约束）
- subsequence_constraint（子序列约束）
- permutation_constraint（排列约束）

数值/代数约束：
- range_bound（值域约束）
- sum_constraint（和约束）
- divisibility（整除/同余）
- parity（奇偶性）
- linear_relation（线性关系）
- modular_arithmetic（模运算约束）

几何约束：
- convexity（凸性）
- distance_bound（距离约束）
- intersection（相交关系）
- orientation（方向/朝向约束）

集合/组合约束：
- subset_constraint（子集约束）
- partition（划分约束）
- coverage（覆盖约束）
- exclusion（互斥/禁止）
- inclusion（包含/必选）

操作/过程约束：
- operation_limit（操作次数限制）
- operation_type（操作类型限制）
- state_transition（状态转移约束）
- concurrency（并发/同步约束）
- reversibility（可逆性）
- transformation（变换/操作规则）

字符串约束：
- palindrome（回文约束）
- pattern_matching（模式匹配）
- alphabet_constraint（字符集约束）
- repetition（重复性/周期性）

博弈/交互约束：
- turn_based（回合制）
- optimal_play（最优策略）
- query_limit（询问次数限制）

概率/随机约束：
- probability_distribution（概率分布约束）
- independence（独立性约束）

规则：
1. 优先使用上述清单中的标签作为 name。
2. 如果确实没有匹配项，允许创建新标签（必须抽象化且简洁）。
3. 避免对同一约束创建多种同义标签。
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
    return f"""请从以下题目的全文中抽取核心约束条件：

标题：{problem.get('title', 'N/A')}

题目描述（IMPORTANT - 主要约束来源）：
{problem.get('description', '')}

输入格式（可能包含约束）：
{problem.get('input', '')}

输出格式（可能包含约束）：
{problem.get('output', '')}

约束条件（通常只有时间/内存/数值范围）：
{problem.get('constraints', '')}

---

请输出该题的核心约束集合 JSON，格式如下：

{{
    "constraints": [
        {{
            "name": "约束的简短英文标识（如 distinct_leq_k, max_min_diff_leq_d）",
            "description": "约束的中文描述（清晰完整，如：区间内不同元素数量不超过 K）",
            "formal": "形式化表达（可选，如：|distinct(A[l:r])| <= K）"
        }},
        ...
    ]
}}

注意：
1. 必须阅读题目描述全文，不要只看 Constraints 字段！
2. 只提取业务逻辑约束，不包括：
   - 纯粹的数值范围（如 1 ≤ n ≤ 10^5）
   - 时间/内存限制（如 Time Limit: 2s）
3. 如果题目没有明显的业务约束，返回空数组 []
4. 每个约束的 description 必须清晰完整，能够独立理解
5. formal 字段可选，如果能用数学公式或伪代码表达清楚，则填写
6. 所有约束的 name 和 description 必须是算法领域的抽象概括，不得包含题目中的具体情境词汇（如角色名、物品名、场景名等），需翻译为通用的算法/数据结构术语
7. 如果推荐清单中没有合适标签，必须自由新增更准确的标签，不要为了套用而强行归类
"""


CONSTRAINTS_SCHEMA = {
    "type": "object",
    "required": ["constraints"],
    "properties": {
        "constraints": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "description"],
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "formal": {"type": "string"}
                }
            }
        }
    }
}
