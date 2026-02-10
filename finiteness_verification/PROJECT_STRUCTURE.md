# finiteness_verification 项目结构分析

本文总结 `finiteness_verification` 的目录结构、核心模块、数据流向与入口脚本，便于快速理解和协作维护。

## 1. 项目定位

- 目标：对编程竞赛题目进行四维抽取/归一化/投票/分析，验证标签集合有限性。
- 语言：Python 3。
- 关键流程：抽取（I/C/O/V）→ 归一化 → 投票 → 分析（Phase 1）→ 封闭分类与覆盖率报告（Phase 2）。

## 2. 目录结构

```
finiteness_verification/
├── data/                          # 采样数据
│   ├── sample_pilot.json          # Pilot 50 题
│   └── sample_phase1.json         # Phase 1 1500 题
├── output/                        # 运行输出（按阶段）
│   └── pilot/
│       ├── raw/                   # 抽取原始结果（按轮次）
│       ├── normalized/            # 归一化结果（按题目）
│       ├── voted/                 # 投票结果（按题目）
│       ├── label_registry/        # 标签注册表（四维各一）
│       └── logs/                  # 日志
├── prompts/                       # Prompt 模板
│   ├── prompt_input_structure.py  # I 维：输入结构
│   ├── prompt_constraints.py      # C 维：核心约束
│   ├── prompt_objective.py        # O 维：优化目标
│   ├── prompt_invariant.py        # V 维：算法不变量
│   └── prompt_normalize.py        # 归一化 Prompt
├── finiteness_verification/       # Python 包（核心逻辑）
│   ├── qwen_client.py             # LLM API 客户端
│   ├── extract.py                 # 抽取入口
│   ├── normalize.py               # 归一化入口
│   ├── vote.py                    # 投票入口
│   ├── analyze.py                 # Phase 1 分析入口
│   ├── classify.py                # Phase 2 封闭分类入口
│   ├── report.py                  # Phase 2 覆盖率报告入口
│   ├── sample.py                  # 采样脚本
│   ├── verify_prompts_structure.py# Prompt 结构验证
│   └── test_prompts_qa.py          # Prompt QA 测试
├── README_PILOT.md                # Pilot 使用说明
├── README_PHASE1.md               # Phase 1 使用说明
├── README_PHASE2.md               # Phase 2 使用说明
└── AGENTS.md                      # 代理指引与命令约定
```

## 3. 核心模块说明

### 3.1 抽取与归一化

- `extract.py`

  - 作用：多轮抽取四维标签（I/C/O/V）。
  - 输出：`output/<phase>/raw/` 下按题目、维度、轮次保存 JSON。
  - 特点：支持 `--resume` 断点续传与速率限制。
- `normalize.py`

  - 作用：对抽取结果进行聚类归一化，维护动态标签注册表。
  - 输出：`output/<phase>/normalized/`、`output/<phase>/label_registry/`。

### 3.2 投票与分析

- `vote.py`

  - 作用：对多轮结果进行多数投票，得到稳态结果。
  - 输出：`output/<phase>/voted/`。
- `analyze.py`（Phase 1）

  - 作用：对标签饱和曲线进行统计与拟合，判定有限性。
  - 输出：`labels_per_dimension.json`、饱和曲线图与指标文件。

### 3.3 封闭分类与覆盖率（Phase 2）

- `classify.py`

  - 作用：使用 Phase 1 标签集合，对全量题目进行封闭分类。
  - 输出：`output/phase2/classified_<platform>/`。
- `report.py`

  - 作用：统计覆盖率与 OTHER 收敛情况。
  - 输出：`output/phase2/coverage_report.json` 等统计文件。

### 3.4 公共组件

- `qwen_client.py`
  - 作用：封装千问 API 调用与 JSON 提取逻辑。
  - 说明：需要设置 `DASHSCOPE_API_KEY` 或 `QWEN_API_KEY`。

## 4. 数据流与处理流程

### 4.1 Pilot 流程（50 题）

```
sample.py
  → data/sample_pilot.json
  → extract.py (raw)
  → normalize.py (normalized + label_registry)
  → vote.py (voted)
```

### 4.2 Phase 1（1500 题）

```
sample.py
  → data/sample_phase1.json
  → extract.py
  → normalize.py
  → vote.py
  → analyze.py (饱和曲线 + 有限性判定)
```

### 4.3 Phase 2（封闭分类）

```
labels_per_dimension.json
  → classify.py (全量题目)
  → report.py (覆盖率与 OTHER 收敛)
```

## 5. 主要数据文件

- `data/sample_pilot.json`：Pilot 样本（50 题）。
- `data/sample_phase1.json`：Phase 1 样本（1500 题）。
- `output/<phase>/raw/`：抽取原始结果。
- `output/<phase>/normalized/`：归一化结果。
- `output/<phase>/label_registry/`：动态标签注册表。
- `output/<phase>/voted/`：投票结果。
- `output/phase1/labels_per_dimension.json`：每维标签集合。
- `output/phase2/coverage_report.json`：覆盖率报告。
