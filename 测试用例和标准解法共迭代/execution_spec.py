from __future__ import annotations

from typing import Any

from models import ExecutionSpec, TestCase


REQUIRED_EXECUTION_SPEC_FIELDS = {
    "problem_id",
    "input_contract",
    "output_contract",
    "judge_type",
    "oracle_limits",
    "test_buckets",
}


def normalize_execution_spec(payload: dict[str, Any]) -> ExecutionSpec:
    if not isinstance(payload, dict):
        raise ValueError("execution_spec 必须是 JSON 对象。")

    missing = sorted(REQUIRED_EXECUTION_SPEC_FIELDS - set(payload))
    if missing:
        raise ValueError("execution_spec 缺少必填字段：" + ", ".join(missing))

    problem_id = str(payload.get("problem_id", "")).strip()
    if not problem_id:
        raise ValueError("execution_spec.problem_id 不能为空。")

    judge_type = str(payload.get("judge_type", "")).strip()
    if judge_type not in {"exact", "checker"}:
        raise ValueError("execution_spec.judge_type 只能是 exact 或 checker。")

    input_contract = _require_dict(payload, "input_contract")
    output_contract = _require_dict(payload, "output_contract")
    oracle_limits = _require_dict(payload, "oracle_limits")
    test_buckets = _require_list(payload, "test_buckets")

    return ExecutionSpec(
        problem_id=problem_id,
        input_contract=input_contract,
        output_contract=output_contract,
        judge_type=judge_type,
        oracle_limits=oracle_limits,
        test_buckets=[item for item in test_buckets if isinstance(item, dict)],
        sample_tests=[item for item in payload.get("sample_tests", []) if isinstance(item, dict)],
        performance_limits=dict(payload.get("performance_limits", {}) or {}),
        ambiguity_notes=[str(item) for item in payload.get("ambiguity_notes", []) if str(item).strip()],
    )


def normalize_tests(raw_tests: Any, spec: ExecutionSpec) -> list[TestCase]:
    if not isinstance(raw_tests, list):
        raise ValueError("test_generator 必须返回测试列表。")

    tests: list[TestCase] = []
    for index, item in enumerate(raw_tests, start=1):
        if not isinstance(item, dict):
            continue
        input_text = str(item.get("input", "")).strip()
        if not input_text:
            continue
        tests.append(
            TestCase(
                input=input_text,
                source=str(item.get("source", f"generated_{index}")),
                purpose=str(item.get("purpose", "")) or "模型生成测试",
                expect_oracle=bool(item.get("expect_oracle", not bool(item.get("is_large", False)))),
                is_sample=bool(item.get("is_sample", False)),
                is_large=bool(item.get("is_large", False)),
                metadata=dict(item.get("metadata", {}) or {}),
            )
        )

    for index, item in enumerate(spec.sample_tests, start=1):
        input_text = str(item.get("input", "")).strip()
        if not input_text:
            continue
        tests.insert(
            0,
            TestCase(
                input=input_text,
                source=str(item.get("source", f"sample_{index}")),
                purpose=str(item.get("purpose", "题面样例")),
                expect_oracle=bool(item.get("expect_oracle", True)),
                is_sample=True,
                is_large=False,
                metadata=dict(item.get("metadata", {}) or {}),
            ),
        )
    return tests


def _require_dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"execution_spec.{key} 必须是对象。")
    return value


def _require_list(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ValueError(f"execution_spec.{key} 必须是列表。")
    return value

