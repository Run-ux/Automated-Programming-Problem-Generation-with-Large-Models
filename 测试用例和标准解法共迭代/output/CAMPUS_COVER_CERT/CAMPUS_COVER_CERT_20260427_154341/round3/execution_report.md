# 题包生成验证报告

## 总览

- 状态：revise
- 失败原因：validation_failed
- 问题数量：12
- 错误解杀伤率：1.0

## 问题列表

- [blocker] standard_oracle_mismatch：标准解与 oracle 不一致
  详情：测试 problem_statement 上标准解输出与 oracle 输出不同。
  修复建议：回流 StandardSolutionGenerator 与 OracleGenerator，定位反例。
- [blocker] checker_rejects_standard_output：checker 拒绝标准解输出
  详情：测试 problem_statement 的标准输出未被 checker 接受。
  修复建议：回流 ToolGenerator 和 StandardSolutionGenerator，确认 checker 合法性谓词与标准解输出。
- [blocker] checker_rejects_standard_output：checker 拒绝标准解输出
  详情：测试 problem_statement 的标准输出未被 checker 接受。
  修复建议：回流 ToolGenerator 和 StandardSolutionGenerator，确认 checker 合法性谓词与标准解输出。
- [blocker] checker_rejects_standard_output：checker 拒绝标准解输出
  详情：测试 problem_statement 的标准输出未被 checker 接受。
  修复建议：回流 ToolGenerator 和 StandardSolutionGenerator，确认 checker 合法性谓词与标准解输出。
- [blocker] standard_oracle_mismatch：标准解与 oracle 不一致
  详情：测试 problem_statement 上标准解输出与 oracle 输出不同。
  修复建议：回流 StandardSolutionGenerator 与 OracleGenerator，定位反例。
- [blocker] checker_rejects_standard_output：checker 拒绝标准解输出
  详情：测试 problem_statement 的标准输出未被 checker 接受。
  修复建议：回流 ToolGenerator 和 StandardSolutionGenerator，确认 checker 合法性谓词与标准解输出。
- [blocker] checker_rejects_standard_output：checker 拒绝标准解输出
  详情：测试 custom 的标准输出未被 checker 接受。
  修复建议：回流 ToolGenerator 和 StandardSolutionGenerator，确认 checker 合法性谓词与标准解输出。
- [blocker] standard_oracle_mismatch：标准解与 oracle 不一致
  详情：测试 custom 上标准解输出与 oracle 输出不同。
  修复建议：回流 StandardSolutionGenerator 与 OracleGenerator，定位反例。
- [blocker] checker_rejects_standard_output：checker 拒绝标准解输出
  详情：测试 custom 的标准输出未被 checker 接受。
  修复建议：回流 ToolGenerator 和 StandardSolutionGenerator，确认 checker 合法性谓词与标准解输出。
- [blocker] checker_rejects_standard_output：checker 拒绝标准解输出
  详情：测试 random 的标准输出未被 checker 接受。
  修复建议：回流 ToolGenerator 和 StandardSolutionGenerator，确认 checker 合法性谓词与标准解输出。
- [blocker] standard_oracle_mismatch：标准解与 oracle 不一致
  详情：测试 custom 上标准解输出与 oracle 输出不同。
  修复建议：回流 StandardSolutionGenerator 与 OracleGenerator，定位反例。
- [high] validator_rejects_generated_case：validator 拒绝生成测试
  详情：测试 custom 未通过输入合法性检查。
  修复建议：回流 ToolGenerator 或测试生成器，修正输入约束或测试生成逻辑。

## 回流摘要

- issues_by_category: {'standard_oracle_mismatch': ['测试 problem_statement 上标准解输出与 oracle 输出不同。', '测试 problem_statement 上标准解输出与 oracle 输出不同。', '测试 custom 上标准解输出与 oracle 输出不同。', '测试 custom 上标准解输出与 oracle 输出不同。'], 'checker_rejects_standard_output': ['测试 problem_statement 的标准输出未被 checker 接受。', '测试 problem_statement 的标准输出未被 checker 接受。', '测试 problem_statement 的标准输出未被 checker 接受。', '测试 problem_statement 的标准输出未被 checker 接受。', '测试 custom 的标准输出未被 checker 接受。', '测试 custom 的标准输出未被 checker 接受。', '测试 random 的标准输出未被 checker 接受。'], 'validator_rejects_generated_case': ['测试 custom 未通过输入合法性检查。']}
- failed_hard_checks: ['standard_oracle_mismatch', 'checker_rejects_standard_output', 'checker_rejects_standard_output', 'checker_rejects_standard_output', 'standard_oracle_mismatch', 'checker_rejects_standard_output', 'checker_rejects_standard_output', 'standard_oracle_mismatch', 'checker_rejects_standard_output', 'checker_rejects_standard_output', 'standard_oracle_mismatch']
- tool_feedback: ['测试 custom 未通过输入合法性检查。', '测试 problem_statement 的标准输出未被 checker 接受。', '测试 problem_statement 的标准输出未被 checker 接受。', '测试 problem_statement 的标准输出未被 checker 接受。', '测试 problem_statement 的标准输出未被 checker 接受。', '测试 custom 的标准输出未被 checker 接受。', '测试 custom 的标准输出未被 checker 接受。', '测试 random 的标准输出未被 checker 接受。']
- solution_feedback: ['测试 problem_statement 上标准解输出与 oracle 输出不同。', '测试 problem_statement 上标准解输出与 oracle 输出不同。', '测试 custom 上标准解输出与 oracle 输出不同。', '测试 custom 上标准解输出与 oracle 输出不同。']
- oracle_feedback: ['测试 problem_statement 上标准解输出与 oracle 输出不同。', '测试 problem_statement 上标准解输出与 oracle 输出不同。', '测试 custom 上标准解输出与 oracle 输出不同。', '测试 custom 上标准解输出与 oracle 输出不同。']
- test_feedback: []
- surviving_wrong_solutions: []
