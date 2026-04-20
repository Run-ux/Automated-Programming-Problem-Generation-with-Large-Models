# 题目质量与反换皮评估报告

## 总览
- status: reject_as_retheme
- quality_score: 20.0
- divergence_score: 0.0
- schema_distance: 0.0
- generated_status: difference_insufficient

## 质量维度
- variant_fidelity: 1.0 / 5 | 生成题面所有核心字段均为空，new_schema 中定义的输入结构、操作规则、优化目标及校园主题均未在 generated_problem 中体现。hard_checks 明确指出 objective_alignment 失败且 changed_axes 落地数为 0。
- spec_completeness: 1.0 / 5 | 题面 description、input_format、output_format、constraints 全部为空字符串或空数组，完全缺失独立解题所需的关键信息，读者无法获取任何任务规则。
- cross_section_consistency: 1.0 / 5 | 由于所有题面章节均为空，无法进行任何交叉验证，且与 new_schema 的完整定义存在根本性断裂，不符合题面内部一致性的基本要求。
- sample_quality: 1.0 / 5 | 样例数组为空，hard_checks 明确报告样例数量为 0，低于最低要求的 2 组，无法辅助理解题意或验证逻辑。
- oj_readability: 1.0 / 5 | 题面标题、描述、格式说明等全部缺失，状态标记为 difference_insufficient，完全不具备 OJ 题面的可读性与可用性。

## 与原题差异分析
- changed_axes_planned: 无
- changed_axes_realized: 无
- semantic_difference: 0.0
- solution_transfer_risk: 1.0
- surface_retheme_risk: 1.0
- verdict: reject_as_retheme
- rationale: 新题的 new_schema 与 original_schema 在输入结构、核心约束、优化目标及算法不变量上完全一致，schema_distance 为 0.0。difference_plan 未落地任何差异轴（changed_axes_realized 为空），且 generated_problem 状态为 difference_insufficient，所有题面字段均为空，生成流程彻底失败。原题的“乘以2/乘以2加1”操作、集合互异性、最小化最大值目标以及基于二叉树祖先下探的贪心策略被原样保留。熟悉原题的选手可直接复用优先队列/贪心解法，无需任何建模或算法调整。本题属于典型的零差异换皮/生成失败案例。

## 硬检查
- [PASS] source_problem_resolved (blocker/invalid): 已成功加载原题文本。
- [PASS] generated_problem_present (blocker/invalid): artifact 已包含 generated_problem。
- [PASS] new_schema_present (blocker/invalid): artifact 已包含 new_schema 或兼容字段 new_schema_snapshot。
- [PASS] difference_plan_present (blocker/invalid): artifact 已持久化 difference_plan。
- [FAIL] generated_status_ok (blocker/retheme_issue): 生成产物状态为 difference_insufficient：difference_plan.changed_axes 与 new_schema 的真实变化不一致。
- [PASS] predicted_schema_distance_present (blocker/invalid): artifact 已包含 predicted_schema_distance。
- [PASS] distance_breakdown_present (blocker/invalid): artifact 已包含 distance_breakdown。
- [PASS] changed_axes_realized_present (blocker/invalid): artifact 已包含 changed_axes_realized。
- [FAIL] schema_distance_threshold (blocker/retheme_issue): schema_distance=0.00，低于 0.35。 已接近同母题换皮（<0.25）。
- [FAIL] changed_axes_threshold (blocker/retheme_issue): 仅落地了 0 个核心差异轴：无。
- [PASS] source_leakage (blocker/retheme_issue): 未发现原题标题或题源泄露。
- [PASS] title_overlap (major/retheme_issue): 标题重合度=0.00。
- [FAIL] sample_count (major/quality_issue): 样例数量=0。 少于 2 组。
- [PASS] sample_line_alignment (major/quality_issue): 输入结构不是固定小数组，跳过样例行数检查。
- [PASS] input_count_alignment (blocker/quality_issue): 输入结构不是固定小数组，跳过输入项数量声明检查。
- [FAIL] objective_alignment (blocker/quality_issue): 数值目标未在题面中明确表达。
- [PASS] structural_option_alignment (blocker/quality_issue): 结构选项已在题面中落地。

## 问题清单
- [blocker] retheme_issue: generated status ok | 生成产物状态为 difference_insufficient：difference_plan.changed_axes 与 new_schema 的真实变化不一致。
  修复建议: 先修复生成阶段的 schema 或 difference 问题，再重新生成题面。
- [blocker] retheme_issue: schema distance threshold | schema_distance=0.00，低于 0.35。 已接近同母题换皮（<0.25）。
  修复建议: 提高输入、约束与目标的结构差异，避免停留在同母题换皮。
- [blocker] retheme_issue: changed axes threshold | 仅落地了 0 个核心差异轴：无。
  修复建议: 至少让 I、C、O、V 中两个核心轴发生实质变化。
- [major] quality_issue: sample count | 样例数量=0。 少于 2 组。
  修复建议: 至少补齐两组可验证样例。
- [blocker] quality_issue: objective alignment | 数值目标未在题面中明确表达。
  修复建议: 在 output_format 和 notes 中明确真实目标函数与必要的 tie-break。
- [major] quality_issue: 题面内容完全缺失 | generated_problem 的 title, description, input_format, output_format, constraints 均为空，未生成任何有效文本，导致题目无法阅读。
  修复建议: 重新触发生成流程，确保 LLM 或模板引擎正确填充所有题面字段，避免空输出。
- [major] quality_issue: 优化目标未声明 | hard_checks 指出 objective_alignment 失败，题面未明确“最小化初始集合最大元素”的核心目标，违反 new_schema.objective 定义。
  修复建议: 在 output_format 和 description 中清晰写出需要输出的目标值及其最小化要求。
- [major] quality_issue: 样例缺失 | samples 字段为空数组，不满足 OJ 题面至少 2 组样例的规范，无法提供基础验证。
  修复建议: 补充至少两组符合输入约束的样例输入输出，并附带简要解释。
- [major] quality_issue: 规划差异未落地 | schema_distance 为 0.00，changed_axes 为 0，说明 new_schema 的变体设计（如操作规则、主题映射）未实际写入题面，pipeline 报告 difference_insufficient。
  修复建议: 检查 difference_plan 与生成器的对接逻辑，确保 schema 中的 operation_type 和 theme 映射被正确渲染到题面中。
- [blocker] retheme_issue: solution transfer risk too high | 新题的 new_schema 与 original_schema 在输入结构、核心约束、优化目标及算法不变量上完全一致，schema_distance 为 0.0。difference_plan 未落地任何差异轴（changed_axes_realized 为空），且 generated_problem 状态为 difference_insufficient，所有题面字段均为空，生成流程彻底失败。原题的“乘以2/乘以2加1”操作、集合互异性、最小化最大值目标以及基于二叉树祖先下探的贪心策略被原样保留。熟悉原题的选手可直接复用优先队列/贪心解法，无需任何建模或算法调整。本题属于典型的零差异换皮/生成失败案例。
  修复建议: 增加输入、约束与目标的实质变化，降低原题解法的直接迁移性。

## 建议修改
- 先修复生成阶段的 schema 或 difference 问题，再重新生成题面。
- 提高输入、约束与目标的结构差异，避免停留在同母题换皮。
- 至少让 I、C、O、V 中两个核心轴发生实质变化。
- 至少补齐两组可验证样例。
- 在 output_format 和 notes 中明确真实目标函数与必要的 tie-break。
- 重新触发生成流程，确保 LLM 或模板引擎正确填充所有题面字段，避免空输出。
- 在 output_format 和 description 中清晰写出需要输出的目标值及其最小化要求。
- 补充至少两组符合输入约束的样例输入输出，并附带简要解释。
- 检查 difference_plan 与生成器的对接逻辑，确保 schema 中的 operation_type 和 theme 映射被正确渲染到题面中。
- 增加输入、约束与目标的实质变化，降低原题解法的直接迁移性。
- 彻底重构生成逻辑，确保 new_schema 的每个字段（输入数组、操作规则、最小化目标、校园主题）都能映射到具体的题面文本中。
- 补充符合约束的样例输入输出及解释，修复 objective_alignment 和 sample_count 的 hard_check 失败项。
- 排查 pipeline 中 difference_insufficient 报错的根因，确保差异轴能正确驱动题面生成，避免空壳输出。
- 优先改写核心任务定义，而不是继续替换故事背景。

## 回流摘要
- round_index: 2
- overall_status: reject_as_retheme
- generated_status: difference_insufficient
- quality_score: 20.0
- divergence_score: 0.0

## 快照
- original_problem: D. Generating Sets
- difference_plan_rationale: difference_plan.changed_axes 与 new_schema 的真实变化不一致。
