# 题目质量与反换皮评估报告

## 总览
- status: reject_as_retheme
- quality_score: 20.0
- divergence_score: 0.0
- schema_distance: 0.0
- generated_status: difference_insufficient

## 质量维度
- variant_fidelity: 1.0 / 5 | 生成题面所有核心字段均为空，new_schema 中定义的输入结构（三元组）、交互限制（query_count ≤ 5N）、最短路径构造目标及校园主题均未在 description、input_format、output_format 或 constraints 中落地。
- spec_completeness: 1.0 / 5 | 题面完全缺失任务说明、输入输出格式、约束条件等关键信息，读者无法获取任何解题所需规则或边界条件，属于严重缺失。
- cross_section_consistency: 1.0 / 5 | 由于 description、input_format、output_format、constraints、samples 均为空，不存在有效内容可供交叉验证，整体规格完全失效，无法构成一致的题面。
- sample_quality: 1.0 / 5 | 样例数组为空，数量为 0，未提供任何输入输出示例及解释，完全无法辅助理解任务或验证格式。
- oj_readability: 1.0 / 5 | 题面内容为空字符串，无任何可读文本、结构或排版，不符合 OJ 题面基本规范，参赛者无法阅读或理解。

## 与原题差异分析
- changed_axes_planned: 无
- changed_axes_realized: 无
- semantic_difference: 0.0
- solution_transfer_risk: 1.0
- surface_retheme_risk: 0.9
- verdict: reject_as_retheme
- rationale: new_schema 与 original_schema 在输入结构、核心约束、目标函数和不变量上完全一致，schema_distance 为 0.0，且 changed_axes_realized 为空数组，表明未进行任何实质性的规则或结构变更。generated_problem 状态为 difference_insufficient，所有题面字段均为空，生成流程因“没有规则通过资格校验”而失败，未能将任何表层主题映射落地为实际题目。因此，新题在任务语义上无任何差异，原题的交互查询策略、距离可加性筛选逻辑及 5N 限制可直接原样迁移，属于典型的换皮规划失败产物。

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
- [major] quality_issue: 生成流程失败导致题面完全为空 | generated_problem 的 status 为 difference_insufficient，error_reason 明确指出“没有规则通过资格校验”，导致所有题面字段均为空字符串或空数组。
  修复建议: 检查规则校验逻辑或更换种子题，确保生成流程能产出有效文本，并正确填充 description、input_format 等字段。
- [major] quality_issue: Schema 距离为 0 且未落地任何差异轴 | schema_distance=0.00，changed_axes_realized 为空，说明生成器未对原题进行任何有效变换或重写，直接输出了空结果，未达到最小差异阈值。
  修复建议: 调整 difference_plan 或 applied_rule，确保至少落地一个核心差异轴（如交互限制、路径约束或主题映射），并达到 schema_distance ≥ 0.35 的要求。
- [major] quality_issue: 样例完全缺失 | samples 字段为空数组，hard_checks 明确提示样例数量少于 2 组，无法覆盖 new_schema 中定义的输入范围与构造目标。
  修复建议: 根据 new_schema 的输入结构（长度3的元组，值域1-300）和最短路径目标，补充至少 2 组符合约束的样例输入输出及必要解释。
- [blocker] retheme_issue: solution transfer risk too high | new_schema 与 original_schema 在输入结构、核心约束、目标函数和不变量上完全一致，schema_distance 为 0.0，且 changed_axes_realized 为空数组，表明未进行任何实质性的规则或结构变更。generated_problem 状态为 difference_insufficient，所有题面字段均为空，生成流程因“没有规则通过资格校验”而失败，未能将任何表层主题映射落地为实际题目。因此，新题在任务语义上无任何差异，原题的交互查询策略、距离可加性筛选逻辑及 5N 限制可直接原样迁移，属于典型的换皮规划失败产物。
  修复建议: 增加输入、约束与目标的实质变化，降低原题解法的直接迁移性。

## 建议修改
- 先修复生成阶段的 schema 或 difference 问题，再重新生成题面。
- 提高输入、约束与目标的结构差异，避免停留在同母题换皮。
- 至少让 I、C、O、V 中两个核心轴发生实质变化。
- 至少补齐两组可验证样例。
- 检查规则校验逻辑或更换种子题，确保生成流程能产出有效文本，并正确填充 description、input_format 等字段。
- 调整 difference_plan 或 applied_rule，确保至少落地一个核心差异轴（如交互限制、路径约束或主题映射），并达到 schema_distance ≥ 0.35 的要求。
- 根据 new_schema 的输入结构（长度3的元组，值域1-300）和最短路径目标，补充至少 2 组符合约束的样例输入输出及必要解释。
- 增加输入、约束与目标的实质变化，降低原题解法的直接迁移性。
- 修复生成管线中的规则校验失败问题，确保 new_schema 中的交互限制（query_count ≤ 5N）、最短路径目标和校园主题能正确映射到 description 和 constraints 中。
- 按照 OJ 标准格式补全 input_format、output_format 和 constraints 字段，明确 N 的范围、查询接口定义、输出序列格式及边界条件。
- 构造并填充至少两组样例，覆盖正常最短路径查询与边界情况，并附带样例解释以验证格式与逻辑。
- 优先改写核心任务定义，而不是继续替换故事背景。

## 回流摘要
- round_index: 1
- overall_status: reject_as_retheme
- generated_status: difference_insufficient
- quality_score: 20.0
- divergence_score: 0.0

## 快照
- original_problem: p02064 Restore Shortest Path
- difference_plan_rationale: 没有规则通过资格校验。
