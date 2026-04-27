# 题包生成验证

该模块实现“测试用例与标准解法共迭代”的后续流程。它接收 `生成题面` 的 artifact 与 Markdown 题面，生成可执行规格、标准解法、oracle、validator、checker、测试生成器和错误解池，并通过真实执行报告判断题包是否可交付。

## 运行

在本模块目录的 `.env` 中配置 OpenAI-compatible LLM 接口：

```env
LLM_API_KEY=你的_百炼_API_Key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen3.6-plus
LLM_TIMEOUT_S=360
```

```bash
python main.py ^
  --artifact D:\AutoProblemGen\生成题面\artifacts\...\round1.json ^
  --markdown D:\AutoProblemGen\生成题面\output\...\round1.md ^
  --rounds 3
```

默认输出到：

```text
题包生成验证/output/<problem_id>/<run_id>/
  round1/
  round2/
  final/
  iteration_summary.json
```

## 产物合同

- `execution_spec.json`：输入约束、输出合同、判题方式、oracle 小规模范围和测试桶。
- `standard_solution.py`：标准解法，必须实现 `solve(input_str: str) -> str`。
- `oracle_solution.py`：小规模暴力 oracle，必须实现 `solve(input_str: str) -> str`。
- `validator.py`：必须实现 `validate(input_str: str) -> bool`。
- `checker.py`：必须实现 `check(input_str: str, output_str: str, expected_str: str | None) -> bool`。
- `test_generator.py`：必须实现 `generate_tests() -> list[dict]`。
- `schema_mistake_points.json`：基于 `new_schema` 抽取的真实选手误解点，用于审计 schema 创新点如何映射到错误解。
- `wrong_solutions/`：候选错误解池，每份错误解实现 `solve(input_str: str) -> str`。错误解来源包含只看题面的弱选手模拟，以及内部使用 `new_schema` 的 schema-aware 误解点模拟。
- `execution_report.json`：执行矩阵、失败分类、错误解杀伤率和回流摘要。

## 报告可信度门禁

`execution_report.json` 中的 `base_consistency` 表示基础产物是否自洽。只有当 validator、标准解、oracle（适用时）与 checker 的基础检查全部通过时，错误解杀伤率才是可信指标。

- `wrong_solution_stats.valid == true`：已执行错误解筛选，`kill_rate` 可用于判断测试集杀伤效果。
- `wrong_solution_stats.valid == false`：基础自洽失败，已跳过错误解筛选，`kill_rate` 不可用。
- `wrong_solution_stats.skip_reason == "baseline_validation_failed"`：跳过原因是标准解、oracle、validator 或 checker 至少一处基础校验失败。

对于 `judge_type == "checker"` 的题包，标准解与 oracle 都允许输出任意合法证书。流程不会再用字符串相等判断二者是否一致，而是分别用 checker 校验它们的输出合法性。对于 `judge_type == "exact"` 的题包，仍保留规范化字符串比较。

## 回流摘要语义

`execution_report.json` 中的 `revision_context` 保存本轮验证矩阵暴露出的结构化诊断视图。流程会额外维护两类修订上下文：

- `revision_audit_history.json`：完整保留每一轮 `revision_context`，用于审计和追踪。
- 下一轮 LLM 使用的 active 修订上下文：只保留当前仍未解决的问题。每轮验证后，如果某个历史问题的 `issue_fingerprint` 不再出现，就视为已解决，并从下一轮 active 上下文中移除。

从第 2 轮开始，流程不再全量重写题包，而是在上一轮工作副本基础上只重生成 active 诊断命中的角色；未命中的组件直接沿用当前工作副本。若规格抽取器被明确命中，则会级联重生成依赖 `execution_spec` 的组件。

当前结构如下：

- `summary`：按失败类别聚合的概览，记录类别、次数、最高严重级别和代表性测试来源。
- `diagnostics_by_category`：按 `category -> diagnostic[]` 保存诊断对象。
- `role_diagnostics`：按生成器角色保存行动诊断，例如 `StandardSolutionGenerator`、`OracleGenerator`、`ToolGenerator`、`WeakPlayerGenerator`、`SchemaMistakeAnalyzer`、`SchemaAwareWrongSolutionGenerator`。
- `failed_hard_checks`：去重后的 `severity == blocker` 类别名。
- `surviving_wrong_solution_details`：未被当前测试杀死的错误解详情，包含 `solution_id`、`bug_type`、`expected_failure`、`reason`、`passed_tests`、`killed_tests` 和 `metadata`。

每个 diagnostic 固定包含：

- `category`、`severity`、`title`、`detail`、`fix_hint`
- `issue_fingerprint`：用于跨轮判断同一问题是否仍然存在
- `target_roles`：下一轮应消费该诊断的生成器角色
- `evidence`：失败测试、输入摘要、执行结果、标准输出、oracle 输出、checker 结果等结构化证据
- `diff`：仅在标准解输出与 oracle 输出不一致时出现，记录首个不同 token/行和差异窗口

证据保留策略：

- 小规模、`expect_oracle == true`、非 large 的失败反例优先完整保留输入输出。
- 大输入或大输出只保留规模信息、头尾片段和差异窗口，并标注 `truncated`、`original_length`、`kept_strategy`。
- traceback 会提取异常类型、最后几层调用栈和最终错误行。
- 超时、运行错误和 checker 拒绝都会保留执行状态、耗时、错误原因和测试 metadata。

角色路由规则：

- 标准解生成器重点接收标准解运行失败、性能失败、标准解/checker 冲突和标准解/oracle 差异。
- oracle 生成器重点接收 oracle 运行失败、oracle 输出被 checker 拒绝和标准解/oracle 差异。
- 工具生成器重点接收 test_generator、validator、checker 相关失败。
- 测试生成器职责所在的工具生成器、弱选手错误解生成器和 schema-aware 错误解生成器会接收 `surviving_wrong_solution_details`，用于补定向反例或调整错误模式。

`iteration_summary.json` 中每轮记录 active 上下文管理计数：

- `active_issue_count`：本轮验证后仍需处理的问题数量。
- `new_issue_count`：本轮新出现的问题数量。
- `resolved_issue_count`：上一轮 active 中本轮已消失的问题数量。
- `carried_issue_count`：跨轮仍存在的问题数量。

## 设计边界

v1 只支持 Python 代码执行，不自动修改题面生成模块。若发现题面、样例或输出合同存在歧义，报告会标记为 `statement_revision_required` 或相关失败类型，后续由上游题面生成流程处理。
