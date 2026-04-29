# 题包生成验证

该模块实现“测试用例与标准解法共迭代”的后续流程。它接收 `生成题面` 的 artifact 与 Markdown 题面，直接基于题面字段和 schema 四字段生成标准解、正确暴力解、validator、checker、三类测试输入和错误解池，并通过真实执行报告判断题包是否可交付。

## 运行

在本模块目录的 `.env` 中配置 OpenAI-compatible LLM 接口：

```env
LLM_API_KEY=你的_百炼_API_Key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen3.6-plus
LLM_TIMEOUT_S=360

# 可选：RevisionAdvisor 独立模型；留空时复用主 LLM 配置。
REVISION_ADVISOR_LLM_API_KEY=
REVISION_ADVISOR_LLM_BASE_URL=
REVISION_ADVISOR_LLM_MODEL=
REVISION_ADVISOR_LLM_TIMEOUT_S=360
```

安装运行依赖：

```bash
pip install -r requirements.txt
```

`requirements.txt` 固定包含 `cyaron==0.7.0`。随机与对抗测试输入生成器允许使用该依赖，其它生成代码仍只允许使用 Python 标准库。

```bash
python main.py ^
  --artifact D:\AutoProblemGen\生成题面\artifacts\...\round1.json ^
  --markdown D:\AutoProblemGen\生成题面\output\...\round1.md ^
  --rounds 6
```

运行时终端会输出当前轮次、生成子步骤、验证矩阵、错误解筛选和最终摘要写入等阶段进度。

代码生成阶段的上下文策略如下：

- `prompts/` 继续按功能再分成 `standard_solution/`、`bruteforce_solution/`、`tool_generation/`、`wrong_solution/` 四个子包；每个子包内统一提供 `build_system_prompt()` / `build_user_prompt(...)`，并在各自模块内直接维护完整 prompt 文本，不再通过 `prompt_builder.py` 或共享 prompt composer 聚合系统/用户提示词。
- 统一构造 `problem_context.json`，只抽取 `generated_problem.title/description/input_format/output_format/constraints/samples/notes`。
- schema 只透传 `new_schema_snapshot` 或 `new_schema` 中的 `input_structure/core_constraints/objective/invariant`；`invariant` 缺失时按 `{}` 透传。
- 标准解、正确暴力解、validator、checker、测试输入和错误解生成器都不接收 `algorithmic_delta_claim`。

默认输出到：

```text
题包生成验证/output/<problem_id>/<run_id>/
  round1/
  round2/
  final/              # 仅严格通过时写入
  last_attempt/       # 未通过时写入，仅用于排查
  NOT_DELIVERABLE.md  # 未通过时写入
  iteration_summary.json
  regression_cases.json
  known_good_cases.json
  candidate_gate_history.json
```

## 产物合同

- `problem_context.json`：artifact 上下文快照，包含题面字段、schema 四字段、样例测试和推断的 `judge_type`。
- `standard_solution.py`：标准解法，必须实现 `solve(input_str: str) -> str`。
- `bruteforce_solution.py`：正确暴力解，必须实现 `solve(input_str: str) -> str`，只在样例和小规模测试上强校验。
- `validator.py`：必须实现 `validate(input_str: str) -> bool`。
- `checker.py`：必须实现 `check(input_str: str, output_str: str, expected_str: str | None) -> bool`。
- `test_inputs/random_generator.py`：随机测试输入生成器，必须实现 `generate_test_input() -> str` 和 `validate_test_input(input_string: str) -> bool`，允许使用 `cyaron==0.7.0`。
- `test_inputs/adversarial_generator.py`：对抗/边界测试输入生成器，接口同上，允许使用 `cyaron==0.7.0`。
- `test_inputs/small_challenge_inputs.json`：小规模挑战输入列表，每项包含 `input/source/purpose/expect_bruteforce/is_large/metadata`。
- `schema_mistake_points.json`：LLM 根据具体题面和 schema 四字段自由分析出的真实错误策略，不设置固定数量、不自动补齐数量。
- `wrong_solutions/`：候选错误解池，每份错误解实现 `solve(input_str: str) -> str`。错误解来源包含固定五类错误策略和自由策略逐条生成两路。
- `execution_report.json`：执行矩阵、失败分类、错误解杀伤率和回流摘要。
- `known_good_cases.json`：累计记录已通过的样例、小规模暴力校验用例、历史回归用例和关键性能用例；下一轮候选包必须全部通过。
- `candidate_gate_history.json`：记录候选包级不退化门禁的晋级/拒绝历史。

## 报告可信度门禁

`execution_report.json` 中的 `base_consistency` 表示基础产物是否自洽。只有当 validator、标准解、正确暴力解（适用时）与 checker 的基础检查全部通过时，错误解杀伤率才是可信指标。

- `wrong_solution_stats.valid == true`：已执行错误解筛选，`kill_rate` 可用于判断测试集杀伤效果。
- `wrong_solution_stats.valid == false`：基础自洽失败，已跳过错误解筛选，`kill_rate` 不可用。
- `wrong_solution_stats.skip_reason == "baseline_validation_failed"`：跳过原因是标准解、正确暴力解、validator 或 checker 至少一处基础校验失败。
- `kill_rate_threshold` 是错误解质量门槛的必要条件，不再单独构成 `pass` 的充分条件；即使杀伤率达标，只要仍存在高价值幸存错误解，题包也不会判为通过。

对于 `judge_type == "checker"` 的题包，标准解与正确暴力解都允许输出任意合法证书。流程不会再用字符串相等判断二者是否一致，而是分别用 checker 校验它们的输出合法性。对于 `judge_type == "exact"` 的题包，仍保留规范化字符串比较。

基础自洽未通过时，流程不生成新的错误解池，也不执行错误解筛选。只有基础组件通过 validator、标准解、正确暴力解、checker 与语义门禁后，才会进入固定五类错误解、自由策略分析和逐策略错误解生成阶段。

增量修订采用“候选组件晋级”策略：新生成的标准解、正确暴力解、validator、checker 或测试输入产物会先经过语法、接口、样例/历史反例等轻量门禁；候选失败时保留上一轮组件，并把 `component_gate_failed` 写入报告回流。

轻量门禁通过后，流程会临时组装 `candidate_package` 执行包级不退化门禁。候选必须同时满足：上一轮 active blocker/high 问题减少或命中的 active issue 消失、不新增 blocker/high 类别、`known_good_cases` 全部通过、`semantic_gate_issues` 不增加、且基础自洽通过后的 `kill_rate` 不下降。失败时不会覆盖旧组件，并记录 `candidate_regression_detected` 或 `candidate_not_better_than_current`。

`regression_cases.json` 会记录历史失败反例。下一轮验证会优先执行这些回归反例，再执行三类测试输入产物生成的新用例，避免同类失败在不同随机样本上反复出现。

`known_good_cases.json` 与 `regression_cases.json` 分工不同：前者是“不得回退”的已通过路径，候选包失败会报告 `known_good_case_failed`；后者是“必须重测”的历史失败反例，用于确认旧问题是否真正消失。

`semantic_gate_issues` 用于记录题包合同与 checker 能力之间的结构性冲突。例如 checker 题要求“字典序最小冲突区间”等最小证书时，checker 必须体现最小性校验；否则报告 `semantic_kernel_required` 并停止盲目迭代。

## 迭代停止条件

- 仅当题包达到严格通过时，流程才会提前停止，`stop_reason == "all_checks_passed"`。
- 若基础自洽连续两轮暴露完全相同的 concrete baseline fingerprints，流程会提前停止，`stop_reason == "stalled_on_baseline"`，避免在同一基线问题上无效堆轮次。
- 若语义门禁发现需要共享语义内核或题面修订的问题，流程会提前停止，`stop_reason == "semantic_gate_failed"`。
- 只要未严格通过，流程会持续运行直到 `--rounds` 上限，结束时 `stop_reason == "reached_requested_rounds"`。
- 严格通过同时要求：基础自洽检查通过、不存在 `severity in {"blocker", "high"}` 的问题，且不存在高价值幸存错误解。

## 回流摘要语义

`execution_report.json` 中的 `revision_context` 保存本轮验证矩阵暴露出的结构化诊断视图。流程会额外维护两类修订上下文：

- `revision_audit_history.json`：完整保留每一轮 `revision_context`，用于审计和追踪。
- 下一轮 LLM 使用的 active 修订上下文：只保留当前仍未解决的问题。每轮验证后，如果某个历史问题的 `issue_fingerprint` 不再出现，就视为已解决，并从下一轮 active 上下文中移除。

从第 2 轮开始，流程不再全量重写题包，而是在上一轮工作副本基础上只重生成 active 诊断命中的角色；未命中的组件直接沿用当前工作副本。若 artifact 上下文构造被明确命中，则会级联重生成依赖题面字段和 schema 四字段的组件。

当前结构如下：

- `summary`：按失败类别聚合的概览，记录类别、次数、最高严重级别和代表性测试来源。
- `diagnostics_by_category`：按 `category -> diagnostic[]` 保存诊断对象。
- `role_diagnostics`：按生成器角色保存行动诊断，例如 `StandardSolutionGenerator`、`BruteForceSolutionGenerator`、`ValidatorGenerator`、`CheckerGenerator`、`TestGenerator`、`FixedCategoryWrongSolutionGenerator`、`SchemaMistakeAnalyzer`、`StrategyWrongSolutionGenerator`。
- `failed_hard_checks`：去重后的 `severity == blocker` 类别名。
- `surviving_wrong_solution_details`：未被当前测试杀死的高价值错误解详情，不包含 `unexpected_correct` 这类误生成的正确候选；字段包含 `solution_id`、`bug_type`、`expected_failure`、`reason`、`passed_tests`、`killed_tests` 和 `metadata`。

每个 diagnostic 固定包含：

- `category`、`severity`、`title`、`detail`、`fix_hint`
- `issue_fingerprint`：用于跨轮判断同一问题是否仍然存在
- `target_roles`：下一轮应消费该诊断的生成器角色
- `evidence`：失败测试、输入摘要、执行结果、标准输出、正确暴力解输出、checker 结果等结构化证据
- `diff`：仅在标准解输出与正确暴力解输出不一致时出现，记录首个不同 token/行和差异窗口
- `advisor_revision`：由 RevisionAdvisor 基于失败证据包生成的定向修订建议，包含 `root_cause`、`revision_advice`、`target_roles`、`evidence_used`、`confidence` 和 `risk_notes`。

RevisionAdvisor 会在验证矩阵生成结构化诊断后运行。它接收的失败证据包包括诊断身份、失败现场、输出差异、命中角色相关的当前工作副本、幸存错误解详情，以及 carried issue 的上一轮建议。生成器 prompt 会优先使用 `advisor_revision.revision_advice` 作为回流上下文；`fix_hint` 仅保留为报告中的原始模板线索。若 RevisionAdvisor 调用失败或返回缺少 `revision_advice`，本轮流程会直接失败暴露错误，不继续使用旧模板建议回流。

同一失败类别出现大量重复样本时，RevisionAdvisor 最多分析 3 个代表诊断；其余同类诊断复用代表建议并标记 `cluster_reused`，避免重复消耗 LLM 调用。

角色路由以 RevisionAdvisor 的 `advisor_revision.target_roles` 为优先级最高的定向结果；只有 advisor 未给出有效角色时，才回退到类别级默认路由。因此当 advisor 明确只修 `StandardSolutionGenerator` 时，下一轮不会再因为类别默认值额外重生成 `CheckerGenerator` 或 `BruteForceSolutionGenerator`。

证据保留策略：

- 小规模、`expect_bruteforce == true`、非 large 的失败反例优先完整保留输入输出。
- 大输入或大输出只保留规模信息、头尾片段和差异窗口，并标注 `truncated`、`original_length`、`kept_strategy`。
- traceback 会提取异常类型、最后几层调用栈和最终错误行。
- 超时、运行错误和 checker 拒绝都会保留执行状态、耗时、错误原因和测试 metadata。

角色路由规则：

- 标准解生成器重点接收标准解运行失败、性能失败、标准解/checker 冲突和标准解/正确暴力解差异。
- 正确暴力解生成器重点接收暴力解运行失败、暴力解输出被 checker 拒绝和标准解/正确暴力解差异。
- 工具生成器重点接收测试输入、validator、checker 相关失败。
- 测试输入生成器、固定分类错误解生成器、自由策略分析器和逐策略错误解生成器会接收 `surviving_wrong_solution_details`，用于补定向反例或调整错误模式。
- `kill_rate_skipped_due_to_invalid_baseline` 是报告型派生问题：它仍会出现在 `issues`、`execution_report.json` 和 `execution_report.md` 中说明本轮杀伤率不可用，但不进入下一轮 `role_diagnostics`，也不参与角色决策或基线停滞判定。

`wrong_solution_stats` 额外记录：

- `high_value_survivor_count`：当前仍存活、且应被后续测试击穿的错误解数量。
- `unexpected_correct_count`：被误生成为“错误解”但实际通过当前全部测试的候选数量。

`iteration_summary.json` 中每轮记录 active 上下文管理计数：

- `active_issue_count`：本轮验证后仍需处理的问题数量。
- `new_issue_count`：本轮新出现的问题数量。
- `resolved_issue_count`：上一轮 active 中本轮已消失的问题数量。
- `carried_issue_count`：跨轮仍存在的问题数量。
- `baseline_passed`：本轮基础自洽是否通过。
- `baseline_failed_categories`：本轮基础自洽失败类别，不包含派生的杀伤率跳过问题。
- `baseline_failure_streak`：连续出现相同 concrete baseline fingerprints 的轮数，用于触发 `stalled_on_baseline`。
- `deliverable_dir`：严格通过时的最终题包目录；未通过时为空。
- `last_attempt_dir`：未通过时的最后尝试目录；严格通过时为空。
- `semantic_gate_status`：语义门禁状态。
- `prompt_payload_bytes_by_round`：各轮压缩后修订上下文字节数。
- `regression_case_count`：累计回归反例数量。
- `known_good_case_count`：累计 known-good 用例数量。
- `candidate_gate_rejection_count`：候选轻量门禁或包级门禁的累计拒绝次数。
- `regression_prevention_count`：包级不退化门禁拦下潜在回归的累计次数。

`execution_report.json` 额外包含：

- `component_gate_results`：候选组件晋级门禁结果。
- `candidate_package_gate_results`：候选组件通过轻量门禁后，临时组装候选包执行的不退化门禁结果。
- `known_good_results`：本轮 known-good 用例配置、执行、通过和失败数量。
- `candidate_delta_summary`：候选包门禁的接受/拒绝数量、拒绝组件和拒绝原因摘要。
- `regression_results`：本轮回归反例配置与执行数量。
- `semantic_gate_issues`：语义门禁暴露的问题。

新增诊断类别：

- `candidate_regression_detected`：候选修掉了部分 active 问题，但引入 known-good、语义门禁、杀伤率或 blocker/high 类别回退。
- `known_good_case_failed`：已记录为 known-good 的用例在当前验证中失败。
- `candidate_not_better_than_current`：候选未减少 active blocker/high，也没有消除命中的 active issue。

## 设计边界

v1 只支持 Python 代码执行，不自动修改题面生成模块。若发现题面、样例或输出合同存在歧义，报告会标记为 `statement_revision_required` 或相关失败类型，后续由上游题面生成流程处理。
