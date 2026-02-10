# Phase 2 封闭分类 + 覆盖率报告

## 📋 概述

phase2 在 phase1 完成后执行，使用 Phase 1 生成的标签集合作为封闭类别，
对全量 13K 题目进行四维分类，并生成覆盖率与 OTHER 收敛报告。

---

## 🚀 执行步骤

### 前置条件

1. ✅ phase1已完成（`labels_per_dimension.json` 已生成）
2. ✅ API Key 已设置（`DASHSCOPE_API_KEY` 或 `QWEN_API_KEY`）
3. ✅ 全量题目数据存在：
   - `爬取题目/output/luogu/index.json`
   - `爬取题目/output/codeforces/index.json`
   - `爬取题目/output/icpc/index.json`

---

### Step 1: 全量封闭分类（三平台分别运行）

使用 Phase 1 的标签集合对全量题目进行封闭分类：

```bash
cd D:\Automated-Programming-Problem-Generation-with-Large-Models

python -m finiteness_verification.classify \
    --labels finiteness_verification/output/phase1/labels_per_dimension.json \
    --input 爬取题目/output/luogu/index.json \
    --output finiteness_verification/output/phase2/classified_luogu/ \
    --platform luogu \
    --resume

python -m finiteness_verification.classify \
    --labels finiteness_verification/output/phase1/labels_per_dimension.json \
    --input 爬取题目/output/codeforces/index.json \
    --output finiteness_verification/output/phase2/classified_codeforces/ \
    --platform codeforces \
    --resume

python -m finiteness_verification.classify \
    --labels finiteness_verification/output/phase1/labels_per_dimension.json \
    --input 爬取题目/output/icpc/index.json \
    --output finiteness_verification/output/phase2/classified_icpc/ \
    --platform icpc \
    --resume
```

**预计时间**：13,253 题 × 4 维 ≈ 53,012 次 API 调用

- 速率限制：1 秒/次
- **预计耗时**：约 14.7 小时

**输出**：

- `finiteness_verification/output/phase2/classified_luogu/` — Luogu 分类结果
- `finiteness_verification/output/phase2/classified_codeforces/` — Codeforces 分类结果
- `finiteness_verification/output/phase2/classified_icpc/` — ICPC 分类结果

---

### Step 2: 覆盖率与收敛报告

```bash
python -m finiteness_verification.report \
    --input finiteness_verification/output/phase2/ \
    --output finiteness_verification/output/phase2/
```

**输出**：

- `finiteness_verification/output/phase2/coverage_report.json` — 覆盖率统计
- `finiteness_verification/output/phase2/other_convergence/` — OTHER 收敛曲线（4 维）

---

## 📊 验证与分析

### 检查覆盖率报告

```bash
python -c "
import json
r = json.load(open(r'finiteness_verification/output/phase2/coverage_report.json', encoding='utf-8'))
for dim, data in r['per_dimension'].items():
    print(f'{dim}: coverage={data["coverage_rate"]:.1%}, OTHER={data["other_rate"]:.1%}')
"
```

### 跨平台一致性检查

```bash
python -c "
import json
r = json.load(open(r'finiteness_verification/output/phase2/coverage_report.json', encoding='utf-8'))
pp = r['per_platform']
dims = ['input_structure', 'core_constraints', 'objective', 'invariant']
for d in dims:
    print(f'{d}: luogu={pp["luogu"][d]["coverage_rate"]:.1%}, cf={pp["codeforces"][d]["coverage_rate"]:.1%}, icpc={pp["icpc"][d]["coverage_rate"]:.1%}')
"
```

---

## 📁 输出目录结构

```
finiteness_verification/output/phase2/
├── classified_luogu/                # Luogu 全量分类结果
├── classified_codeforces/           # Codeforces 全量分类结果
├── classified_icpc/                 # ICPC 全量分类结果
├── coverage_report.json             # 覆盖率统计报告
└── other_convergence/               # OTHER 收敛曲线（4 维）
```

---

## 🔧 故障排查

### 问题 1: 分类过程中断

**解决**：使用 `--resume` 参数继续

```bash
python -m finiteness_verification.classify \
    --labels finiteness_verification/output/phase1/labels_per_dimension.json \
    --input 爬取题目/output/luogu/index.json \
    --output finiteness_verification/output/phase2/classified_luogu/ \
    --platform luogu \
    --resume
```

### 问题 2: 覆盖率报告缺少平台数据

**原因**：某个平台分类结果目录为空或不存在

**解决**：检查分类输出目录是否生成，必要时重新运行对应平台分类

---

## 🎯 最终产物

完成 phase2 后，将得到：

- 四维 I/C/O/V 的全量覆盖率统计
- OTHER 收敛曲线
- 跨平台一致性对比结果
