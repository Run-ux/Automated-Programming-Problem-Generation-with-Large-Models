# 题目质量与反换皮评估报告

## 总览
- status: reject_as_retheme
- quality_score: 20.0
- divergence_score: 0.0
- schema_distance: 0.0
- generated_status: difference_insufficient

## 质量维度
- variant_fidelity: 1.0 / 5 | 生成题面所有核心字段均为空，new_schema 中定义的输入结构、状态转移约束、最小化目标及校园主题均未在题面中落地。
- spec_completeness: 1.0 / 5 | 题面缺失任务说明、输入输出格式、约束条件及样例，完全无法提供独立解题所需的关键信息，读者无法猜测任何规则。
- cross_section_consistency: 1.0 / 5 | 由于题面内容全为空，各部分之间无任何实质内容可供校验一致性，属于严重缺失导致无法构成有效题面。
- sample_quality: 1.0 / 5 | 样例数组为空，数量为0，无法覆盖任何关键结构或辅助理解，hard_checks 已明确报错。
- oj_readability: 1.0 / 5 | 标题、描述、格式等均为空字符串，且状态标记为失败，完全不符合 OJ 题面规范，无法阅读。

## 优点
- 无。生成产物处于失败状态，未产出有效题面内容。

## 与原题差异分析
- changed_axes_planned: 无
- changed_axes_realized: 无
- semantic_difference: 0.0
- solution_transfer_risk: 1.0
- surface_retheme_risk: 1.0
- verdict: reject_as_retheme
- rationale: new_schema 与 original_schema 在输入结构、核心约束、目标函数和不变量上完全一致，schema_distance 为 0.0，未改变任何关键求解轴。generated_problem 状态为 difference_insufficient，题面内容全空，hard_checks 明确报告 changed_axes_threshold 与 schema_distance_threshold 失败，且样例数为 0、目标未对齐。这表明生成流程未能落地任何差异规划，新题实质为原题的失败换皮。选手无需改变建模思路，原解法（垂直步数+列坐标单调夹逼后的水平步数）可直接迁移，语义差异为零。

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
- [major] quality_issue: 生成流程完全失败，题面内容为空 | generated_problem 的 title, description, input_format, output_format, constraints, samples 均为空，status 为 difference_insufficient，error_reason 提示“没有规则通过资格校验”。
  修复建议: 修复差异规则生成逻辑，确保至少有一条规则通过校验并填充完整题面字段。
- [major] quality_issue: 核心目标与约束未落地 | new_schema 明确定义了光标移动的状态转移约束和最小化按键次数的目标，但 hard_checks.objective_alignment 失败，题面中未表达任何数值目标。
  修复建议: 在 description 和 output_format 中明确写出“求最少按键次数”及光标移动规则。
- [major] quality_issue: 样例缺失 | samples 数组为空，hard_checks.sample_count 明确报错样例数量少于2组。
  修复建议: 补充至少2组符合输入输出格式的样例，并附带解释。
- [minor] quality_issue: 变体距离为0，未实现规划差异 | schema_distance=0.00，changed_axes_realized 为空，说明规划意图未落地，题面与原题无实质差异。
  修复建议: 调整 difference_plan 规则，确保输入结构、约束或主题映射产生有效变化。
- [blocker] retheme_issue: solution transfer risk too high | new_schema 与 original_schema 在输入结构、核心约束、目标函数和不变量上完全一致，schema_distance 为 0.0，未改变任何关键求解轴。generated_problem 状态为 difference_insufficient，题面内容全空，hard_checks 明确报告 changed_axes_threshold 与 schema_distance_threshold 失败，且样例数为 0、目标未对齐。这表明生成流程未能落地任何差异规划，新题实质为原题的失败换皮。选手无需改变建模思路，原解法（垂直步数+列坐标单调夹逼后的水平步数）可直接迁移，语义差异为零。
  修复建议: 增加输入、约束与目标的实质变化，降低原题解法的直接迁移性。

## 建议修改
- 先修复生成阶段的 schema 或 difference 问题，再重新生成题面。
- 提高输入、约束与目标的结构差异，避免停留在同母题换皮。
- 至少让 I、C、O、V 中两个核心轴发生实质变化。
- 至少补齐两组可验证样例。
- 在 output_format 和 notes 中明确真实目标函数与必要的 tie-break。
- 修复差异规则生成逻辑，确保至少有一条规则通过校验并填充完整题面字段。
- 在 description 和 output_format 中明确写出“求最少按键次数”及光标移动规则。
- 补充至少2组符合输入输出格式的样例，并附带解释。
- 调整 difference_plan 规则，确保输入结构、约束或主题映射产生有效变化。
- 增加输入、约束与目标的实质变化，降低原题解法的直接迁移性。
- 重新运行生成管线，确保 difference_plan 能产出有效规则并填充所有题面字段。
- 严格按照 new_schema 的 input_structure 和 core_constraints 编写 description 与 input/output format。
- 补充符合校园主题（如教室/社团排队）的包装描述，并实现光标移动逻辑的清晰表述。
- 添加至少两组覆盖边界情况（如行首行尾、列越界截断）的样例及解释。
- 优先改写核心任务定义，而不是继续替换故事背景。

## 回流摘要
- round_index: 1
- overall_status: reject_as_retheme
- generated_status: difference_insufficient
- quality_score: 20.0
- divergence_score: 0.0
- strengths_to_keep: 无。生成产物处于失败状态，未产出有效题面内容。

## 快照
- original_problem: 253_C. Text Editor
- difference_plan_rationale: 没有规则通过资格校验。
