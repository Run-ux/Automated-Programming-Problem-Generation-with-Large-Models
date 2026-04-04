from __future__ import annotations


INPUT_STRUCTURE_TYPE_LABELS = [
    ("integer", "单个整数或整数标量输入"),
    ("float", "单个浮点数或实数标量输入"),
    ("char", "单个字符输入"),
    ("boolean", "单个布尔标记输入"),
    ("tuple", "定长元组、pair 或记录型输入"),
    ("array", "线性数组或列表输入"),
    ("string", "字符串输入"),
    ("matrix", "二维矩阵或网格输入"),
    ("graph", "一般图输入"),
    ("tree", "树输入"),
    ("composite", "不存在单一主结构的复合输入"),
    ("other", "以上类别都不适配时使用"),
]


INPUT_STRUCTURE_PROPERTY_KEYS = [
    "directed",
    "weighted",
    "connected",
    "rooted",
    "ordered",
    "sorted",
    "distinct",
    "permutation",
    "cyclic",
    "multiple_test_cases",
    "online_queries",
]


CORE_CONSTRAINT_LABELS = [
    ("connectivity", "连通性或可达性约束"),
    ("acyclicity", "无环性约束"),
    ("planarity", "平面性约束"),
    ("bipartiteness", "二部性约束"),
    ("degree_bound", "度数上下界约束"),
    ("path_constraint", "路径限制，如简单路径或长度限制"),
    ("matching_constraint", "匹配约束"),
    ("flow_constraint", "流量、容量或守恒约束"),
    ("coloring_constraint", "染色相关约束"),
    ("spanning_constraint", "生成结构约束"),
    ("order_constraint", "有序性、相对位置或排序相关约束"),
    ("distinctness", "唯一性或互异性约束"),
    ("adjacency_relation", "相邻关系约束"),
    ("frequency_bound", "频次上界或下界约束"),
    ("subsequence_constraint", "子序列或子串约束"),
    ("permutation_constraint", "排列或置换约束"),
    ("range_bound", "具有语义作用的范围约束"),
    ("sum_constraint", "和相关约束"),
    ("divisibility", "整除或同余约束"),
    ("parity", "奇偶性约束"),
    ("linear_relation", "线性关系约束"),
    ("modular_arithmetic", "模运算约束"),
    ("convexity", "凸性约束"),
    ("distance_bound", "距离约束"),
    ("overlap_constraint", "相交或重叠关系约束"),
    ("orientation_constraint", "方向或朝向约束"),
    ("subset_constraint", "子集选择约束"),
    ("partition", "划分约束"),
    ("coverage", "覆盖约束"),
    ("exclusion", "互斥或禁止约束"),
    ("inclusion", "包含或必选约束"),
    ("operation_limit", "操作次数或配额约束"),
    ("operation_type", "允许操作类型约束"),
    ("state_transition", "状态转移合法性约束"),
    ("rewrite_rule", "变换、替换或映射规则约束"),
    ("palindrome", "回文约束"),
    ("pattern_matching", "模式匹配约束"),
    ("alphabet_constraint", "字符集约束"),
    ("periodicity", "重复性或周期性约束"),
    ("optimal_play", "最优策略约束"),
    ("probability_distribution", "概率分布约束"),
    ("independence", "独立性约束"),
]


OBJECTIVE_LABELS = [
    ("maximize_value", "最大化某个值"),
    ("minimize_value", "最小化某个值"),
    ("maximize_count", "最大化可选数量"),
    ("minimize_count", "最小化数量或操作次数"),
    ("maximize_expected_value", "最大化期望值"),
    ("minimize_expected_value", "最小化期望值"),
    ("min_max", "极小化极大值"),
    ("max_min", "极大化极小值"),
    ("lexicographic_optimize", "字典序优化"),
    ("feasibility", "判定是否存在合法解"),
    ("construction", "输出一个合法或最优方案"),
    ("enumeration", "统计合法方案数"),
    ("game_outcome", "判断博弈结果"),
]


INVARIANT_LABELS = [
    ("monotonicity", "单调推进或单调边界不变量"),
    ("state_transition", "状态转移不变量"),
    ("interval_additivity", "区间可加性不变量"),
    ("interval_mergeable", "区间可合并性不变量"),
    ("topological_order", "拓扑顺序不变量"),
    ("flow_conservation", "流守恒不变量"),
    ("convexity", "凸性不变量"),
    ("symmetry", "对称性不变量"),
    ("idempotency", "幂等性不变量"),
    ("exchange_argument", "交换论证不变量"),
    ("potential_function", "势函数不变量"),
]


CONSTRAINT_SOURCE_SECTIONS = [
    "description",
    "input",
    "output",
    "constraints",
]


INVARIANT_EVIDENCE_SOURCES = [
    "statement",
    "solution_code",
    "both",
]
