# 题目质量与反换皮评估报告

## 总览
- status: reject_as_retheme
- quality_score: 98.0
- divergence_score: 58.3
- schema_distance: 0.4803
- generated_status: ok

## 质量维度
- variant_fidelity: 5.0 / 5 | 重点看实例化 schema 是否真实落地到题面字段。
- spec_completeness: 5.0 / 5 | 检查关键段落、限制条件和任务说明是否齐全。
- cross_section_consistency: 5.0 / 5 | 检查 description、input/output、constraints、samples 是否互相一致。
- sample_quality: 4.8 / 5 | 检查样例数量、解释和与输入结构的匹配度。
- oj_readability: 4.3 / 5 | 检查题面是否具备正常 OJ 可读性且无明显污染。

## 优点
- variant_fidelity 表现稳定
- spec_completeness 表现稳定
- cross_section_consistency 表现稳定
- sample_quality 表现稳定
- oj_readability 表现稳定

## 与原题差异分析
- changed_axes_planned: I, C, O, V, T
- changed_axes_realized: I, C, O, V, T
- semantic_difference: 0.45
- solution_transfer_risk: 0.65
- surface_retheme_risk: 0.75
- verdict: reject_as_retheme
- rationale: 核心数学模型完全一致：两题均基于数组差分前缀和的不变量（sum(a[l..r]) == sum(b[l..r])）来定义合法操作区间。原题的核心难点在于发现这一前缀和性质并验证覆盖性，新题完全复用了这一核心洞察。虽然目标函数从可行性（YES/NO）变为最小化操作数，但这只是在原核心逻辑之上叠加了一个标准的区间覆盖贪心/DP 问题，并未改变问题的本质约束结构。熟悉原题的选手可直接迁移前缀和预处理及合法区间识别逻辑，仅需修改最后一步的决策算法，解法迁移风险较高。表层叙事虽从机器人变为校园物资，但输入结构、约束形式及变量映射高度重合。

## 硬检查
- [PASS] source_problem_resolved (blocker/invalid): 已成功加载原题文本。
- [PASS] generated_status_ok (blocker/invalid): 生成状态正常。
- [PASS] difference_plan_present (major/retheme_issue): artifact 已持久化 difference_plan。
- [PASS] schema_distance_threshold (blocker/retheme_issue): schema_distance=0.48，达到中等差异阈值。
- [PASS] changed_axes_threshold (blocker/retheme_issue): 已落地核心差异轴：I, C, O, V, T。
- [PASS] source_leakage (blocker/retheme_issue): 未发现原题标题/题源泄露。
- [PASS] title_overlap (major/retheme_issue): 标题重合度=0.00。
- [PASS] sample_count (major/quality_issue): 样例数量=2。
- [PASS] sample_line_alignment (major/quality_issue): 输入结构不是固定小数组，跳过样例行数检查。
- [PASS] input_count_alignment (blocker/quality_issue): 输入结构不是固定小数组，跳过输入项数量声明检查。
- [PASS] objective_alignment (blocker/quality_issue): 目标函数已经在题面中落地。
- [PASS] structural_option_alignment (blocker/quality_issue): 结构选项已在题面中落地。

## 问题清单
- [blocker] retheme_issue: solution transfer risk too high | 核心数学模型完全一致：两题均基于数组差分前缀和的不变量（sum(a[l..r]) == sum(b[l..r])）来定义合法操作区间。原题的核心难点在于发现这一前缀和性质并验证覆盖性，新题完全复用了这一核心洞察。虽然目标函数从可行性（YES/NO）变为最小化操作数，但这只是在原核心逻辑之上叠加了一个标准的区间覆盖贪心/DP 问题，并未改变问题的本质约束结构。熟悉原题的选手可直接迁移前缀和预处理及合法区间识别逻辑，仅需修改最后一步的决策算法，解法迁移风险较高。表层叙事虽从机器人变为校园物资，但输入结构、约束形式及变量映射高度重合。
  修复建议: 增加输入/约束/目标的实质变化，降低原题解法的直接迁移性。

## 建议修改
- 增加输入/约束/目标的实质变化，降低原题解法的直接迁移性。
- 优先改写核心任务定义，而不是继续替换故事背景。

## 快照
- original_problem: C. Sanae and Giant Robot
- difference_plan_rationale: 该方案保持同族算法线索，但通过目标函数、结构选项、输入视角与不变量提示拉开差异。 objective=minimize_operations，structural_options=无，input_options=zero_enabled_values, overlap_enabled_segments，invariant_options=counting_decomposition, frequency_aggregation，预测距离=0.48，落地轴=I, C, O, V, T。
