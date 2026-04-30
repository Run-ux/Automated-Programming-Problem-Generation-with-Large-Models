from __future__ import annotations

import logging
from typing import Any, Callable

try:  # 兼容包内导入与当前目录直接运行两种方式。
    from .llm_client import ChatLLMClient, OpenAIChatLLMClient
    from .llm_config import LLMConfig
    from .llm_json import (
        parse_json_object,
        validate_checker_response,
        validate_small_challenge_response,
        validate_solution_response,
        validate_strategy_analysis_response,
        validate_test_generator_response,
        validate_wrong_solution_response,
    )
    from .prompts.bruteforce_solution import prompt_bruteforce_solution
    from .prompts.standard_solution import prompt_standard_solution
    from .prompts.tool_generation import (
        prompt_adversarial_test_input,
        prompt_checker,
        prompt_random_test_input,
        prompt_small_challenge_test_input,
    )
    from .prompts.wrong_solution import (
        prompt_fixed_category_wrong_solution,
        prompt_schema_mistake_analysis,
        prompt_strategy_wrong_solution,
    )
except ImportError:  # pragma: no cover - 当前测试以顶层模块方式导入。
    from llm_client import ChatLLMClient, OpenAIChatLLMClient
    from llm_config import LLMConfig
    from llm_json import (
        parse_json_object,
        validate_checker_response,
        validate_small_challenge_response,
        validate_solution_response,
        validate_strategy_analysis_response,
        validate_test_generator_response,
        validate_wrong_solution_response,
    )
    from prompts.bruteforce_solution import prompt_bruteforce_solution
    from prompts.standard_solution import prompt_standard_solution
    from prompts.tool_generation import (
        prompt_adversarial_test_input,
        prompt_checker,
        prompt_random_test_input,
        prompt_small_challenge_test_input,
    )
    from prompts.wrong_solution import (
        prompt_fixed_category_wrong_solution,
        prompt_schema_mistake_analysis,
        prompt_strategy_wrong_solution,
    )


logger = logging.getLogger(__name__)

Validator = Callable[[dict[str, Any]], dict[str, Any]]


def _call_prompt(
    client: ChatLLMClient,
    *,
    task_name: str,
    system_prompt: str,
    user_prompt: str,
    validator: Validator,
) -> dict[str, Any]:
    raw_response = client.complete_json(task_name=task_name, system_prompt=system_prompt, user_prompt=user_prompt)
    parsed = parse_json_object(raw_response, task_name)
    return validator(parsed)


def _build_client(config: LLMConfig | None, client: ChatLLMClient | None) -> tuple[LLMConfig | None, ChatLLMClient]:
    if client is not None:
        return config, client
    resolved_config = config or LLMConfig.from_dotenv()
    return resolved_config, OpenAIChatLLMClient(resolved_config)


def _metadata(config: LLMConfig | None, client: ChatLLMClient, strategy_count: int) -> dict[str, Any]:
    model = config.model if config else getattr(client, "model", "")
    base_url_configured = bool(config.base_url) if config else bool(getattr(client, "base_url", None))
    return {
        "model": model,
        "base_url_configured": base_url_configured,
        "json_mode": True,
        "fixed_wrong_category_count": len(prompt_fixed_category_wrong_solution.FIXED_WRONG_CATEGORIES),
        "strategy_wrong_solution_count": strategy_count,
    }


def generate_all_artifacts(
    artifact: dict[str, Any],
    config: LLMConfig | None = None,
    *,
    client: ChatLLMClient | None = None,
) -> dict[str, Any]:
    """调用 LLM 生成本模块负责的全部产物。"""
    resolved_config, active_client = _build_client(config, client)

    standard_solution = _call_prompt(
        active_client,
        task_name="standard_solution",
        system_prompt=prompt_standard_solution.build_system_prompt(),
        user_prompt=prompt_standard_solution.build_user_prompt(artifact),
        validator=lambda payload: validate_solution_response(
            payload,
            task_name="standard_solution",
            markdown_key="solution_markdown",
        ),
    )
    bruteforce_solution = _call_prompt(
        active_client,
        task_name="bruteforce_solution",
        system_prompt=prompt_bruteforce_solution.build_system_prompt(),
        user_prompt=prompt_bruteforce_solution.build_user_prompt(artifact),
        validator=lambda payload: validate_solution_response(
            payload,
            task_name="bruteforce_solution",
            markdown_key="bruteforce_markdown",
        ),
    )

    random_test_input = _call_prompt(
        active_client,
        task_name="random_test_input",
        system_prompt=prompt_random_test_input.build_system_prompt(),
        user_prompt=prompt_random_test_input.build_user_prompt(artifact),
        validator=lambda payload: validate_test_generator_response(payload, task_name="random_test_input"),
    )
    adversarial_test_input = _call_prompt(
        active_client,
        task_name="adversarial_test_input",
        system_prompt=prompt_adversarial_test_input.build_system_prompt(),
        user_prompt=prompt_adversarial_test_input.build_user_prompt(artifact),
        validator=lambda payload: validate_test_generator_response(payload, task_name="adversarial_test_input"),
    )
    small_challenge_test_input = _call_prompt(
        active_client,
        task_name="small_challenge_test_input",
        system_prompt=prompt_small_challenge_test_input.build_system_prompt(),
        user_prompt=prompt_small_challenge_test_input.build_user_prompt(artifact),
        validator=lambda payload: validate_small_challenge_response(payload, task_name="small_challenge_test_input"),
    )

    checker = _call_prompt(
        active_client,
        task_name="checker",
        system_prompt=prompt_checker.build_system_prompt(),
        user_prompt=prompt_checker.build_user_prompt(artifact),
        validator=validate_checker_response,
    )

    fixed_wrong_solutions: dict[str, dict[str, Any]] = {}
    for category in prompt_fixed_category_wrong_solution.FIXED_WRONG_CATEGORIES:
        task_name = f"fixed_wrong_solution:{category}"
        fixed_wrong_solutions[category] = _call_prompt(
            active_client,
            task_name=task_name,
            system_prompt=prompt_fixed_category_wrong_solution.build_system_prompt(),
            user_prompt=prompt_fixed_category_wrong_solution.build_user_prompt(artifact, category),
            validator=lambda payload, task_name=task_name: validate_wrong_solution_response(payload, task_name=task_name),
        )

    strategy_analysis = _call_prompt(
        active_client,
        task_name="strategy_analysis",
        system_prompt=prompt_schema_mistake_analysis.build_system_prompt(),
        user_prompt=prompt_schema_mistake_analysis.build_user_prompt(artifact),
        validator=validate_strategy_analysis_response,
    )
    strategies = strategy_analysis["strategies"]
    logger.info("错误策略分析完成: strategy_count=%s", len(strategies))

    strategy_based_wrong_solutions: list[dict[str, Any]] = []
    for index, strategy in enumerate(strategies):
        task_name = f"strategy_wrong_solution:{index}"
        response = _call_prompt(
            active_client,
            task_name=task_name,
            system_prompt=prompt_strategy_wrong_solution.build_system_prompt(),
            user_prompt=prompt_strategy_wrong_solution.build_user_prompt(artifact, strategy),
            validator=lambda payload, task_name=task_name: validate_wrong_solution_response(payload, task_name=task_name),
        )
        strategy_based_wrong_solutions.append({"strategy": strategy, "solution": response})

    return {
        "standard_solution": standard_solution,
        "bruteforce_solution": bruteforce_solution,
        "test_inputs": {
            "random": random_test_input,
            "adversarial": adversarial_test_input,
            "small_challenge": small_challenge_test_input,
        },
        "checker": checker,
        "wrong_solutions": {
            "fixed_categories": fixed_wrong_solutions,
            "strategy_analysis": strategy_analysis,
            "strategy_based": strategy_based_wrong_solutions,
        },
        "metadata": _metadata(resolved_config, active_client, len(strategies)),
    }

