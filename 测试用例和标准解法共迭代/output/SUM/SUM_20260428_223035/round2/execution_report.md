# 题包生成验证报告

## 总览

- 状态：revise
- 失败原因：validation_failed
- 问题数量：2
- 基础自洽：未通过
- 语义门禁：passed
- 错误解杀伤率：不可用

## 问题列表

- [blocker] candidate_not_better_than_current：候选包未优于当前题包
  详情：组件 test_generator 的候选通过轻量门禁，但包级验证未晋级。 拒绝原因：candidate_not_better_than_current。
  修复建议：保留上一轮组件；下一轮候选必须同时减少 active 问题且不破坏 known-good、语义门禁和杀伤率。
- [high] kill_rate_skipped_due_to_invalid_baseline：基础自洽失败，跳过错误解杀伤率统计
  详情：validator、标准解、oracle 或 checker 的基础自洽检查未通过，本轮杀伤率不可作为可信指标。
  修复建议：优先修复基础自洽问题，再重新执行错误解筛选。

## 组件晋级门禁

- test_generator: 通过

## 候选包级门禁

- test_generator: 未通过，原因：candidate_not_better_than_current

## Known-good 用例

- 配置数量：2
- 执行数量：2
- 失败数量：0

## 回归反例

- 配置数量：0
- 执行数量：0

## 回流摘要

- summary: [{'category': 'candidate_not_better_than_current', 'count': 1, 'severity': 'blocker', 'representative_sources': [], 'titles': ['候选包未优于当前题包']}, {'category': 'kill_rate_skipped_due_to_invalid_baseline', 'count': 1, 'severity': 'high', 'representative_sources': [], 'titles': ['基础自洽失败，跳过错误解杀伤率统计']}]
- diagnostics_by_category: {'candidate_not_better_than_current': [{'category': 'candidate_not_better_than_current', 'severity': 'blocker', 'title': '候选包未优于当前题包', 'detail': '组件 test_generator 的候选通过轻量门禁，但包级验证未晋级。 拒绝原因：candidate_not_better_than_current。', 'fix_hint': '保留上一轮组件；下一轮候选必须同时减少 active 问题且不破坏 known-good、语义门禁和杀伤率。', 'target_roles': ['TestGenerator'], 'evidence': {'component': 'test_generator', 'candidate_gate_result': {'component': 'test_generator', 'passed': False, 'status': 'rejected', 'rejection_reasons': ['candidate_not_better_than_current'], 'regression_detected': False, 'fixed_issue_fingerprints': [], 'introduced_blocker_high_categories': [], 'known_good_failed_sources': [], 'previous_overall': {'status': 'revise', 'issue_count': 1, 'stop_reason': 'validation_failed', 'semantic_gate_status': 'passed'}, 'candidate_overall': {'status': 'revise', 'issue_count': 1, 'stop_reason': 'validation_failed', 'semantic_gate_status': 'passed'}, 'previous_wrong_solution_stats': {'candidate_count': 2, 'valuable_count': 1, 'independent_count': 1, 'high_value_survivor_count': 1, 'unexpected_correct_count': 0, 'rejected_count': 0, 'kill_rate': 0.5, 'kill_rate_threshold': 0.5, 'passed_threshold': True, 'valid': True, 'skip_reason': ''}, 'candidate_wrong_solution_stats': {'candidate_count': 2, 'valuable_count': 1, 'independent_count': 1, 'high_value_survivor_count': 1, 'unexpected_correct_count': 0, 'rejected_count': 0, 'kill_rate': 0.5, 'kill_rate_threshold': 0.5, 'passed_threshold': True, 'valid': True, 'skip_reason': ''}, 'candidate_known_good_results': {'configured_count': 2, 'executed_count': 2, 'passed_count': 2, 'failed_count': 0, 'sources': ['known_good:zero', 'known_good:basic'], 'failed_sources': [], 'passed_cases': [{'input': '0 0', 'source': 'known_good:known_good:zero', 'purpose': '零值边界', 'expect_oracle': True, 'is_sample': False, 'is_large': False, 'metadata': {'known_good': True, 'known_good_source': 'known_good', 'case_group': 'known_good'}}, {'input': '1 2', 'source': 'known_good:known_good:basic', 'purpose': '基础求和', 'expect_oracle': True, 'is_sample': False, 'is_large': False, 'metadata': {'known_good': True, 'known_good_source': 'known_good', 'case_group': 'known_good'}}]}, 'candidate_semantic_gate_issue_count': 0, 'previous_semantic_gate_issue_count': 0, 'active_case_count': 0}}, 'issue_fingerprint': '8ae4c0b478bd8d20'}], 'kill_rate_skipped_due_to_invalid_baseline': [{'category': 'kill_rate_skipped_due_to_invalid_baseline', 'severity': 'high', 'title': '基础自洽失败，跳过错误解杀伤率统计', 'detail': 'validator、标准解、oracle 或 checker 的基础自洽检查未通过，本轮杀伤率不可作为可信指标。', 'fix_hint': '优先修复基础自洽问题，再重新执行错误解筛选。', 'target_roles': ['TestGenerator', 'StandardSolutionGenerator', 'OracleGenerator'], 'evidence': {}, 'issue_fingerprint': 'a8ae410763d11e7b'}]}
- role_diagnostics: {'TestGenerator': [{'category': 'candidate_not_better_than_current', 'severity': 'blocker', 'title': '候选包未优于当前题包', 'detail': '组件 test_generator 的候选通过轻量门禁，但包级验证未晋级。 拒绝原因：candidate_not_better_than_current。', 'fix_hint': '保留上一轮组件；下一轮候选必须同时减少 active 问题且不破坏 known-good、语义门禁和杀伤率。', 'target_roles': ['TestGenerator'], 'evidence': {'component': 'test_generator', 'candidate_gate_result': {'component': 'test_generator', 'passed': False, 'status': 'rejected', 'rejection_reasons': ['candidate_not_better_than_current'], 'regression_detected': False, 'fixed_issue_fingerprints': [], 'introduced_blocker_high_categories': [], 'known_good_failed_sources': [], 'previous_overall': {'status': 'revise', 'issue_count': 1, 'stop_reason': 'validation_failed', 'semantic_gate_status': 'passed'}, 'candidate_overall': {'status': 'revise', 'issue_count': 1, 'stop_reason': 'validation_failed', 'semantic_gate_status': 'passed'}, 'previous_wrong_solution_stats': {'candidate_count': 2, 'valuable_count': 1, 'independent_count': 1, 'high_value_survivor_count': 1, 'unexpected_correct_count': 0, 'rejected_count': 0, 'kill_rate': 0.5, 'kill_rate_threshold': 0.5, 'passed_threshold': True, 'valid': True, 'skip_reason': ''}, 'candidate_wrong_solution_stats': {'candidate_count': 2, 'valuable_count': 1, 'independent_count': 1, 'high_value_survivor_count': 1, 'unexpected_correct_count': 0, 'rejected_count': 0, 'kill_rate': 0.5, 'kill_rate_threshold': 0.5, 'passed_threshold': True, 'valid': True, 'skip_reason': ''}, 'candidate_known_good_results': {'configured_count': 2, 'executed_count': 2, 'passed_count': 2, 'failed_count': 0, 'sources': ['known_good:zero', 'known_good:basic'], 'failed_sources': [], 'passed_cases': [{'input': '0 0', 'source': 'known_good:known_good:zero', 'purpose': '零值边界', 'expect_oracle': True, 'is_sample': False, 'is_large': False, 'metadata': {'known_good': True, 'known_good_source': 'known_good', 'case_group': 'known_good'}}, {'input': '1 2', 'source': 'known_good:known_good:basic', 'purpose': '基础求和', 'expect_oracle': True, 'is_sample': False, 'is_large': False, 'metadata': {'known_good': True, 'known_good_source': 'known_good', 'case_group': 'known_good'}}]}, 'candidate_semantic_gate_issue_count': 0, 'previous_semantic_gate_issue_count': 0, 'active_case_count': 0}}, 'issue_fingerprint': '8ae4c0b478bd8d20'}]}
- failed_hard_checks: ['candidate_not_better_than_current']
- surviving_wrong_solution_details: []
