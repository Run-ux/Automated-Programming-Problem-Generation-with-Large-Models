# Problem Schema 五元组的正式定义

## 1. 引入 Problem Schema 的动机

为了实现可扩展、可去重、可自动生成的编程竞赛题目生成系统，本项目将每一道题目抽象为一个 **Problem Schema**。

Problem Schema 的设计目标包括：

- **可扩展性**：支持在同一算法原型下进行参数化与组合式变形
- **可去重性**：能够在结构层面判定不同题目是否属于同一母题
- **可生成性**：为题目生成器、数据生成器和解法生成器提供结构化输入

为此，本项目将 Problem Schema 形式化为一个**五元组表示**。

---

## 2. Problem Schema 五元组定义

一个 Problem Schema 被定义为如下五元组：

S = (I, C, O, V, T)

其中：

- `I`：Input Structure（输入结构）
- `C`：Core Constraints（核心约束集合）
- `O`：Objective（目标函数）
- `V`：Invariant（算法不变量）
- `T`：Transform Space（可变参数空间）

该五元组用于描述一类编程竞赛题目的**算法本质**，而非某一道具体题目。

---

## 3. 五元组各组成部分的含义与设计动机

### 3.1 输入结构（Input Structure, I）

#### 含义

输入结构用于描述题目的数据组织形式，包括但不限于：

- 一维数组
- 图（有向 / 无向）
- 树
- 字符串
- 矩阵

#### 设计动机

- 输入结构是算法选择的第一决定因素
- 不同输入结构通常对应完全不同的解题范式
- 在 Schema 层面明确输入结构，有助于：
  - 快速分类母题
  - 约束解法生成范围

#### Python 结构设计

```python
@dataclass
class InputStructure:
    type: str                    # 如 "array", "graph", "tree"
    length: Dict[str, int]       # {"min": 1, "max": 200000}
    value_range: Dict[str, int]  # {"min": 0, "max": 10**9}
    properties: Dict[str, Any]   # 额外性质，如是否有序
```

### 3.2 核心约束集合（Core Constraints, C）

#### 含义

核心约束描述题目中必须满足的限制条件，例如：

- 区间内不同元素个数 ≤ K
- 最大值 − 最小值 ≤ D
- 路径长度限制
- 状态转移合法性条件

约束被视为一个集合，而非单一条件。

#### 设计动机

- 约束集合决定了问题的"难度形态"
- 多约束的组合是竞赛题难度提升的主要手段
- 将约束显式建模，有利于：
  - 约束组合生成
  - Schema 相似度计算（去重）

#### Python 结构设计

```python
@dataclass
class Constraint:
    name: str
    description: str
    check: Callable[[Dict[str, Any]], bool]
```

约束集合表示为：

```python
core_constraints: List[Constraint]
```

示例：不同元素个数 ≤ K

```python
def distinct_leq_k(ctx):
    return ctx["distinct"] <= ctx["K"]

constraint_distinct = Constraint(
    name="distinct_leq_k",
    description="区间内不同元素数量不超过 K",
    check=distinct_leq_k
)
```

### 3.3 目标函数（Objective, O）

#### 含义

目标函数描述题目要求求解的目标类型，例如：

- 最大值 / 最小值（如最长子数组）
- 计数（如满足条件的区间数量）
- 判定（是否存在合法解）

#### 设计动机

- 同一算法结构在不同目标下可形成不同题目
- 目标函数变化通常不改变算法不变量
- 将目标函数单独建模，有助于：
  - 生成同一 Schema 下的不同题型
  - 控制题目难度梯度

#### Python 结构设计

```python
@dataclass
class Objective:
    type: str          # "max_length", "count", "decision"
    description: str
```

### 3.4 算法不变量（Invariant, V）

#### 含义

算法不变量用于描述题目解法中始终成立的结构性条件，例如：

- 双指针左右端点单调前进
- 前缀和可叠加
- DP 状态只依赖子状态

#### 设计动机（最核心）

- 不变量几乎决定了解法范式
- 不同不变量对应本质不同的母题
- 在 Schema 去重与距离计算中，不变量权重最高

可以认为：

> 不变量定义了"为什么这个算法成立"。

#### Python 结构设计

```python
@dataclass
class Invariant:
    name: str
    description: str
    properties: Dict[str, Any]
```

示例（双指针）

```python
invariant = Invariant(
    name="two_pointer",
    description="左右指针单调前进，区间合法性可单调维护",
    properties={
        "left_monotonic": True,
        "right_monotonic": True,
        "window_shrinkable": True
    }
)
```

### 3.5 可变参数空间（Transform Space, T）

#### 含义

可变参数空间定义了在不破坏不变量的前提下，题目可被变形的维度，例如：

- 参数 K、D 的取值范围
- 是否允许多约束叠加
- 目标函数是否可切换
- 数据规模等级

#### 设计动机

- 这是自动出题系统的"调节旋钮"
- 决定同一 Schema 能生成多少不同题目
- 用于控制难度与多样性

#### Python 结构设计

```python
transform_params: Dict[str, Any]
```

示例：

```python
transform_params = {
    "K": {"min": 1, "max": 100000},
    "D": {"min": 0, "max": 10**9},
    "objective_options": ["max_length", "count"],
    "multi_constraints": True
}
```

## 4. 完整 Problem Schema 的 Python 表示

综合上述五个部分，一个 Problem Schema 在 Python 中表示为：

```python
@dataclass
class ProblemSchema:
    name: str
    input_structure: InputStructure
    core_constraints: List[Constraint]
    objective: Objective
    invariant: Invariant
    transform_params: Dict[str, Any]
```

该结构具备以下特性：

- 可序列化（JSON / 数据库存储）
- 可用于 Schema 距离计算
- 可直接作为自动出题模块的输入

## 5. 五元组如何支撑系统三大能力

### 5.1 可扩展性

- Transform Space 提供参数化与组合能力
- 同一 Schema 可生成大量题目实例

### 5.2 可去重性

- 基于五元组定义 Schema 距离函数
- 在结构层面判断母题是否相同或相近

### 5.3 可生成性

- 输入结构指导数据生成
- 约束集合与目标函数指导题面生成
- 不变量指导解法与验证器生成

## 6. 本阶段小结

本节正式定义了 Problem Schema 五元组，并从：

- 理论建模
- 工程实现
- 系统能力支撑

三个角度说明了其必要性与可行性。

该五元组构成了本项目后续所有模块的统一中间表示。