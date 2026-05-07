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

- 已实现：artifact 字段抽取、prompt 模块、LLM API 调用、严格 JSON 解析、JSON 输出合同校验、生成后本地验证闭环、错误解池增强验证、单元测试。
- 未实现：题包流水线、CLI、旧项目迁移。
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
OPENAI_TIMEOUT_SECONDS=1200
OPENAI_MAX_RETRIES=3
EXECUTION_TEST_INPUT_TIMEOUT_SECONDS=5
EXECUTION_TEST_INPUT_MEMORY_LIMIT_MB=512
EXECUTION_BRUTEFORCE_TIMEOUT_SECONDS=5
EXECUTION_BRUTEFORCE_MEMORY_LIMIT_MB=512
EXECUTION_CHECKER_TIMEOUT_SECONDS=5
EXECUTION_CHECKER_MEMORY_LIMIT_MB=512
```

说明：

- `.env` 用于本地密钥，已被 `.gitignore` 忽略。
- `.env.example` 只保存空值或安全默认值，可提交。
- `OPENAI_API_KEY` 和 `OPENAI_MODEL` 必填，缺失时会 fail-fast。
- `OPENAI_BASE_URL` 可选；使用 OpenAI 兼容服务时填写对应 `/v1` 地址。
- `EXECUTION_*` 只控制本地子进程执行生成器、暴力解法和 checker 的时间/空间限制，不影响 LLM 调用。
- `.env` 解析只支持空行、`#` 注释、`KEY=VALUE` 和简单单双引号，不支持变量插值或复杂 shell 语法。

## 库函数入口

```python
from generation_pipeline import generate_all_artifacts
from llm_config import LLMConfig

config = LLMConfig.from_dotenv()
result = generate_all_artifacts(artifact, config)
```

只生成产物时使用 `generate_all_artifacts`。需要执行需求 1-5 的验证闭环时使用：

```python
from generation_pipeline import generate_verified_artifacts
from llm_config import LLMConfig

config = LLMConfig.from_dotenv()
result = generate_verified_artifacts(artifact, config)
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

`generate_verified_artifacts` 在上述结构基础上额外返回：

```python
{
    "verified_test_inputs": {
        "status": "ok",
        "cases": [...],
        "count": 30,  # 基础输入数量；错误解池阶段可能追加 targeted 输入
        "source_counts": {
            "random": 10,
            "adversarial": 10,
            "small_challenge": 10,
        },
    },
    "bruteforce_verification": {
        "status": "ok",
        "final_code": "...",
        "solved_cases": [...],
        "large_scale_inputs": [...],
        "repair_history": [...],
    },
    "checker_verification": {...},
    "wrong_solution_pool_verification": {...},
    "execution_metadata": {...},
}
```

验证入口会把修复后的暴力解法写回 `bruteforce_solution.code`，并保留 `bruteforce_solution.initial_code`；需要 checker 且完成验证时，也会把修复后的 checker 写回 `checker.checker_code`，并保留 `checker.initial_checker_code`。

调用默认启用 `response_format={"type": "json_object"}`。普通生成入口只解析和校验 LLM 返回的 JSON；验证入口会在受限子进程中执行生成代码，但不落盘。

## 验证闭环行为

- 输入收集：随机输入和对抗输入各运行生成器 10 次，并通过各自 `validate_test_input`；小规模挑战输入使用初始返回加 9 次额外 LLM 调用凑满 10 条，并用随机输入的 validate 函数校验。
- 暴力解法：对 30 条输入逐一运行 `solve`。编译错误、接口错误和运行时错误会触发暴力 debug LLM 修复，并从头重新验证；超时或超内存输入会归为 `large_scale_inputs`，不触发 debug。
- 真值用例：最终只保留暴力解法能正常返回字符串输出的 `solved_cases`，数量允许少于已验证输入总数。
- checker：当 `needs_checker=false` 时跳过 checker 闭环；当需要 checker 时，先用 `solved_cases` 验证不误拒合法输出，再由反例生成 LLM 构造错误输出集合验证不误收非法输出。
- 修复循环：暴力解法、checker 误拒和 checker 误收修复均不设轮数上限，直到本地执行结果通过对应阶段。
- 错误解池增强：基础 checker 验证完成后，默认执行单题临时错误解池；无 checker 题使用输出字符串差异识别错误解问题，有 checker 题只使用已修复 checker 判定错误解输出是否暴露问题。
- 定向补测：错误解池会为全部当前尚未暴露问题的错误解生成单条 targeted 输入；输入通过现有 validate 函数且暴力解能产出真值时，会追加到 `verified_test_inputs` 和 `solved_cases`。当原始未暴露问题的错误解累计暴露比例达到 0.8，或某轮没有新增有效输入时停止。

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
- `prompts.verification.prompt_bruteforce_debug`
- `prompts.verification.prompt_checker_counterexample`
- `prompts.verification.prompt_checker_false_accept_debug`
- `prompts.verification.prompt_checker_false_reject_debug`
- `prompts.tool_generation.prompt_wrong_solution_targeted_test_input`
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
- 暴力 debug：`code`
- checker 误拒/误收修复：`analysis`、`fix_plan`、`checker_code`
- checker 反例生成：`counterexamples`、`skipped`；进入 `counterexamples` 的反例 `confidence` 必须大于等于 `0.85`
- 错误解池定向输入：`test_input`
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
