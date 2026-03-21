# 题目质量与反换皮评估报告

## 总览
- status: reject_as_retheme
- quality_score: 88.0
- divergence_score: 41.3
- schema_distance: 0.4742
- generated_status: ok

## 质量维度
- variant_fidelity: 3.0 / 5 | Schema contains internal contradictions regarding coordinate signs and exposure levels which are not fully resolved in the problem statement. Specifically, 'allow_negative_coordinates' is in selected_structural_options but the problem enforces non-negative. 'allow_multiple_sun_exposure_levels' is selected but the logic is binary (visible/blocked) rather than multi-level.
- spec_completeness: 5.0 / 5 | All necessary sections (Description, Input, Output, Constraints, Samples, Notes) are present and clearly defined. Overlap rules and order dependence are explicitly stated.
- cross_section_consistency: 5.0 / 5 | No contradictions found between description, input/output formats, constraints, and samples. Sample explanations align perfectly with the rules described.
- sample_quality: 5.0 / 5 | Two samples provided cover key cases: partial overlap, full overlap, and edge contact (non-overlap). Explanations are detailed and helpful.
- oj_readability: 5.0 / 5 | Standard OJ format, clear language, appropriate theme mapping. No noise or confusing text.

## 优点
- Clear and standard OJ problem structure.
- Sample explanations effectively clarify edge cases like edge contact vs. overlap.
- Thematic mapping (Club Booths) fits the Campus Operations theme well.
- Constraints and limits are explicitly defined.

## 与原题差异分析
- changed_axes_planned: C, O, V, T
- changed_axes_realized: C, O, V, T
- semantic_difference: 0.15
- solution_transfer_risk: 0.95
- surface_retheme_risk: 0.85
- verdict: reject_as_retheme
- rationale: 核心几何判定逻辑完全一致：原题与新题均要求判断每个矩形是否与所有后续矩形无重叠（原题'完全暴露'等价于新题'无遮挡'）。虽然新题将输出从'逐个判断'改为'统计总数'，但这在算法层面不改变复杂度或解法框架（仍需对每个矩形执行相同的几何检查），属于 trivial 的后处理差异。此外，instantiated_schema 中选中的'allow_negative_coordinates'选项在 generated_problem 约束中未落地（仍限制为非负），显示结构修改未真实执行。熟悉原题的选手可直接复用线段树或坐标压缩等核心代码，仅修改输出累加逻辑即可 AC，属于典型的换皮题。

## 硬检查
- [PASS] source_problem_resolved (blocker/invalid): 已成功加载原题文本。
- [PASS] generated_status_ok (blocker/invalid): 生成状态正常。
- [PASS] difference_plan_present (major/retheme_issue): artifact 已持久化 difference_plan。
- [PASS] schema_distance_threshold (blocker/retheme_issue): schema_distance=0.47，达到中等差异阈值。
- [PASS] changed_axes_threshold (blocker/retheme_issue): 已落地核心差异轴：C, O, V, T。
- [PASS] source_leakage (blocker/retheme_issue): 未发现原题标题/题源泄露。
- [PASS] title_overlap (major/retheme_issue): 标题重合度=0.00。
- [PASS] sample_count (major/quality_issue): 样例数量=2。
- [PASS] sample_line_alignment (major/quality_issue): 输入结构不是固定小数组，跳过样例行数检查。
- [PASS] input_count_alignment (blocker/quality_issue): 输入结构不是固定小数组，跳过输入项数量声明检查。
- [PASS] objective_alignment (blocker/quality_issue): 目标函数已经在题面中落地。
- [PASS] structural_option_alignment (blocker/quality_issue): 结构选项已在题面中落地。

## 问题清单
- [major] quality_issue: Schema Option Contradiction on Coordinates | The schema selects 'allow_negative_coordinates' in structural_options, but input_structure.properties and selected_input_options enforce 'non_negative_coordinates'. The problem statement follows the non-negative constraint, ignoring the structural option.
  修复建议: Ensure selected_structural_options align with input_structure.properties. If non-negative is required, remove allow_negative_coordinates from options.
- [minor] quality_issue: Exposure Level Logic Simplification | The schema option 'allow_multiple_sun_exposure_levels' is selected, but the problem implements a binary visibility check (blocked or not) rather than utilizing multiple exposure levels in the objective or constraints.
  修复建议: Clarify if 'multiple levels' implies stacking depth should be output or used in constraints, or remove the option if binary visibility is intended.
- [minor] quality_issue: Coverage Scope Specificity | Schema constraint 'coverage' mentions 'any other rectangle', while the problem specifies 'any subsequent rectangle'. This is a valid thematic refinement but deviates from the generic constraint text.
  修复建议: Ensure the core_constraints description in schema reflects the ordered nature if 'subsequent' is the intended logic.
- [blocker] retheme_issue: solution transfer risk too high | 核心几何判定逻辑完全一致：原题与新题均要求判断每个矩形是否与所有后续矩形无重叠（原题'完全暴露'等价于新题'无遮挡'）。虽然新题将输出从'逐个判断'改为'统计总数'，但这在算法层面不改变复杂度或解法框架（仍需对每个矩形执行相同的几何检查），属于 trivial 的后处理差异。此外，instantiated_schema 中选中的'allow_negative_coordinates'选项在 generated_problem 约束中未落地（仍限制为非负），显示结构修改未真实执行。熟悉原题的选手可直接复用线段树或坐标压缩等核心代码，仅修改输出累加逻辑即可 AC，属于典型的换皮题。
  修复建议: 增加输入/约束/目标的实质变化，降低原题解法的直接迁移性。

## 建议修改
- Ensure selected_structural_options align with input_structure.properties. If non-negative is required, remove allow_negative_coordinates from options.
- Clarify if 'multiple levels' implies stacking depth should be output or used in constraints, or remove the option if binary visibility is intended.
- Ensure the core_constraints description in schema reflects the ordered nature if 'subsequent' is the intended logic.
- 增加输入/约束/目标的实质变化，降低原题解法的直接迁移性。
- Resolve the contradiction between 'allow_negative_coordinates' and 'non_negative_coordinates' in the schema before generation.
- Clarify the intent of 'allow_multiple_sun_exposure_levels' to ensure the problem logic matches the selected option.
- Update schema constraint descriptions to match the ordered/subsequent logic if that is the intended variant.
- 优先改写核心任务定义，而不是继续替换故事背景。

## 快照
- original_problem: [COCI 2018/2019 #2] Sunčanje
- difference_plan_rationale: 该方案保持同族算法线索，但通过目标函数、结构选项、输入视角与不变量提示拉开差异。 objective=count，structural_options=allow_negative_coordinates, allow_multiple_sun_exposure_levels，input_options=non_negative_coordinates，invariant_options=overlap_conflict_resolution，预测距离=0.47，落地轴=C, O, V, T。
