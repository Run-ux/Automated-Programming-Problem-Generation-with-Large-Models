from __future__ import annotations

from typing import Any

from models import ExecutionResult, TestCase, WrongSolution, to_dict
from runners import CodeRunner


class WrongSolutionCurator:
    def __init__(self, *, runner: CodeRunner, kill_rate_threshold: float = 0.8):
        self.runner = runner
        self.kill_rate_threshold = kill_rate_threshold

    def curate(
        self,
        *,
        candidates: list[WrongSolution],
        tests: list[TestCase],
        checker_code: str,
        expected_outputs: dict[str, str],
    ) -> dict[str, Any]:
        valuable: list[dict[str, Any]] = []
        independent: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        matrix: list[dict[str, Any]] = []

        for candidate in candidates:
            result = self._evaluate_candidate(
                candidate=candidate,
                tests=tests,
                checker_code=checker_code,
                expected_outputs=expected_outputs,
            )
            matrix.extend(result["matrix"])
            if result["category"] == "valuable_wrong_solution":
                valuable.append(result)
            elif result["category"] == "possibly_correct_solution":
                independent.append(result)
            else:
                rejected.append(result)

        total = len(valuable) + len(independent)
        killed = len(valuable)
        kill_rate = killed / total if total else 0.0
        return {
            "valuable_wrong_solutions": valuable,
            "independent_solutions": independent,
            "rejected_candidates": rejected,
            "matrix": matrix,
            "stats": {
                "candidate_count": len(candidates),
                "valuable_count": len(valuable),
                "independent_count": len(independent),
                "rejected_count": len(rejected),
                "kill_rate": round(kill_rate, 4),
                "kill_rate_threshold": self.kill_rate_threshold,
                "passed_threshold": kill_rate >= self.kill_rate_threshold if total else True,
            },
        }

    def _evaluate_candidate(
        self,
        *,
        candidate: WrongSolution,
        tests: list[TestCase],
        checker_code: str,
        expected_outputs: dict[str, str],
    ) -> dict[str, Any]:
        if not tests:
            return _candidate_record(candidate, "invalid_code", "没有可用于筛选的测试。", [], [])

        passed: list[str] = []
        killed: list[str] = []
        matrix: list[dict[str, Any]] = []
        first_error = ""
        executable_seen = False

        for test in tests:
            solution_result = self.runner.run_solve(
                artifact_name=candidate.solution_id,
                code=candidate.code,
                input_data=test.input,
                test_source=test.source,
            )
            matrix.append(to_dict(solution_result))
            if solution_result.status in {"compile_error", "invalid_interface"}:
                return _candidate_record(
                    candidate,
                    "invalid_code",
                    solution_result.error_reason or solution_result.status,
                    killed,
                    matrix,
                )
            if solution_result.status != "ok":
                killed.append(test.source)
                first_error = first_error or solution_result.error_reason or solution_result.status
                continue

            executable_seen = True
            expected = expected_outputs.get(test.source)
            check_result = self.runner.run_check(
                artifact_name="checker",
                code=checker_code,
                input_data=test.input,
                output_data=str(solution_result.result),
                expected_data=expected,
                test_source=test.source,
            )
            matrix.append(to_dict(check_result))
            if check_result.status != "ok" or check_result.result is not True:
                killed.append(test.source)
                first_error = first_error or check_result.error_reason or "checker 拒绝候选错误解输出。"
            else:
                passed.append(test.source)

        if not executable_seen:
            return _candidate_record(candidate, "trivial_failure", first_error or "候选解无法在任何测试上正常运行。", killed, matrix)
        if not killed:
            return _candidate_record(candidate, "possibly_correct_solution", "当前测试未能杀掉该候选解。", killed, matrix)
        if not passed:
            return _candidate_record(candidate, "trivial_failure", first_error or "候选解没有通过任何测试。", killed, matrix)
        return _candidate_record(
            candidate,
            "valuable_wrong_solution",
            first_error or "候选解能通过部分测试，但存在明确反例。",
            killed,
            matrix,
            passed=passed,
        )


def _candidate_record(
    candidate: WrongSolution,
    category: str,
    reason: str,
    killed_tests: list[str],
    matrix: list[dict[str, Any]],
    *,
    passed: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "solution_id": candidate.solution_id,
        "source": candidate.source,
        "bug_type": candidate.bug_type,
        "expected_failure": candidate.expected_failure,
        "category": category,
        "reason": reason,
        "passed_tests": list(passed or []),
        "killed_tests": list(killed_tests),
        "metadata": dict(candidate.metadata),
        "matrix": matrix,
    }

