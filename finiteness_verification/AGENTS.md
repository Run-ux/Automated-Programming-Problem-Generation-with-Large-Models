# AGENTS 指南（finiteness_verification）

本文件给自动化编码代理使用，包含构建/测试命令与代码风格规范。
若与你的操作环境不同，请先阅读 README_TASK3/4/5 并根据实际路径调整。

## 项目概览

- 目标：对编程竞赛题目进行四维抽取/归一化/投票/分析，验证标签集合有限性。
- 语言：Python 3
- 关键模块：
  - 抽取：`finiteness_verification.extract`
  - 归一化：`finiteness_verification.normalize`
  - 投票：`finiteness_verification.vote`
  - 分析：`finiteness_verification.analyze`
  - 封闭分类：`finiteness_verification.classify`
  - 覆盖率报告：`finiteness_verification.report`
- Prompt：`finiteness_verification/prompts/*`

## 运行前置

- 必须设置 API Key：`DASHSCOPE_API_KEY` 或 `QWEN_API_KEY`
- Windows PowerShell 示例：
  - 临时：`$env:DASHSCOPE_API_KEY = "your-api-key"`
  - 永久：`setx DASHSCOPE_API_KEY "your-api-key"`
- Linux/Mac：`export DASHSCOPE_API_KEY="your-api-key"`

## 构建 / 运行 / 测试命令

说明：本项目暂无标准化 build/lint 工具链；主要通过 Python 脚本运行。

### 安装依赖

- 基础依赖（最低）：`pip install requests`
- 分析/绘图（可选）：`pip install numpy scipy matplotlib`

### 核心流水线（示例）

- 抽取（Pilot 50 题）：
  - `python -m finiteness_verification.extract --input finiteness_verification/data/sample_pilot.json --output finiteness_verification/output/pilot/ --rounds 3`
- 归一化：
  - `python -m finiteness_verification.normalize --input finiteness_verification/output/pilot/raw/ --output finiteness_verification/output/pilot/normalized/`
- 投票：
  - `python -m finiteness_verification.vote --input finiteness_verification/output/pilot/normalized/ --output finiteness_verification/output/pilot/voted/`
- Phase1 分析：
  - `python -m finiteness_verification.analyze --input finiteness_verification/output/phase1/voted/ --output finiteness_verification/output/phase1/saturation_curves/`
- Phase2 分类：
  - `python -m finiteness_verification.classify --labels finiteness_verification/output/phase1/labels_per_dimension.json --input 爬取题目/output/luogu/index.json --output finiteness_verification/output/phase2/classified_luogu/ --platform luogu --resume`
- 覆盖率报告：
  - `python -m finiteness_verification.report --input finiteness_verification/output/phase2/ --output finiteness_verification/output/phase2/coverage_report.json`

### 单测 / 单脚本

本仓库没有 pytest 等测试框架，以下为“单脚本”验证方式：

- Prompt 结构验证（不调用真实 API）：
  - `python finiteness_verification/verify_prompts_structure.py`
- Prompt QA 验证（会调用 API）：
  - `python finiteness_verification/test_prompts_qa.py`

### 运行单个“测试”或脚本

若要跑单个脚本，直接调用文件或模块即可：

- `python finiteness_verification/verify_prompts_structure.py`
- `python -m finiteness_verification.extract --help`

### Lint / 格式化

当前仓库未配置 lint/format 命令。
如需引入，可讨论是否采用 `ruff` 或 `black`，并在此文件补充命令。

## 代码风格与约定

### 代码组织

- 以模块方式运行：优先使用 `python -m finiteness_verification.*`
- Prompt 模板放在 `finiteness_verification/prompts/` 下
- 输出目录按阶段放在 `finiteness_verification/output/*`
- 不要在模块中写死相对路径（除非与现有脚本保持一致）

### 导入与依赖

- 标准库优先，其次第三方，再本地包
- 使用绝对导入：`from finiteness_verification...`
- 避免循环依赖；Prompt 与核心逻辑分离

### 类型与数据结构

- 已使用 `from __future__ import annotations`
- 类型提示以 `typing`/`dataclasses` 为主
- JSON 结构需保持稳定字段：
  - 抽取：`problem_id`, `source`, `dimension`, `round`, `result`, `status`
  - 投票：`input_structure/core_constraints/objective/invariant`

### 命名约定

- 文件/模块：`snake_case.py`
- 函数/变量：`snake_case`
- 类名：`PascalCase`
- 标签名（归一化输出）：`lower_snake_case`

### 格式与可读性

- 行宽保持可读（无需强制 79/88）
- JSON 输出使用 `ensure_ascii=False, indent=2`
- 日志使用 `logging`，避免裸 `print`（除独立脚本）

### 错误处理

- 调用外部 API 必须捕获异常并记录错误信息
- 对输入路径、文件存在性做显式校验
- 出错时保持输出结构（`status: failed` + `error`）

### Prompt 相关

- System prompt 明确 JSON 输出要求
- User prompt 必须包含题目完整信息（title/description/input/output/constraints）
- Schema 变更需同步 `verify_prompts_structure.py` 的验证逻辑

### 性能与速率限制

- API 调用必须经过限速（当前默认 1 秒/次）
- 断点续传通过 `--resume` 跳过已完成文件

## 目录与路径约定

- 根目录：`D:\Automated-Programming-Problem-Generation-with-Large-Models`
- 题库数据：`爬取题目/output/*/index.json`
- 采样数据：`finiteness_verification/data/*.json`
- 输出结果：`finiteness_verification/output/<phase>/...`

## 规则文件

- 未发现 `.cursor/rules/`、`.cursorrules` 或 `.github/copilot-instructions.md`
- 若之后添加上述规则文件，请在此处同步摘要

## 变更建议

- 任何新脚本请补充用法与示例命令
- 若引入测试框架或 lint 工具，务必更新本文件的命令区
