# Phase 1 全量抽取 + 饱和曲线分析

## 📋 概述

phase1 在 Pilot Run 验证通过后执行，对 3000 题样本进行完整抽取，并生成饱和曲线以判定标签集合是否"有限且可列"。

---

## 🚀 执行步骤

### 前置条件

1. ✅ Pilot Run 已完成（50 题验证通过）
2. ✅ API Key 已设置（`DASHSCOPE_API_KEY` 或 `QWEN_API_KEY`）
3. ✅ 依赖已安装：`numpy`, `scipy`, `matplotlib`

---

### Step 1: Phase 1 全量抽取（3000 题）

使用与 Pilot Run 相同的管线，对 3000 题样本进行抽取：

```bash
cd D:\Automated-Programming-Problem-Generation-with-Large-Models

python -m finiteness_verification.extract --input finiteness_verification/data/sample_phase1.json --output finiteness_verification/output/phase1/ --rounds 3 --resume

# 可选参数
# --temperature 0.4   # 抽取阶段 LLM 采样温度（默认 0.4）
# --log-level INFO    # 日志级别（DEBUG/INFO/WARNING/ERROR）
```

**预计时间**：3000 题 × 4 维 × 3 轮 = 36,000 次 API 调用

- 速率限制：1 秒/次
- **预计耗时**：约 10 小时（36000 秒 ≈ 10 小时）

**输出**：

- `finiteness_verification/output/phase1/raw/` — 36,000 个原始 JSON 文件
- `finiteness_verification/output/phase1/logs/extract.log` — 运行日志

**断点续传**：如果中断，使用 `--resume` 参数继续（会跳过已完成文件）

---

### Step 2: 归一化

```bash
python -m finiteness_verification.normalize \
    --input finiteness_verification/output/phase1/raw/ \
    --output finiteness_verification/output/phase1/normalized/ \
    --embedding-threshold 0.85

# 可选参数
# --log-level INFO    # 日志级别（DEBUG/INFO/WARNING/ERROR）
```

**说明**：

- 归一化使用“embedding 相似度 + LLM 兜底”（模型：qwen-flash）
- 每题每维仅调用 1 次 LLM，embedding 用于先行归并相近标签

**输出**：

- `finiteness_verification/output/phase1/normalized/` — 3000 个归一化文件
- `finiteness_verification/output/phase1/label_registry/` — 动态标签注册表（四维各一个 JSON）

**断点续跑**：normalize 会自动跳过已存在的 `normalized/{problem_id}.json`，如需重跑可删除对应文件

---

### Step 3: 投票

```bash
python -m finiteness_verification.vote --input finiteness_verification/output/phase1/normalized/ --output finiteness_verification/output/phase1/voted/

# 可选参数
# --log-level INFO    # 日志级别（DEBUG/INFO/WARNING/ERROR）
```

**输出**：

- `finiteness_verification/output/phase1/voted/` — 3000 个投票结果文件（invariant 为多条不变量）

---

### Step 4: 饱和曲线分析

```bash
python -m finiteness_verification.analyze --input finiteness_verification/output/phase1/voted/ --output finiteness_verification/output/phase1/saturation_curves/

# 可选参数
# --log-level INFO    # 日志级别（DEBUG/INFO/WARNING/ERROR）
```

**输出**：

- `finiteness_verification/output/phase1/labels_per_dimension.json` — 每维的唯一标签集合
- `finiteness_verification/output/phase1/saturation_curves/saturation_input_structure.png` — I 维饱和曲线
- `finiteness_verification/output/phase1/saturation_curves/saturation_core_constraints.png` — C 维饱和曲线
- `finiteness_verification/output/phase1/saturation_curves/saturation_objective.png` — O 维饱和曲线
- `finiteness_verification/output/phase1/saturation_curves/saturation_invariant.png` — V 维饱和曲线
- `finiteness_verification/output/phase1/saturation_curves/metrics.json` — 收敛指标（R²、尾部新增率、总标签数）
- `finiteness_verification/output/phase1/saturation_curves/finiteness_judgment.json` — 有限性判定结果

---

## 📊 验证与分析

### 检查抽取完整性

```bash
# 检查 voted 文件数量（应为 3000）
python -c "import os; files = os.listdir('finiteness_verification/output/phase1/voted/'); print(f'Voted files: {len(files)}'); assert len(files) == 3000"
```

### 查看收敛指标

```bash
python -c "
import json
metrics = json.load(open('finiteness_verification/output/phase1/saturation_curves/metrics.json', encoding='utf-8'))
for dim, data in metrics.items():
    print(f'{dim}:')
    print(f'  总标签数: {data[\"total_labels\"]}')
    print(f'  R²: {data[\"r_squared\"]:.3f}')
    print(f'  尾部新增率 (最后100题): {data[\"tail_new_rate\"]:.3%}')
    print()
"
```

### 查看有限性判定

```bash
python -c "
import json
judgments = json.load(open('finiteness_verification/output/phase1/saturation_curves/finiteness_judgment.json', encoding='utf-8'))
for dim, judgment in judgments.items():
    print(f'{dim}: {judgment}')
"
```

---

## 🎯 判定标准

### "有限且可列"的量化阈值

| 指标           | 强收敛（FINITE） | 中等收敛（LIKELY_FINITE） | 不确定（UNCERTAIN） |
| -------------- | ---------------- | ------------------------- | ------------------- |
| **R²**         | > 0.95           | > 0.90                    | > 0.80              |
| **尾部新增率** | < 2%             | < 5%                      | < 10%               |

**判定逻辑**：

- **FINITE**：R² > 0.95 且尾部新增率 < 2% → 强收敛 + 饱和
- **LIKELY_FINITE**：R² > 0.90 且尾部新增率 < 5% → 中等收敛
- **UNCERTAIN**：R² > 0.80 → 收敛趋势明显，但需更多数据

**预期结果**：

- **I 维（Input Structure）**：预计 FINITE（数据结构类型有限）
- **O 维（Objective）**：预计 FINITE 或 LIKELY_FINITE（优化目标类型有限）
- **C 维（Core Constraints）**：预计 LIKELY_FINITE（组合约束多，但原子约束有限）
- **V 维（Invariant）**：预计 UNCERTAIN 或 LIKELY_FINITE（算法不变量种类较多）

---

## 📁 输出目录结构

```
finiteness_verification/output/phase1/
├── raw/                           # 原始抽取（36,000 个文件）
-├── normalized/                    # 归一化结果（3,000 个文件）
-├── voted/                         # 投票结果（3,000 个文件；invariant 为数组）
├── labels_per_dimension.json      # 每维标签集合
├── saturation_curves/
│   ├── saturation_input_structure.png
│   ├── saturation_core_constraints.png
│   ├── saturation_objective.png
│   ├── saturation_invariant.png
│   ├── metrics.json               # 收敛指标
│   └── finiteness_judgment.json   # 判定结果
└── logs/
    └── extract.log                # 抽取日志
```

---

## 🔧 故障排查

### 问题 1: 抽取过程中断

**解决**：使用 `--resume` 参数继续

```bash
python -m finiteness_verification.extract \
    --input finiteness_verification/data/sample_phase1.json \
    --output finiteness_verification/output/phase1/ \
    --rounds 3 \
    --resume
```

### 问题 2: 饱和曲线图片未生成

**原因**：matplotlib 后端问题

**解决**：

```python
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
```

（analyze.py 已包含此设置）

### 问题 3: R² 为 NaN 或负数

**原因**：数据点不足或拟合失败

**解决**：检查 voted/ 目录中文件数量是否符合预期（3000 个）

---

## 🎯 下一步

完成 phase1 后，继续执行：

- Phase 2 封闭分类（13K 题全量）+ 覆盖率报告
