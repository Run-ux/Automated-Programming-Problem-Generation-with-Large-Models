# 题目质量与反换皮评估报告

## 总览
- status: reject_as_retheme
- quality_score: 20.0
- divergence_score: 0.0
- schema_distance: 0.0
- generated_status: difference_insufficient

## 质量维度
- variant_fidelity: 1.0 / 5 | 生成题面所有核心字段均为空，new_schema 中定义的加权有根树结构、边权除以2操作、根到叶子路径和阈值约束及最小化操作次数目标均未在题面中体现，完全未落地。
- spec_completeness: 1.0 / 5 | 题面完全缺失任务说明、输入输出格式、数据范围与约束条件，读者无法获取任何独立解题所需的关键信息，属于严重缺失。
- cross_section_consistency: 1.0 / 5 | 题面各模块（描述、输入、输出、约束、样例）均为空字符串或空数组，不存在有效的交叉一致性，整体结构完全失效。
- sample_quality: 1.0 / 5 | 样例数量为0，未提供任何输入输出示例，无法覆盖关键结构或辅助理解任务，直接违反基础质量要求。
- oj_readability: 1.0 / 5 | 题面内容为空，无任何可读文本、结构排版或背景包装，完全不符合 OJ 题面表达习惯，无法供参赛者阅读。

## 优点
- new_schema 结构定义清晰，约束条件、目标函数与不变量描述完整，为后续生成提供了明确的规范。

## 与原题差异分析
- changed_axes_planned: 无
- changed_axes_realized: 无
- semantic_difference: 0.0
- solution_transfer_risk: 1.0
- surface_retheme_risk: 1.0
- verdict: reject_as_retheme
- rationale: 新题生成完全失败（generated_problem 各字段为空，status 标记为 difference_insufficient），且 new_schema 与 original_schema 在输入结构、核心约束、目标函数与不变量上完全一致（schema_distance=0.0，changed_axes_realized=[]，axis_scores 全为 0.0）。I/C/O/V 关键轴均未发生任何实质改变，仅尝试附加表层主题词（campus_ops）。若按此 schema 落地，原题的标准解法（计算每条边覆盖的叶子数得到贡献值，使用优先队列贪心选取单次操作边际收益最大的边进行 floor(w/2) 操作）可完全无缝迁移，无需任何建模调整。hard_checks 明确提示 schema_distance 低于 0.35 阈值且未落地任何差异轴，属于典型的换皮失败/未生成案例。

## 硬检查
- [PASS] source_problem_resolved (blocker/invalid): 已成功加载原题文本。
- [PASS] generated_problem_present (blocker/invalid): artifact 已包含 generated_problem。
- [PASS] new_schema_present (blocker/invalid): artifact 已包含 new_schema 或兼容字段 new_schema_snapshot。
- [PASS] difference_plan_present (blocker/invalid): artifact 已持久化 difference_plan。
- [FAIL] generated_status_ok (blocker/retheme_issue): 生成产物状态为 difference_insufficient：规划结果未达到硬门槛，预测距离=0.3427，落地轴=C, O, V。
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
- [blocker] retheme_issue: generated status ok | 生成产物状态为 difference_insufficient：规划结果未达到硬门槛，预测距离=0.3427，落地轴=C, O, V。
  修复建议: 先修复生成阶段的 schema 或 difference 问题，再重新生成题面。
- [blocker] retheme_issue: schema distance threshold | schema_distance=0.00，低于 0.35。 已接近同母题换皮（<0.25）。
  修复建议: 提高输入、约束与目标的结构差异，避免停留在同母题换皮。
- [blocker] retheme_issue: changed axes threshold | 仅落地了 0 个核心差异轴：无。
  修复建议: 至少让 I、C、O、V 中两个核心轴发生实质变化。
- [major] quality_issue: sample count | 样例数量=0。 少于 2 组。
  修复建议: 至少补齐两组可验证样例。
- [blocker] quality_issue: objective alignment | 数值目标未在题面中明确表达。
  修复建议: 在 output_format 和 notes 中明确真实目标函数与必要的 tie-break。
- [major] quality_issue: 题面生成完全为空 | generated_problem 的 title, description, input_format, output_format, constraints, samples 均为空字符串或空数组，导致题面无法使用。
  修复建议: 检查生成模型或模板渲染流程，确保输出完整的题面文本，避免空值返回。
- [major] quality_issue: 规划差异轴与目标函数未落地 | difference_plan 显示 changed_axes 为空，schema_distance 为 0.0，且 objective_alignment 硬检查失败，new_schema 中的最小化操作次数目标未在 output_format 中声明。
  修复建议: 重新执行差异规划，确保将操作规则、阈值约束与优化目标准确映射到题面描述与输出格式中。
- [major] quality_issue: 样例缺失 | 样例数量为 0，未通过 sample_count 硬检查，无法验证格式或提供解题线索。
  修复建议: 补充至少 2 组符合约束的样例输入输出，并附带简要解释以覆盖关键边界。
- [blocker] retheme_issue: solution transfer risk too high | 新题生成完全失败（generated_problem 各字段为空，status 标记为 difference_insufficient），且 new_schema 与 original_schema 在输入结构、核心约束、目标函数与不变量上完全一致（schema_distance=0.0，changed_axes_realized=[]，axis_scores 全为 0.0）。I/C/O/V 关键轴均未发生任何实质改变，仅尝试附加表层主题词（campus_ops）。若按此 schema 落地，原题的标准解法（计算每条边覆盖的叶子数得到贡献值，使用优先队列贪心选取单次操作边际收益最大的边进行 floor(w/2) 操作）可完全无缝迁移，无需任何建模调整。hard_checks 明确提示 schema_distance 低于 0.35 阈值且未落地任何差异轴，属于典型的换皮失败/未生成案例。
  修复建议: 增加输入、约束与目标的实质变化，降低原题解法的直接迁移性。

## 建议修改
- 先修复生成阶段的 schema 或 difference 问题，再重新生成题面。
- 提高输入、约束与目标的结构差异，避免停留在同母题换皮。
- 至少让 I、C、O、V 中两个核心轴发生实质变化。
- 至少补齐两组可验证样例。
- 在 output_format 和 notes 中明确真实目标函数与必要的 tie-break。
- 检查生成模型或模板渲染流程，确保输出完整的题面文本，避免空值返回。
- 重新执行差异规划，确保将操作规则、阈值约束与优化目标准确映射到题面描述与输出格式中。
- 补充至少 2 组符合约束的样例输入输出，并附带简要解释以覆盖关键边界。
- 增加输入、约束与目标的实质变化，降低原题解法的直接迁移性。
- 修复生成管线空输出问题，确保所有字段填充有效文本。
- 将 new_schema 中的树结构、边权更新规则、路径和阈值 S 及最小化目标完整写入 description 与 input/output_format。
- 结合“校园运营”主题进行背景包装，提升题面可读性与代入感。
- 补充符合数据范围的样例及解释，确保格式与题意严格对齐。
- 优先改写核心任务定义，而不是继续替换故事背景。

## 回流摘要
- round_index: 1
- overall_status: reject_as_retheme
- generated_status: difference_insufficient
- quality_score: 20.0
- divergence_score: 0.0
- strengths_to_keep: new_schema 结构定义清晰，约束条件、目标函数与不变量描述完整，为后续生成提供了明确的规范。

## 快照
- original_problem: 1399_E1. Weights Division (easy version)
- difference_plan_rationale: 规划结果未达到硬门槛，预测距离=0.3427，落地轴=C, O, V。
