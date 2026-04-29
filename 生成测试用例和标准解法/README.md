# 生成测试用例和标准解法

本目录当前只实现 LLM prompt 构建层，用于从上游 artifact 中抽取题面与 schema 信息，并生成各类 LLM 调用所需的 system/user prompt。

## 范围边界

- 已实现：artifact 字段抽取、prompt 模块、JSON 输出合同、单元测试。
- 未实现：LLM API 调用、prompt 返回 JSON 的解析、生成代码的执行、对拍验证、题包流水线、旧项目迁移。
- 不复用 `D:\AutoProblemGen\测试用例和标准解法共迭代` 的代码实现。

## Artifact 字段

题面字段只从 `generated_problem` 中读取以下字段：

- `title`
- `description`
- `input_format`
- `output_format`
- `constraints`
- `samples`
- `notes`

需要题目结构信息的 prompt 额外读取 `new_schema_snapshot` 的以下字段：

- `input_structure`
- `core_constraints`
- `objective`
- `invariant`

字段缺失时会抛出 `ValueError`。本模块只读取 `output_format`，不兼容 `ouput_format`。

## Prompt 模块

每个 prompt 模块统一暴露：

```python
def build_system_prompt() -> str:
    ...

def build_user_prompt(...) -> str:
    ...
```

模块分组如下：

- `prompts.tool_generation.prompt_random_test_input`
- `prompts.tool_generation.prompt_adversarial_test_input`
- `prompts.tool_generation.prompt_small_challenge_test_input`
- `prompts.tool_generation.prompt_checker`
- `prompts.standard_solution.prompt_standard_solution`
- `prompts.bruteforce_solution.prompt_bruteforce_solution`
- `prompts.wrong_solution.prompt_fixed_category_wrong_solution`
- `prompts.wrong_solution.prompt_schema_mistake_analysis`
- `prompts.wrong_solution.prompt_strategy_wrong_solution`

## JSON 输出合同

所有 prompt 都要求 LLM 最终只输出单个 JSON 对象，不允许 JSON 外解释或 Markdown 代码块。

- 随机/对抗测试输入：`constraint_analysis`、`generate_test_input_code`、`validate_test_input_code`
- 小规模挑战输入：`test_input`
- 标准解：`status`、`block_reason`、`solution_markdown`、`code`、`time_complexity`、`space_complexity`
- 暴力解：`status`、`block_reason`、`bruteforce_markdown`、`code`、`time_complexity`、`space_complexity`
- checker：不需要时返回 `needs_checker=false`、`reason`；需要时返回 `needs_checker=true`、`output_rule_analysis`、`checker_code`、`notes`
- schema 错误策略分析：`strategies` 列表，每项包含 `title`、`wrong_idea`、`plausible_reason`、`failure_reason`、`trigger_case`
- 固定错误解/按策略错误解：`code`

解法类代码统一要求实现：

```python
def solve(input_str: str) -> str:
    ...
```

## 测试

```powershell
python -m unittest discover -s tests
```

