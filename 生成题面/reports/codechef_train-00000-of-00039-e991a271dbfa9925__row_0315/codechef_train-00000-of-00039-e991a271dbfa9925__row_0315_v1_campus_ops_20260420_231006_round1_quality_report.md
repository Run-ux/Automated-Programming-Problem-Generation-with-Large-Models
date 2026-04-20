# 题目质量与反换皮评估报告

## 总览
- status: reject_as_retheme
- quality_score: 20.0
- divergence_score: 0.0
- schema_distance: 0.0
- generated_status: difference_insufficient

## 质量维度
- variant_fidelity: 1.0 / 5 | generated_problem 所有核心字段均为空，new_schema 中定义的多测结构、用户身份阈值（INDIAN 200 / NON_INDIAN 400）、活动记录累加等变体要素完全未落地到题面中。
- spec_completeness: 1.0 / 5 | 题面缺失任务说明、输入输出格式、约束条件等所有关键信息，读者无法获取任何解题所需内容，完全不具备独立做题条件。
- cross_section_consistency: 1.0 / 5 | 由于 description、input_format、output_format、constraints、samples 均为空字符串或空数组，不存在内部一致性，整体处于未生成状态。
- sample_quality: 1.0 / 5 | 样例数量为 0，未提供任何输入输出示例，无法辅助理解题意或验证逻辑，严重违反 OJ 题面基本规范。
- oj_readability: 1.0 / 5 | 题面内容为空，不符合任何 OJ 题面表达习惯与结构要求，完全无法阅读或用于比赛。

## 优点
- 生成管线正确识别了规则校验失败的状态，并返回了 difference_insufficient 及明确的 error_reason，避免了无效或误导性题面流入下游评审环节。

## 与原题差异分析
- changed_axes_planned: 无
- changed_axes_realized: 无
- semantic_difference: 0.0
- solution_transfer_risk: 1.0
- surface_retheme_risk: 1.0
- verdict: reject_as_retheme
- rationale: new_schema 与 original_schema 在输入结构、核心约束、目标函数和不变量上完全一致（schema_distance=0.0，changed_axes_realized 为空）。generated_problem 状态为 difference_insufficient，所有题面字段均为空，hard_checks 明确报告 schema_distance_threshold、changed_axes_threshold、generated_status_ok 和 objective_alignment 均未通过。由于未发生任何实质性的轴变化，且生成产物为空/无效，熟悉原题的选手可直接套用原解法（累加积分后按身份阈值整除），属于典型的规则规划失败导致的直接换皮/未生成状态。

## 硬检查
- [PASS] source_problem_resolved (blocker/invalid): 已成功加载原题文本。
- [PASS] generated_problem_present (blocker/invalid): artifact 已包含 generated_problem。
- [PASS] new_schema_present (blocker/invalid): artifact 已包含 new_schema 或兼容字段 new_schema_snapshot。
- [PASS] difference_plan_present (blocker/invalid): artifact 已持久化 difference_plan。
- [FAIL] generated_status_ok (blocker/retheme_issue): 生成产物状态为 difference_insufficient：没有规则通过资格校验。
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
- [blocker] retheme_issue: generated status ok | 生成产物状态为 difference_insufficient：没有规则通过资格校验。
  修复建议: 先修复生成阶段的 schema 或 difference 问题，再重新生成题面。
- [blocker] retheme_issue: schema distance threshold | schema_distance=0.00，低于 0.35。 已接近同母题换皮（<0.25）。
  修复建议: 提高输入、约束与目标的结构差异，避免停留在同母题换皮。
- [blocker] retheme_issue: changed axes threshold | 仅落地了 0 个核心差异轴：无。
  修复建议: 至少让 I、C、O、V 中两个核心轴发生实质变化。
- [major] quality_issue: sample count | 样例数量=0。 少于 2 组。
  修复建议: 至少补齐两组可验证样例。
- [blocker] quality_issue: objective alignment | 数值目标未在题面中明确表达。
  修复建议: 在 output_format 和 notes 中明确真实目标函数与必要的 tie-break。
- [major] quality_issue: 生成流程失败导致题面完全为空 | generated_problem.status 为 difference_insufficient，error_reason 明确指出没有规则通过资格校验，导致所有题面字段为空字符串或空数组。
  修复建议: 检查规则校验逻辑或更换种子题，确保生成流程能正常产出文本内容，避免空字段流入下游。
- [major] quality_issue: 核心差异轴未落地且 schema 距离为 0 | difference_plan 显示 changed_axes 为空，schema_distance=0.00，远低于 0.35 阈值，说明未对原题进行任何有效改编或规则规划失败。
  修复建议: 重新设计差异规则，明确至少一个核心改编轴（如输入结构、约束或目标函数），并强制落地到题面描述中。
- [major] quality_issue: 数值目标未在题面中表达 | new_schema.objective 要求计算最大可兑换月数，但 objective_alignment 检查失败，output_format 为空，未声明输出对象。
  修复建议: 在 output_format 中明确说明需要输出一个整数，代表按身份阈值计算的最大兑换月数，并与 constraints 中的阈值逻辑对齐。
- [blocker] retheme_issue: solution transfer risk too high | new_schema 与 original_schema 在输入结构、核心约束、目标函数和不变量上完全一致（schema_distance=0.0，changed_axes_realized 为空）。generated_problem 状态为 difference_insufficient，所有题面字段均为空，hard_checks 明确报告 schema_distance_threshold、changed_axes_threshold、generated_status_ok 和 objective_alignment 均未通过。由于未发生任何实质性的轴变化，且生成产物为空/无效，熟悉原题的选手可直接套用原解法（累加积分后按身份阈值整除），属于典型的规则规划失败导致的直接换皮/未生成状态。
  修复建议: 增加输入、约束与目标的实质变化，降低原题解法的直接迁移性。

## 建议修改
- 先修复生成阶段的 schema 或 difference 问题，再重新生成题面。
- 提高输入、约束与目标的结构差异，避免停留在同母题换皮。
- 至少让 I、C、O、V 中两个核心轴发生实质变化。
- 至少补齐两组可验证样例。
- 在 output_format 和 notes 中明确真实目标函数与必要的 tie-break。
- 检查规则校验逻辑或更换种子题，确保生成流程能正常产出文本内容，避免空字段流入下游。
- 重新设计差异规则，明确至少一个核心改编轴（如输入结构、约束或目标函数），并强制落地到题面描述中。
- 在 output_format 中明确说明需要输出一个整数，代表按身份阈值计算的最大兑换月数，并与 constraints 中的阈值逻辑对齐。
- 增加输入、约束与目标的实质变化，降低原题解法的直接迁移性。
- 修复生成规则或更换种子题，确保 generated_problem 的 description、input_format、output_format 等字段被正确填充。
- 根据 new_schema 补充多测结构说明、用户身份（INDIAN/NON_INDIAN）对应的月度兑换阈值（200/400）及活动积分累加规则。
- 至少提供 2 组覆盖不同身份和边界情况的样例，并附带清晰的样例解释。
- 确保 output_format 明确声明输出目标为整数 months，与 new_schema.objective.target 严格对齐。
- 优先改写核心任务定义，而不是继续替换故事背景。

## 回流摘要
- round_index: 1
- overall_status: reject_as_retheme
- generated_status: difference_insufficient
- quality_score: 20.0
- divergence_score: 0.0
- strengths_to_keep: 生成管线正确识别了规则校验失败的状态，并返回了 difference_insufficient 及明确的 error_reason，避免了无效或误导性题面流入下游评审环节。

## 快照
- original_problem: laddu
- difference_plan_rationale: 没有规则通过资格校验。
