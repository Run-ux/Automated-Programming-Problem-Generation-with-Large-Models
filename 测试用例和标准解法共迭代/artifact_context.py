from __future__ import annotations

from typing import Any

from models import ProblemContext, TestCase


GENERATED_PROBLEM_FIELDS = (
    "title",
    "description",
    "input_format",
    "output_format",
    "constraints",
    "samples",
    "notes",
)

SCHEMA_FIELDS = ("input_structure", "core_constraints", "objective", "invariant")


def build_problem_context(context: dict[str, Any]) -> ProblemContext:
    generated_problem = _compact_generated_problem(context.get("generated_problem"))
    schema_snapshot = _compact_schema_snapshot(context.get("new_schema_snapshot") or context.get("new_schema"))
    return ProblemContext(
        problem_id=str(context.get("problem_id") or generated_problem.get("title") or "generated_problem"),
        generated_problem=generated_problem,
        schema_snapshot=schema_snapshot,
        judge_type=_infer_judge_type(generated_problem, schema_snapshot),
        sample_tests=_sample_tests_from_generated_problem(generated_problem),
    )


def build_llm_problem_payload(context: dict[str, Any]) -> dict[str, Any]:
    problem = build_problem_context(context)
    generated = problem.generated_problem
    schema = problem.schema_snapshot
    return {
        "input_structure": schema.get("input_structure", {}),
        "core_constraints": schema.get("core_constraints", {}),
        "objective": schema.get("objective", {}),
        "invariant": schema.get("invariant", {}),
        "title": generated.get("title", ""),
        "description": generated.get("description", ""),
        "input_format": generated.get("input_format", ""),
        "output_format": generated.get("output_format", ""),
        "constraints": generated.get("constraints", []),
        "samples": generated.get("samples", []),
        "notes": generated.get("notes", ""),
    }


def normalize_tests(raw_tests: Any, problem: ProblemContext) -> list[TestCase]:
    if not isinstance(raw_tests, list):
        raise ValueError("测试输入生成器必须返回测试列表。")

    tests: list[TestCase] = []
    for index, item in enumerate(raw_tests, start=1):
        normalized = _normalize_generated_test_item(item, index)
        if normalized is not None:
            tests.append(normalized)

    sample_cases: list[TestCase] = []
    for index, item in enumerate(problem.sample_tests, start=1):
        input_text = str(item.get("input", "")).strip()
        if not input_text:
            continue
        sample_cases.append(
            TestCase(
                input=input_text,
                source=str(item.get("source") or f"sample_{index}"),
                purpose=str(item.get("purpose") or "题面样例"),
                expect_bruteforce=True,
                is_sample=True,
                is_large=False,
                metadata={
                    "sample_output": str(item.get("output", "")),
                    **(dict(item.get("metadata", {}) or {}) if isinstance(item.get("metadata"), dict) else {}),
                },
            ),
        )
    tests = [*sample_cases, *tests]
    return _dedupe_tests(tests)


def normalize_small_challenge_tests(raw_tests: Any) -> list[dict[str, Any]]:
    if isinstance(raw_tests, dict):
        raw_tests = raw_tests.get("tests") or raw_tests.get("test_inputs") or []
    if not isinstance(raw_tests, list):
        raise ValueError("小规模挑战输入必须是列表或包含 tests/test_inputs 的对象。")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(raw_tests, start=1):
        if isinstance(item, str):
            input_text = item.strip()
            if input_text:
                result.append(
                    {
                        "input": input_text,
                        "source": f"small_challenge_{index}",
                        "purpose": "小规模挑战输入",
                        "expect_bruteforce": True,
                        "is_large": False,
                        "metadata": {"generator": "small_challenge"},
                    }
                )
            continue
        if isinstance(item, dict):
            input_text = str(item.get("input", "")).strip()
            if input_text:
                result.append(
                    {
                        "input": input_text,
                        "source": str(item.get("source") or f"small_challenge_{index}"),
                        "purpose": str(item.get("purpose") or "小规模挑战输入"),
                        "expect_bruteforce": _bool_with_legacy(item, "expect_bruteforce", "expect_oracle", True),
                        "is_large": bool(item.get("is_large", False)),
                        "metadata": dict(item.get("metadata", {}) or {}),
                    }
                )
    return result


def _compact_generated_problem(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    result = {key: source.get(key, [] if key == "samples" else "") for key in GENERATED_PROBLEM_FIELDS}
    if not isinstance(result["samples"], list):
        result["samples"] = []
    if not isinstance(result["constraints"], list):
        result["constraints"] = [str(result["constraints"])] if str(result["constraints"]).strip() else []
    return result


def _compact_schema_snapshot(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    return {key: source.get(key, {}) if isinstance(source.get(key, {}), dict) else source.get(key, {}) for key in SCHEMA_FIELDS}


def _sample_tests_from_generated_problem(generated_problem: dict[str, Any]) -> list[dict[str, Any]]:
    samples = generated_problem.get("samples", [])
    if not isinstance(samples, list):
        return []
    result: list[dict[str, Any]] = []
    for index, sample in enumerate(samples, start=1):
        if not isinstance(sample, dict):
            continue
        input_text = str(sample.get("input", "")).strip()
        if not input_text:
            continue
        result.append(
            {
                "input": input_text,
                "output": str(sample.get("output", "")).strip(),
                "source": f"sample_{index}",
                "purpose": str(sample.get("explanation") or "题面样例"),
            }
        )
    return result


def _infer_judge_type(generated_problem: dict[str, Any], schema_snapshot: dict[str, Any]) -> str:
    text = "\n".join(
        [
            str(generated_problem.get("description", "")),
            str(generated_problem.get("output_format", "")),
            str(generated_problem.get("notes", "")),
            str(schema_snapshot.get("objective", "")),
        ]
    ).lower()
    checker_markers = (
        "任意合法",
        "任意满足",
        "任意方案",
        "构造",
        "方案",
        "证书",
        "多解",
        "any valid",
        "construct",
        "certificate",
    )
    return "checker" if any(marker in text for marker in checker_markers) else "exact"


def _normalize_generated_test_item(item: Any, index: int) -> TestCase | None:
    if isinstance(item, str):
        input_text = item.strip()
        if not input_text:
            return None
        return TestCase(
            input=input_text,
            source=f"generated_{index}",
            purpose="模型生成测试",
            expect_bruteforce=True,
            is_sample=False,
            is_large=False,
            metadata={},
        )
    if not isinstance(item, dict):
        return None
    input_text = str(item.get("input", "")).strip()
    if not input_text:
        return None
    return TestCase(
        input=input_text,
        source=str(item.get("source", f"generated_{index}")),
        purpose=str(item.get("purpose", "")) or "模型生成测试",
        expect_bruteforce=_bool_with_legacy(
            item,
            "expect_bruteforce",
            "expect_oracle",
            not bool(item.get("is_large", False)),
        ),
        is_sample=bool(item.get("is_sample", False)),
        is_large=bool(item.get("is_large", False)),
        metadata=dict(item.get("metadata", {}) or {}),
    )


def _dedupe_tests(tests: list[TestCase]) -> list[TestCase]:
    seen: set[str] = set()
    result: list[TestCase] = []
    for test in tests:
        if test.input in seen:
            continue
        seen.add(test.input)
        result.append(test)
    return result


def _bool_with_legacy(item: dict[str, Any], key: str, legacy_key: str, default: bool) -> bool:
    if key in item:
        return bool(item.get(key))
    if legacy_key in item:
        return bool(item.get(legacy_key))
    return bool(default)
