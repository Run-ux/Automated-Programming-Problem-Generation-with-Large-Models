# 项目背景与总体目标

## 1. 研究背景

在编程竞赛与算法教学场景中，传统题目构建方式主要依赖人工设计。这种方式存在以下问题：

- 出题成本高，难以规模化
- 题目风格和难度不稳定
- 题目之间容易出现结构性重复
- 难以根据指定算法或考点进行定向生成

随着大语言模型（LLM）在程序理解与生成方面能力的提升，利用 AI 自动生成编程竞赛题目成为可能。然而，直接“从零生成题目”容易导致：

- 算法模型不清晰
- 题目质量不稳定
- 难以控制题目多样性与重复率

因此，有必要构建一套**结构化、可解释、可扩展的 AI 自动出题框架**。

---

## 2. 核心思想概述

本项目的核心思想是：

> **将编程竞赛题目抽象为 Problem Schema，并以 Schema 为核心驱动自动出题流程。**

具体而言：

- 不直接让 AI 从空白生成题目
- 而是从一组“母题”中抽象出稳定的算法结构（Schema）
- 再基于 Schema 进行系统化变形与组合，生成新题

---

## 3. 三层问题建模结构

在本项目中，编程竞赛问题被划分为三个层级：

- **具体题目（Problem）**  
  指某一次竞赛或平台上的具体题目描述

- **Schema 实例**  
  在母题 Schema 基础上，给定具体参数（如数据范围、约束组合）形成的题目实例

- **母题 Schema**  
  抽象后的算法结构原型，用于描述一类题目的共性解法与不变量

本项目的目标是：  
**自动构建高质量的母题 Schema 库，并基于该库生成大量不重复、难度可控的新题。**

---

## 4. 技术路线概览

整体技术路线如下：

1. 从高质量竞赛平台收集候选题目文本
2. 使用大语言模型自动抽取每道题的 Problem Schema 五元组
3. 基于 Schema 距离函数进行母题去重与聚类
4. 构建母题 Schema 库
5. 基于 Schema 与变形规则自动生成新题与对应解法

---

## 5. 项目最终目标

本项目希望实现：

- 一个**结构化的算法考纲 + 母题 Schema 体系**
- 一套**Schema 驱动的自动出题框架**
- 能够覆盖从入门到 ICPC 区域赛级别的题目生成能力
- 为算法教学、竞赛训练和研究提供可复用工具链

---

# 母题 → Schema → 自动出题 的系统架构设计

## 1. 为什么需要引入 Problem Schema

在自动生成编程竞赛题目的过程中，直接基于大语言模型生成题目存在以下问题：

- 题目结构不稳定，算法模型不清晰
- 难以控制题目难度与考点覆盖
- 不同生成结果之间容易出现结构性重复
- 难以系统性评估生成题目的多样性

为解决上述问题，本项目引入 **Problem Schema** 作为中间抽象层，用于连接“已有高质量题目”与“自动生成新题”。

Problem Schema 的作用是：

- 抽象题目的**算法本质**
- 显式描述题目的**输入结构、约束与不变量**
- 作为自动出题系统中的**最小可复用单元**

---

## 2. 系统整体分层架构

整个系统采用自底向上的三层架构：

┌─────────────────────────────┐
│ 自动生成的新题目 │
│ （题面 / 数据 / 标程） │
└─────────────▲──────────────┘
│
┌─────────────┴──────────────┐
│ Problem Schema 实例层 │
│ （参数化 / 变形后的 Schema）│
└─────────────▲──────────────┘
│
┌─────────────┴──────────────┐
│ 母题 Schema 库 │
│ （算法结构原型集合） │
└─────────────────────────────┘

其中：

- **母题 Schema 库** 是系统的核心资产
- 所有新题均由母题 Schema 经参数化和变形生成
- Schema 的质量直接决定生成题目的质量上限

---

## 3. 从具体题目到母题 Schema 的抽象流程

系统首先从已有竞赛题目出发，而不是从空白生成。

### 3.1 候选题目输入

候选题目来自高质量竞赛平台，包括：

- ICPC World Finals / Regional 题目
- Codeforces（Div2 D/E，Div1 C/D）
- AtCoder（ABC F，ARC，AGC）
- NOI / 省选公开题目

输入形式为**结构完整的题面文本**，包含：

- 问题描述
- 输入输出格式
- 数据范围与约束

---

### 3.2 基于大语言模型的 Schema 抽取

对于每一道候选题目：

- 使用大语言模型自动抽取其 Problem Schema 表示
- Schema 使用统一的“五元组”结构进行描述
- 抽取过程不依赖具体代码解法，而关注题目语义与算法结构

这一阶段的输出是：

题目文本 → Schema 五元组（结构化表示）

---

### 3.3 母题 Schema 的去重与聚类

由于不同题目可能属于同一算法原型，系统需要对抽取出的 Schema 进行去重。

基本原则是：

- **不在题目层面去重**
- 而是在 **Schema 层面进行相似性判断**

通过定义 Schema 距离函数：

- 将高度相似的 Schema 合并为同一个母题
- 将显著不同的 Schema 作为新的母题加入母题库

最终得到一个规模受控、结构多样的母题 Schema 库。

---

## 4. 基于 Schema 的自动出题流程

在母题 Schema 库构建完成后，自动出题流程如下：

选择母题 Schema
↓
选择变形参数（约束 / 目标 / 数据规模）
↓
生成 Schema 实例
↓
生成新题目描述
↓
生成测试数据
↓
生成或验证标准解法

其中：

- **母题 Schema** 决定算法骨架与不变量
- **变形参数** 决定难度、考点组合与题目风格
- 新生成的题目在 Schema 层面可被证明为“非重复”

---

## 5. Schema 在系统中的核心地位

在整个系统中，Problem Schema 具有以下关键作用：

- 作为母题去重与分类的基本单位
- 作为自动出题的最小生成单元
- 作为题目多样性与覆盖度的度量基础
- 作为连接 AI 理解能力与工程规则的中介表示

可以认为：

> **Schema 是算法竞赛题目的“中间表示（IR）”。**

---

## 6. 本阶段小结

本节明确了：

- 为什么自动出题不能直接依赖自然语言生成
- 为什么需要 Problem Schema 作为中间抽象
- Schema 在“题目获取 → 去重 → 生成”中的核心位置
- 整个系统的端到端数据流与结构划分

---

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

---
# 母题来源与候选题目的系统化获取方式

## 1. 母题来源选择原则

本项目中的“母题”并非直接等同于某一道具体题目，而是从高质量竞赛题目中抽象出的算法结构原型。因此，在候选题目的选择上，需要满足以下原则：

1. **算法模型清晰**：题目应具有明确、稳定的算法核心
2. **题面信息完整**：包含清晰的问题描述、输入输出格式与约束
3. **竞赛验证充分**：题目来源于成熟竞赛体系
4. **结构可抽象**：适合被归纳为 Problem Schema

基于上述原则，本项目仅选取以下高质量竞赛平台作为候选题来源。

---

## 2. 候选题来源概述

### 2.1 ICPC World Finals / Regional 题目

#### 选择原因

- 题目质量最高，算法模型稳定
- 母题纯度高，适合抽象 Schema
- 题面通常以 PDF 形式公开，结构完整

#### 获取方式（工程视角）

- 手动或半自动收集公开 PDF 题集
- 从 PDF 中提取纯文本题面
- 按统一模板整理为标准题面文本

#### 工程实现思路

```text
PDF 文件
  → 文本提取（人工或工具）
  → 标准化题面格式（Title / Description / Input / Output / Constraints）
  → 保存为 .txt 或 .md
```

### 2.2 Codeforces 竞赛题目

#### 选择原因

- 题目数量充足，覆盖多种算法
- 题面结构高度规范
- 同一 Schema 下存在丰富变形

#### 重点选取：

- Div.2 D / E
- Div.1 C / D

#### 获取方式（推荐：官方 API）

Codeforces 提供官方 API，可用于获取题目信息。

#### 工程流程

```text
Codeforces API
  → 获取题目列表
  → 获取题目 HTML
  → 清洗并提取题面文本
  → 统一格式存储
```

#### 代码层面思路（示意）

```python
import requests
from bs4 import BeautifulSoup

def fetch_cf_problem(contest_id, problem_index):
    url = f"https://codeforces.com/contest/{contest_id}/problem/{problem_index}"
    html = requests.get(url).text
    soup = BeautifulSoup(html, "html.parser")

    statement = soup.find("div", class_="problem-statement")
    # 提取标题、描述、输入输出
    return statement.get_text(separator="\n")
```

### 2.3 AtCoder 题目（ABC / ARC / AGC）

#### 选择原因

- 题面语言严谨、冗余极少
- 数据与约束描述规范
- 非常适合 Schema 抽象

#### 推荐选取：

- ABC F
- ARC C 及以上
- AGC 全部题目

#### 获取方式

- 官网 HTML 题面
- GitHub 上的 AtCoder Problem Archive

#### 工程实现思路

```text
题目页面 HTML
  → 抽取 Problem Statement 区域
  → 按段落整理文本
  → 标准化格式存储
```

### 2.4 NOI / 省选题目

#### 选择原因

- 覆盖高难度 DP / 图论 Schema
- 算法结构严谨，母题价值高

#### 获取方式

- 公开 PDF 题面
- 教学整理资料

## 3. 候选题目文本的标准化格式

为了便于大语言模型抽取 Problem Schema，所有候选题目文本需统一为如下结构：

```text
[Problem Title]

[Problem Description]

Input
...

Output
...

Constraints
...
```

#### 说明：

- 不包含样例
- 不包含提示或解题说明
- 保留所有约束信息

## 4. 候选题获取的整体流水线

综合上述来源，本项目采用如下候选题获取流水线：

```graphql
竞赛平台 / PDF / API
        ↓
题面文本获取
        ↓
文本清洗与标准化
        ↓
结构化存储（txt / md）
        ↓
输入至 LLM 进行 Schema 抽取
```

## 5. 与 Problem Schema 抽取的衔接关系

候选题获取模块的输出直接作为下一阶段的输入：

- 每个标准化题面文本
- 对应一次 LLM 的 Schema 抽取请求
- 输出为 Problem Schema 五元组结构

该设计确保：

- 题目来源与 Schema 抽取解耦
- 可替换不同题源而不影响后续流程

## 6. 本阶段小结

本节系统性地说明了：

- 母题候选的来源选择原则
- 各类竞赛平台的获取方式
- 候选题文本的标准化要求
- 工程层面的获取与预处理流程

该阶段为后续的 Schema 抽取、去重与生成奠定了数据基础。
---
# 基于 Problem Schema 的母题去重与相似度计算方法

## 1. 为什么需要在 Schema 层面进行去重

在自动出题系统中，如果仅在“题目文本层面”进行去重，会面临以下问题：

- 同一道题可能存在多个平台版本
- 不同题面描述可能对应同一算法结构
- 简单文本相似度无法反映算法本质是否相同

因此，本项目明确采用如下原则：

> **不在题目层面去重，而在 Problem Schema 层面去重。**

即：  
只要两道题在 Schema 结构上高度相似，就认为它们属于同一母题或同一母题族。

---

## 2. 去重对象的定义层级

在系统中区分以下三个概念：

- **Problem（具体题目）**
- **Schema Instance（参数化后的 Schema）**
- **Mother Schema（母题 Schema）**

本节讨论的去重目标是：

> **Mother Schema 层级的去重与聚类**

---

## 3. Schema 相似度的整体建模思路

每一个 Problem Schema 表示为五元组：

S = (I, C, O, V, T)

Schema 去重的核心问题可表述为：

> 如何衡量两个 Schema 在结构层面“有多不一样”？

为此，本项目定义 **Schema 距离函数**：

D(S1, S2) ∈ [0, 1]

- 距离越小，Schema 越相似
- 距离越大，Schema 越不同

---

## 4. Schema 距离的分量化设计

Schema 距离由五个维度的距离加权求和得到，对应五元组的五个组成部分。

### 4.1 输入结构距离（Input Structure Distance）

#### 定义

输入结构为离散类型（array / graph / tree / string 等），采用人工定义的距离矩阵。

#### 设计原则

- 相同输入结构：距离为 0
- 完全不同结构：距离接近 1
- 具有包含或相似关系的结构：中等距离

#### 示例

| I1 | I2 | 距离 |
|----|----|------|
| array | array | 0.0 |
| tree | graph | 0.3 |
| array | graph | 1.0 |

#### Python 实现思路

```python
INPUT_STRUCTURE_DISTANCE = {
    ("array", "array"): 0.0,
    ("tree", "graph"): 0.3,
    ("array", "graph"): 1.0,
}
```

#### 4.2 核心约束集合距离（Constraint Set Distance）

##### 定义

将核心约束视为集合：

```
C1 = {c1, c2, ...}
C2 = {c1, c3, ...}
```

采用 Jaccard Distance 进行度量：

```
d_C = 1 - |C1 ∩ C2| / |C1 ∪ C2|
```

##### 设计动机

- 约束组合是竞赛题难度变化的核心来源
- Jaccard 距离天然适合衡量集合差异
- 可解释性强，便于论文表述

##### Python 实现思路

```python
def constraint_distance(c1, c2):
    set1 = set(c.name for c in c1)
    set2 = set(c.name for c in c2)
    return 1 - len(set1 & set2) / len(set1 | set2)
```

#### 4.3 目标函数距离（Objective Distance）

##### 定义

目标函数属于有限枚举类型：

- max / min
- count
- decision

##### 设计原则

- 目标不同不一定代表母题不同
- 但一定增加 Schema 距离

##### 示例距离定义

| O1 | O2 | 距离 |
|----|----|------|
| max_length | max_length | 0.0 |
| max_length | count | 0.5 |
| count | decision | 0.7 |

##### Python 实现思路

```python
OBJECTIVE_DISTANCE = {
    ("max_length", "count"): 0.5,
    ("count", "decision"): 0.7,
}
```

#### 4.4 算法不变量距离（Invariant Distance）

##### 定义（最关键）

算法不变量描述解法成立的核心逻辑，例如：

- two_pointer
- prefix_sum
- dp_interval
- graph_shortest_path

##### 设计动机

- 不变量几乎直接决定解法范式
- 是区分母题的最重要维度
- 在总距离中应赋予最高权重

##### 示例

| V1 | V2 | 距离 |
|----|----|------|
| two_pointer | two_pointer | 0.0 |
| two_pointer | prefix_sum | 1.0 |
| dp_tree | dp_interval | 0.8 |

##### Python 实现思路

```python
INVARIANT_DISTANCE = {
    ("two_pointer", "two_pointer"): 0.0,
    ("two_pointer", "prefix_sum"): 1.0,
}
```

#### 4.5 可变参数空间距离（Transform Space Distance）

##### 定义

可变参数空间反映 Schema 的"变形能力"，包括：

- 参数数量
- 是否支持多约束
- 是否支持目标切换

##### 简化度量方式

采用参数数量的相对差异：

```
d_T = |len(T1) - len(T2)| / max(len(T1), len(T2))
```

##### Python 实现思路

```python
def transform_distance(t1, t2):
    return abs(len(t1) - len(t2)) / max(len(t1), len(t2))
```

### 5. Schema 总距离函数

将上述五个分量线性加权，得到 Schema 总距离：

```
D(S1, S2) =
  w1 * d_I +
  w2 * d_C +
  w3 * d_O +
  w4 * d_V +
  w5 * d_T
```

##### 推荐权重设置

| 维度 | 权重 |
|------|------|
| 不变量（V） | 0.35 |
| 约束集合（C） | 0.25 |
| 输入结构（I） | 0.15 |
| 目标函数（O） | 0.15 |
| 变形空间（T） | 0.10 |

### 6. 去重与聚类判定规则

根据 Schema 距离，定义如下判定区间：

- D < 0.25：同一母题
- 0.25 ≤ D < 0.5：同一母题族
- D ≥ 0.5：不同母题

该规则用于：

- 决定是否合并 Schema
- 控制母题库规模
- 评估 Schema 多样性

### 7. 母题去重的整体流程

```
候选题目 Schema 集合
        ↓
逐一计算 Schema 距离
        ↓
与已有母题 Schema 比较
        ↓
小于阈值 → 合并
否则 → 新增母题
```

##### Python 流程示意

```python
mother_schemas = []

for schema in candidate_schemas:
    for m in mother_schemas:
        if schema_distance(schema, m) < THRESHOLD:
            break
    else:
        mother_schemas.append(schema)
```

### 8. 本阶段小结

本节给出了：

- 母题去重的必要性与层级定义
- Problem Schema 的距离建模方法
- 各五元组分量的可计算距离设计
- 去重阈值与工程实现思路

该方法为构建高质量、低冗余的母题 Schema 库提供了可解释、可复现的技术基础。
---
# Schema 驱动的自动出题流水线设计

## 1. 自动出题流水线的设计目标

在构建母题 Schema 库并完成去重之后，系统的核心任务转变为：

> **如何以 Problem Schema 为核心，自动生成高质量、结构正确、难度可控的新题目。**

自动出题流水线的设计目标包括：

- **结构正确性**：生成题目在 Schema 层面必然可解
- **算法一致性**：题目解法符合 Schema 所定义的不变量
- **难度可控性**：通过参数与约束调节题目难度
- **工程可扩展性**：不同 Schema 可复用同一流水线框架

---

## 2. 自动出题流水线的总体结构

整个自动出题流程以 Problem Schema 为中心，采用模块化设计：

```
Mother Schema
↓
Schema 参数实例化
↓
题面生成（Problem Statement Generator）
↓
测试数据生成（Testcase Generator）
↓
标准解法生成 / 验证（Solver / Verifier）
```

每个模块均围绕 Schema 的五元组信息展开。

---

## 3. Schema 参数实例化模块

### 3.1 模块职责

Schema 参数实例化模块的作用是：

- 从母题 Schema 的 Transform Space 中选择一组具体参数
- 生成一个 **Schema Instance**
- 确定本次生成题目的：
  - 数据规模
  - 约束组合
  - 目标函数类型
  - 难度等级

### 3.2 实现思路

```python
def instantiate_schema(schema, difficulty):
    params = {}
    for k, v in schema.transform_params.items():
        params[k] = sample_param(v, difficulty)
    return params
```

该模块不关心题面或代码，仅负责生成"题目配置"。

### 4. 题面生成模块（Problem Statement Generator）

#### 4.1 模块职责

题面生成模块根据以下信息生成自然语言题目描述：

- 输入结构（Input Structure）
- 核心约束集合（Core Constraints）
- 目标函数（Objective）
- 参数实例（Schema Instance）

#### 4.2 设计原则

- 题面描述不包含解题提示
- 所有约束必须显式出现在题面中
- 题面语言保持竞赛风格、简洁明确

#### 4.3 实现思路（LLM 驱动）

```text
输入：
- Schema 五元组
- 实例化参数

输出：
- 标准竞赛题面文本
```

题面生成通常由大语言模型完成，Schema 作为结构化输入，用于约束生成结果。

### 5. 测试数据生成模块（Testcase Generator）

#### 5.1 模块职责

- 根据输入结构生成合法输入数据
- 覆盖边界情况与极端参数
- 为解法验证提供数据支持

#### 5.2 与 Schema 的关系

| Schema 信息 | 用途 |
|-------------|------|
| Input Structure | 决定数据形态 |
| Transform Space | 决定规模与分布 |
| Core Constraints | 决定合法性 |

#### 5.3 实现思路

```python
class TestcaseGenerator:
    def generate(self, schema, params):
        # 1. 根据 InputStructure 生成数据框架
        # 2. 根据 Transform Params 决定规模
        # 3. 调整数据以触发关键约束
        pass
```
### 6. 标准解法生成与验证模块（Solver / Verifier）

#### 6.1 模块职责

该模块负责：

- 提供该 Schema 下的标准解法模板
- 对生成的数据进行正确性验证
- 保证生成题目"必然可解"

#### 6.2 不变量驱动的解法选择

Solver 的选择依据是：

- Schema 中的算法不变量（Invariant）

例如：

| Invariant | Solver |
|-----------|--------|
| two_pointer | 双指针模板 |
| prefix_sum | 前缀和模板 |
| dp_interval | 区间 DP 模板 |

#### 6.3 实现思路

```python
class Solver:
    def __init__(self, schema):
        self.invariant = schema.invariant.name

    def solve(self, input_data):
        if self.invariant == "two_pointer":
            return solve_two_pointer(input_data)
```
### 7. 各模块之间的解耦关系

自动出题流水线各模块之间保持最小耦合：

- 题面生成不依赖数据生成细节
- 数据生成不依赖具体解法实现
- Solver 仅依赖不变量，不依赖题面文本

这种设计保证了：

- Schema 可复用
- 模块可独立替换
- 系统易于扩展

### 8. 自动出题流水线的整体伪流程

```
选择母题 Schema
      ↓
实例化 Schema 参数
      ↓
生成题面文本
      ↓
生成测试数据
      ↓
运行 Solver 验证正确性
      ↓
输出完整新题
```
