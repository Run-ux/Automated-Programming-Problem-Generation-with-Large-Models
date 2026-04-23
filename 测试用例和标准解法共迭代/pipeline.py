from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from config import DEFAULT_KILL_RATE_THRESHOLD, DEFAULT_LARGE_RUN_TIMEOUT_S, DEFAULT_OUTPUT_DIR, DEFAULT_RUN_TIMEOUT_S
from curation import WrongSolutionCurator
from execution_spec import normalize_tests
from generators import (
    OracleGenerator,
    SpecExtractor,
    StandardSolutionGenerator,
    ToolGenerator,
    WeakPlayerGenerator,
    build_rule_based_wrong_solutions,
)
from models import (
    ExecutionSpec,
    FailureIssue,
    GeneratedCodeArtifact,
    IterationSummary,
    TestCase,
    ValidationReport,
    WrongSolution,
    to_dict,
)
from report_renderer import render_execution_report_markdown
from runners import CodeRunner


class PackageValidationPipeline:
    def __init__(
        self,
        *,
        client: Any,
        output_dir: Path = DEFAULT_OUTPUT_DIR,
        runner: CodeRunner | None = None,
        kill_rate_threshold: float = DEFAULT_KILL_RATE_THRESHOLD,
        run_timeout_s: float = DEFAULT_RUN_TIMEOUT_S,
        large_run_timeout_s: float = DEFAULT_LARGE_RUN_TIMEOUT_S,
        spec_extractor: SpecExtractor | None = None,
        standard_generator: StandardSolutionGenerator | None = None,
        oracle_generator: OracleGenerator | None = None,
        tool_generator: ToolGenerator | None = None,
        weak_player_generator: WeakPlayerGenerator | None = None,
        progress_writer: Any | None = None,
    ):
        self.client = client
        self.output_dir = output_dir
        self.runner = runner or CodeRunner(timeout_s=run_timeout_s)
        self.kill_rate_threshold = kill_rate_threshold
        self.run_timeout_s = run_timeout_s
        self.large_run_timeout_s = large_run_timeout_s
        self.spec_extractor = spec_extractor or SpecExtractor(client)
        self.standard_generator = standard_generator or StandardSolutionGenerator(client)
        self.oracle_generator = oracle_generator or OracleGenerator(client)
        self.tool_generator = tool_generator or ToolGenerator(client)
        self.weak_player_generator = weak_player_generator or WeakPlayerGenerator(client)
        self.progress_writer = progress_writer or (lambda message: print(message, flush=True))

    def run(
        self,
        *,
        artifact_path: Path,
        markdown_path: Path | None = None,
        rounds: int = 3,
    ) -> dict[str, Any]:
        artifact = _read_json(artifact_path)
        markdown = markdown_path.read_text(encoding="utf-8") if markdown_path and markdown_path.exists() else ""
        context = _build_context(artifact=artifact, markdown=markdown, artifact_path=artifact_path, markdown_path=markdown_path)
        problem_id = context["problem_id"]
        run_id = _build_run_id(problem_id)
        run_dir = self.output_dir / problem_id / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        revision_context: dict[str, Any] = {}
        round_records: list[dict[str, Any]] = []
        final_status = "not_deliverable"
        stop_reason = "reached_requested_rounds"
        final_round_index = 0
        last_package: dict[str, Any] | None = None
        no_new_high_value_failures = 0
        previous_high_value_count = -1

        for round_index in range(1, rounds + 1):
            self._emit(f"[package] 第 {round_index}/{rounds} 轮：生成题包组件。")
            round_dir = run_dir / f"round{round_index}"
            round_dir.mkdir(parents=True, exist_ok=True)
            package = self._generate_round_package(context, revision_context)
            self._write_round_package(round_dir, package)

            self._emit(f"[package] 第 {round_index}/{rounds} 轮：执行验证矩阵。")
            report = self._validate_package(package)
            self._write_report(round_dir, report)

            high_value_count = len([item for item in report.issues if item.get("severity") in {"blocker", "high"}])
            if high_value_count == previous_high_value_count:
                no_new_high_value_failures += 1
            else:
                no_new_high_value_failures = 0
            previous_high_value_count = high_value_count

            final_round_index = round_index
            last_package = package
            round_record = {
                "round_index": round_index,
                "round_dir": str(round_dir),
                "status": report.overall["status"],
                "issue_count": report.overall["issue_count"],
                "kill_rate": report.wrong_solution_stats.get("kill_rate", 0.0),
            }
            round_records.append(round_record)

            if report.overall["status"] == "pass":
                final_status = "pass"
                stop_reason = "all_checks_passed"
                break
            if no_new_high_value_failures >= 1 and round_index >= 2:
                final_status = "not_deliverable"
                stop_reason = "no_new_high_value_failure_samples"
                revision_context = report.revision_context
                break
            revision_context = report.revision_context

        if last_package is not None:
            final_dir = run_dir / "final"
            self._write_round_package(final_dir, last_package)

        summary = IterationSummary(
            run_id=run_id,
            problem_id=problem_id,
            requested_rounds=rounds,
            final_status=final_status,
            final_round_index=final_round_index,
            stop_reason=stop_reason,
            rounds=round_records,
        )
        summary_path = run_dir / "iteration_summary.json"
        summary_path.write_text(json.dumps(to_dict(summary), ensure_ascii=False, indent=2), encoding="utf-8")
        return {"run_dir": str(run_dir), "summary_path": str(summary_path), "summary": to_dict(summary)}

    def _generate_round_package(self, context: dict[str, Any], revision_context: dict[str, Any]) -> dict[str, Any]:
        spec = self.spec_extractor.generate(context, revision_context)
        standard = self.standard_generator.generate(context, spec, revision_context)
        oracle = self.oracle_generator.generate(context, spec, revision_context)
        tools = self.tool_generator.generate(context, spec, revision_context)
        weak_wrong = self.weak_player_generator.generate(_statement_only_context(context), revision_context)
        wrong_solutions = [*weak_wrong, *build_rule_based_wrong_solutions(spec, standard.code)]
        return {
            "context": context,
            "execution_spec": spec,
            "standard_solution": standard,
            "oracle_solution": oracle,
            "validator": tools["validator"],
            "checker": tools["checker"],
            "test_generator": tools["test_generator"],
            "wrong_solutions": wrong_solutions,
        }

    def _validate_package(self, package: dict[str, Any]) -> ValidationReport:
        spec: ExecutionSpec = package["execution_spec"]
        standard: GeneratedCodeArtifact = package["standard_solution"]
        oracle: GeneratedCodeArtifact = package["oracle_solution"]
        validator: GeneratedCodeArtifact = package["validator"]
        checker: GeneratedCodeArtifact = package["checker"]
        test_generator: GeneratedCodeArtifact = package["test_generator"]
        wrong_solutions: list[WrongSolution] = package["wrong_solutions"]

        issues: list[FailureIssue] = []
        matrix: list[dict[str, Any]] = []

        generated_tests_result = self.runner.run_generate_tests(
            artifact_name=test_generator.name,
            code=test_generator.code,
            timeout_s=self.run_timeout_s,
        )
        matrix.append(to_dict(generated_tests_result))
        if generated_tests_result.status != "ok":
            issues.append(
                FailureIssue(
                    category="test_generator_failed",
                    severity="blocker",
                    title="测试生成器执行失败",
                    detail=generated_tests_result.error_reason,
                    fix_hint="回流 ToolGenerator，修复 test_generator 接口或运行错误。",
                )
            )
            tests: list[TestCase] = []
        else:
            try:
                tests = normalize_tests(generated_tests_result.result, spec)
            except ValueError as exc:
                issues.append(
                    FailureIssue(
                        category="test_generator_failed",
                        severity="blocker",
                        title="测试生成器返回结构非法",
                        detail=str(exc),
                        fix_hint="回流 ToolGenerator，要求 generate_tests 返回 list[dict]。",
                    )
                )
                tests = []
        if not tests:
            issues.append(
                FailureIssue(
                    category="test_suite_empty",
                    severity="blocker",
                    title="测试生成器未产出有效测试",
                    detail="generate_tests 未返回任何可执行输入，无法验证标准解、oracle 和错误解池。",
                    fix_hint="回流 ToolGenerator，要求 test_generator 至少生成样例、边界和基础随机测试。",
                )
            )

        expected_outputs: dict[str, str] = {}
        for test in tests:
            validation = self.runner.run_validate(
                artifact_name=validator.name,
                code=validator.code,
                input_data=test.input,
                test_source=test.source,
                timeout_s=self.run_timeout_s,
            )
            matrix.append(to_dict(validation))
            if validation.status != "ok" or validation.result is not True:
                issues.append(
                    FailureIssue(
                        category="validator_rejects_generated_case",
                        severity="high",
                        title="validator 拒绝生成测试",
                        detail=f"测试 {test.source} 未通过输入合法性检查。",
                        evidence_refs=[test.source],
                        fix_hint="回流 ToolGenerator 或测试生成器，修正输入约束或测试生成逻辑。",
                    )
                )
                continue

            timeout = self.large_run_timeout_s if test.is_large else self.run_timeout_s
            standard_result = self.runner.run_solve(
                artifact_name=standard.name,
                code=standard.code,
                input_data=test.input,
                test_source=test.source,
                timeout_s=timeout,
            )
            matrix.append(to_dict(standard_result))
            if standard_result.status != "ok":
                issues.append(
                    FailureIssue(
                        category="performance_failure" if standard_result.status == "timeout" or test.is_large else "standard_solution_failed",
                        severity="blocker",
                        title="标准解执行失败",
                        detail=standard_result.error_reason or standard_result.status,
                        evidence_refs=[test.source],
                        fix_hint="回流 StandardSolutionGenerator，修正实现或复杂度。",
                    )
                )
                continue
            expected_outputs[test.source] = str(standard_result.result)

            oracle_expected: str | None = None
            if test.expect_oracle and not test.is_large:
                oracle_result = self.runner.run_solve(
                    artifact_name=oracle.name,
                    code=oracle.code,
                    input_data=test.input,
                    test_source=test.source,
                    timeout_s=self.run_timeout_s,
                )
                matrix.append(to_dict(oracle_result))
                if oracle_result.status != "ok":
                    issues.append(
                        FailureIssue(
                            category="oracle_failed",
                            severity="high",
                            title="oracle 执行失败",
                            detail=oracle_result.error_reason or oracle_result.status,
                            evidence_refs=[test.source],
                            fix_hint="回流 OracleGenerator，修正暴力逻辑或适用范围。",
                        )
                    )
                else:
                    oracle_expected = str(oracle_result.result)
                    if _normalize_output(oracle_expected) != _normalize_output(str(standard_result.result)):
                        issues.append(
                            FailureIssue(
                                category="standard_oracle_mismatch",
                                severity="blocker",
                                title="标准解与 oracle 不一致",
                                detail=f"测试 {test.source} 上标准解输出与 oracle 输出不同。",
                                evidence_refs=[test.source],
                                fix_hint="回流 StandardSolutionGenerator 与 OracleGenerator，定位反例。",
                            )
                        )

            checker_result = self.runner.run_check(
                artifact_name=checker.name,
                code=checker.code,
                input_data=test.input,
                output_data=str(standard_result.result),
                expected_data=oracle_expected,
                test_source=test.source,
                timeout_s=self.run_timeout_s,
            )
            matrix.append(to_dict(checker_result))
            if checker_result.status != "ok" or checker_result.result is not True:
                issues.append(
                    FailureIssue(
                        category="checker_rejects_standard_output",
                        severity="blocker",
                        title="checker 拒绝标准解输出",
                        detail=checker_result.error_reason or f"测试 {test.source} 的标准输出未被 checker 接受。",
                        evidence_refs=[test.source],
                        fix_hint="回流 ToolGenerator 和 StandardSolutionGenerator，确认 checker 合法性谓词与标准解输出。",
                    )
                )

        curator = WrongSolutionCurator(runner=self.runner, kill_rate_threshold=self.kill_rate_threshold)
        curation = curator.curate(
            candidates=wrong_solutions,
            tests=tests,
            checker_code=checker.code,
            expected_outputs=expected_outputs,
        )
        matrix.extend(curation["matrix"])
        wrong_stats = curation["stats"]
        if not wrong_stats["passed_threshold"]:
            issues.append(
                FailureIssue(
                    category="wrong_solution_survived",
                    severity="high",
                    title="错误解杀伤率不足",
                    detail=f"当前杀伤率 {wrong_stats['kill_rate']}，低于阈值 {wrong_stats['kill_rate_threshold']}。",
                    fix_hint="回流测试生成器，针对幸存错误解补充反例。",
                )
            )

        status = "pass" if not [item for item in issues if item.severity in {"blocker", "high"}] else "revise"
        revision_context = _build_revision_context(issues, curation)
        report = ValidationReport(
            overall={
                "status": status,
                "issue_count": len(issues),
                "stop_reason": "" if status == "pass" else "validation_failed",
            },
            issues=[to_dict(item) for item in issues],
            execution_matrix=matrix,
            wrong_solution_stats=wrong_stats,
            revision_context=revision_context,
        )
        return report

    def _write_round_package(self, round_dir: Path, package: dict[str, Any]) -> None:
        round_dir.mkdir(parents=True, exist_ok=True)
        (round_dir / "execution_spec.json").write_text(
            json.dumps(to_dict(package["execution_spec"]), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _write_code_artifact(round_dir / "standard_solution.py", package["standard_solution"])
        _write_code_artifact(round_dir / "oracle_solution.py", package["oracle_solution"])
        _write_code_artifact(round_dir / "validator.py", package["validator"])
        _write_code_artifact(round_dir / "checker.py", package["checker"])
        _write_code_artifact(round_dir / "test_generator.py", package["test_generator"])
        wrong_dir = round_dir / "wrong_solutions"
        if wrong_dir.exists():
            shutil.rmtree(wrong_dir)
        wrong_dir.mkdir(parents=True, exist_ok=True)
        for item in package["wrong_solutions"]:
            solution_dir = wrong_dir / _safe_name(item.solution_id)
            solution_dir.mkdir(parents=True, exist_ok=True)
            (solution_dir / "solution.py").write_text(item.code, encoding="utf-8")
            (solution_dir / "metadata.json").write_text(
                json.dumps(to_dict(item), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def _write_report(self, round_dir: Path, report: ValidationReport) -> None:
        payload = to_dict(report)
        (round_dir / "execution_report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        (round_dir / "execution_report.md").write_text(render_execution_report_markdown(payload), encoding="utf-8")

    def _emit(self, message: str) -> None:
        self.progress_writer(message)


def _build_context(
    *,
    artifact: dict[str, Any],
    markdown: str,
    artifact_path: Path,
    markdown_path: Path | None,
) -> dict[str, Any]:
    generated_problem = artifact.get("generated_problem", {}) if isinstance(artifact.get("generated_problem"), dict) else {}
    new_schema = artifact.get("new_schema") or artifact.get("new_schema_snapshot") or {}
    problem_id = str(artifact.get("problem_id") or new_schema.get("problem_id") or generated_problem.get("title") or "generated_problem")
    return {
        "problem_id": problem_id,
        "artifact_path": str(artifact_path),
        "markdown_path": str(markdown_path) if markdown_path else "",
        "statement_markdown": markdown,
        "generated_problem": generated_problem,
        "new_schema": new_schema,
        "algorithmic_delta_claim": artifact.get("algorithmic_delta_claim", {}),
        "difference_plan": artifact.get("difference_plan", {}),
        "applied_rule": artifact.get("applied_rule", ""),
    }


def _statement_only_context(context: dict[str, Any]) -> dict[str, Any]:
    generated_problem = dict(context.get("generated_problem", {}) or {})
    return {
        "problem_id": context.get("problem_id", ""),
        "statement_markdown": context.get("statement_markdown", ""),
        "generated_problem": generated_problem,
    }


def _build_revision_context(issues: list[FailureIssue], curation: dict[str, Any]) -> dict[str, Any]:
    by_category: dict[str, list[str]] = {}
    for issue in issues:
        by_category.setdefault(issue.category, []).append(issue.detail)
    return {
        "issues_by_category": by_category,
        "failed_hard_checks": [issue.category for issue in issues if issue.severity == "blocker"],
        "tool_feedback": by_category.get("validator_rejects_generated_case", [])
        + by_category.get("checker_rejects_standard_output", [])
        + by_category.get("test_generator_failed", []),
        "solution_feedback": by_category.get("standard_solution_failed", [])
        + by_category.get("standard_oracle_mismatch", [])
        + by_category.get("performance_failure", []),
        "oracle_feedback": by_category.get("oracle_failed", []) + by_category.get("standard_oracle_mismatch", []),
        "test_feedback": by_category.get("wrong_solution_survived", []),
        "surviving_wrong_solutions": [
            item["solution_id"]
            for item in curation.get("independent_solutions", [])
        ],
    }


def _write_code_artifact(path: Path, artifact: GeneratedCodeArtifact) -> None:
    path.write_text(artifact.code, encoding="utf-8")
    path.with_suffix(path.suffix + ".metadata.json").write_text(
        json.dumps(to_dict(artifact), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_run_id(problem_id: str) -> str:
    return f"{_safe_name(problem_id)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def _safe_name(text: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in str(text))
    return cleaned.strip("_") or "generated"


def _normalize_output(text: str) -> str:
    return "\n".join(line.rstrip() for line in str(text).strip().splitlines()).strip()
