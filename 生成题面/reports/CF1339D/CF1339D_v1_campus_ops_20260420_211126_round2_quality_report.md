# 题目质量与反换皮评估报告

## 总览
- status: reject_as_retheme
- quality_score: 20.0
- divergence_score: 0.0
- schema_distance: 0.0
- generated_status: difference_insufficient

## 质量维度
- variant_fidelity: 1.0 / 5 | generated_problem 所有核心字段均为空，new_schema 中定义的树结构、叶子路径异或约束、最值目标及校园主题均未落地。hard_checks 中 objective_alignment 明确失败。
- spec_completeness: 1.0 / 5 | 题面 description、input_format、output_format、constraints 全为空字符串或空数组，完全缺失独立解题所需的关键信息，读者无法获取任何任务规则。
- cross_section_consistency: 1.0 / 5 | 由于题面各部分均为空，无法构成任何有效逻辑或格式对应关系，整体处于未生成状态，一致性无从谈起。
- sample_quality: 1.0 / 5 | 样例数量为 0，hard_checks 中 sample_count 明确失败，无法覆盖关键结构或提供解释。
- oj_readability: 1.0 / 5 | 题面所有文本字段为空，且状态标记为 difference_insufficient 并附带错误提示，完全不符合 OJ 题面规范，无法阅读。

## 优点
- new_schema 自身的约束定义、不变量分析与主题映射意图清晰，为后续生成提供了明确的结构蓝图。

## 与原题差异分析
- changed_axes_planned: 无
- changed_axes_realized: 无
- semantic_difference: 0.0
- solution_transfer_risk: 1.0
- surface_retheme_risk: 1.0
- verdict: reject_as_retheme
- rationale: 新题生成流程完全失败，且schema未做任何实质修改。new_schema与original_schema在输入结构、核心约束（任意两叶子路径异或和为0）、目标函数（不同边权数量最值）及不变量上完全一致，schema_distance为0.0，changed_axes_realized为空数组。generated_problem状态明确为difference_insufficient，所有题面字段（标题、描述、输入输出格式、样例）均为空，未落地任何主题映射或规则变化。hard_checks中schema_distance_threshold、changed_axes_threshold、generated_status_ok及objective_alignment均失败。因此，语义差异为0，原题解法（深度奇偶性判定最小值、兄弟叶子边合并统计最大值）可100%直接迁移，属于未成功生成且完全克隆原题结构的失败产物。

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
- [major] quality_issue: 生成管线失败导致题面完全为空 | generated_problem 的 title、description、input_format 等核心字段均为空字符串，status 为 difference_insufficient，error_reason 指出没有规则通过资格校验。
  修复建议: 检查规则校验逻辑或更换种子题，确保生成流程能输出完整题面文本。
- [major] quality_issue: 核心差异轴与目标函数未落地 | hard_checks 显示 changed_axes_threshold 和 objective_alignment 均失败，schema_distance 为 0.00。new_schema 规划的叶子异或约束与最值目标未在题面中体现。
  修复建议: 根据 new_schema 的 core_constraints 和 objective 字段，在 description 和 output_format 中明确写出异或约束与输出要求。
- [major] quality_issue: 样例缺失 | samples 数组为空，hard_checks.sample_count 失败，不满足 OJ 题面至少 2 组样例的基本要求。
  修复建议: 构造至少两组符合树结构与异或约束的样例，并附带对应的最小/最大边权数输出及简要解释。
- [blocker] retheme_issue: solution transfer risk too high | 新题生成流程完全失败，且schema未做任何实质修改。new_schema与original_schema在输入结构、核心约束（任意两叶子路径异或和为0）、目标函数（不同边权数量最值）及不变量上完全一致，schema_distance为0.0，changed_axes_realized为空数组。generated_problem状态明确为difference_insufficient，所有题面字段（标题、描述、输入输出格式、样例）均为空，未落地任何主题映射或规则变化。hard_checks中schema_distance_threshold、changed_axes_threshold、generated_status_ok及objective_alignment均失败。因此，语义差异为0，原题解法（深度奇偶性判定最小值、兄弟叶子边合并统计最大值）可100%直接迁移，属于未成功生成且完全克隆原题结构的失败产物。
  修复建议: 增加输入、约束与目标的实质变化，降低原题解法的直接迁移性。

## 建议修改
- 先修复生成阶段的 schema 或 difference 问题，再重新生成题面。
- 提高输入、约束与目标的结构差异，避免停留在同母题换皮。
- 至少让 I、C、O、V 中两个核心轴发生实质变化。
- 至少补齐两组可验证样例。
- 在 output_format 和 notes 中明确真实目标函数与必要的 tie-break。
- 检查规则校验逻辑或更换种子题，确保生成流程能输出完整题面文本。
- 根据 new_schema 的 core_constraints 和 objective 字段，在 description 和 output_format 中明确写出异或约束与输出要求。
- 构造至少两组符合树结构与异或约束的样例，并附带对应的最小/最大边权数输出及简要解释。
- 增加输入、约束与目标的实质变化，降低原题解法的直接迁移性。
- 修复生成管线的规则校验环节，确保 difference_plan 能成功落地。
- 依据 new_schema 补全 description 中的校园运营背景与异或约束描述。
- 在 output_format 中明确说明需输出两个整数（最小与最大不同边权数量）。
- 补充至少 2 组覆盖单奇偶类与双奇偶类情况的样例，并添加 notes 解释。
- 优先改写核心任务定义，而不是继续替换故事背景。

## 回流摘要
- round_index: 2
- overall_status: reject_as_retheme
- generated_status: difference_insufficient
- quality_score: 20.0
- divergence_score: 0.0
- strengths_to_keep: new_schema 自身的约束定义、不变量分析与主题映射意图清晰，为后续生成提供了明确的结构蓝图。

## 快照
- original_problem: 1339_D. Edge Weight Assignment
- difference_plan_rationale: 没有规则通过资格校验。
