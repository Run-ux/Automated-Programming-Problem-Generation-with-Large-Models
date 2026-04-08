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
- `input_structure.components` 是归一化最终结果中的正式字段。组件项包含 `role`、`role_description`、`type`、`length`、`value_range`、`properties`。模型单轮抽取出的组件结构会原样进入最终结果。
- 当 `input_structure.type=composite` 时，`components` 必须为非空数组，且每个组件都必须提供非空 `role` 与 `role_description`。缺失时抽取阶段直接记为失败，不写入成功结果。
- `core_constraints.name` 优先复用规范词表；存在明确语义缺口时允许新建抽象标签，具体题目限制写入 `description`、`formal` 与可选 `source_sections`。
- `objective.type` 统一到目标词表，可选扩展 `target` 与 `requires_solution`。
- `invariant` 只保留可由代码或题面支撑的稳定维护性质，不把算法范式直接当作不变量标签；优先复用规范词表，存在明确语义缺口时允许新建抽象标签；有代码时以代码为主证据，无充分证据时允许返回空数组。
- `label_vocab.py` 中的预设标签描述已经扩展为可直接放入 prompt 的判定说明，覆盖适用场景与常见排除边界。
- 四个维度的 system prompt 都加入科研定义、规范标签说明与标签判别边界，用于压缩标签漂移并提高单轮抽取一致性。
- `input_structure` 额外把 `properties` 可复用键的语义说明注入 system prompt，降低把题目情境词误写成性质键的概率。
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

## 完整流程

1. 读取题目 schema JSON。
   `extract.py` 接收单个文件或目录，随后调用 `problem_schema.py` 读取并校验题目数据。
2. 执行统一预处理。
   预处理会保留完整 `description`，切分 `input`、`output`、`constraints` 分节，把 `limits` 合并进 `constraints`，并在存在 `reference_solution.code` 时补出 `standard_solution_code`。
3. 进行四维独立抽取。
   抽取阶段固定处理 `input_structure`、`core_constraints`、`objective`、`invariant` 四个维度。四个维度都会看到标题、题面全文、Input 分节、Output 分节、Constraints 分节。`invariant` 维额外把标准解法代码作为高优先级证据。
4. 写出单轮原始结果。
   每题每维调用一次模型，结果写入 `output/<run>/raw/{problem_id}_{dimension}.json`。每个文件包含 `problem_id`、`source`、`dimension`、`result`、`status`。
5. 聚合同题四个维度。
   `normalize.py` 读取 `raw/` 下的所有文件，按 `problem_id` 组装成单题对象。缺失维度保留默认失败状态，重复文件只保留首个文件。
6. 加载并刷新标签注册表。
   归一化阶段会先读取 `output/<run>/label_registry/` 中的已有注册表，再把 `label_vocab.py` 中的预设标签写入内存，作为本轮规范标签集合。
7. 执行 embedding 归一化。
   对每个维度，先提取原始标签名，与注册表中的规范标签名做 embedding 相似度比较。达到阈值的条目直接映射到已有规范标签。
8. 执行 LLM 归一化。
   embedding 未解决的条目进入 LLM 归一化。prompt 会同时提供维度策略、已有标签列表和结构化原始条目。`input_structure` 与 `objective` 采用强归并，`core_constraints` 与 `invariant` 采用半开放归并。模型返回映射关系和可能的新标签定义。
9. 回写归一化结果与标签注册表。
   归一化只统一标签字段。`input_structure` 与 `objective` 主要更新 `type`，`core_constraints` 与 `invariant` 主要更新每项的 `name`。新标签和别名会同步写回 `label_registry/<dimension>.json`。
10. 生成最终四元组结果。
    四个维度全部归一化完成后，系统会生成 `output/<run>/normalized/{problem_id}.json`。该文件只保留最终消费所需字段：`problem_id`、`source`、`input_structure`、`core_constraints`、`objective`、`invariant`。抽取失败的维度会落成默认空结构，例如 `objective.type=null`、`core_constraints.constraints=[]`。

## 验证

结构验证：

```powershell
python verify_prompts_structure.py
```

该脚本会检查：

- user prompt 是否包含标题、题面全文、`input`、`output`、`constraints` 分节。
- invariant 维在有标准解法代码时是否把代码注入 prompt。
- schema 必填字段与新增可选字段是否齐全。
- `input_structure.type=composite` 时，组件 schema 与模型输出是否包含 `role_description`。
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

- 运行时会先尝试读取当前模块目录下的 `.env` 文件，也就是 [四元组抽取/.env](/D:/AutoProblemGen/四元组抽取/.env)。
- 运行时只读取这个 `.env` 文件中的配置，不再读取同名进程环境变量。
- 可直接参考 [四元组抽取/.env.example](/D:/AutoProblemGen/四元组抽取/.env.example) 填写 [四元组抽取/.env](/D:/AutoProblemGen/四元组抽取/.env)。
- 在 `.env` 中设置 `DASHSCOPE_API_KEY` 或 `QWEN_API_KEY`。
- 可选模型环境变量：
  - `QWEN_MODEL`：通用对话模型默认值。抽取阶段默认读取它，归一化阶段也会把它作为后备值。
  - `QWEN_EXTRACT_MODEL`：只覆盖抽取阶段模型。
  - `QWEN_NORMALIZE_MODEL`：只覆盖归一化阶段模型。未设置时默认 `qwen-flash`。
  - `QWEN_EMBEDDING_MODEL`：覆盖 embedding 模型，默认 `text-embedding-v4`。
- 输入文件来自 `D:\AutoProblemGen\爬取题目\output\imandra_curated_schema_inputs`。
