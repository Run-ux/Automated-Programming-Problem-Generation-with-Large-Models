# 四元组抽取 项目结构分析

本文总结 `四元组抽取` 目录当前面向的新输入结构、核心模块与处理流程。

## 1. 项目定位

- 目标：对单题 schema JSON 进行四维抽取、归一化与投票。
- 语言：Python 3。
- 主输入：`D:\AutoProblemGen\爬取题目\output\imandra_curated_schema_inputs\*.json`
- 关键流程：读取单题 schema → 题面分节切分 → 抽取 I/C/O/V → 归一化 → 投票。

## 2. 输入结构

每个输入文件对应 1 道题，核心字段包括：

- `problem_id`
- `title`
- `description`
- `source.source_name`
- `limits`
- `reference_solution.code`

其中：

- `description` 会完整保留，并作为 prompt 的主输入
- 代码会尝试从 `description` 中切分 `Input`、`Output`、`Constraints` 作为辅助字段
- `reference_solution.code` 会在 invariant 抽取时作为额外证据输入模型

## 3. 核心模块

```text
四元组抽取/
├── prompts/
│   ├── prompt_input_structure.py
│   ├── prompt_constraints.py
│   ├── prompt_objective.py
│   ├── prompt_invariant.py
│   └── prompt_normalize.py
├── problem_schema.py             # 新 schema 读取、校验、分节切分
├── extract.py                    # 抽取入口，接受单文件或目录
├── normalize.py                  # 归一化入口
├── vote.py                       # 投票入口
├── verify_prompts_structure.py   # Prompt 结构验证
├── test_prompts_qa.py            # Prompt QA 测试
├── qwen_client.py                # 模型调用
├── README.md
└── README_PILOT.md
```

## 4. 数据流

```text
imandra_curated_schema_inputs/*.json
  → problem_schema.py
  → extract.py
  → output/<run>/raw/
  → normalize.py
  → output/<run>/normalized/
  → vote.py
  → output/<run>/voted/
```

## 5. 主要输出

- `output/<run>/raw/`：每题每维每轮抽取结果
- `output/<run>/normalized/`：归一化结果
- `output/<run>/label_registry/`：标签注册表
- `output/<run>/voted/`：投票结果
