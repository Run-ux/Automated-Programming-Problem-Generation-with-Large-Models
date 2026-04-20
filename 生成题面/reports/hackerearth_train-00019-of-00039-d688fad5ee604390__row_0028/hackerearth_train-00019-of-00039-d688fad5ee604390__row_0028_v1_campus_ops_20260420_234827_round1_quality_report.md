# 题目质量与反换皮评估报告

## 总览
- status: reject_as_retheme
- quality_score: 20.0
- divergence_score: 0.0
- schema_distance: 0.0
- generated_status: difference_insufficient

## 质量维度
- variant_fidelity: 1.0 / 5 | 生成题面所有核心字段均为空，完全未落地 new_schema 规定的数组输入、多测结构、欧拉函数约束、最小化总成本目标及校园主题。
- spec_completeness: 1.0 / 5 | 题面描述、输入输出格式、约束条件全部缺失，参赛者无法获取任何解题所需的关键信息，任务说明完全空白。
- cross_section_consistency: 1.0 / 5 | 题面内容为空，不存在可交叉验证的字段，整体结构断裂，无法形成一致的题意表达与格式对应。
- sample_quality: 1.0 / 5 | 样例数组为空，数量为 0，严重违反 OJ 题面至少提供 2 组样例的基本要求，无法辅助理解题意。
- oj_readability: 1.0 / 5 | 标题、描述等均为空字符串，无任何可读文本，完全不符合 OJ 题面规范，参赛者无法阅读。

## 与原题差异分析
- changed_axes_planned: 无
- changed_axes_realized: 无
- semantic_difference: 0.0
- solution_transfer_risk: 1.0
- surface_retheme_risk: 1.0
- verdict: reject_as_retheme
- rationale: 新题生成完全失败，generated_problem 所有核心字段为空且状态明确标记为 difference_insufficient。new_schema 与 original_schema 在输入结构、核心约束（φ(h_i) ≥ s_i）、目标函数（最小化总成本）及不变量（可加性、单调性）上完全一致，schema_distance 为 0.0，且 changed_axes_realized 为空数组。这意味着题目在任务语义、状态定义和求解关注点上没有任何实质变化，原题的逐查询独立求解+预处理/二分查找最小高度的解法可 100% 直接迁移。hard_checks 中 schema_distance_threshold、changed_axes_threshold、objective_alignment 和 sample_count 均失败，证实该题仅为未成功落地的结构级复制，无任何有效差异轴被实现。

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
- [major] quality_issue: 生成产物完全为空 | generated_problem 的 title, description, input_format, output_format, constraints, samples 均为空字符串或空数组，导致题面无法使用。
  修复建议: 检查生成管线是否因 difference_insufficient 状态中断，需强制输出完整题面结构，避免空值返回。
- [major] quality_issue: 核心差异轴未落地且 schema 距离为 0 | difference_plan.changed_axes 为空，schema_distance=0.00，表明生成过程未对原题进行任何有效改写或主题映射，规划意图完全未兑现。
  修复建议: 重新规划 difference_plan，确保至少落地 1 个核心差异轴（如输入结构或目标函数），并触发实际文本生成。
- [major] quality_issue: 目标函数未在题面中声明 | hard_checks.objective_alignment 失败，new_schema 要求最小化总成本，但 output_format 为空，未明确输出要求。
  修复建议: 在 output_format 中明确说明需输出一个整数表示最小总花费，并在 description 中强调优化目标。
- [major] quality_issue: 样例缺失 | 样例数量为 0，无法验证格式与逻辑，不符合基础质量要求。
  修复建议: 根据 new_schema 的约束（多测、数组、φ(h)≥s）构造至少 2 组覆盖边界与常规情况的样例，并附带解释。
- [blocker] retheme_issue: solution transfer risk too high | 新题生成完全失败，generated_problem 所有核心字段为空且状态明确标记为 difference_insufficient。new_schema 与 original_schema 在输入结构、核心约束（φ(h_i) ≥ s_i）、目标函数（最小化总成本）及不变量（可加性、单调性）上完全一致，schema_distance 为 0.0，且 changed_axes_realized 为空数组。这意味着题目在任务语义、状态定义和求解关注点上没有任何实质变化，原题的逐查询独立求解+预处理/二分查找最小高度的解法可 100% 直接迁移。hard_checks 中 schema_distance_threshold、changed_axes_threshold、objective_alignment 和 sample_count 均失败，证实该题仅为未成功落地的结构级复制，无任何有效差异轴被实现。
  修复建议: 增加输入、约束与目标的实质变化，降低原题解法的直接迁移性。

## 建议修改
- 先修复生成阶段的 schema 或 difference 问题，再重新生成题面。
- 提高输入、约束与目标的结构差异，避免停留在同母题换皮。
- 至少让 I、C、O、V 中两个核心轴发生实质变化。
- 至少补齐两组可验证样例。
- 在 output_format 和 notes 中明确真实目标函数与必要的 tie-break。
- 检查生成管线是否因 difference_insufficient 状态中断，需强制输出完整题面结构，避免空值返回。
- 重新规划 difference_plan，确保至少落地 1 个核心差异轴（如输入结构或目标函数），并触发实际文本生成。
- 在 output_format 中明确说明需输出一个整数表示最小总花费，并在 description 中强调优化目标。
- 根据 new_schema 的约束（多测、数组、φ(h)≥s）构造至少 2 组覆盖边界与常规情况的样例，并附带解释。
- 增加输入、约束与目标的实质变化，降低原题解法的直接迁移性。
- 修复生成管线状态检查逻辑，避免 difference_insufficient 导致空输出。
- 严格对照 new_schema 填充 description（融入校园排队/分配主题）、input_format（多测+数组）、output_format（最小总成本）、constraints（1≤n≤10000, 1≤a_i≤10^6, φ(h)≥s）。
- 补充符合格式的样例及解释，确保覆盖单元素、多元素及边界值。
- 优先改写核心任务定义，而不是继续替换故事背景。

## 回流摘要
- round_index: 1
- overall_status: reject_as_retheme
- generated_status: difference_insufficient
- quality_score: 20.0
- divergence_score: 0.0

## 快照
- original_problem: climbing-ladder-1
- difference_plan_rationale: difference_plan.changed_axes 与 new_schema 的真实变化不一致。
