# 题目质量评价

该目录提供“题面质量 + 反换皮”单题评估器。当前版本只支持 `生成题面` 的 v3 artifact 合同，直接消费 `生成题面/artifacts/*.json`，同时读取源 schema，并默认按 `problem_id` 自动加载原题，输出：

- `reports/json/*_quality_report.json`
- `reports/md/*_quality_report.md`

报告中现在还会固定包含一个结构化 `revision_brief`，供 `生成题面` 的质量闭环模式回流使用。

## 当前合同

评测器当前要求 artifact 至少包含以下字段：

- `new_schema` 或兼容字段 `new_schema_snapshot`
- `difference_plan`
- `predicted_schema_distance`
- `distance_breakdown`
- `changed_axes_realized`
- `generated_problem`

其中：

- `new_schema` 是评审语义层使用的统一名称。若上游仍输出旧字段 `new_schema_snapshot`，评测器会兼容读取
- `difference_plan` 用于记录规划差异轴与规划理由
- `predicted_schema_distance`、`distance_breakdown`、`changed_axes_realized` 由上游直接提供，评测器只做校验和透传，不在本地重算
- `generated_problem` 是唯一题面来源。评测流程不会解析 Markdown，也不会用 Markdown 回填结构化字段

`planning_status`、`planning_error_reason`、`planning_feedback` 会作为失败状态与错误信息的补充来源。若 `generated_problem.status` 缺失，评测器会优先使用 `planning_status`。

若 artifact 来自质量闭环模式，评测器会继续透传 `iteration` 元信息，但不会依赖这些字段做本地判分。

Judge 还会额外参考 `review_context`。该上下文由评测器从 artifact 中提取，只包含结构化规划信息：

- `difference_plan.summary`
- `difference_plan.mode`
- `difference_plan.changed_axes`
- `changed_axes_realized`
- `distance_breakdown`
- `applied_rule`
- `applied_helpers`
- `algorithmic_delta_claim`
- `anti_shallow_rationale`

以下字段不会进入 Judge 输入：

- `selection_trace`
- `validation_trace`
- `candidate_attempts`
- `rule_selection_reason`

若缺少 `predicted_schema_distance`、`distance_breakdown` 或 `changed_axes_realized`，artifact 会直接判为无效。

## 核心能力

- 质量评分：`variant_fidelity`、`spec_completeness`、`cross_section_consistency`、`sample_quality`、`oj_readability`
- 反换皮判定：基于 `schema_distance`、`changed_axes`、原题文本对比和 `solution_transfer_risk`
- 状态输出：`pass`、`revise_quality`、`reject_as_retheme`、`reject_invalid`
- 回流摘要：输出固定结构的 `revision_brief`，供下一轮规划和题面生成使用

## `revision_brief` 合同

`revision_brief` 只保留生成侧真正需要回流的稳定字段：

- `round_index`
- `overall_status`
- `generated_status`
- `quality_score`
- `divergence_score`
- `failed_hard_checks`
- `issues`
- `suggested_revisions`
- `strengths_to_keep`

其中：

- `failed_hard_checks` 只收录未通过的硬检查
- `issues` 与报告正文中的 `issues` 保持同一语义口径
- `strengths_to_keep` 来自质量评审返回的 `strengths`

当前实现只把这份结构化摘要回流给生成模块，不要求生成侧消费 Markdown 报告全文。

## 运行

```bash
python main.py ^
  --schema D:\AutoProblemGen\四元组抽取\output\batch\normalized\CF1513D.json ^
  --artifact D:\AutoProblemGen\生成题面\artifacts\CF1513D_v1_campus_ops_20260409_225026.json

# 如需覆盖自动查找结果，可显式提供原题 JSON
python main.py ^
  --schema D:\AutoProblemGen\四元组抽取\output\batch\normalized\CF1513D.json ^
  --artifact D:\AutoProblemGen\生成题面\artifacts\CF1513D_v1_campus_ops_20260409_225026.json ^
  --original-problem D:\AutoProblemGen\原题数据\CF1513D.json
```

当前版本强制要求可用的 LLM Judge。若没有可用的 `QWEN_API_KEY`、`DASHSCOPE_API_KEY` 或显式传入的 `judge_client`，评测会直接报错。质量评审与反换皮评审一旦调用失败、超时或返回不合格 JSON，也会直接报错，不再回退到启发式评分。

若从 Python 直接调用 `ProblemEvaluator.evaluate_problem`，还可以传入可选的 `round_index`。CLI 入口不暴露该参数，默认按 `1` 写入 `revision_brief.round_index`。

评测器当前从本目录的 `config.py` 读取 Judge 配置。默认会继续读取本目录 `.env` 中的参数，常用项包括：

- `QWEN_MODEL`
- `QWEN_BASE_URL`
- `QWEN_API_KEY`
- `DASHSCOPE_API_KEY`
- `QWEN_TIMEOUT_S`
- `QWEN_EMBEDDING_MODEL`

若未设置 `QWEN_MODEL`，默认使用 `qwen3.6-plus`。若未设置 `QWEN_BASE_URL`，默认使用 DashScope 兼容接口地址。

默认情况下，评测器会按 `problem_id` 自动加载原题，查找顺序为：

- `爬取题目/output/codeforces/index.json`
- `爬取题目/output/luogu/index.json`
- `爬取题目/output/icpc/index.json`
- `爬取题目/output/atcoder/index.json`
- `爬取题目/output/imandra_curated_schema_inputs/*.json` 逐文件匹配 `problem_id`

说明：

- 查询只使用 `problem_id`，不会使用 `source`。
- 若同一个 `problem_id` 在多个索引中重复，采用固定优先级首命中：`codeforces -> luogu -> icpc -> atcoder`。
- `atcoder` 目录为空或缺少 `index.json` 时会直接跳过。
- `imandra_curated_schema_inputs/manifest.json` 会被跳过。
- `--original-problem` 为可选参数，提供后会覆盖自动查找结果。

默认情况下，报告会保存到当前项目目录下的 `reports/json` 和 `reports/md`。如需覆盖该行为，可显式传入 `--output-json` 或 `--output-md`。`--markdown` 参数会保留到报告快照中，但不会参与题面解析。报告快照中的 schema 路径统一使用 `snapshots.new_schema`。

质量闭环模式下，`生成题面` 会按 `_round1`、`_round2`、`_round3` 规则命名每轮 artifact，并生成对应的 `*_quality_report.json` 与 `*_quality_report.md`。评测器本身不要求轮次后缀，但会把调用方传入的 `round_index` 写进 `revision_brief`。

## 测试

```bash
python -m unittest discover -s D:\AutoProblemGen\题目质量评价\tests -v
```

测试基线当前覆盖：

- v3 artifact 成功评测与差异字段透传
- `--original-problem` 可选参数校验与解析
- 原题 JSON 路径加载回归
- 按 `problem_id` 自动从平台 `index.json` 查找原题
- 按 `problem_id` 自动从 `imandra_curated_schema_inputs` 逐文件匹配原题
- 自动查找失败时的无效状态回归
- `planning_status` 到 `generated_status` 的映射
- `revision_brief` 字段生成与 Markdown 渲染
- 只提供 `new_schema` 的成功评测
- 只提供 `new_schema_snapshot` 的兼容读取
- 同时缺少 `new_schema` 与 `new_schema_snapshot` 的无效 artifact
- 缺少差异字段时的无效 artifact
- LLM 评审失败或返回非法结果时的报错路径
