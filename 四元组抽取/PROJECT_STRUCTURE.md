# 四元组抽取 项目结构分析

本文总结 `四元组抽取` 目录当前的输入假设、核心模块和处理流程。

## 1. 项目定位

- 目标：对单题 schema JSON 进行四维抽取与归一化。
- 语言：Python 3。
- 主输入：`D:\AutoProblemGen\爬取题目\output\imandra_curated_schema_inputs\*.json`
- 主流程：读取单题 schema → 题面分节切分 → 抽取 I/C/O/V → 结构化归一化。

## 2. 输入结构

每个输入文件对应 1 道题，核心字段包括：

- `problem_id`
- `title`
- `description`
- `source.source_name`
- `limits`
- `reference_solution.code`

当前预处理行为：

- `description` 会完整保留，并作为 prompt 的基础文本。
- `problem_schema.py` 会从 `description` 中切分 `Input`、`Output`、`Constraints`。
- `limits` 会被并入 `constraints` 文本。
- `reference_solution.code` 会在 invariant 维作为额外证据输入模型。

## 3. 统一词表与 schema

- `label_vocab.py`：维护四维统一词表与可直接注入 prompt 的标签判定说明。`input_structure.type` 只保留输入载体类型，既覆盖 `integer`、`float`、`char`、`boolean`、`tuple` 这类标量或定长记录，也覆盖数组、字符串、图、树等结构；`pair` 归入 `tuple`，集合语义通过 `array` 加 `properties` 表达；语义性质下沉到 `properties`，并补充 `properties` 键的文字说明。
- `prompt_input_structure.py`：顶层保留 `type`、`length`、`value_range`、`properties`，新增可选 `components`。组件项包含 `role`、`role_description`、`type`、`length`、`value_range`、`properties`；当顶层为 `composite` 时，组件角色名与角色说明都必须存在。system prompt 内含输入结构科研定义、规范标签说明、性质键说明与标签边界，user prompt 为关键字段补充填写语义与误填提醒。
- `prompt_constraints.py`：顶层保留 `constraints[]`，单项新增可选 `source_sections`，system prompt 内含核心约束科研定义、规范标签说明、标签边界与语义缺口下的新标签规则，user prompt 为关键字段补充填写语义与误填提醒。
- `prompt_objective.py`：顶层保留 `type` 与 `description`，新增可选 `target`、`requires_solution`，system prompt 内含目标维度科研定义、规范标签说明与标签边界，user prompt 为关键字段补充填写语义与误填提醒。
- `prompt_invariant.py`：顶层保留 `invariants[]`，单项新增可选 `evidence_source`，system prompt 内含算法不变量科研定义、规范标签说明、标签边界与语义缺口下的新标签规则，user prompt 为关键字段补充填写语义与误填提醒。
- `prompt_normalize.py`：归一化 prompt 接收结构化原始条目，而不是裸标签字符串，同时为关键字段补充填写语义与误填提醒。
- `normalize.py`：读取单轮原始抽取结果，完成 embedding 加 LLM 两阶段标签归一化，并直接输出最终四维结果。

## 4. 核心模块

```text
四元组抽取/
├── .env.example                # 模块级环境变量模板
├── env_loader.py               # 读取当前目录下的 .env
├── scripts/
│   └── set_qwen_env.ps1         # 历史遗留的 PowerShell 环境变量写入脚本
├── prompts/
│   ├── prompt_input_structure.py
│   ├── prompt_constraints.py
│   ├── prompt_objective.py
│   ├── prompt_invariant.py
│   ├── prompt_normalize.py
│   └── prompt_sections.py
├── label_vocab.py               # 四维统一词表与枚举定义
├── problem_schema.py            # schema 读取、校验、分节切分
├── extract.py                   # 抽取入口，接受单文件或目录
├── normalize.py                 # 归一化入口，embedding + LLM 两阶段
├── test_normalize.py            # 归一化单元测试
├── prompt_test_cases.py         # 验证脚本用的题型选样工具
├── verify_prompts_structure.py  # Prompt 结构验证
├── test_prompts_qa.py           # Prompt QA 测试
├── qwen_client.py               # 模型调用
├── README.md
└── README_PILOT.md
```

## 5. 数据流

```text
imandra_curated_schema_inputs/*.json
  → problem_schema.py
  → extract.py
  → output/<run>/raw/
  → normalize.py
     → embedding 归一化
     → LLM 归一化
  → output/<run>/normalized/
```

## 6. 主要输出

- `output/<run>/raw/`：每题每维单轮抽取结果
- `output/<run>/normalized/`：归一化后的最终结果
- `output/<run>/label_registry/`：动态标签注册表

## 7. 环境变量读取

- `qwen_client.py` 会在导入时先加载当前目录下的 `.env`。
- 运行时只读取 `.env` 中的值，不再读取同名进程环境变量。
- 推荐把模块专属配置写入本目录的 `.env`，避免依赖全局环境变量。
