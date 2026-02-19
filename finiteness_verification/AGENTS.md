# AGENTS.md - finiteness_verification 项目代理指南

本文件提供给自动化编码代理使用，包含项目背景、架构说明、构建/运行/测试命令与代码风格规范。

## 项目概述

### 目标
对编程竞赛题目进行四维独立抽取、归一化、投票和分析，验证标签集合是否"有限且可列"（finite and enumerable）。这是为"自动编程题目生成"研究项目提供理论基础的关键验证环节。

### 核心概念：四维标签体系（I/C/O/V）
1. **Input Structure (I) - 输入结构**：数据组织形式（array, graph, tree, string, matrix 等）
2. **Core Constraints (C) - 核心约束**：题目必须满足的限制条件（connectivity, ordering, distinctness 等）
3. **Objective (O) - 优化目标**：题目要求求解的目标类型（maximize_value, minimize_count, feasibility 等）
4. **Invariant (V) - 算法不变量**：解法中始终成立的结构性条件（monotonicity, optimal_substructure, greedy_choice 等）

### 验证方法
采用"开放抽取→归一化→多数投票→饱和曲线分析→封闭分类→覆盖率报告"的完整流程，验证四维标签集合是否收敛（即随着题目数量增加，新标签出现率趋近于零）。

## 技术栈

- **语言**：Python 3（使用 `from __future__ import annotations` 注解）
- **核心依赖**：
  - `requests` - HTTP 客户端（API 调用）
  - `numpy`, `scipy`, `matplotlib` - 数据分析与可视化（可选，用于饱和曲线）
- **API**：阿里云 DashScope（千问大模型）
- **数据格式**：JSON（所有输入输出均为 UTF-8 编码的 JSON）

## 项目结构

```
finiteness_verification/
├── __init__.py                     # 包初始化，定义 __version__ = "0.1.0"
├── qwen_client.py                  # 千问 API 客户端（含 embedding 支持）
│
├── extract.py                      # 抽取模块：多轮四维独立抽取
├── normalize.py                    # 归一化模块：embedding + LLM 双阶段归一化
├── vote.py                         # 投票模块：多数投票选出稳态结果
├── analyze.py                      # 分析模块：饱和曲线与有限性判定
├── classify.py                     # 分类模块：Phase 2 封闭分类
├── report.py                       # 报告模块：覆盖率与 OTHER 收敛分析
│
├── sample.py                       # 采样脚本：从三平台生成分层样本
├── verify_prompts_structure.py     # Prompt 结构验证（不调用 API）
├── test_prompts_qa.py              # Prompt QA 验证（调用真实 API）
│
├── count_input_structure.py        # I 维标签统计工具
├── count_core_constraints.py       # C 维标签统计工具
├── count_invariants.py             # V 维标签统计工具
├── count_objective.py              # O 维标签统计工具
│
├── prompts/                        # Prompt 模板子包
│   ├── __init__.py
│   ├── prompt_input_structure.py   # I 维 Prompt
│   ├── prompt_constraints.py       # C 维 Prompt
│   ├── prompt_objective.py         # O 维 Prompt
│   ├── prompt_invariant.py         # V 维 Prompt
│   └── prompt_normalize.py         # 归一化 Prompt
│
├── data/                           # 采样数据目录
│   ├── sample_pilot.json           # Pilot 50 题样本
│   └── sample_phase1.json          # Phase 1 1500 题样本
│
├── output/                         # 运行输出目录（按阶段组织）
│   ├── pilot/                      # Pilot Run 输出
│   │   ├── raw/                    # 原始抽取结果（每题每维每轮独立文件）
│   │   ├── normalized/             # 归一化结果
│   │   ├── label_registry/         # 动态标签注册表（四维各一个 JSON）
│   │   ├── voted/                  # 投票结果
│   │   └── logs/                   # 运行日志
│   └── phase1/                     # Phase 1 输出（结构同 pilot）
│       ├── raw/
│       ├── normalized/
│       ├── label_registry/
│       ├── voted/
│       ├── labels_per_dimension.json   # 每维唯一标签集合
│       ├── saturation_curves/          # 饱和曲线图与指标
│       └── logs/
│   └── phase2/                     # Phase 2 输出
│       ├── classified_luogu/       # Luogu 分类结果
│       ├── classified_codeforces/  # Codeforces 分类结果
│       ├── classified_icpc/        # ICPC 分类结果
│       ├── coverage_report.json    # 覆盖率报告
│       └── other_convergence/      # OTHER 收敛曲线
│
├── README_PILOT.md                 # Pilot Run 使用说明
├── README_PHASE1.md                # Phase 1 使用说明
├── README_PHASE2.md                # Phase 2 使用说明
├── PROJECT_STRUCTURE.md            # 项目结构详细说明
└── AGENTS.md                       # 本文件
```

## 运行前置

### 1. API Key 设置（必须）

本项目使用阿里千问 API，必须设置环境变量：

**Windows PowerShell**：
```powershell
# 临时设置（仅当前会话）
$env:DASHSCOPE_API_KEY = "your-api-key"

# 永久设置（需新开终端生效）
setx DASHSCOPE_API_KEY "your-api-key"
```

**Linux/Mac**：
```bash
export DASHSCOPE_API_KEY="your-api-key"
```

**验证是否设置成功**：
```bash
python -c "import os; print('SET' if os.getenv('DASHSCOPE_API_KEY') else 'NOT SET')"
```

### 2. 依赖安装

```bash
# 基础依赖（必须）
pip install requests

# 分析/绘图依赖（可选，用于 analyze.py 和 report.py）
pip install numpy scipy matplotlib
```

## 构建 / 运行 / 测试命令

### 运行模式
所有模块必须使用 `python -m` 以模块方式运行：

```bash
cd D:\Automated-Programming-Problem-Generation-with-Large-Models
python -m finiteness_verification.<module_name> [args]
```

### Pilot Run 完整流程（50 题验证）

```bash
# Step 1: 抽取（600 次 API 调用 ≈ 10 分钟）
python -m finiteness_verification.extract \
    --input finiteness_verification/data/sample_pilot.json \
    --output finiteness_verification/output/pilot/ \
    --rounds 3

# Step 2: 归一化（embedding + LLM 兜底）
python -m finiteness_verification.normalize \
    --input finiteness_verification/output/pilot/raw/ \
    --output finiteness_verification/output/pilot/normalized/ \
    --embedding-threshold 0.85

# Step 3: 投票
python -m finiteness_verification.vote \
    --input finiteness_verification/output/pilot/normalized/ \
    --output finiteness_verification/output/pilot/voted/
```

### Phase 1 完整流程（1500 题全量抽取 + 饱和曲线分析）

```bash
# Step 1: 全量抽取（18000 次 API 调用 ≈ 5 小时）
python -m finiteness_verification.extract \
    --input finiteness_verification/data/sample_phase1.json \
    --output finiteness_verification/output/phase1/ \
    --rounds 3 \
    --resume

# Step 2: 归一化
python -m finiteness_verification.normalize \
    --input finiteness_verification/output/phase1/raw/ \
    --output finiteness_verification/output/phase1/normalized/ \
    --embedding-threshold 0.85

# Step 3: 投票
python -m finiteness_verification.vote \
    --input finiteness_verification/output/phase1/normalized/ \
    --output finiteness_verification/output/phase1/voted/

# Step 4: 饱和曲线分析
python -m finiteness_verification.analyze \
    --input finiteness_verification/output/phase1/voted/ \
    --output finiteness_verification/output/phase1/saturation_curves/
```

### Phase 2 封闭分类与覆盖率报告

```bash
# 三平台分别运行（约 53000 次 API 调用 ≈ 14.7 小时）

# Luogu
python -m finiteness_verification.classify \
    --labels finiteness_verification/output/phase1/labels_per_dimension.json \
    --input 爬取题目/output/luogu/index.json \
    --output finiteness_verification/output/phase2/classified_luogu/ \
    --platform luogu \
    --resume

# Codeforces
python -m finiteness_verification.classify \
    --labels finiteness_verification/output/phase1/labels_per_dimension.json \
    --input 爬取题目/output/codeforces/index.json \
    --output finiteness_verification/output/phase2/classified_codeforces/ \
    --platform codeforces \
    --resume

# ICPC
python -m finiteness_verification.classify \
    --labels finiteness_verification/output/phase1/labels_per_dimension.json \
    --input 爬取题目/output/icpc/index.json \
    --output finiteness_verification/output/phase2/classified_icpc/ \
    --platform icpc \
    --resume

# 覆盖率报告
python -m finiteness_verification.report \
    --input finiteness_verification/output/phase2/ \
    --output finiteness_verification/output/phase2/coverage_report.json
```

### 验证与测试脚本

```bash
# Prompt 结构验证（不调用真实 API）
python finiteness_verification/verify_prompts_structure.py

# Prompt QA 验证（调用真实 API，需设置 API Key）
python finiteness_verification/test_prompts_qa.py

# 标签统计（对比 Prompt 预设标签与 LLM 新增标签）
python finiteness_verification/count_input_structure.py
python finiteness_verification/count_core_constraints.py
python finiteness_verification/count_invariants.py
python finiteness_verification/count_objective.py
```

### 各模块参数帮助

```bash
python -m finiteness_verification.extract --help
python -m finiteness_verification.normalize --help
python -m finiteness_verification.vote --help
python -m finiteness_verification.analyze --help
python -m finiteness_verification.classify --help
python -m finiteness_verification.report --help
```

## 代码风格与约定

### 导入顺序
```python
from __future__ import annotations

# 标准库
import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

# 第三方库
import numpy as np
from scipy.optimize import curve_fit

# 本地包
from finiteness_verification.qwen_client import QwenClient
from finiteness_verification.prompts import prompt_input_structure
```

### 命名约定
- **文件/模块**：`snake_case.py`
- **函数/变量**：`snake_case`
- **类名**：`PascalCase`
- **常量**：`UPPER_SNAKE_CASE`
- **标签名**（归一化输出）：`lower_snake_case`

### JSON 输出规范
所有 JSON 输出必须：
- 使用 `ensure_ascii=False` 以支持中文
- 使用 `indent=2` 格式化
- 使用 UTF-8 编码

示例：
```python
output_file.write_text(
    json.dumps(data, ensure_ascii=False, indent=2),
    encoding="utf-8"
)
```

### 日志规范
- 使用 `logging` 模块，避免裸 `print`
- 日志级别：DEBUG（详细调试）、INFO（正常进度）、WARNING（警告）、ERROR（错误）
- 格式：`%(asctime)s [%(levelname)s] %(message)s`

### 错误处理
- API 调用必须捕获异常并记录错误信息
- 出错时保持输出结构（`status: failed` + `error` 字段）
- 断点续传通过 `--resume` 跳过已完成文件

### 路径处理
- 统一使用 `pathlib.Path` 处理路径
- 目录写入前确保存在：`mkdir(parents=True, exist_ok=True)`
- 使用 UTF-8 编码读写文件

### 速率限制
- API 调用必须经过限速（默认 1 秒/次）
- 使用 `RateLimiter` 类实现
- embedding 批量调用时批次间休眠 0.3 秒

## 关键数据结构

### 抽取结果格式（raw/）
```json
{
  "problem_id": "P5070",
  "source": "luogu",
  "dimension": "input_structure",
  "round": 1,
  "result": {...},
  "status": "success"
}
```

### 归一化结果格式（normalized/）
```json
{
  "problem_id": "P5070",
  "source": "luogu",
  "input_structure": [{"round": 1, "status": "success", "result": {...}}, ...],
  "core_constraints": [...],
  "objective": [...],
  "invariant": [...]
}
```

### 投票结果格式（voted/）
```json
{
  "problem_id": "P5070",
  "source": "luogu",
  "input_structure": {"type": "array", "confidence": "3/3", "all_rounds": [...]},
  "core_constraints": {"constraints": [...], "all_rounds": [...]},
  "objective": {"type": "maximize_count", "confidence": "3/3", "all_rounds": [...]},
  "invariant": {"invariants": [...], "all_rounds": [...]}
}
```

### 标签注册表格式（label_registry/）
```json
{
  "array": {
    "name": "array",
    "description": "数组/序列",
    "aliases": [],
    "examples": []
  }
}
```

## 有限性判定标准

### 饱和曲线指标
| 指标 | 强收敛（FINITE） | 中等收敛（LIKELY_FINITE） | 不确定（UNCERTAIN） |
|------|-----------------|--------------------------|-------------------|
| **R²** | > 0.95 | > 0.90 | > 0.80 |
| **尾部新增率** | < 2% | < 5% | < 10% |

### 判定逻辑
- **FINITE**：R² > 0.95 且尾部新增率 < 2%
- **LIKELY_FINITE**：R² > 0.90 且尾部新增率 < 5%
- **UNCERTAIN**：R² > 0.80

## 安全与注意事项

1. **API Key 保护**：不要将 API Key 硬编码在代码中，始终使用环境变量
2. **断点续传**：长时间运行的任务（extract/classify）务必使用 `--resume` 参数
3. **限速保护**：API 调用有速率限制（1 秒/次），已内置于 `RateLimiter`
4. **成本控制**：注意 API 调用次数（Pilot 600 次，Phase 1 18000 次，Phase 2 53000 次）

## 故障排查

### 问题 1: `ModuleNotFoundError: No module named 'finiteness_verification'`
**解决**：必须在仓库根目录运行，且使用 `python -m` 语法

### 问题 2: 缺少 API Key
**解决**：参考上文"运行前置"设置环境变量

### 问题 3: 抽取过程中断
**解决**：使用 `--resume` 参数继续

### 问题 4: 饱和曲线图片未生成
**解决**：安装 matplotlib，或检查 `analyze.py` 中已包含 `matplotlib.use('Agg')` 设置

### 问题 5: R² 为 NaN 或负数
**解决**：检查 voted/ 目录中文件数量是否符合预期

## 相关文档

- `README_PILOT.md` - Pilot Run 详细说明
- `README_PHASE1.md` - Phase 1 详细说明
- `README_PHASE2.md` - Phase 2 详细说明
- `PROJECT_STRUCTURE.md` - 项目结构详细说明

## 变更日志

- 初始版本：基于 Pilot Run 验证通过后的完整项目结构
- 支持四维独立抽取、归一化、投票、分析、封闭分类全流程
