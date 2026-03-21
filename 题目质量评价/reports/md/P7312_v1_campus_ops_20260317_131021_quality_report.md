# 题目质量与反换皮评估报告

## 总览
- status: reject_as_retheme
- quality_score: 100.0
- divergence_score: 44.1
- schema_distance: 0.4742
- generated_status: ok

## 质量维度
- variant_fidelity: 5.0 / 5 | 生成的题面准确实现了 instantiated_schema 中定义的输入结构（N 个矩形，坐标及尺寸范围）、目标函数（统计成功数量）及核心约束（矩形覆盖逻辑）。虽然 schema 内部 core_constraints 与 selected_input_options 在负坐标选项上存在文本冲突，但生成题面正确遵循了 input_structure 和 selected_input_options 中的非负坐标定义，保持了数据定义的一致性。
- spec_completeness: 5.0 / 5 | 题面包含了任务说明、输入格式、输出格式、数据约束、样例及注释。特别在注释中明确了重叠的定义（面积大于 0，边界接触不算），消除了几何题常见的歧义，信息完整。
- cross_section_consistency: 5.0 / 5 | 描述、输入、输出、约束和样例之间逻辑一致。样例解释中的几何计算与题目定义的遮挡规则吻合（如样例 1 中边界接触不计入遮挡）。约束中的范围与输入格式描述一致。
- sample_quality: 5.0 / 5 | 提供了 2 个样例，分别覆盖了部分重叠遮挡、边界接触不遮挡、完全重合遮挡等关键情况。样例解释清晰，有助于理解遮挡判定逻辑。
- oj_readability: 5.0 / 5 | 题面结构符合标准 OJ 规范，语言通顺，术语准确（如'左下角坐标'、'宽度'、'高度'）。主题映射（社团展位）自然，无噪声文本。

## 优点
- 准确处理了 schema 中关于坐标非负性的潜在冲突，遵循了 input_structure 定义。
- 样例解释详细，明确说明了重叠面积计算和边界情况。
- 主题包装（社团展位）与几何约束结合自然，易于理解。
- 注释部分补充了重叠定义的细节，减少了歧义。

## 与原题差异分析
- changed_axes_planned: C, O, V, T
- changed_axes_realized: C, O, V, T
- semantic_difference: 0.2
- solution_transfer_risk: 0.9
- surface_retheme_risk: 0.8
- verdict: reject_as_retheme
- rationale: 核心算法逻辑完全一致。原题要求判断每个矩形是否被后续矩形遮挡（输出 N 个布尔值），新题要求统计未被遮挡的矩形总数（输出 1 个计数值）。从‘逐个判断’到‘统计总数’仅是输出聚合方式的改变，不改变几何覆盖/相交检测的核心难点（如线段树维护覆盖、扫描线等）。解题者可直接复用原题的数据结构和状态转移逻辑，仅需在最后累加结果。Schema 中虽然标记了 objective 从 feasibility 变为 count，但这在算法复杂度与建模上无实质差异。背景故事从‘晒太阳’改为‘社团展位’属于典型表层换皮。

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
- [blocker] retheme_issue: solution transfer risk too high | 核心算法逻辑完全一致。原题要求判断每个矩形是否被后续矩形遮挡（输出 N 个布尔值），新题要求统计未被遮挡的矩形总数（输出 1 个计数值）。从‘逐个判断’到‘统计总数’仅是输出聚合方式的改变，不改变几何覆盖/相交检测的核心难点（如线段树维护覆盖、扫描线等）。解题者可直接复用原题的数据结构和状态转移逻辑，仅需在最后累加结果。Schema 中虽然标记了 objective 从 feasibility 变为 count，但这在算法复杂度与建模上无实质差异。背景故事从‘晒太阳’改为‘社团展位’属于典型表层换皮。
  修复建议: 增加输入/约束/目标的实质变化，降低原题解法的直接迁移性。

## 建议修改
- 增加输入/约束/目标的实质变化，降低原题解法的直接迁移性。
- 虽然当前题面已足够清晰，若需进一步提升严谨性，可在注释中明确矩形区域是开区间还是闭区间（题面已提及左闭右开或连续区域，保持即可）。
- 确认时间限制 1.0 秒对于 N=100,000 的矩形覆盖问题是否足够支持 O(N log N) 解法，确保数据强度与时限匹配。
- 优先改写核心任务定义，而不是继续替换故事背景。

## 快照
- original_problem: [COCI 2018/2019 #2] Sunčanje
- difference_plan_rationale: 该方案保持同族算法线索，但通过目标函数、结构选项、输入视角与不变量提示拉开差异。 objective=count，structural_options=allow_negative_coordinates, allow_multiple_sun_exposure_levels，input_options=non_negative_coordinates，invariant_options=overlap_conflict_resolution，预测距离=0.47，落地轴=C, O, V, T。
