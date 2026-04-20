# 题目质量与反换皮评估报告

## 总览
- status: reject_as_retheme
- quality_score: 20.0
- divergence_score: 0.0
- schema_distance: 0.0
- generated_status: difference_insufficient

## 质量维度
- variant_fidelity: 1.0 / 5 | 生成题面所有核心字段均为空，new_schema 中定义的树结构、操作规则、目标函数及主题映射均未落地。
- spec_completeness: 1.0 / 5 | 题面完全缺失任务说明、输入输出格式、约束条件等关键信息，无法独立做题。
- cross_section_consistency: 1.0 / 5 | 由于题面内容为空，各部分之间无任何实质内容可供校验一致性，整体处于失效状态。
- sample_quality: 1.0 / 5 | 样例数组为空，数量为0，无法提供任何参考或验证。
- oj_readability: 1.0 / 5 | 题面全为空字符串，无任何可读文本，不符合OJ题面基本规范。

## 与原题差异分析
- changed_axes_planned: 无
- changed_axes_realized: 无
- semantic_difference: 0.0
- solution_transfer_risk: 1.0
- surface_retheme_risk: 1.0
- verdict: reject_as_retheme
- rationale: new_schema 与 original_schema 在输入结构、核心约束、目标函数及不变量上完全一致，schema_distance 为 0.0，且 difference_plan 明确指出“规则规划失败”，落地差异轴数量为 0。generated_problem 处于 difference_insufficient 状态，所有题面字段（标题、描述、输入输出格式、样例等）均为空，未生成任何有效内容。因此，新题在任务语义上无任何实质变化，原题解法（基于减半收益的贪心+双指针/前缀和）可直接原样迁移，属于典型的生成失败/完全未脱离原题框架的换皮。

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
- [major] quality_issue: 生成流程完全失败，题面为空 | generated_problem 的 title、description、input_format 等核心字段均为空字符串或空数组，状态标记为 difference_insufficient，表明规则规划失败，未产出任何有效内容。
  修复建议: 检查规则生成与过滤逻辑，确保至少有一条有效规则通过校验并触发题面生成；或更换种子题/调整差异轴规划。
- [major] quality_issue: Schema 距离与差异轴未达标 | schema_distance 为 0.00，changed_axes 为 0，说明生成器未对原题进行任何实质性修改或主题映射，直接导致生成被拦截。
  修复建议: 在 difference_plan 中明确指定至少一个核心差异轴（如操作类型、目标函数或主题映射），并提高 schema_distance 阈值要求。
- [blocker] retheme_issue: solution transfer risk too high | new_schema 与 original_schema 在输入结构、核心约束、目标函数及不变量上完全一致，schema_distance 为 0.0，且 difference_plan 明确指出“规则规划失败”，落地差异轴数量为 0。generated_problem 处于 difference_insufficient 状态，所有题面字段（标题、描述、输入输出格式、样例等）均为空，未生成任何有效内容。因此，新题在任务语义上无任何实质变化，原题解法（基于减半收益的贪心+双指针/前缀和）可直接原样迁移，属于典型的生成失败/完全未脱离原题框架的换皮。
  修复建议: 增加输入、约束与目标的实质变化，降低原题解法的直接迁移性。

## 建议修改
- 先修复生成阶段的 schema 或 difference 问题，再重新生成题面。
- 提高输入、约束与目标的结构差异，避免停留在同母题换皮。
- 至少让 I、C、O、V 中两个核心轴发生实质变化。
- 至少补齐两组可验证样例。
- 在 output_format 和 notes 中明确真实目标函数与必要的 tie-break。
- 检查规则生成与过滤逻辑，确保至少有一条有效规则通过校验并触发题面生成；或更换种子题/调整差异轴规划。
- 在 difference_plan 中明确指定至少一个核心差异轴（如操作类型、目标函数或主题映射），并提高 schema_distance 阈值要求。
- 增加输入、约束与目标的实质变化，降低原题解法的直接迁移性。
- 修复生成管线中的规则校验模块，确保 new_schema 中的差异规划能正确转化为题面文本。
- 补充完整的题面结构，至少包含符合 new_schema 设定的树形输入格式、向下取整除以2的操作描述、总路径和不超过S的约束以及最小化代价的输出要求。
- 根据 theme 映射提示，将抽象的树与边权操作包装为校园运营场景（如社团物资调配、教室排课等），并生成至少2组覆盖边界情况的样例。
- 优先改写核心任务定义，而不是继续替换故事背景。

## 回流摘要
- round_index: 1
- overall_status: reject_as_retheme
- generated_status: difference_insufficient
- quality_score: 20.0
- divergence_score: 0.0

## 快照
- original_problem: 1399_E2. Weights Division (hard version)
- difference_plan_rationale: 没有规则通过资格校验。
