# 生成测试用例和标准解法

本目录实现从上游 artifact 构建 LLM prompt，并通过 OpenAI 兼容 Chat Completions API 真实生成以下产物：

- 标准解
- 暴力解
- 随机测试输入生成器
- 对抗测试输入生成器
- 小规模挑战测试输入
- checker
- 固定类别错误解
- 基于 schema 错误策略分析的错误解

## 范围边界

- 已实现：artifact 字段抽取、prompt 模块、LLM API 调用、严格 JSON 解析、JSON 输出合同校验、单元测试。
- 未实现：生成代码的执行、对拍验证、题包流水线、CLI、旧项目迁移。
- 不复用 `D:\AutoProblemGen\测试用例和标准解法共迭代` 的代码实现。

## 环境配置

安装依赖：

```powershell
pip install -r requirements.txt
```

复制 `.env.example` 为 `.env`，并填写真实配置：

```dotenv
OPENAI_API_KEY=
OPENAI_BASE_URL=
OPENAI_MODEL=
OPENAI_TEMPERATURE=0.2
OPENAI_TIMEOUT_SECONDS=60
OPENAI_MAX_RETRIES=2
```

说明：

- `.env` 用于本地密钥，已被 `.gitignore` 忽略。
- `.env.example` 只保存空值或安全默认值，可提交。
- `OPENAI_API_KEY` 和 `OPENAI_MODEL` 必填，缺失时会 fail-fast。
- `OPENAI_BASE_URL` 可选；使用 OpenAI 兼容服务时填写对应 `/v1` 地址。
- `.env` 解析只支持空行、`#` 注释、`KEY=VALUE` 和简单单双引号，不支持变量插值或复杂 shell 语法。

## 库函数入口

```python
from generation_pipeline import generate_all_artifacts
from llm_config import LLMConfig

config = LLMConfig.from_dotenv()
result = generate_all_artifacts(artifact, config)
```

返回结构：

```python
{
    "standard_solution": {...},
    "bruteforce_solution": {...},
    "test_inputs": {
        "random": {...},
        "adversarial": {...},
        "small_challenge": {...},
    },
    "checker": {...},
    "wrong_solutions": {
        "fixed_categories": {...},
        "strategy_analysis": {...},
        "strategy_based": [...],
    },
    "metadata": {...},
}
```

调用默认启用 `response_format={"type": "json_object"}`。本模块只解析和校验 LLM 返回的 JSON，不执行返回代码，不生成标准输出，不落盘。

## Artifact 字段

题面字段只从 `generated_problem` 中读取以下字段：

- `title`
- `description`
- `input_format`
- `output_format`
- `constraints`
- `samples`
- `notes`

需要题目结构信息的 prompt 额外读取 `new_schema_snapshot` 的以下字段；当前标准解、暴力解、checker、schema 错误策略分析和按策略错误解会读取这些字段：

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

所有 prompt 都要求 LLM 最终只输出单个 JSON 对象，不允许 JSON 外解释或 Markdown 代码块。流水线会严格 `json.loads`，不会尝试修复脏文本。

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

checker 代码统一要求实现：

```python
def check_output(input_string, output_string) -> bool:
    ...
```

## 测试

```powershell
python -m unittest discover -s tests
```
