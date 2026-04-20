# 题目质量与反换皮评估报告

## 总览
- status: reject_as_retheme
- quality_score: 20.0
- divergence_score: 0.0
- schema_distance: 0.0
- generated_status: difference_insufficient

## 质量维度
- variant_fidelity: 1.0 / 5 | generated_problem 所有核心文本字段均为空，new_schema 中定义的输入结构（data_array、query_list）、目标函数（max_min_difference）及校园运营主题均未在题面中体现，完全未落地。
- spec_completeness: 1.0 / 5 | description、input_format、output_format、constraints 全部为空数组或空字符串，完全缺失独立解题所需的关键信息与边界条件。
- cross_section_consistency: 1.0 / 5 | 由于题面各模块内容均为空，无法形成有效的逻辑关联与一致性校验，整体处于生成失败状态，无法支撑交叉验证。
- sample_quality: 1.0 / 5 | samples 数组为空，未提供任何输入输出对及解释，hard_checks.sample_count 明确失败，无法用于理解或验证任务。
- oj_readability: 1.0 / 5 | 标题、描述、格式说明均为空字符串，status 标记为 difference_insufficient，完全不符合 OJ 题面的基本排版与表达规范，无法阅读。

## 优点
- new_schema 对输入结构、目标函数和主题包装的定义非常清晰，为后续生成提供了明确基准。

## 与原题差异分析
- changed_axes_planned: 无
- changed_axes_realized: 无
- semantic_difference: 0.0
- solution_transfer_risk: 1.0
- surface_retheme_risk: 1.0
- verdict: reject_as_retheme
- rationale: 新题的 new_schema 与 original_schema 在输入结构、核心约束与目标函数上完全一致，schema_distance 为 0.0，且 changed_axes_realized 为空，表明未规划或落地任何关键差异轴。生成产物状态为 difference_insufficient，题面所有字段（title、description、samples 等）均为空，并明确报错“没有规则通过资格校验”。这说明生成流程未能产出有效题目，仅尝试在 schema 层添加表层主题（campus_ops）但未实际改写题面。在此情况下，原题的区间最值查询（RMQ/线段树/ST表）解法可 100% 直接迁移，无需任何建模调整或逻辑修改。综合结构距离、生成失败状态与硬检查失败项，该题属于典型的生成失败/纯换皮尝试，无实质语义差异。

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
- [major] quality_issue: 生成产物完全为空且状态异常 | generated_problem 的 title、description、input_format 等核心字段均为空字符串，status 为 difference_insufficient，表明生成流程未产出有效题面文本。
  修复建议: 检查生成管线或规则校验逻辑，确保在通过资格校验后输出完整、非空的题面文本。
- [major] quality_issue: 核心目标与输入结构未落地 | new_schema 明确指定了计算区间最大最小值差值的目标及双数组输入结构，但题面中完全缺失对应描述，hard_checks.objective_alignment 已明确失败。
  修复建议: 在 description 和 output_format 中明确写出计算 max-min 差值的任务要求，并描述输入数组与查询区间的格式。
- [major] quality_issue: 样例数据缺失 | samples 数组为空，hard_checks.sample_count 失败，无法提供基础验证与格式参考。
  修复建议: 补充至少 2 组覆盖常规与边界情况的样例输入输出，并附带简要解释。
- [blocker] retheme_issue: solution transfer risk too high | 新题的 new_schema 与 original_schema 在输入结构、核心约束与目标函数上完全一致，schema_distance 为 0.0，且 changed_axes_realized 为空，表明未规划或落地任何关键差异轴。生成产物状态为 difference_insufficient，题面所有字段（title、description、samples 等）均为空，并明确报错“没有规则通过资格校验”。这说明生成流程未能产出有效题目，仅尝试在 schema 层添加表层主题（campus_ops）但未实际改写题面。在此情况下，原题的区间最值查询（RMQ/线段树/ST表）解法可 100% 直接迁移，无需任何建模调整或逻辑修改。综合结构距离、生成失败状态与硬检查失败项，该题属于典型的生成失败/纯换皮尝试，无实质语义差异。
  修复建议: 增加输入、约束与目标的实质变化，降低原题解法的直接迁移性。

## 建议修改
- 先修复生成阶段的 schema 或 difference 问题，再重新生成题面。
- 提高输入、约束与目标的结构差异，避免停留在同母题换皮。
- 至少让 I、C、O、V 中两个核心轴发生实质变化。
- 至少补齐两组可验证样例。
- 在 output_format 和 notes 中明确真实目标函数与必要的 tie-break。
- 检查生成管线或规则校验逻辑，确保在通过资格校验后输出完整、非空的题面文本。
- 在 description 和 output_format 中明确写出计算 max-min 差值的任务要求，并描述输入数组与查询区间的格式。
- 补充至少 2 组覆盖常规与边界情况的样例输入输出，并附带简要解释。
- 增加输入、约束与目标的实质变化，降低原题解法的直接迁移性。
- 修复生成中断问题，确保输出非空且结构完整的题面文本。
- 严格对照 new_schema 填充 description、input/output format 和 constraints 字段。
- 补充符合题意与格式的样例数据，并添加必要的说明。
- 优先改写核心任务定义，而不是继续替换故事背景。

## 回流摘要
- round_index: 1
- overall_status: reject_as_retheme
- generated_status: difference_insufficient
- quality_score: 20.0
- divergence_score: 0.0
- strengths_to_keep: new_schema 对输入结构、目标函数和主题包装的定义非常清晰，为后续生成提供了明确基准。

## 快照
- original_problem: mqry
- difference_plan_rationale: 没有规则通过资格校验。
