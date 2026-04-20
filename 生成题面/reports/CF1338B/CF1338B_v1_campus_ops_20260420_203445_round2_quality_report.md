# 题目质量与反换皮评估报告

## 总览
- status: reject_as_retheme
- quality_score: 20.0
- divergence_score: 0.0
- schema_distance: 0.0
- generated_status: difference_insufficient

## 质量维度
- variant_fidelity: 1.0 / 5 | new_schema 中定义的树结构、叶子路径异或约束、最值目标及校园主题均未在生成题面中体现。generated_problem 所有核心字段均为空，hard_checks 明确指出 schema_distance=0.00 且 changed_axes_threshold 未通过，变体完全未落地。
- spec_completeness: 1.0 / 5 | 题面完全缺失任务说明、输入输出格式、约束条件等关键信息，读者无法获取任何解题所需规则。description、input_format、output_format、constraints 均为空字符串或空数组。
- cross_section_consistency: 1.0 / 5 | 由于题面各部分内容全部为空，不存在任何字段数量、目标定义或符号含义的交叉验证基础，一致性维度彻底失效。
- sample_quality: 1.0 / 5 | 样例数量为 0，hard_checks.sample_count 明确失败（少于 2 组），无法覆盖任何关键结构或验证输出格式。
- oj_readability: 1.0 / 5 | 题面标题、描述、格式说明等全部为空字符串，完全不符合 OJ 题面表达习惯，无任何可读性。

## 与原题差异分析
- changed_axes_planned: 无
- changed_axes_realized: 无
- semantic_difference: 0.0
- solution_transfer_risk: 1.0
- surface_retheme_risk: 1.0
- verdict: reject_as_retheme
- rationale: 新题的 new_schema 与 original_schema 在输入结构、核心约束（任意两叶子路径异或和为0）、目标函数（不同边权数量的最小/最大值）及关键不变量上完全一致，schema_distance 为 0.0。review_context 中 changed_axes_realized 为空数组，difference_plan 未规划任何有效差异轴。generated_problem 状态为 difference_insufficient，所有题面字段为空，生成流程已明确失败。因此，新题在任务语义上无任何实质变化，原题的标准解法（基于叶子到根距离奇偶性分类判定最小值，基于共享父节点叶子边权值强制相同扣减最大值）可完全原样迁移。hard_checks 中的 schema_distance_threshold 与 changed_axes_threshold 均明确失败，直接判定为差异不足的换皮尝试。

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
- [PASS] objective_alignment (blocker/quality_issue): 目标函数已经在题面中落地。
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
- [major] quality_issue: 生成题面内容完全为空 | generated_problem 的 title, description, input_format, output_format, constraints, samples 均为空字符串或空数组，导致无法进行任何有效评估与做题。
  修复建议: 检查生成管线状态与模板渲染逻辑，确保 new_schema 被正确解析并完整填充至题面各字段。
- [major] quality_issue: 规划差异轴与 schema 距离未达标 | hard_checks 显示 schema_distance=0.00 且 changed_axes_threshold 失败，说明 new_schema 中定义的变体（叶子路径异或约束、最值目标、校园主题）未落地，生成流程可能因校验失败直接输出了空模板。
  修复建议: 修正 difference_plan 生成逻辑，确保 changed_axes 与 new_schema 的真实变化一致后再进行文本生成，或调整阈值校验策略。
- [major] quality_issue: 样例数量缺失 | hard_checks.sample_count 明确失败，样例数量为 0，少于要求的 2 组，无法辅助理解题意或验证边界条件。
  修复建议: 根据题意构造至少 2 组覆盖关键情况（如所有叶子同奇偶类、不同奇偶类）的样例输入输出及详细解释。
- [blocker] retheme_issue: solution transfer risk too high | 新题的 new_schema 与 original_schema 在输入结构、核心约束（任意两叶子路径异或和为0）、目标函数（不同边权数量的最小/最大值）及关键不变量上完全一致，schema_distance 为 0.0。review_context 中 changed_axes_realized 为空数组，difference_plan 未规划任何有效差异轴。generated_problem 状态为 difference_insufficient，所有题面字段为空，生成流程已明确失败。因此，新题在任务语义上无任何实质变化，原题的标准解法（基于叶子到根距离奇偶性分类判定最小值，基于共享父节点叶子边权值强制相同扣减最大值）可完全原样迁移。hard_checks 中的 schema_distance_threshold 与 changed_axes_threshold 均明确失败，直接判定为差异不足的换皮尝试。
  修复建议: 增加输入、约束与目标的实质变化，降低原题解法的直接迁移性。

## 建议修改
- 先修复生成阶段的 schema 或 difference 问题，再重新生成题面。
- 提高输入、约束与目标的结构差异，避免停留在同母题换皮。
- 至少让 I、C、O、V 中两个核心轴发生实质变化。
- 至少补齐两组可验证样例。
- 检查生成管线状态与模板渲染逻辑，确保 new_schema 被正确解析并完整填充至题面各字段。
- 修正 difference_plan 生成逻辑，确保 changed_axes 与 new_schema 的真实变化一致后再进行文本生成，或调整阈值校验策略。
- 根据题意构造至少 2 组覆盖关键情况（如所有叶子同奇偶类、不同奇偶类）的样例输入输出及详细解释。
- 增加输入、约束与目标的实质变化，降低原题解法的直接迁移性。
- 重新执行生成流程，将 new_schema 中的树结构、异或约束、最值目标及校园主题完整映射至 description 与 input/output format。
- 补充至少 2 组符合逻辑的样例输入输出及详细解释，确保覆盖叶子节点奇偶性划分的不同情况。
- 修复生成管线中 difference_plan 与 new_schema 的对齐校验逻辑，避免输出空模板或中断生成。
- 优先改写核心任务定义，而不是继续替换故事背景。

## 回流摘要
- round_index: 2
- overall_status: reject_as_retheme
- generated_status: difference_insufficient
- quality_score: 20.0
- divergence_score: 0.0

## 快照
- original_problem: 1338_B. Edge Weight Assignment
- difference_plan_rationale: difference_plan.changed_axes 与 new_schema 的真实变化不一致。
