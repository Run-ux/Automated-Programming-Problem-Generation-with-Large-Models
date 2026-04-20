# 题目质量与反换皮评估报告

## 总览
- status: reject_as_retheme
- quality_score: 20.0
- divergence_score: 0.0
- schema_distance: 0.0
- generated_status: difference_insufficient

## 质量维度
- variant_fidelity: 1.0 / 5 | 生成题面的所有核心字段（description、input_format、output_format、constraints）均为空字符串或空数组，new_schema 中明确规划的向量反向匹配约束、计数目标、等价类不变量及校园运营主题完全未落地到题面文本中。
- spec_completeness: 1.0 / 5 | 题面缺失任务说明、输入输出格式、数据范围及样例等全部关键信息，读者无法获取任何解题所需的规则或边界条件，完全不具备独立做题的基础。
- cross_section_consistency: 1.0 / 5 | 由于题面各部分均为空，不存在任何有效信息可供交叉验证，字段数量、目标定义与格式声明全面缺失，属于严重的结构性断裂。
- sample_quality: 1.0 / 5 | 样例数组为空，数量为0，无任何输入输出对照或解释说明，无法覆盖关键结构或辅助理解题意。
- oj_readability: 1.0 / 5 | 题面标题、描述、格式说明均为空，状态标记为 difference_insufficient 并附带生成失败反馈，存在明显的管线中断污染，完全不符合 OJ 题面表达规范。

## 优点
- new_schema 规划清晰，明确定义了向量反向匹配的几何约束、归一化等价类不变量以及顺序累加的计数策略，为后续题面生成提供了良好的算法骨架。
- 主题映射方向（校园运营/排队/视线交互）具有较好的现实贴合度，若成功落地可有效提升题面可读性与趣味性。

## 与原题差异分析
- changed_axes_planned: 无
- changed_axes_realized: 无
- semantic_difference: 0.0
- solution_transfer_risk: 1.0
- surface_retheme_risk: 1.0
- verdict: reject_as_retheme
- rationale: 新题生成完全失败，generated_problem 核心字段均为空且状态标记为 difference_insufficient。new_schema 与 original_schema 在输入结构、核心约束、目标函数及不变量上完全一致，schema_distance 为 0.0，且 changed_axes_realized 为空，表明未进行任何实质性的规则或维度调整。hard_checks 明确拦截了 schema_distance_threshold 和 changed_axes_threshold。由于题目未实际产出，不存在任何语义差异，原题的标准解法（方向向量归一化+频次表统计相反向量对）可无条件直接迁移。表层换皮意图明确但执行彻底失败，属于典型的无效换皮/生成阻断案例。

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
- [PASS] objective_alignment (blocker/quality_issue): 目标函数已经在题面中落地。
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
- [major] quality_issue: 生成管线完全失败，题面内容为空 | generated_problem 的 title、description、input_format、output_format、constraints、samples 等核心字段全部为空字符串或空数组，且 status 为 difference_insufficient，表明规则未通过资格校验，未产出任何有效文本。
  修复建议: 检查生成管线的规则过滤与文本渲染逻辑，确保在规则校验通过后能正确将 new_schema 映射为完整题面文本。
- [major] quality_issue: 核心差异轴未落地，Schema 距离为 0 | hard_checks 显示 schema_distance=0.00 且 changed_axes_realized 为空，说明规划中的向量归一化、配对计数逻辑及校园主题映射均未在题面中体现，属于同母题未换皮或生成中断。
  修复建议: 重新配置差异规则或调整种子题，确保至少有一个核心差异轴（如约束转化、主题映射、输入结构）被成功实例化到题面中。
- [major] quality_issue: 样例完全缺失 | samples 字段为空数组，不满足 OJ 题面至少提供 2 组样例的基本要求，无法验证格式或逻辑。
  修复建议: 根据 new_schema 的输入结构（多组测试用例、数组长度 1~1e5）和计数目标，构造至少 2 组覆盖基础匹配与边界情况的样例，并补充对应输出。
- [blocker] retheme_issue: solution transfer risk too high | 新题生成完全失败，generated_problem 核心字段均为空且状态标记为 difference_insufficient。new_schema 与 original_schema 在输入结构、核心约束、目标函数及不变量上完全一致，schema_distance 为 0.0，且 changed_axes_realized 为空，表明未进行任何实质性的规则或维度调整。hard_checks 明确拦截了 schema_distance_threshold 和 changed_axes_threshold。由于题目未实际产出，不存在任何语义差异，原题的标准解法（方向向量归一化+频次表统计相反向量对）可无条件直接迁移。表层换皮意图明确但执行彻底失败，属于典型的无效换皮/生成阻断案例。
  修复建议: 增加输入、约束与目标的实质变化，降低原题解法的直接迁移性。

## 建议修改
- 先修复生成阶段的 schema 或 difference 问题，再重新生成题面。
- 提高输入、约束与目标的结构差异，避免停留在同母题换皮。
- 至少让 I、C、O、V 中两个核心轴发生实质变化。
- 至少补齐两组可验证样例。
- 检查生成管线的规则过滤与文本渲染逻辑，确保在规则校验通过后能正确将 new_schema 映射为完整题面文本。
- 重新配置差异规则或调整种子题，确保至少有一个核心差异轴（如约束转化、主题映射、输入结构）被成功实例化到题面中。
- 根据 new_schema 的输入结构（多组测试用例、数组长度 1~1e5）和计数目标，构造至少 2 组覆盖基础匹配与边界情况的样例，并补充对应输出。
- 增加输入、约束与目标的实质变化，降低原题解法的直接迁移性。
- 修复生成管线中断问题，确保规则校验通过后能输出完整的 Markdown 题面结构。
- 严格对照 new_schema 填充 description（融入校园排队/视线交互场景）、input_format（明确多组测试用例与数组范围）、output_format（明确输出配对总数）。
- 补充至少 2 组样例，包含无匹配、单组匹配及多组匹配情况，并附带简要解释说明向量归一化与反向匹配的计算过程。
- 清理 status 和 feedback 等调试字段，确保最终交付物仅包含标准 OJ 题面内容。
- 优先改写核心任务定义，而不是继续替换故事背景。

## 回流摘要
- round_index: 1
- overall_status: reject_as_retheme
- generated_status: difference_insufficient
- quality_score: 20.0
- divergence_score: 0.0
- strengths_to_keep: new_schema 规划清晰，明确定义了向量反向匹配的几何约束、归一化等价类不变量以及顺序累加的计数策略，为后续题面生成提供了良好的算法骨架。；主题映射方向（校园运营/排队/视线交互）具有较好的现实贴合度，若成功落地可有效提升题面可读性与趣味性。

## 快照
- original_problem: 1468_F. Full Turn
- difference_plan_rationale: 没有规则通过资格校验。
