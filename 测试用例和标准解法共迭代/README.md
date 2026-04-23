# 题包生成验证

该模块实现“测试用例与标准解法共迭代”的后续流程。它接收 `生成题面` 的 artifact 与 Markdown 题面，生成可执行规格、标准解法、oracle、validator、checker、测试生成器和错误解池，并通过真实执行报告判断题包是否可交付。

## 运行

```bash
python main.py ^
  --artifact D:\AutoProblemGen\生成题面\artifacts\...\round1.json ^
  --markdown D:\AutoProblemGen\生成题面\output\...\round1.md ^
  --rounds 3
```

默认输出到：

```text
题包生成验证/output/<problem_id>/<run_id>/
  round1/
  round2/
  final/
  iteration_summary.json
```

## 产物合同

- `execution_spec.json`：输入约束、输出合同、判题方式、oracle 小规模范围和测试桶。
- `standard_solution.py`：标准解法，必须实现 `solve(input_str: str) -> str`。
- `oracle_solution.py`：小规模暴力 oracle，必须实现 `solve(input_str: str) -> str`。
- `validator.py`：必须实现 `validate(input_str: str) -> bool`。
- `checker.py`：必须实现 `check(input_str: str, output_str: str, expected_str: str | None) -> bool`。
- `test_generator.py`：必须实现 `generate_tests() -> list[dict]`。
- `wrong_solutions/`：候选错误解池，每份错误解实现 `solve(input_str: str) -> str`。
- `execution_report.json`：执行矩阵、失败分类、错误解杀伤率和回流摘要。

## 设计边界

v1 只支持 Python 代码执行，不自动修改题面生成模块。若发现题面、样例或输出合同存在歧义，报告会标记为 `statement_revision_required` 或相关失败类型，后续由上游题面生成流程处理。

