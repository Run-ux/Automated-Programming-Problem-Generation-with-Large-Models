# 题包生成验证报告

## 总览

- 状态：revise
- 失败原因：validation_failed
- 问题数量：1
- 基础自洽：通过
- 语义门禁：passed
- 错误解杀伤率：0.5

## 问题列表

- [high] wrong_solution_survived：错误解筛选未满足严格通过条件
  详情：当前杀伤率 0.5，阈值 0.5。 高价值幸存错误解 1 个。 unexpected_correct 候选 0 个。 是否仅剩 unexpected_correct 候选：否。 当前仍有应被测试击穿但未被杀掉的高价值幸存错误解。
  修复建议：回流测试生成器，针对幸存错误解补充反例。

## Known-good 用例

- 配置数量：0
- 执行数量：0
- 失败数量：0

## 回归反例

- 配置数量：0
- 执行数量：0

## 回流摘要

- summary: [{'category': 'wrong_solution_survived', 'count': 1, 'severity': 'high', 'representative_sources': [], 'titles': ['错误解筛选未满足严格通过条件']}]
- diagnostics_by_category: {'wrong_solution_survived': [{'category': 'wrong_solution_survived', 'severity': 'high', 'title': '错误解筛选未满足严格通过条件', 'detail': '当前杀伤率 0.5，阈值 0.5。 高价值幸存错误解 1 个。 unexpected_correct 候选 0 个。 是否仅剩 unexpected_correct 候选：否。 当前仍有应被测试击穿但未被杀掉的高价值幸存错误解。', 'fix_hint': '回流测试生成器，针对幸存错误解补充反例。', 'target_roles': ['TestGenerator', 'WeakPlayerGenerator', 'SchemaMistakeAnalyzer', 'SchemaAwareWrongSolutionGenerator'], 'evidence': {}, 'issue_fingerprint': '18f57e7072500371'}]}
- role_diagnostics: {'TestGenerator': [{'category': 'wrong_solution_survived', 'severity': 'high', 'title': '错误解筛选未满足严格通过条件', 'detail': '当前杀伤率 0.5，阈值 0.5。 高价值幸存错误解 1 个。 unexpected_correct 候选 0 个。 是否仅剩 unexpected_correct 候选：否。 当前仍有应被测试击穿但未被杀掉的高价值幸存错误解。', 'fix_hint': '回流测试生成器，针对幸存错误解补充反例。', 'target_roles': ['TestGenerator', 'WeakPlayerGenerator', 'SchemaMistakeAnalyzer', 'SchemaAwareWrongSolutionGenerator'], 'evidence': {}, 'issue_fingerprint': '18f57e7072500371'}], 'WeakPlayerGenerator': [{'category': 'wrong_solution_survived', 'severity': 'high', 'title': '错误解筛选未满足严格通过条件', 'detail': '当前杀伤率 0.5，阈值 0.5。 高价值幸存错误解 1 个。 unexpected_correct 候选 0 个。 是否仅剩 unexpected_correct 候选：否。 当前仍有应被测试击穿但未被杀掉的高价值幸存错误解。', 'fix_hint': '回流测试生成器，针对幸存错误解补充反例。', 'target_roles': ['TestGenerator', 'WeakPlayerGenerator', 'SchemaMistakeAnalyzer', 'SchemaAwareWrongSolutionGenerator'], 'evidence': {}, 'issue_fingerprint': '18f57e7072500371'}], 'SchemaMistakeAnalyzer': [{'category': 'wrong_solution_survived', 'severity': 'high', 'title': '错误解筛选未满足严格通过条件', 'detail': '当前杀伤率 0.5，阈值 0.5。 高价值幸存错误解 1 个。 unexpected_correct 候选 0 个。 是否仅剩 unexpected_correct 候选：否。 当前仍有应被测试击穿但未被杀掉的高价值幸存错误解。', 'fix_hint': '回流测试生成器，针对幸存错误解补充反例。', 'target_roles': ['TestGenerator', 'WeakPlayerGenerator', 'SchemaMistakeAnalyzer', 'SchemaAwareWrongSolutionGenerator'], 'evidence': {}, 'issue_fingerprint': '18f57e7072500371'}], 'SchemaAwareWrongSolutionGenerator': [{'category': 'wrong_solution_survived', 'severity': 'high', 'title': '错误解筛选未满足严格通过条件', 'detail': '当前杀伤率 0.5，阈值 0.5。 高价值幸存错误解 1 个。 unexpected_correct 候选 0 个。 是否仅剩 unexpected_correct 候选：否。 当前仍有应被测试击穿但未被杀掉的高价值幸存错误解。', 'fix_hint': '回流测试生成器，针对幸存错误解补充反例。', 'target_roles': ['TestGenerator', 'WeakPlayerGenerator', 'SchemaMistakeAnalyzer', 'SchemaAwareWrongSolutionGenerator'], 'evidence': {}, 'issue_fingerprint': '18f57e7072500371'}]}
- failed_hard_checks: []
- surviving_wrong_solution_details: [{'solution_id': 'survivor_logic_gap', 'bug_type': 'logic_gap', 'expected_failure': '边界输入应失败。', 'reason': '当前测试未能杀掉该候选解。', 'passed_tests': [], 'killed_tests': [], 'metadata': {}}]
