# 四元组抽取

当前目录直接面向 `D:\AutoProblemGen\爬取题目\output\imandra_curated_schema_inputs` 中的单题 schema JSON。

## 输入约定

- 每个输入文件对应 1 道题。
- 顶层字段至少包含 `problem_id`、`title`、`description`、`source`。
- `description` 中包含题面正文以及 `Input`、`Output`、`Constraints`、`Examples` 等分节。
- `reference_solution.code` 为标准解法代码，仅在 invariant 维作为高优先级证据使用。

抽取前会先做统一预处理：

- 保留完整 `description` 作为 prompt 主输入。
- 从 `description` 中切分 `input`、`output`、`constraints`，并在每个 user prompt 中显式展示。
- 从 `limits` 中补充时间与空间限制文本。

## Prompt 约定

- 四个抽取维度与归一化维度的 user prompt 都会给关键 JSON 字段补充简短说明，固定说明字段含义、填写条件、留空条件与常见误填。
- JSON 示例继续保留，但改为中性结构骨架，用于约束层级与字段形状，不再用具体题型词汇暗示语义。
- `input_structure.type` 只描述输入载体形态，既允许 `integer`、`float`、`char`、`boolean`、`tuple` 这类标量或定长记录类型，也允许数组、字符串、图、树等结构类型；`pair` 统一归入 `tuple`，集合语义仍归入 `array` 并通过 `properties` 表达，复合输入写入可选 `components`。
- `input_structure.components` 是归一化最终结果中的正式字段。模型单轮抽取出的组件结构会原样进入最终结果。
- `core_constraints.name` 优先复用规范词表；存在明确语义缺口时允许新建抽象标签，具体题目限制写入 `description`、`formal` 与可选 `source_sections`。
- `objective.type` 统一到目标词表，可选扩展 `target` 与 `requires_solution`。
- `invariant` 只保留可由代码或题面支撑的稳定维护性质，不把算法范式直接当作不变量标签；优先复用规范词表，存在明确语义缺口时允许新建抽象标签；有代码时以代码为主证据，无充分证据时允许返回空数组。
- 四个维度的 system prompt 都加入科研定义与标签判别边界，用于压缩标签漂移并提高单轮抽取一致性。
- `prompt_normalize` 接收结构化原始条目，而不是裸标签字符串。Embedding 归一化入口保持不变，结构化信息只用于 LLM 归一化阶段。

## 主流程

单题抽取：

```powershell
python extract.py --input D:\AutoProblemGen\爬取题目\output\imandra_curated_schema_inputs\16_codeforces_1399_e1_weights_division_easy_version.json --output output\single\ --resume
```

目录批量抽取：

```powershell
python extract.py --input D:\AutoProblemGen\爬取题目\output\imandra_curated_schema_inputs --output output\batch\ --resume
```

后续处理：

```powershell
python normalize.py --input output\batch\raw\ --output output\batch\normalized\ --embedding-threshold 0.85
```

`normalized\` 目录中的文件就是最终可消费结果。

## 验证

结构验证：

```powershell
python verify_prompts_structure.py
```

该脚本会检查：

- user prompt 是否包含标题、题面全文、`input`、`output`、`constraints` 分节。
- invariant 维在有标准解法代码时是否把代码注入 prompt。
- schema 必填字段与新增可选字段是否齐全。
- 样本是否覆盖单数组题、图题、树加查询题、判定题、计数题、无标准解法代码题。

需要实际调用模型时：

```powershell
python test_prompts_qa.py
```

归一化单元测试：

```powershell
python -m unittest test_normalize.py
```

## 环境要求

- 设置 `DASHSCOPE_API_KEY` 或 `QWEN_API_KEY`。
- 可选模型环境变量：
  - `QWEN_MODEL`：通用对话模型默认值。抽取阶段默认读取它，归一化阶段也会把它作为后备值。
  - `QWEN_EXTRACT_MODEL`：只覆盖抽取阶段模型。
  - `QWEN_NORMALIZE_MODEL`：只覆盖归一化阶段模型。未设置时默认 `qwen-flash`。
  - `QWEN_EMBEDDING_MODEL`：覆盖 embedding 模型，默认 `text-embedding-v3`。
- 可直接执行 [scripts/set_qwen_env.ps1](/D:/AutoProblemGen/四元组抽取/scripts/set_qwen_env.ps1) 写入环境变量：

```powershell
.\scripts\set_qwen_env.ps1 -ApiKey "your-api-key"
.\scripts\set_qwen_env.ps1 -ApiKey "your-api-key" -PersistUser
```

- 第一条命令只写入当前 PowerShell 会话。
- 第二条命令会同时写入当前会话和用户级环境变量，新开终端后仍然有效。
- 输入文件来自 `D:\AutoProblemGen\爬取题目\output\imandra_curated_schema_inputs`。
