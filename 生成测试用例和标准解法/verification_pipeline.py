from __future__ import annotations

import json
import logging
from typing import Any, Callable

try:  # 兼容包内导入与当前目录直接运行两种方式。
    from .execution_config import ExecutionConfig
    from .generation_pipeline import generate_all_artifacts
    from .llm_client import ChatLLMClient, OpenAIChatLLMClient
    from .llm_config import LLMConfig
    from .llm_json import (
        parse_json_object,
        validate_checker_repair_response,
        validate_code_repair_response,
        validate_counterexample_response,
        validate_small_challenge_response,
    )
    from .local_execution import (
        EXECUTION_MEMORY_LIMIT,
        EXECUTION_OK,
        EXECUTION_TIMEOUT,
        ExecutionResult,
        run_checker,
        run_generate_test_input,
        run_solution,
        run_validate_test_input,
    )
    from .prompts.tool_generation import prompt_small_challenge_test_input
    from .prompts.verification import (
        prompt_bruteforce_debug,
        prompt_checker_counterexample,
        prompt_checker_false_accept_debug,
        prompt_checker_false_reject_debug,
    )
except ImportError:  # pragma: no cover - 当前测试以顶层模块方式导入。
    from execution_config import ExecutionConfig
    from generation_pipeline import generate_all_artifacts
    from llm_client import ChatLLMClient, OpenAIChatLLMClient
    from llm_config import LLMConfig
    from llm_json import (
        parse_json_object,
        validate_checker_repair_response,
        validate_code_repair_response,
        validate_counterexample_response,
        validate_small_challenge_response,
    )
    from local_execution import (
        EXECUTION_MEMORY_LIMIT,
        EXECUTION_OK,
        EXECUTION_TIMEOUT,
        ExecutionResult,
        run_checker,
        run_generate_test_input,
        run_solution,
        run_validate_test_input,
    )
    from prompts.tool_generation import prompt_small_challenge_test_input
    from prompts.verification import (
        prompt_bruteforce_debug,
        prompt_checker_counterexample,
        prompt_checker_false_accept_debug,
        prompt_checker_false_reject_debug,
    )


logger = logging.getLogger(__name__)

Validator = Callable[[dict[str, Any]], dict[str, Any]]


class VerificationError(RuntimeError):
    """表示生成后验证流水线无法安全继续。"""


def _build_client(config: LLMConfig | None, client: ChatLLMClient | None) -> tuple[LLMConfig | None, ChatLLMClient]:
    if client is not None:
        return config, client
    resolved_config = config or LLMConfig.from_dotenv()
    return resolved_config, OpenAIChatLLMClient(resolved_config)


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


def _truncate_middle(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    marker = "\n...<truncated>...\n"
    if limit <= len(marker):
        return value[:limit]
    keep_each_side = (limit - len(marker)) // 2
    return value[:keep_each_side] + marker + value[-keep_each_side:]


def _result_summary(result: ExecutionResult) -> dict[str, Any]:
    payload = result.to_dict()
    if payload.get("stdout") and len(payload["stdout"]) > 2000:
        payload["stdout"] = _truncate_middle(payload["stdout"], 2000)
    if payload.get("stderr") and len(payload["stderr"]) > 2000:
        payload["stderr"] = _truncate_middle(payload["stderr"], 2000)
    if payload.get("traceback") and len(payload["traceback"]) > 4000:
        payload["traceback"] = _truncate_middle(payload["traceback"], 4000)
    if payload.get("user_stdout") and len(payload["user_stdout"]) > 2000:
        payload["user_stdout"] = _truncate_middle(payload["user_stdout"], 2000)
    if payload.get("user_stderr") and len(payload["user_stderr"]) > 2000:
        payload["user_stderr"] = _truncate_middle(payload["user_stderr"], 2000)
    return payload


def _format_execution_report(result: ExecutionResult, *, expectation: str) -> str:
    return json.dumps(
        {
            "expectation": expectation,
            "execution_result": _result_summary(result),
        },
        ensure_ascii=False,
        indent=2,
    )


def _fail_execution(context: str, result: ExecutionResult) -> None:
    raise VerificationError(
        f"{context} 执行失败："
        + json.dumps(_result_summary(result), ensure_ascii=False, indent=2)
    )


def _ensure_string_result(context: str, result: ExecutionResult) -> str:
    if result.status != EXECUTION_OK:
        _fail_execution(context, result)
    if not isinstance(result.return_value, str) or not result.return_value.strip():
        raise VerificationError(f"{context} 必须返回非空字符串。实际返回：{result.return_value!r}")
    return result.return_value


def _ensure_true_result(context: str, result: ExecutionResult) -> None:
    if result.status != EXECUTION_OK:
        _fail_execution(context, result)
    if result.return_value is not True:
        raise VerificationError(f"{context} 校验未通过。实际返回：{result.return_value!r}")


def _validate_input(
    *,
    context: str,
    validate_code: str,
    input_string: str,
    execution_config: ExecutionConfig,
) -> None:
    result = run_validate_test_input(
        validate_code,
        input_string,
        timeout_seconds=execution_config.test_input_timeout_seconds,
        memory_limit_mb=execution_config.test_input_memory_limit_mb,
    )
    _ensure_true_result(context, result)


def _collect_generated_inputs(
    *,
    source: str,
    generator_code: str,
    validate_code: str,
    start_index: int,
    execution_config: ExecutionConfig,
) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for local_index in range(1, 11):
        result = run_generate_test_input(
            generator_code,
            timeout_seconds=execution_config.test_input_timeout_seconds,
            memory_limit_mb=execution_config.test_input_memory_limit_mb,
        )
        input_string = _ensure_string_result(f"{source} 第 {local_index} 次生成输入", result)
        _validate_input(
            context=f"{source} 第 {local_index} 条输入",
            validate_code=validate_code,
            input_string=input_string,
            execution_config=execution_config,
        )
        case_id = f"case_{start_index + local_index - 1:03d}"
        cases.append(
            {
                "case_id": case_id,
                "source": source,
                "source_index": local_index,
                "input": input_string,
            }
        )
    return cases


def _collect_small_challenge_inputs(
    *,
    artifact: dict[str, Any],
    client: ChatLLMClient,
    initial_payload: dict[str, Any],
    validate_code: str,
    start_index: int,
    execution_config: ExecutionConfig,
) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for local_index in range(1, 11):
        if local_index == 1:
            payload = initial_payload
        else:
            task_name = f"small_challenge_test_input:verified:{local_index}"
            payload = _call_prompt(
                client,
                task_name=task_name,
                system_prompt=prompt_small_challenge_test_input.build_system_prompt(),
                user_prompt=prompt_small_challenge_test_input.build_user_prompt(artifact),
                validator=lambda item, task_name=task_name: validate_small_challenge_response(
                    item,
                    task_name=task_name,
                ),
            )
        input_string = payload["test_input"]
        _validate_input(
            context=f"small_challenge 第 {local_index} 条输入",
            validate_code=validate_code,
            input_string=input_string,
            execution_config=execution_config,
        )
        case_id = f"case_{start_index + local_index - 1:03d}"
        cases.append(
            {
                "case_id": case_id,
                "source": "small_challenge",
                "source_index": local_index,
                "input": input_string,
            }
        )
    return cases


def collect_verified_test_inputs(
    artifact: dict[str, Any],
    generated_artifacts: dict[str, Any],
    client: ChatLLMClient,
    execution_config: ExecutionConfig,
) -> dict[str, Any]:
    """收集 30 个已通过本地 validate 函数的合法输入。"""

    test_inputs = generated_artifacts["test_inputs"]
    random_payload = test_inputs["random"]
    adversarial_payload = test_inputs["adversarial"]
    small_payload = test_inputs["small_challenge"]

    cases: list[dict[str, Any]] = []
    cases.extend(
        _collect_generated_inputs(
            source="random",
            generator_code=random_payload["generate_test_input_code"],
            validate_code=random_payload["validate_test_input_code"],
            start_index=1,
            execution_config=execution_config,
        )
    )
    cases.extend(
        _collect_generated_inputs(
            source="adversarial",
            generator_code=adversarial_payload["generate_test_input_code"],
            validate_code=adversarial_payload["validate_test_input_code"],
            start_index=11,
            execution_config=execution_config,
        )
    )
    cases.extend(
        _collect_small_challenge_inputs(
            artifact=artifact,
            client=client,
            initial_payload=small_payload,
            validate_code=random_payload["validate_test_input_code"],
            start_index=21,
            execution_config=execution_config,
        )
    )
    return {
        "status": "ok",
        "cases": cases,
        "count": len(cases),
        "source_counts": {
            "random": 10,
            "adversarial": 10,
            "small_challenge": 10,
        },
        "small_challenge_llm_calls_including_initial": 10,
    }


def _repair_bruteforce(
    artifact: dict[str, Any],
    client: ChatLLMClient,
    *,
    current_code: str,
    failing_input: str,
    error_report: str,
) -> dict[str, Any]:
    return _call_prompt(
        client,
        task_name="bruteforce_debug",
        system_prompt=prompt_bruteforce_debug.build_system_prompt(),
        user_prompt=prompt_bruteforce_debug.build_user_prompt(
            artifact,
            bruteforce_code=current_code,
            failing_input=failing_input,
            error_report=error_report,
        ),
        validator=lambda payload: validate_code_repair_response(payload, task_name="bruteforce_debug"),
    )


def verify_bruteforce_solution(
    artifact: dict[str, Any],
    bruteforce_payload: dict[str, Any],
    input_cases: list[dict[str, Any]],
    client: ChatLLMClient,
    execution_config: ExecutionConfig,
) -> dict[str, Any]:
    if bruteforce_payload.get("status") != "ok":
        raise VerificationError("暴力解法未生成成功，无法执行验证：" + str(bruteforce_payload.get("block_reason", "")))

    current_code = bruteforce_payload["code"]
    repair_history: list[dict[str, Any]] = []
    iteration = 0
    while True:
        iteration += 1
        solved_cases: list[dict[str, Any]] = []
        large_scale_inputs: list[dict[str, Any]] = []
        should_restart = False

        for case in input_cases:
            result = run_solution(
                current_code,
                case["input"],
                timeout_seconds=execution_config.bruteforce_timeout_seconds,
                memory_limit_mb=execution_config.bruteforce_memory_limit_mb,
            )
            if result.status == EXECUTION_OK and isinstance(result.return_value, str):
                solved_cases.append(
                    {
                        "case_id": case["case_id"],
                        "source": case["source"],
                        "input": case["input"],
                        "output": result.return_value,
                    }
                )
                continue
            if result.status in (EXECUTION_TIMEOUT, EXECUTION_MEMORY_LIMIT):
                large_scale_inputs.append(
                    {
                        "case_id": case["case_id"],
                        "source": case["source"],
                        "input": case["input"],
                        "classification": "large_scale_input",
                        "execution_result": _result_summary(result),
                    }
                )
                continue

            if result.status == EXECUTION_OK:
                error_report = json.dumps(
                    {
                        "expectation": "solve(input_str) 必须返回字符串。",
                        "actual_return_value": result.return_value,
                        "execution_result": _result_summary(result),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            else:
                error_report = _format_execution_report(result, expectation="暴力解法应正常返回输出字符串。")
            repair = _repair_bruteforce(
                artifact,
                client,
                current_code=current_code,
                failing_input=case["input"],
                error_report=error_report,
            )
            repair_history.append(
                {
                    "iteration": iteration,
                    "failed_case_id": case["case_id"],
                    "failed_input": case["input"],
                    "error_report": error_report,
                    "repair": repair,
                }
            )
            current_code = repair["code"]
            should_restart = True
            logger.info("暴力解法已修复，准备重新验证全部输入: iteration=%s", iteration)
            break

        if not should_restart:
            return {
                "status": "ok",
                "final_code": current_code,
                "solved_cases": solved_cases,
                "solved_case_count": len(solved_cases),
                "large_scale_inputs": large_scale_inputs,
                "large_scale_input_count": len(large_scale_inputs),
                "repair_history": repair_history,
                "repair_iteration_count": len(repair_history),
            }


def _repair_checker_false_reject(
    artifact: dict[str, Any],
    client: ChatLLMClient,
    *,
    current_code: str,
    failing_input: str,
    failing_output: str,
    error_report: str,
) -> dict[str, Any]:
    return _call_prompt(
        client,
        task_name="checker_false_reject_debug",
        system_prompt=prompt_checker_false_reject_debug.build_system_prompt(),
        user_prompt=prompt_checker_false_reject_debug.build_user_prompt(
            artifact,
            checker_code=current_code,
            failing_input=failing_input,
            failing_output=failing_output,
            error_report=error_report,
        ),
        validator=lambda payload: validate_checker_repair_response(
            payload,
            task_name="checker_false_reject_debug",
        ),
    )


def _repair_checker_false_accept(
    artifact: dict[str, Any],
    client: ChatLLMClient,
    *,
    current_code: str,
    failing_input: str,
    wrong_output: str,
    error_report: str,
) -> dict[str, Any]:
    return _call_prompt(
        client,
        task_name="checker_false_accept_debug",
        system_prompt=prompt_checker_false_accept_debug.build_system_prompt(),
        user_prompt=prompt_checker_false_accept_debug.build_user_prompt(
            artifact,
            checker_code=current_code,
            failing_input=failing_input,
            wrong_output=wrong_output,
            error_report=error_report,
        ),
        validator=lambda payload: validate_checker_repair_response(
            payload,
            task_name="checker_false_accept_debug",
        ),
    )


def _verify_checker_property_1(
    artifact: dict[str, Any],
    client: ChatLLMClient,
    *,
    checker_code: str,
    solved_cases: list[dict[str, Any]],
    execution_config: ExecutionConfig,
    repair_history: list[dict[str, Any]],
) -> str:
    while True:
        restarted = False
        for case in solved_cases:
            result = run_checker(
                checker_code,
                case["input"],
                case["output"],
                timeout_seconds=execution_config.checker_timeout_seconds,
                memory_limit_mb=execution_config.checker_memory_limit_mb,
            )
            if result.status == EXECUTION_OK and result.return_value is True:
                continue
            error_report = _format_execution_report(result, expectation="合法输出必须被 checker 判为 AC/True。")
            repair = _repair_checker_false_reject(
                artifact,
                client,
                current_code=checker_code,
                failing_input=case["input"],
                failing_output=case["output"],
                error_report=error_report,
            )
            repair_history.append(
                {
                    "property": "no_false_reject",
                    "failed_case_id": case["case_id"],
                    "failed_input": case["input"],
                    "failed_output": case["output"],
                    "error_report": error_report,
                    "repair": repair,
                }
            )
            checker_code = repair["checker_code"]
            restarted = True
            logger.info("checker 误拒修复完成，重新验证性质1。")
            break
        if not restarted:
            return checker_code


def _generate_counterexamples(
    artifact: dict[str, Any],
    client: ChatLLMClient,
    solved_cases: list[dict[str, Any]],
) -> dict[str, Any]:
    prompt_cases = [
        {
            "case_id": case["case_id"],
            "input": case["input"],
            "correct_output": case["output"],
        }
        for case in solved_cases
    ]
    return _call_prompt(
        client,
        task_name="checker_counterexample_generation",
        system_prompt=prompt_checker_counterexample.build_system_prompt(),
        user_prompt=prompt_checker_counterexample.build_user_prompt(artifact, solved_cases=prompt_cases),
        validator=lambda payload: validate_counterexample_response(
            payload,
            task_name="checker_counterexample_generation",
        ),
    )


def verify_checker(
    artifact: dict[str, Any],
    checker_payload: dict[str, Any],
    solved_cases: list[dict[str, Any]],
    client: ChatLLMClient,
    execution_config: ExecutionConfig,
) -> dict[str, Any]:
    if not checker_payload.get("needs_checker"):
        return {
            "status": "skipped",
            "reason": checker_payload.get("reason", "该题不需要特殊 checker。"),
        }
    if not solved_cases:
        return {
            "status": "skipped",
            "reason": "没有可由暴力解法产出真值的测试用例，无法验证 checker。",
        }

    checker_code = checker_payload["checker_code"]
    repair_history: list[dict[str, Any]] = []
    checker_code = _verify_checker_property_1(
        artifact,
        client,
        checker_code=checker_code,
        solved_cases=solved_cases,
        execution_config=execution_config,
        repair_history=repair_history,
    )

    counterexamples = _generate_counterexamples(artifact, client, solved_cases)
    invalid_cases = counterexamples["counterexamples"]
    if not invalid_cases:
        return {
            "status": "counterexamples_empty",
            "final_checker_code": checker_code,
            "property_1": {"status": "ok", "checked_count": len(solved_cases)},
            "property_2": {"status": "not_checked", "checked_count": 0},
            "counterexamples": counterexamples,
            "repair_history": repair_history,
        }

    checked_counterexamples: list[dict[str, Any]] = []
    index = 0
    while index < len(invalid_cases):
        item = invalid_cases[index]
        result = run_checker(
            checker_code,
            item["input"],
            item["wrong_output"],
            timeout_seconds=execution_config.checker_timeout_seconds,
            memory_limit_mb=execution_config.checker_memory_limit_mb,
        )
        if result.status == EXECUTION_OK and result.return_value is False:
            checked_counterexamples.append(
                {
                    "source_case_id": item["source_case_id"],
                    "primary_strategy": item["primary_strategy"],
                    "verdict": "WA",
                    "execution_result": _result_summary(result),
                }
            )
            index += 1
            continue

        expectation = "非法输出必须被 checker 稳定判为 WA/False。"
        error_report = _format_execution_report(result, expectation=expectation)
        repair = _repair_checker_false_accept(
            artifact,
            client,
            current_code=checker_code,
            failing_input=item["input"],
            wrong_output=item["wrong_output"],
            error_report=error_report,
        )
        repair_history.append(
            {
                "property": "no_false_accept",
                "source_case_id": item["source_case_id"],
                "wrong_output": item["wrong_output"],
                "primary_strategy": item["primary_strategy"],
                "error_report": error_report,
                "repair": repair,
            }
        )
        checker_code = repair["checker_code"]
        checker_code = _verify_checker_property_1(
            artifact,
            client,
            checker_code=checker_code,
            solved_cases=solved_cases,
            execution_config=execution_config,
            repair_history=repair_history,
        )
        checked_counterexamples = []
        index = 0
        logger.info("checker 误收修复完成，重新验证性质1和性质2。")

    return {
        "status": "ok",
        "final_checker_code": checker_code,
        "property_1": {"status": "ok", "checked_count": len(solved_cases)},
        "property_2": {"status": "ok", "checked_count": len(invalid_cases)},
        "counterexamples": counterexamples,
        "checked_counterexamples": checked_counterexamples,
        "repair_history": repair_history,
        "repair_iteration_count": len(repair_history),
    }


def generate_verified_artifacts(
    artifact: dict[str, Any],
    config: LLMConfig | None = None,
    *,
    client: ChatLLMClient | None = None,
    execution_config: ExecutionConfig | None = None,
) -> dict[str, Any]:
    """生成全部产物，并执行测试输入、暴力解法和 checker 验证闭环。"""

    resolved_config, active_client = _build_client(config, client)
    active_execution_config = execution_config or ExecutionConfig.from_dotenv()
    generated_artifacts = generate_all_artifacts(artifact, resolved_config, client=active_client)

    verified_test_inputs = collect_verified_test_inputs(
        artifact,
        generated_artifacts,
        active_client,
        active_execution_config,
    )
    bruteforce_verification = verify_bruteforce_solution(
        artifact,
        generated_artifacts["bruteforce_solution"],
        verified_test_inputs["cases"],
        active_client,
        active_execution_config,
    )
    checker_verification = verify_checker(
        artifact,
        generated_artifacts["checker"],
        bruteforce_verification["solved_cases"],
        active_client,
        active_execution_config,
    )

    result = dict(generated_artifacts)
    final_checker_code = checker_verification.get("final_checker_code")
    if generated_artifacts["checker"].get("needs_checker") and final_checker_code:
        checker_result = {
            **generated_artifacts["checker"],
            "initial_checker_code": generated_artifacts["checker"]["checker_code"],
            "checker_code": final_checker_code,
            "verified_checker_code": final_checker_code,
        }
    else:
        checker_result = generated_artifacts["checker"]

    result.update(
        {
            "bruteforce_solution": {
                **generated_artifacts["bruteforce_solution"],
                "initial_code": generated_artifacts["bruteforce_solution"]["code"],
                "code": bruteforce_verification["final_code"],
                "verified_code": bruteforce_verification["final_code"],
            },
            "checker": checker_result,
            "verified_test_inputs": verified_test_inputs,
            "bruteforce_verification": bruteforce_verification,
            "checker_verification": checker_verification,
            "execution_metadata": {
                "execution_config": {
                    "test_input_timeout_seconds": active_execution_config.test_input_timeout_seconds,
                    "test_input_memory_limit_mb": active_execution_config.test_input_memory_limit_mb,
                    "bruteforce_timeout_seconds": active_execution_config.bruteforce_timeout_seconds,
                    "bruteforce_memory_limit_mb": active_execution_config.bruteforce_memory_limit_mb,
                    "checker_timeout_seconds": active_execution_config.checker_timeout_seconds,
                    "checker_memory_limit_mb": active_execution_config.checker_memory_limit_mb,
                },
                "verified_test_input_count": verified_test_inputs["count"],
                "solved_case_count": bruteforce_verification["solved_case_count"],
                "large_scale_input_count": bruteforce_verification["large_scale_input_count"],
            },
        }
    )
    return result
