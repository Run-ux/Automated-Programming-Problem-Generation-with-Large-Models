# 五元组有限性验证 - 使用说明

## 📋 前置条件

### 1. 设置 API Key（**必需**）

本项目使用阿里千问 API 进行题目抽取，需要先设置 API Key：

**Windows PowerShell**:

```powershell
# 临时设置（仅当前会话）
$env:DASHSCOPE_API_KEY = "your-api-key-here"

# 永久设置（需新开终端生效）
setx DASHSCOPE_API_KEY "your-api-key-here"
```

**Linux/Mac**:

```bash
export DASHSCOPE_API_KEY="your-api-key-here"
```

**验证是否设置成功**:

```bash
python -c "import os; print('API Key:', 'SET' if os.getenv('DASHSCOPE_API_KEY') else 'NOT SET')"
```

### 2. 安装依赖

确保已安装以下依赖：

```bash
pip install requests
```

---

## 🚀 运行 Pilot Run（50 题测试）

### Step 1: 抽取（extract.py）

对 50 题进行 3 轮 × 4 维抽取（共 600 次 API 调用）：

```bash
cd D:\Automated-Programming-Problem-Generation-with-Large-Models

python -m finiteness_verification.extract --input finiteness_verification/data/sample_pilot.json --output finiteness_verification/output/pilot/ --rounds 3
```

**断点续传**（如果中断后继续）：

```bash
python -m finiteness_verification.extract \
    --input finiteness_verification/data/sample_pilot.json \
    --output finiteness_verification/output/pilot/ \
    --rounds 3 \
    --resume
```

**输出**：

- `finiteness_verification/output/pilot/raw/` — 原始抽取结果（600 个 JSON 文件）
- `finiteness_verification/output/pilot/logs/extract.log` — 运行日志

---

### Step 2: 归一化（normalize.py）

归一化采用“embedding 相似度 + LLM 兜底”的双阶段策略（模型：qwen-flash），
每题每维仅调用 1 次 LLM，embedding 用于先行归并相近标签：

```bash
python -m finiteness_verification.normalize --input finiteness_verification/output/pilot/raw/ --output finiteness_verification/output/pilot/normalized/ --embedding-threshold 0.85
```

**输出**：

- `finiteness_verification/output/pilot/normalized/` — 归一化结果（50 个 JSON 文件，每题包含 4 维 × 3 轮）
- `finiteness_verification/output/pilot/label_registry/` — 动态标签注册表（四维各一个 JSON）

---

### Step 3: 投票（vote.py）

多数投票选出最终结果：

```bash
python -m finiteness_verification.vote --input finiteness_verification/output/pilot/normalized/ --output finiteness_verification/output/pilot/voted/
```

**输出**：

- `finiteness_verification/output/pilot/voted/` — 最终结果（50 个 JSON 文件，invariant 为多条不变量 + 置信度）

---

## 📊 验证结果

### 检查完整性

```bash
# 检查 voted/ 目录下文件数量（应为 50）
python -c "import os; files = os.listdir(r'finiteness_verification/output/pilot/voted/'); print(f'Voted files: {len(files)}'); assert len(files) == 50, f'Expected 50, got {len(files)}'"

# 检查单个文件结构（invariant 现在是 invariants 数组）
python -c "import json; d = json.load(open(r'finiteness_verification/output/pilot/voted/P5070.json', encoding='utf-8')); assert all(k in d for k in ['input_structure', 'core_constraints', 'objective', 'invariant']), f'Missing dimensions: {d.keys()}'; assert 'invariants' in d['invariant'], 'Missing invariant.invariants'"
```

### 查看置信度统计

```bash
python -c "
import json
from pathlib import Path
from collections import Counter

voted_dir = Path(r'finiteness_verification/output/pilot/voted/')
confidences = {'I': [], 'C': [], 'O': [], 'V': []}

for f in voted_dir.glob('*.json'):
    data = json.load(f.open(encoding='utf-8'))
    confidences['I'].append(data['input_structure'].get('confidence', '0/3'))
    confidences['O'].append(data['objective'].get('confidence', '0/3'))
    for inv in data.get('invariant', {}).get('invariants', []):
        confidences['V'].append(inv.get('confidence', '0/3'))

for dim in ['I', 'O']:
    print(f'{dim} 维度置信度分布: {Counter(confidences[dim])}')
print(f"V 维度不变量条目置信度分布: {Counter(confidences['V'])}")
"
```

---

## 🔧 故障排查

### 问题 1: `ModuleNotFoundError: No module named 'finiteness_verification'`

**原因**：未以模块方式运行

**解决**：必须在仓库根目录运行，且使用 `python -m` 语法：

```bash
cd D:\Automated-Programming-Problem-Generation-with-Large-Models
python -m finiteness_verification.extract --help
```

### 问题 2: `缺少API Key：请设置环境变量 DASHSCOPE_API_KEY 或 QWEN_API_KEY`

**原因**：API Key 未设置

**解决**：参考上文"设置 API Key"章节

### 问题 3: API 调用超时或失败

**原因**：网络问题或 API 限流

**解决**：

1. 检查网络连接
2. 使用 `--resume` 参数断点续传
3. 查看 `logs/extract.log` 获取详细错误信息

---

## 📁 输出目录结构

```
finiteness_verification/output/pilot/
├── raw/
│   ├── P5070_input_structure_round1.json
│   ├── P5070_input_structure_round2.json
│   ├── P5070_input_structure_round3.json
│   ├── P5070_core_constraints_round1.json
│   ├── ...（共 50 题 × 4 维 × 3 轮 = 600 个文件）
├── normalized/
│   ├── P5070.json  # 包含 4 维 × 3 轮归一化结果
│   ├── ...（共 50 个文件）
├── voted/
│   ├── P5070.json  # 包含 4 维投票结果 + 置信度
│   ├── ...（共 50 个文件）
└── logs/
    └── extract.log
```

---

## 🎯 下一步

完成 Pilot Run 验证后，继续执行：

- Phase 1 全量抽取（1500 题）+ 饱和曲线分析
- Phase 2 封闭分类（13K 题）+ 覆盖率报告
