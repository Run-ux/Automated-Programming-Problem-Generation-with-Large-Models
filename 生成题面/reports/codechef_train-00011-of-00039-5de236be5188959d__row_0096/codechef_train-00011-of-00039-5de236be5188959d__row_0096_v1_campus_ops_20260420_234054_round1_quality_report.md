# 题目质量与反换皮评估报告

## 总览
- status: reject_as_retheme
- quality_score: 20.0
- divergence_score: 0.0
- schema_distance: 0.0
- generated_status: difference_insufficient

## 质量维度
- variant_fidelity: 1.0 / 5 | generated_problem 的 description、input_format、output_format 等核心字段均为空，new_schema 中定义的 redistribution 操作规则、目标函数（计算步数或-1）、多测结构及校园主题均未在题面中体现。hard_checks.objective_alignment 与 schema_distance_threshold 均明确失败。
- spec_completeness: 1.0 / 5 | 题面完全缺失任务说明、输入输出格式、数据范围等独立解题必需信息，读者无法获取任何规则或边界条件。hard_checks.sample_count 失败，generated_problem.status 标记为 difference_insufficient。
- cross_section_consistency: 1.0 / 5 | 由于 description、input_format、output_format、constraints 全部为空字符串或空数组，不存在可交叉验证的文本，整体处于未生成状态，无法构成有效的一致性评估基础。
- sample_quality: 1.0 / 5 | 样例数量为 0，未提供任何输入输出示例，无法辅助理解题意或验证实现。hard_checks.sample_count 明确指出失败。
- oj_readability: 1.0 / 5 | 题面标题及正文内容全为空，无任何结构化排版或可读文本，完全不符合 OJ 题面规范，参赛者无法阅读。

## 与原题差异分析
- changed_axes_planned: 无
- changed_axes_realized: 无
- semantic_difference: 0.0
- solution_transfer_risk: 1.0
- surface_retheme_risk: 1.0
- verdict: reject_as_retheme
- rationale: 新题生成完全失败且未产生任何实质差异。new_schema 与 original_schema 在输入结构、核心约束、目标函数和不变量上完全一致，schema_distance 为 0.0。generated_problem 状态为 difference_insufficient，所有题面字段（title/description/input/output/samples）均为空，未落地任何规划轴。hard_checks 明确指出 changed_axes_threshold 和 schema_distance_threshold 均未通过，且 objective_alignment 失败。由于核心任务、状态定义、决策对象和最优性目标未发生任何改变，原题解法可完全直接迁移，属于典型的零差异换皮/生成失败案例。

## 硬检查
- [PASS] source_problem_resolved (blocker/invalid): 已成功加载原题文本。
- [PASS] generated_problem_present (blocker/invalid): artifact 已包含 generated_problem。
- [PASS] new_schema_present (blocker/invalid): artifact 已包含 new_schema 或兼容字段 new_schema_snapshot。
- [PASS] difference_plan_present (blocker/invalid): artifact 已持久化 difference_plan。
- [FAIL] generated_status_ok (blocker/retheme_issue): 生成产物状态为 difference_insufficient：规划结果未达到硬门槛，预测距离=0.3493，落地轴=C, O, V。
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
- [blocker] retheme_issue: generated status ok | 生成产物状态为 difference_insufficient：规划结果未达到硬门槛，预测距离=0.3493，落地轴=C, O, V。
  修复建议: 先修复生成阶段的 schema 或 difference 问题，再重新生成题面。
- [blocker] retheme_issue: schema distance threshold | schema_distance=0.00，低于 0.35。 已接近同母题换皮（<0.25）。
  修复建议: 提高输入、约束与目标的结构差异，避免停留在同母题换皮。
- [blocker] retheme_issue: changed axes threshold | 仅落地了 0 个核心差异轴：无。
  修复建议: 至少让 I、C、O、V 中两个核心轴发生实质变化。
- [major] quality_issue: sample count | 样例数量=0。 少于 2 组。
  修复建议: 至少补齐两组可验证样例。
- [blocker] quality_issue: objective alignment | 数值目标未在题面中明确表达。
  修复建议: 在 output_format 和 notes 中明确真实目标函数与必要的 tie-break。
- [major] quality_issue: 生成管线失败导致题面全空 | generated_problem 的所有文本与结构字段均为空，未产出任何有效题面内容，直接阻断后续评审与使用。
  修复建议: 检查 LLM 生成或模板渲染逻辑，确保 description、input_format、output_format 等字段被正确赋值并返回非空内容。
- [major] quality_issue: 核心规则与目标未落地 | new_schema 中定义的 redistribution 转移规则（取极值、ceil转移量）及 steps/-1 目标未在 output_format 或 description 中声明。hard_checks.objective_alignment 失败。
  修复建议: 在 description 中明确写出操作规则与终止条件，在 output_format 中规定输出单整数（操作步数或 -1）。
- [major] quality_issue: 样例缺失 | samples 数组为空，不满足 OJ 题面至少 2 组样例的基本要求，无法覆盖常规转移、已均分或无法收敛等场景。hard_checks.sample_count 失败。
  修复建议: 补充至少 2 组覆盖关键边界条件的样例，并提供对应的输入输出及简要解释。
- [blocker] retheme_issue: solution transfer risk too high | 新题生成完全失败且未产生任何实质差异。new_schema 与 original_schema 在输入结构、核心约束、目标函数和不变量上完全一致，schema_distance 为 0.0。generated_problem 状态为 difference_insufficient，所有题面字段（title/description/input/output/samples）均为空，未落地任何规划轴。hard_checks 明确指出 changed_axes_threshold 和 schema_distance_threshold 均未通过，且 objective_alignment 失败。由于核心任务、状态定义、决策对象和最优性目标未发生任何改变，原题解法可完全直接迁移，属于典型的零差异换皮/生成失败案例。
  修复建议: 增加输入、约束与目标的实质变化，降低原题解法的直接迁移性。

## 建议修改
- 先修复生成阶段的 schema 或 difference 问题，再重新生成题面。
- 提高输入、约束与目标的结构差异，避免停留在同母题换皮。
- 至少让 I、C、O、V 中两个核心轴发生实质变化。
- 至少补齐两组可验证样例。
- 在 output_format 和 notes 中明确真实目标函数与必要的 tie-break。
- 检查 LLM 生成或模板渲染逻辑，确保 description、input_format、output_format 等字段被正确赋值并返回非空内容。
- 在 description 中明确写出操作规则与终止条件，在 output_format 中规定输出单整数（操作步数或 -1）。
- 补充至少 2 组覆盖关键边界条件的样例，并提供对应的输入输出及简要解释。
- 增加输入、约束与目标的实质变化，降低原题解法的直接迁移性。
- 修复生成流程，确保 generated_problem 各字段非空并完整填充。
- 严格对照 new_schema.core_constraints 编写 redistribution 操作描述，明确极值选择与转移量计算公式。
- 在 output_format 中明确输出目标为操作步数或 -1，并说明多组测试用例的输入结构。
- 补充覆盖关键边界条件（如初始已均分、总和不可整除导致无法收敛、常规转移）的样例及详细解释。
- 优先改写核心任务定义，而不是继续替换故事背景。

## 回流摘要
- round_index: 1
- overall_status: reject_as_retheme
- generated_status: difference_insufficient
- quality_score: 20.0
- divergence_score: 0.0

## 快照
- original_problem: eqidlis
- difference_plan_rationale: 规划结果未达到硬门槛，预测距离=0.3493，落地轴=C, O, V。
