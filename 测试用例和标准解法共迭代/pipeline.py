from __future__ import annotations

import json
import shutil
import copy
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from config import DEFAULT_KILL_RATE_THRESHOLD, DEFAULT_LARGE_RUN_TIMEOUT_S, DEFAULT_OUTPUT_DIR, DEFAULT_RUN_TIMEOUT_S
from curation import WrongSolutionCurator
from execution_spec import normalize_tests
from generators import (
    OracleGenerator,
    RevisionAdvisor,
    SchemaAwareWrongSolutionGenerator,
    SchemaMistakeAnalyzer,
    SpecExtractor,
    StandardSolutionGenerator,
    ToolGenerator,
    WeakPlayerGenerator,
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
        schema_mistake_analyzer: SchemaMistakeAnalyzer | None = None,
        schema_wrong_solution_generator: SchemaAwareWrongSolutionGenerator | None = None,
        revision_advisor: Any | None = None,
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
        self.schema_mistake_analyzer = schema_mistake_analyzer or SchemaMistakeAnalyzer(client)
        self.schema_wrong_solution_generator = schema_wrong_solution_generator or SchemaAwareWrongSolutionGenerator(client)
        self.revision_advisor = revision_advisor if revision_advisor is not None else (RevisionAdvisor(client) if client is not None else None)
        self.progress_writer = progress_writer or (lambda message: print(message, flush=True))

    def run(
        self,
        *,
        artifact_path: Path,
        markdown_path: Path | None = None,
        rounds: int = 6,
    ) -> dict[str, Any]:
        artifact = _read_json(artifact_path)
        markdown = markdown_path.read_text(encoding="utf-8") if markdown_path and markdown_path.exists() else ""
        context = _build_context(artifact=artifact, markdown=markdown, artifact_path=artifact_path, markdown_path=markdown_path)
        problem_id = context["problem_id"]
        run_id = _build_run_id(problem_id)
        run_dir = self.output_dir / problem_id / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        self._emit(f"[启动] 题目 {problem_id}：最多迭代 {rounds} 轮，输出目录 {run_dir}。")

        active_revision_context: dict[str, Any] = {}
        revision_audit_history: list[dict[str, Any]] = []
        context_stats = _empty_context_stats()
        round_records: list[dict[str, Any]] = []
        final_status = "not_deliverable"
        stop_reason = "reached_requested_rounds"
        final_round_index = 0
        current_package: dict[str, Any] | None = None
        no_new_high_value_failures = 0
        previous_high_value_count = -1

        for round_index in range(1, rounds + 1):
            self._emit(f"[轮次] 第 {round_index}/{rounds} 轮：准备修订上下文。")
            round_dir = run_dir / f"round{round_index}"
            round_dir.mkdir(parents=True, exist_ok=True)
            generation_revision_context = _build_generation_revision_context(
                active_revision_context=active_revision_context,
                revision_audit_history=revision_audit_history,
                current_package=current_package,
                round_index=round_index,
            )
            if current_package is None:
                self._emit(f"[生成] 第 {round_index}/{rounds} 轮：全量生成题包组件。")
                package = self._generate_round_package(context, generation_revision_context)
            else:
                self._emit(f"[生成] 第 {round_index}/{rounds} 轮：基于上一轮结果增量修订题包。")
                package = self._generate_incremental_round_package(context, current_package, generation_revision_context)
            self._emit(f"[写入] 第 {round_index}/{rounds} 轮：写入题包产物。")
            self._write_round_package(round_dir, package)

            self._emit(f"[验证] 第 {round_index}/{rounds} 轮：执行验证矩阵。")
            report = self._validate_package(package, previous_active_context=active_revision_context)
            self._emit(f"[写入] 第 {round_index}/{rounds} 轮：写入执行报告。")
            self._write_report(round_dir, report)
            revision_audit_history.append({"round_index": round_index, "revision_context": report.revision_context})
            active_revision_context, context_stats = _update_active_revision_context(
                active_revision_context,
                report.revision_context,
            )
            self._emit(
                f"[回流] 第 {round_index}/{rounds} 轮：active={context_stats['active_issue_count']}，"
                f"新增={context_stats['new_issue_count']}，解决={context_stats['resolved_issue_count']}，"
                f"延续={context_stats['carried_issue_count']}。"
            )

            high_value_count = len([item for item in report.issues if item.get("severity") in {"blocker", "high"}])
            if high_value_count == previous_high_value_count:
                no_new_high_value_failures += 1
            else:
                no_new_high_value_failures = 0
            previous_high_value_count = high_value_count

            final_round_index = round_index
            current_package = package
            round_record = {
                "round_index": round_index,
                "round_dir": str(round_dir),
                "status": report.overall["status"],
                "issue_count": report.overall["issue_count"],
                "kill_rate": report.wrong_solution_stats.get("kill_rate", 0.0),
                **context_stats,
            }
            round_records.append(round_record)
            self._emit(
                f"[轮次] 第 {round_index}/{rounds} 轮完成：状态={report.overall['status']}，"
                f"问题数={report.overall['issue_count']}，杀伤率={report.wrong_solution_stats.get('kill_rate')}。"
            )

            if report.overall["status"] == "pass":
                final_status = "pass"
                stop_reason = "all_checks_passed"
                self._emit(f"[停止] 第 {round_index}/{rounds} 轮：全部检查通过。")
                break
            if no_new_high_value_failures >= 1 and round_index >= 2:
                final_status = "not_deliverable"
                stop_reason = "no_new_high_value_failure_samples"
                self._emit(f"[停止] 第 {round_index}/{rounds} 轮：高价值失败样本未继续增加。")
                break

        if current_package is not None:
            final_dir = run_dir / "final"
            self._emit(f"[写入] 写入最终题包产物：{final_dir}。")
            self._write_round_package(final_dir, current_package)
        self._emit("[写入] 写入修订审计历史。")
        (run_dir / "revision_audit_history.json").write_text(
            json.dumps(revision_audit_history, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        summary = IterationSummary(
            run_id=run_id,
            problem_id=problem_id,
            requested_rounds=rounds,
            final_status=final_status,
            final_round_index=final_round_index,
            stop_reason=stop_reason,
            rounds=round_records,
            active_issue_count=context_stats["active_issue_count"],
            new_issue_count=context_stats["new_issue_count"],
            resolved_issue_count=context_stats["resolved_issue_count"],
            carried_issue_count=context_stats["carried_issue_count"],
        )
        summary_path = run_dir / "iteration_summary.json"
        summary_path.write_text(json.dumps(to_dict(summary), ensure_ascii=False, indent=2), encoding="utf-8")
        self._emit(f"[完成] 迭代结束：final_status={final_status}，stop_reason={stop_reason}，摘要 {summary_path}。")
        return {"run_dir": str(run_dir), "summary_path": str(summary_path), "summary": to_dict(summary)}

    def _generate_incremental_round_package(
        self,
        context: dict[str, Any],
        current_package: dict[str, Any],
        revision_context: dict[str, Any],
    ) -> dict[str, Any]:
        package = copy.deepcopy(current_package)
        roles = _target_roles_for_revision(revision_context)
        if not roles:
            self._emit("[生成] 增量修订：未命中需要重生成的角色，沿用当前题包。")
            return package
        self._emit(f"[生成] 增量修订：命中角色 {', '.join(sorted(roles))}。")

        if "SpecExtractor" in roles:
            roles.update(
                {
                    "StandardSolutionGenerator",
                    "OracleGenerator",
                    "ToolGenerator",
                    "SchemaMistakeAnalyzer",
                    "SchemaAwareWrongSolutionGenerator",
                }
            )
            self._emit("[生成] 增量修订：重生成 execution_spec，并级联重生成依赖组件。")
            package["execution_spec"] = self.spec_extractor.generate(
                context,
                _revision_context_for_roles(revision_context, {"SpecExtractor"}, current_package),
            )

        spec = package["execution_spec"]
        if "StandardSolutionGenerator" in roles:
            self._emit("[生成] 增量修订：重生成标准解。")
            package["standard_solution"] = self.standard_generator.generate(
                context,
                spec,
                _revision_context_for_roles(revision_context, {"StandardSolutionGenerator"}, current_package),
            )
        if "OracleGenerator" in roles:
            self._emit("[生成] 增量修订：重生成 oracle。")
            package["oracle_solution"] = self.oracle_generator.generate(
                context,
                spec,
                _revision_context_for_roles(revision_context, {"OracleGenerator"}, current_package),
            )
        if "ToolGenerator" in roles:
            self._emit("[生成] 增量修订：重生成 validator、checker 和 test_generator。")
            tools = self.tool_generator.generate(
                context,
                spec,
                _revision_context_for_roles(revision_context, {"ToolGenerator"}, current_package),
            )
            package["validator"] = tools["validator"]
            package["checker"] = tools["checker"]
            package["test_generator"] = tools["test_generator"]

        weak_wrong, schema_wrong = _split_wrong_solutions(package.get("wrong_solutions", []))
        if "WeakPlayerGenerator" in roles:
            self._emit("[生成] 增量修订：重生成弱选手错误解。")
            weak_wrong = self.weak_player_generator.generate(
                _statement_only_context(context),
                _revision_context_for_roles(revision_context, {"WeakPlayerGenerator"}, current_package),
            )
            self._emit(f"[生成] 增量修订：弱选手错误解 {len(weak_wrong)} 个。")
        if "SchemaMistakeAnalyzer" in roles:
            self._emit("[生成] 增量修订：重新分析 schema 误解点。")
            package["schema_mistake_points"] = self.schema_mistake_analyzer.generate(
                context,
                spec,
                _revision_context_for_roles(revision_context, {"SchemaMistakeAnalyzer"}, current_package),
            )
            self._emit(f"[生成] 增量修订：schema 误解点 {len(package['schema_mistake_points'])} 个。")
            roles.add("SchemaAwareWrongSolutionGenerator")
        if "SchemaAwareWrongSolutionGenerator" in roles:
            self._emit("[生成] 增量修订：重生成 schema-aware 错误解。")
            schema_wrong = self.schema_wrong_solution_generator.generate(
                context,
                spec,
                package.get("schema_mistake_points", []),
                _revision_context_for_roles(revision_context, {"SchemaAwareWrongSolutionGenerator"}, current_package),
            )
            self._emit(f"[生成] 增量修订：schema-aware 错误解 {len(schema_wrong)} 个。")
        package["wrong_solutions"] = [*weak_wrong, *schema_wrong]
        self._emit(f"[生成] 增量修订完成：错误解候选共 {len(package['wrong_solutions'])} 个。")
        return package

    def _generate_round_package(self, context: dict[str, Any], revision_context: dict[str, Any]) -> dict[str, Any]:
        self._emit("[生成] 抽取 execution_spec。")
        spec = self.spec_extractor.generate(context, revision_context)
        self._emit("[生成] 生成标准解。")
        standard = self.standard_generator.generate(context, spec, revision_context)
        self._emit("[生成] 生成 oracle。")
        oracle = self.oracle_generator.generate(context, spec, revision_context)
        self._emit("[生成] 生成 validator、checker 和 test_generator。")
        tools = self.tool_generator.generate(context, spec, revision_context)
        self._emit("[生成] 生成弱选手错误解。")
        weak_wrong = self.weak_player_generator.generate(_statement_only_context(context), revision_context)
        self._emit(f"[生成] 弱选手错误解 {len(weak_wrong)} 个。")
        self._emit("[生成] 分析 schema 误解点。")
        mistake_points = self.schema_mistake_analyzer.generate(context, spec, revision_context)
        self._emit(f"[生成] schema 误解点 {len(mistake_points)} 个。")
        self._emit("[生成] 生成 schema-aware 错误解。")
        schema_wrong = self.schema_wrong_solution_generator.generate(context, spec, mistake_points, revision_context)
        self._emit(f"[生成] schema-aware 错误解 {len(schema_wrong)} 个。")
        wrong_solutions = [*weak_wrong, *schema_wrong]
        self._emit(f"[生成] 全量题包生成完成：错误解候选共 {len(wrong_solutions)} 个。")
        return {
            "context": context,
            "execution_spec": spec,
            "standard_solution": standard,
            "oracle_solution": oracle,
            "validator": tools["validator"],
            "checker": tools["checker"],
            "test_generator": tools["test_generator"],
            "schema_mistake_points": mistake_points,
            "wrong_solutions": wrong_solutions,
        }

    def _validate_package(
        self,
        package: dict[str, Any],
        previous_active_context: dict[str, Any] | None = None,
    ) -> ValidationReport:
        spec: ExecutionSpec = package["execution_spec"]
        standard: GeneratedCodeArtifact = package["standard_solution"]
        oracle: GeneratedCodeArtifact = package["oracle_solution"]
        validator: GeneratedCodeArtifact = package["validator"]
        checker: GeneratedCodeArtifact = package["checker"]
        test_generator: GeneratedCodeArtifact = package["test_generator"]
        wrong_solutions: list[WrongSolution] = package["wrong_solutions"]

        issues: list[FailureIssue] = []
        matrix: list[dict[str, Any]] = []
        expected_outputs: dict[str, str] = {}
        base_checks: dict[str, Any] = {
            "passed": True,
            "failed_categories": [],
            "validated_test_count": 0,
            "standard_checked_count": 0,
            "oracle_checked_count": 0,
            "wrong_solution_curation_skipped": False,
        }

        self._emit("[验证] 运行 test_generator，生成测试用例。")
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
        self._emit(f"[验证] 可执行测试用例数量：{len(tests)}。")
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

        for test_index, test in enumerate(tests, start=1):
            test_label = _progress_test_label(test)
            self._emit(f"[验证] 测试 {test_index}/{len(tests)}（{test_label}）：运行 validator。")
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
                        evidence=_build_failure_evidence(test=test, validator_result=validation),
                        fix_hint="回流 ToolGenerator 或测试生成器，修正输入约束或测试生成逻辑。",
                    )
                )
                continue
            base_checks["validated_test_count"] += 1

            timeout = self.large_run_timeout_s if test.is_large else self.run_timeout_s
            self._emit(f"[验证] 测试 {test_index}/{len(tests)}（{test_label}）：运行标准解。")
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
                        evidence=_build_failure_evidence(test=test, standard_result=standard_result),
                        fix_hint="回流 StandardSolutionGenerator，修正实现或复杂度。",
                    )
                )
                continue
            expected_outputs[test.source] = str(standard_result.result)

            oracle_expected: str | None = None
            oracle_result = None
            oracle_mismatch = False
            if test.expect_oracle and not test.is_large:
                self._emit(f"[验证] 测试 {test_index}/{len(tests)}（{test_label}）：运行 oracle。")
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
                            evidence=_build_failure_evidence(
                                test=test,
                                standard_output=standard_result.result,
                                oracle_result=oracle_result,
                            ),
                            fix_hint="回流 OracleGenerator，修正暴力逻辑或适用范围。",
                        )
                    )
                else:
                    oracle_expected = str(oracle_result.result)
                    if spec.judge_type == "exact" and _normalize_output(oracle_expected) != _normalize_output(str(standard_result.result)):
                        oracle_mismatch = True

            self._emit(f"[验证] 测试 {test_index}/{len(tests)}（{test_label}）：运行 checker 校验标准解输出。")
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
            if oracle_mismatch:
                issues.append(
                    FailureIssue(
                        category="standard_oracle_mismatch",
                        severity="blocker",
                        title="标准解与 oracle 不一致",
                        detail=f"测试 {test.source} 上标准解输出与 oracle 输出不同。",
                        evidence_refs=[test.source],
                        evidence=_build_failure_evidence(
                            test=test,
                            standard_output=standard_result.result,
                            oracle_output=oracle_expected,
                            checker_result=checker_result,
                        ),
                        fix_hint="回流 StandardSolutionGenerator 与 OracleGenerator，定位反例。",
                    )
                )
            if checker_result.status != "ok" or checker_result.result is not True:
                issues.append(
                    FailureIssue(
                        category="checker_rejects_standard_output",
                        severity="blocker",
                        title="checker 拒绝标准解输出",
                        detail=_checker_reject_detail(spec, checker_result.error_reason or f"测试 {test.source} 的标准输出未被 checker 接受。"),
                        evidence_refs=[test.source],
                        evidence=_build_failure_evidence(
                            test=test,
                            standard_output=standard_result.result,
                            oracle_output=oracle_expected,
                            checker_result=checker_result,
                        ),
                        fix_hint="回流 ToolGenerator 和 StandardSolutionGenerator，确认 checker 合法性谓词与标准解输出。",
                    )
                )
            else:
                base_checks["standard_checked_count"] += 1

            if spec.judge_type == "checker" and oracle_expected is not None:
                self._emit(f"[验证] 测试 {test_index}/{len(tests)}（{test_label}）：运行 checker 校验 oracle 输出。")
                oracle_checker_result = self.runner.run_check(
                    artifact_name=checker.name,
                    code=checker.code,
                    input_data=test.input,
                    output_data=oracle_expected,
                    expected_data=oracle_expected,
                    test_source=test.source,
                    timeout_s=self.run_timeout_s,
                )
                matrix.append(to_dict(oracle_checker_result))
                if oracle_checker_result.status != "ok" or oracle_checker_result.result is not True:
                    issues.append(
                        FailureIssue(
                            category="oracle_output_rejected_by_checker",
                            severity="blocker",
                            title="checker 拒绝 oracle 输出",
                            detail=_checker_reject_detail(
                                spec,
                                oracle_checker_result.error_reason or f"测试 {test.source} 的 oracle 输出未被 checker 接受。",
                            ),
                            evidence_refs=[test.source],
                            evidence=_build_failure_evidence(
                                test=test,
                                standard_output=standard_result.result,
                                oracle_output=oracle_expected,
                                checker_result=oracle_checker_result,
                            ),
                            fix_hint="回流 ToolGenerator 和 OracleGenerator，确认 checker 合法性谓词与 oracle 输出。",
                        )
                    )
                else:
                    base_checks["oracle_checked_count"] += 1

        baseline_issues = [item for item in issues if item.severity in {"blocker", "high"}]
        if baseline_issues:
            base_checks["passed"] = False
            base_checks["failed_categories"] = [item.category for item in baseline_issues]
            base_checks["wrong_solution_curation_skipped"] = True
            curation = {
                "independent_solutions": [],
                "matrix": [],
            }
            self._emit(
                f"[筛选] 基础自洽失败，跳过错误解筛选；候选错误解 {len(wrong_solutions)} 个。"
            )
            wrong_stats = _skipped_wrong_solution_stats(
                candidate_count=len(wrong_solutions),
                kill_rate_threshold=self.kill_rate_threshold,
            )
            issues.append(
                FailureIssue(
                    category="kill_rate_skipped_due_to_invalid_baseline",
                    severity="high",
                    title="基础自洽失败，跳过错误解杀伤率统计",
                    detail="validator、标准解、oracle 或 checker 的基础自洽检查未通过，本轮杀伤率不可作为可信指标。",
                    fix_hint="优先修复基础自洽问题，再重新执行错误解筛选。",
                )
            )
        else:
            self._emit(f"[筛选] 开始错误解筛选：候选错误解 {len(wrong_solutions)} 个，测试 {len(tests)} 个。")
            curator = WrongSolutionCurator(runner=self.runner, kill_rate_threshold=self.kill_rate_threshold)
            curation = curator.curate(
                candidates=wrong_solutions,
                tests=tests,
                checker_code=checker.code,
                expected_outputs=expected_outputs,
            )
            matrix.extend(curation["matrix"])
            wrong_stats = curation["stats"]
            wrong_stats["valid"] = True
            wrong_stats["skip_reason"] = ""
            self._emit(
                f"[筛选] 错误解筛选完成：杀伤率={wrong_stats['kill_rate']}，"
                f"阈值={wrong_stats['kill_rate_threshold']}，达标={wrong_stats['passed_threshold']}。"
            )
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
        revision_context = _build_revision_context(
            issues,
            curation,
            revision_advisor=self.revision_advisor,
            current_package=package,
            previous_active_context=previous_active_context,
        )
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
            base_consistency=base_checks,
        )
        return report

    def _write_round_package(self, round_dir: Path, package: dict[str, Any]) -> None:
        round_dir.mkdir(parents=True, exist_ok=True)
        (round_dir / "execution_spec.json").write_text(
            json.dumps(to_dict(package["execution_spec"]), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (round_dir / "schema_mistake_points.json").write_text(
            json.dumps(to_dict(package.get("schema_mistake_points", [])), ensure_ascii=False, indent=2),
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


def _progress_test_label(test: TestCase) -> str:
    source = str(test.source or "unknown").replace("\n", " ").strip()
    if len(source) <= 60:
        return source
    return f"{source[:57]}..."


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


def _empty_context_stats() -> dict[str, int]:
    return {
        "active_issue_count": 0,
        "new_issue_count": 0,
        "resolved_issue_count": 0,
        "carried_issue_count": 0,
    }


def _build_generation_revision_context(
    *,
    active_revision_context: dict[str, Any],
    revision_audit_history: list[dict[str, Any]],
    current_package: dict[str, Any] | None,
    round_index: int,
) -> dict[str, Any]:
    if not active_revision_context:
        return {}
    context = copy.deepcopy(active_revision_context)
    context.update(
        {
            "active_revision_context": copy.deepcopy(active_revision_context),
            "latest_revision": copy.deepcopy(revision_audit_history[-1]["revision_context"]) if revision_audit_history else {},
            "revision_history": copy.deepcopy(revision_audit_history),
            "revision_mode": "incremental_patch",
            "baseline_round": 1,
            "current_round": round_index,
            "current_artifact": _current_artifact_summary(current_package, None),
            "frozen_contract_summary": _frozen_contract_summary(current_package),
        }
    )
    return context


def _update_active_revision_context(
    previous_active: dict[str, Any],
    latest_revision: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, int]]:
    previous_by_fingerprint = _diagnostics_by_fingerprint(previous_active)
    latest_by_fingerprint = _diagnostics_by_fingerprint(latest_revision)
    previous_fingerprints = set(previous_by_fingerprint)
    latest_fingerprints = set(latest_by_fingerprint)

    resolved = previous_fingerprints - latest_fingerprints
    carried = previous_fingerprints & latest_fingerprints
    new = latest_fingerprints - previous_fingerprints
    active_diagnostics = [latest_by_fingerprint[fingerprint] for fingerprint in sorted(latest_fingerprints)]
    active_context = _revision_context_from_diagnostics(
        active_diagnostics,
        latest_revision.get("surviving_wrong_solution_details", []),
    )
    active_context["context_management"] = {
        "resolved_issue_fingerprints": sorted(resolved),
        "new_issue_fingerprints": sorted(new),
        "carried_issue_fingerprints": sorted(carried),
    }
    stats = {
        "active_issue_count": len(latest_fingerprints),
        "new_issue_count": len(new),
        "resolved_issue_count": len(resolved),
        "carried_issue_count": len(carried),
    }
    return active_context, stats


def _target_roles_for_revision(revision_context: dict[str, Any]) -> set[str]:
    role_diagnostics = revision_context.get("role_diagnostics")
    if not isinstance(role_diagnostics, dict):
        return set()
    return {str(role) for role, diagnostics in role_diagnostics.items() if diagnostics}


def _revision_context_for_roles(
    revision_context: dict[str, Any],
    roles: set[str],
    current_package: dict[str, Any] | None,
) -> dict[str, Any]:
    diagnostics = [
        diagnostic
        for diagnostic in _flatten_diagnostics(revision_context)
        if roles & {str(role) for role in diagnostic.get("target_roles", [])}
    ]
    filtered = _revision_context_from_diagnostics(
        diagnostics,
        revision_context.get("surviving_wrong_solution_details", []),
    )
    filtered.update(
        {
            "active_revision_context": copy.deepcopy(filtered),
            "latest_revision": copy.deepcopy(revision_context.get("latest_revision", {})),
            "revision_history": copy.deepcopy(revision_context.get("revision_history", [])),
            "revision_mode": revision_context.get("revision_mode", "incremental_patch"),
            "baseline_round": revision_context.get("baseline_round", 1),
            "current_round": revision_context.get("current_round", 0),
            "current_artifact": _current_artifact_summary(current_package, roles),
            "frozen_contract_summary": _frozen_contract_summary(current_package),
        }
    )
    return filtered


def _split_wrong_solutions(wrong_solutions: list[WrongSolution]) -> tuple[list[WrongSolution], list[WrongSolution]]:
    weak_wrong: list[WrongSolution] = []
    schema_wrong: list[WrongSolution] = []
    for item in wrong_solutions:
        if item.source == "schema_aware_llm_player":
            schema_wrong.append(item)
        else:
            weak_wrong.append(item)
    return weak_wrong, schema_wrong


def _current_artifact_summary(current_package: dict[str, Any] | None, roles: set[str] | None) -> dict[str, Any]:
    if not current_package:
        return {}
    include_all = roles is None
    summary: dict[str, Any] = {}
    if include_all or "SpecExtractor" in roles:
        summary["execution_spec"] = to_dict(current_package.get("execution_spec"))
    if include_all or "StandardSolutionGenerator" in roles:
        summary["standard_solution"] = _code_artifact_for_context(current_package.get("standard_solution"))
    if include_all or "OracleGenerator" in roles:
        summary["oracle_solution"] = _code_artifact_for_context(current_package.get("oracle_solution"))
    if include_all or "ToolGenerator" in roles:
        summary["validator"] = _code_artifact_for_context(current_package.get("validator"))
        summary["checker"] = _code_artifact_for_context(current_package.get("checker"))
        summary["test_generator"] = _code_artifact_for_context(current_package.get("test_generator"))
    if include_all or "SchemaMistakeAnalyzer" in roles:
        summary["schema_mistake_points"] = to_dict(current_package.get("schema_mistake_points", []))
    if include_all or {"WeakPlayerGenerator", "SchemaAwareWrongSolutionGenerator"} & roles:
        summary["wrong_solutions"] = [
            {
                "solution_id": item.solution_id,
                "source": item.source,
                "bug_type": item.bug_type,
                "expected_failure": item.expected_failure,
                "metadata": item.metadata,
            }
            for item in current_package.get("wrong_solutions", [])
        ]
    return summary


def _code_artifact_for_context(value: Any) -> dict[str, Any]:
    if not isinstance(value, GeneratedCodeArtifact):
        return {}
    return {
        "name": value.name,
        "role": value.role,
        "code": value.code,
        "metadata": value.metadata,
    }


def _frozen_contract_summary(current_package: dict[str, Any] | None) -> dict[str, Any]:
    if not current_package:
        return {}
    spec = current_package.get("execution_spec")
    if not isinstance(spec, ExecutionSpec):
        return {}
    return {
        "problem_id": spec.problem_id,
        "judge_type": spec.judge_type,
        "input_contract": spec.input_contract,
        "output_contract": spec.output_contract,
        "oracle_limits": spec.oracle_limits,
        "performance_limits": spec.performance_limits,
    }


_SEVERITY_RANK = {"info": 0, "low": 1, "medium": 2, "high": 3, "blocker": 4}

_TARGET_ROLES_BY_CATEGORY = {
    "test_generator_failed": ["ToolGenerator"],
    "test_suite_empty": ["ToolGenerator"],
    "validator_rejects_generated_case": ["ToolGenerator"],
    "checker_rejects_standard_output": ["ToolGenerator", "StandardSolutionGenerator"],
    "standard_solution_failed": ["StandardSolutionGenerator"],
    "performance_failure": ["StandardSolutionGenerator"],
    "oracle_failed": ["OracleGenerator"],
    "oracle_output_rejected_by_checker": ["ToolGenerator", "OracleGenerator"],
    "standard_oracle_mismatch": ["StandardSolutionGenerator", "OracleGenerator"],
    "wrong_solution_survived": ["ToolGenerator", "WeakPlayerGenerator", "SchemaMistakeAnalyzer", "SchemaAwareWrongSolutionGenerator"],
    "kill_rate_skipped_due_to_invalid_baseline": ["ToolGenerator", "StandardSolutionGenerator", "OracleGenerator"],
}

_ROLE_DIAGNOSTIC_LIMIT_PER_CATEGORY = 3
_ADVISOR_DIAGNOSTIC_LIMIT_PER_CATEGORY = 3
_FULL_EVIDENCE_TEXT_LIMIT = 1800
_TRUNCATED_TEXT_EDGE = 700
_DIFF_WINDOW = 3


def _build_revision_context(
    issues: list[FailureIssue],
    curation: dict[str, Any],
    *,
    revision_advisor: Any | None = None,
    current_package: dict[str, Any] | None = None,
    previous_active_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    diagnostics_by_category: dict[str, list[dict[str, Any]]] = {}
    for issue in issues:
        diagnostic = _build_diagnostic(issue)
        diagnostics_by_category.setdefault(issue.category, []).append(diagnostic)

    if revision_advisor is not None:
        _enrich_diagnostics_with_advisor(
            diagnostics_by_category,
            revision_advisor=revision_advisor,
            current_package=current_package,
            curation=curation,
            previous_active_context=previous_active_context,
        )

    role_diagnostics: dict[str, list[dict[str, Any]]] = {}
    for diagnostics in diagnostics_by_category.values():
        by_role_category_count: dict[tuple[str, str], int] = {}
        for diagnostic in diagnostics:
            category = str(diagnostic.get("category", ""))
            for role in diagnostic.get("target_roles", []):
                key = (role, category)
                if by_role_category_count.get(key, 0) >= _ROLE_DIAGNOSTIC_LIMIT_PER_CATEGORY:
                    continue
                role_diagnostics.setdefault(role, []).append(diagnostic)
                by_role_category_count[key] = by_role_category_count.get(key, 0) + 1

    return {
        "summary": _build_revision_summary(diagnostics_by_category),
        "diagnostics_by_category": diagnostics_by_category,
        "role_diagnostics": role_diagnostics,
        "failed_hard_checks": _dedupe([issue.category for issue in issues if issue.severity == "blocker"]),
        "surviving_wrong_solution_details": _surviving_wrong_solution_details(curation),
    }


def _enrich_diagnostics_with_advisor(
    diagnostics_by_category: dict[str, list[dict[str, Any]]],
    *,
    revision_advisor: Any,
    current_package: dict[str, Any] | None,
    curation: dict[str, Any],
    previous_active_context: dict[str, Any] | None,
) -> None:
    previous_by_fingerprint = _diagnostics_by_fingerprint(previous_active_context or {})
    survivor_details = _surviving_wrong_solution_details(curation)
    for category, diagnostics in diagnostics_by_category.items():
        representative_count = min(len(diagnostics), _ADVISOR_DIAGNOSTIC_LIMIT_PER_CATEGORY)
        representative_revisions: list[dict[str, Any]] = []
        for diagnostic in diagnostics[:representative_count]:
            packet = _build_failure_packet(
                diagnostic,
                current_package=current_package,
                survivor_details=survivor_details,
                previous_by_fingerprint=previous_by_fingerprint,
                category_issue_count=len(diagnostics),
                representative_count=representative_count,
            )
            try:
                advisor_revision = revision_advisor.generate(packet)
            except Exception as exc:
                raise RuntimeError(
                    f"RevisionAdvisor 生成修订建议失败：category={category}; "
                    f"fingerprint={diagnostic.get('issue_fingerprint', '')}; error={exc}"
                ) from exc
            diagnostic["advisor_revision"] = _normalize_advisor_payload(advisor_revision, diagnostic)
            representative_revisions.append(copy.deepcopy(diagnostic["advisor_revision"]))

        if not representative_revisions:
            continue
        for index, diagnostic in enumerate(diagnostics[representative_count:], start=representative_count):
            reused = copy.deepcopy(representative_revisions[index % len(representative_revisions)])
            reused["cluster_reused"] = True
            reused["cluster_representative_count"] = representative_count
            diagnostic["advisor_revision"] = reused


def _build_failure_packet(
    diagnostic: dict[str, Any],
    *,
    current_package: dict[str, Any] | None,
    survivor_details: list[dict[str, Any]],
    previous_by_fingerprint: dict[str, dict[str, Any]],
    category_issue_count: int,
    representative_count: int,
) -> dict[str, Any]:
    target_roles = {str(role) for role in diagnostic.get("target_roles", [])}
    fingerprint = str(diagnostic.get("issue_fingerprint", "")).strip()
    previous_diagnostic = previous_by_fingerprint.get(fingerprint, {})
    packet: dict[str, Any] = {
        "diagnostic": {
            "category": diagnostic.get("category", ""),
            "severity": diagnostic.get("severity", ""),
            "title": diagnostic.get("title", ""),
            "detail": diagnostic.get("detail", ""),
            "target_roles": list(diagnostic.get("target_roles", [])),
            "issue_fingerprint": fingerprint,
        },
        "evidence": copy.deepcopy(diagnostic.get("evidence", {})),
        "diff": copy.deepcopy(diagnostic.get("diff", {})),
        "current_artifact": _current_artifact_summary(current_package, target_roles) if current_package else {},
        "cluster": {
            "category_issue_count": category_issue_count,
            "advisor_representative_count": representative_count,
        },
    }
    if diagnostic.get("fix_hint"):
        packet["legacy_fix_hint"] = diagnostic.get("fix_hint", "")
    previous_advice = previous_diagnostic.get("advisor_revision") if isinstance(previous_diagnostic, dict) else None
    if isinstance(previous_advice, dict) and previous_advice:
        packet["previous_advice"] = copy.deepcopy(previous_advice)
    if diagnostic.get("category") == "wrong_solution_survived":
        packet["surviving_wrong_solution_details"] = copy.deepcopy(survivor_details)
    return packet


def _normalize_advisor_payload(payload: Any, diagnostic: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("RevisionAdvisor 必须返回 JSON 对象。")
    allowed_roles = {str(role) for role in diagnostic.get("target_roles", [])}
    target_roles = [str(role) for role in payload.get("target_roles", []) if str(role) in allowed_roles] if isinstance(payload.get("target_roles"), list) else []
    if not target_roles:
        target_roles = sorted(allowed_roles)
    confidence = str(payload.get("confidence", "medium")).strip().lower()
    if confidence not in {"low", "medium", "high"}:
        confidence = "medium"
    revision_advice = str(payload.get("revision_advice", "")).strip()
    if not revision_advice:
        raise ValueError("RevisionAdvisor 返回缺少 revision_advice。")
    return {
        "root_cause": str(payload.get("root_cause", "")).strip(),
        "revision_advice": revision_advice,
        "target_roles": target_roles,
        "evidence_used": [str(item).strip() for item in payload.get("evidence_used", []) if str(item).strip()]
        if isinstance(payload.get("evidence_used"), list)
        else [],
        "confidence": confidence,
        "risk_notes": str(payload.get("risk_notes", "")).strip(),
    }


def _revision_context_from_diagnostics(
    diagnostics: list[dict[str, Any]],
    surviving_wrong_solution_details: Any,
) -> dict[str, Any]:
    diagnostics_by_category: dict[str, list[dict[str, Any]]] = {}
    for diagnostic in diagnostics:
        category = str(diagnostic.get("category", ""))
        if category:
            diagnostics_by_category.setdefault(category, []).append(copy.deepcopy(diagnostic))

    role_diagnostics: dict[str, list[dict[str, Any]]] = {}
    for diagnostics_for_category in diagnostics_by_category.values():
        by_role_category_count: dict[tuple[str, str], int] = {}
        for diagnostic in diagnostics_for_category:
            category = str(diagnostic.get("category", ""))
            for role in diagnostic.get("target_roles", []):
                key = (str(role), category)
                if by_role_category_count.get(key, 0) >= _ROLE_DIAGNOSTIC_LIMIT_PER_CATEGORY:
                    continue
                role_diagnostics.setdefault(str(role), []).append(copy.deepcopy(diagnostic))
                by_role_category_count[key] = by_role_category_count.get(key, 0) + 1

    has_wrong_solution_issue = "wrong_solution_survived" in diagnostics_by_category
    survivor_details = surviving_wrong_solution_details if has_wrong_solution_issue else []
    return {
        "summary": _build_revision_summary(diagnostics_by_category),
        "diagnostics_by_category": diagnostics_by_category,
        "role_diagnostics": role_diagnostics,
        "failed_hard_checks": _dedupe(
            [
                str(item.get("category", ""))
                for item in diagnostics
                if str(item.get("severity", "")) == "blocker" and str(item.get("category", ""))
            ]
        ),
        "surviving_wrong_solution_details": copy.deepcopy(survivor_details) if isinstance(survivor_details, list) else [],
    }


def _diagnostics_by_fingerprint(revision_context: dict[str, Any]) -> dict[str, dict[str, Any]]:
    diagnostics_by_fingerprint: dict[str, dict[str, Any]] = {}
    for diagnostic in _flatten_diagnostics(revision_context):
        fingerprint = str(diagnostic.get("issue_fingerprint", "")).strip()
        if not fingerprint:
            fingerprint = _issue_fingerprint(diagnostic)
            diagnostic = {**diagnostic, "issue_fingerprint": fingerprint}
        diagnostics_by_fingerprint[fingerprint] = diagnostic
    return diagnostics_by_fingerprint


def _flatten_diagnostics(revision_context: dict[str, Any]) -> list[dict[str, Any]]:
    diagnostics_by_category = revision_context.get("diagnostics_by_category")
    if not isinstance(diagnostics_by_category, dict):
        active = revision_context.get("active_revision_context")
        if isinstance(active, dict):
            diagnostics_by_category = active.get("diagnostics_by_category")
    if not isinstance(diagnostics_by_category, dict):
        return []

    diagnostics: list[dict[str, Any]] = []
    seen: set[str] = set()
    for items in diagnostics_by_category.values():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            fingerprint = str(item.get("issue_fingerprint", "")).strip() or _issue_fingerprint(item)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            diagnostics.append({**copy.deepcopy(item), "issue_fingerprint": fingerprint})
    return diagnostics


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


def _checker_reject_detail(spec: ExecutionSpec, detail: str) -> str:
    if spec.judge_type != "checker":
        return detail
    return f"{detail} checker 题允许多解，不能用字符串相等判断合法性。"


def _build_failure_evidence(
    *,
    test: TestCase,
    validator_result: Any | None = None,
    standard_result: Any | None = None,
    standard_output: Any | None = None,
    oracle_result: Any | None = None,
    oracle_output: Any | None = None,
    checker_result: Any | None = None,
) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "test": {
            "source": test.source,
            "purpose": test.purpose,
            "expect_oracle": test.expect_oracle,
            "is_sample": test.is_sample,
            "is_large": test.is_large,
            "metadata": dict(test.metadata),
        },
        "test_source": test.source,
        "input": test.input,
    }
    if validator_result is not None:
        evidence["validator_result"] = _result_evidence(validator_result)
    if standard_result is not None:
        evidence["standard_result"] = _result_evidence(standard_result)
    if standard_output is not None:
        evidence["standard_output"] = str(standard_output)
    if oracle_result is not None:
        evidence["oracle_result"] = _result_evidence(oracle_result)
    if oracle_output is not None:
        evidence["oracle_output"] = str(oracle_output)
    if checker_result is not None:
        evidence["checker_result"] = _result_evidence(checker_result)
    return evidence


def _result_evidence(result: Any) -> dict[str, Any]:
    return {
        "status": getattr(result, "status", ""),
        "result": getattr(result, "result", None),
        "error_reason": getattr(result, "error_reason", ""),
        "stdout": getattr(result, "stdout", ""),
        "stderr": getattr(result, "stderr", ""),
        "elapsed_ms": getattr(result, "elapsed_ms", 0),
    }


def _build_diagnostic(issue: FailureIssue) -> dict[str, Any]:
    diagnostic = {
        "category": issue.category,
        "severity": issue.severity,
        "title": issue.title,
        "detail": issue.detail,
        "fix_hint": issue.fix_hint,
        "target_roles": list(_TARGET_ROLES_BY_CATEGORY.get(issue.category, [])),
        "evidence": _summarize_evidence(issue.evidence),
    }
    diff = _build_output_diff(issue.evidence)
    if diff:
        diagnostic["diff"] = diff
    diagnostic["issue_fingerprint"] = _issue_fingerprint(diagnostic)
    return diagnostic


def _issue_fingerprint(diagnostic: dict[str, Any]) -> str:
    evidence = diagnostic.get("evidence") if isinstance(diagnostic.get("evidence"), dict) else {}
    test = evidence.get("test") if isinstance(evidence.get("test"), dict) else {}
    result_statuses = {
        key: value.get("status")
        for key, value in evidence.items()
        if key.endswith("_result") and isinstance(value, dict)
    }
    basis = {
        "category": diagnostic.get("category", ""),
        "target_roles": sorted(str(role) for role in diagnostic.get("target_roles", [])),
        "test_source": test.get("source") or evidence.get("test_source") or "",
        "title": diagnostic.get("title", ""),
        "diff_shape": _fingerprint_diff_shape(diagnostic.get("diff", {})),
        "result_statuses": result_statuses,
    }
    raw = json.dumps(basis, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _fingerprint_diff_shape(diff: Any) -> dict[str, Any]:
    if not isinstance(diff, dict):
        return {}
    token = diff.get("first_different_token") if isinstance(diff.get("first_different_token"), dict) else {}
    line = diff.get("first_different_line") if isinstance(diff.get("first_different_line"), dict) else {}
    shape: dict[str, Any] = {}
    if token:
        shape["first_different_token_index"] = token.get("index")
    if line:
        shape["first_different_line_index"] = line.get("index")
    return shape


def _build_revision_summary(diagnostics_by_category: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for category, diagnostics in diagnostics_by_category.items():
        severity = max((str(item.get("severity", "")) for item in diagnostics), key=lambda item: _SEVERITY_RANK.get(item, -1))
        sources = _dedupe(
            [
                str((item.get("evidence", {}).get("test") or {}).get("source") or item.get("evidence", {}).get("test_source") or "")
                for item in diagnostics
            ]
        )
        summary.append(
            {
                "category": category,
                "count": len(diagnostics),
                "severity": severity,
                "representative_sources": sources[:3],
                "titles": _dedupe([str(item.get("title", "")) for item in diagnostics if item.get("title")])[:3],
            }
        )
    return summary


def _surviving_wrong_solution_details(curation: dict[str, Any]) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for item in curation.get("independent_solutions", []):
        details.append(
            {
                "solution_id": item.get("solution_id", ""),
                "bug_type": item.get("bug_type", ""),
                "expected_failure": item.get("expected_failure", ""),
                "reason": item.get("reason", ""),
                "passed_tests": list(item.get("passed_tests", [])),
                "killed_tests": list(item.get("killed_tests", [])),
                "metadata": dict(item.get("metadata", {}) or {}),
            }
        )
    return details


def _summarize_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    if not evidence:
        return {}
    test = evidence.get("test", {}) if isinstance(evidence.get("test"), dict) else {}
    is_large = bool(test.get("is_large"))
    summarized: dict[str, Any] = {}
    for key, value in evidence.items():
        if key == "input":
            summarized[key] = _summarize_text(value, is_large=is_large, prefer_full=bool(test.get("expect_oracle")) and not is_large)
        elif key in {"standard_output", "oracle_output"}:
            summarized[key] = _summarize_text(value, is_large=is_large, prefer_full=bool(test.get("expect_oracle")) and not is_large)
        elif key.endswith("_result") and isinstance(value, dict):
            summarized[key] = _summarize_result(value, is_large=is_large)
        else:
            summarized[key] = value
    return summarized


def _summarize_result(result: dict[str, Any], *, is_large: bool) -> dict[str, Any]:
    summarized: dict[str, Any] = {}
    for key, value in result.items():
        if key in {"stdout", "stderr"}:
            summarized[key] = _summarize_text(value, is_large=is_large, prefer_full=False)
        elif key == "result":
            summarized[key] = _summarize_text(value, is_large=is_large, prefer_full=False) if isinstance(value, str) else value
        elif key == "error_reason":
            text = str(value or "")
            if "Traceback (most recent call last)" in text:
                summarized["traceback"] = _summarize_traceback(text)
            else:
                summarized[key] = _summarize_text(text, is_large=is_large, prefer_full=False)
        else:
            summarized[key] = value
    return summarized


def _summarize_text(value: Any, *, is_large: bool, prefer_full: bool) -> dict[str, Any]:
    text = "" if value is None else str(value)
    original_length = len(text)
    line_count = len(text.splitlines())
    token_count = len(text.split())
    if prefer_full and original_length <= _FULL_EVIDENCE_TEXT_LIMIT:
        return {
            "content": text,
            "truncated": False,
            "original_length": original_length,
            "line_count": line_count,
            "token_count": token_count,
            "kept_strategy": "full",
        }
    if not is_large and original_length <= _FULL_EVIDENCE_TEXT_LIMIT:
        return {
            "content": text,
            "truncated": False,
            "original_length": original_length,
            "line_count": line_count,
            "token_count": token_count,
            "kept_strategy": "full",
        }
    return {
        "head": text[:_TRUNCATED_TEXT_EDGE],
        "tail": text[-_TRUNCATED_TEXT_EDGE:] if original_length > _TRUNCATED_TEXT_EDGE else "",
        "truncated": original_length > _TRUNCATED_TEXT_EDGE,
        "original_length": original_length,
        "line_count": line_count,
        "token_count": token_count,
        "kept_strategy": "head_tail",
    }


def _summarize_traceback(text: str) -> dict[str, Any]:
    lines = [line for line in text.strip().splitlines() if line.strip()]
    final_error_line = lines[-1] if lines else ""
    exception_type = final_error_line.split(":", 1)[0] if ":" in final_error_line else final_error_line
    frame_lines = [line for line in lines if line.lstrip().startswith('File "')]
    return {
        "exception_type": exception_type,
        "last_frames": frame_lines[-3:],
        "final_error_line": final_error_line,
        "truncated": len(frame_lines) > 3 or len(lines) > 8,
    }


def _build_output_diff(evidence: dict[str, Any]) -> dict[str, Any]:
    standard = evidence.get("standard_output")
    oracle = evidence.get("oracle_output")
    if standard is None or oracle is None:
        return {}
    standard_text = str(standard)
    oracle_text = str(oracle)
    if _normalize_output(standard_text) == _normalize_output(oracle_text):
        return {}
    standard_tokens = standard_text.split()
    oracle_tokens = oracle_text.split()
    token_index = 0
    while token_index < min(len(standard_tokens), len(oracle_tokens)) and standard_tokens[token_index] == oracle_tokens[token_index]:
        token_index += 1
    standard_lines = standard_text.splitlines()
    oracle_lines = oracle_text.splitlines()
    line_index = 0
    while line_index < min(len(standard_lines), len(oracle_lines)) and standard_lines[line_index].rstrip() == oracle_lines[line_index].rstrip():
        line_index += 1
    return {
        "first_different_token": {
            "index": token_index,
            "standard": standard_tokens[token_index] if token_index < len(standard_tokens) else None,
            "oracle": oracle_tokens[token_index] if token_index < len(oracle_tokens) else None,
        },
        "first_different_line": {
            "index": line_index,
            "standard": standard_lines[line_index] if line_index < len(standard_lines) else None,
            "oracle": oracle_lines[line_index] if line_index < len(oracle_lines) else None,
        },
        "standard_window": _window(standard_lines, line_index, _DIFF_WINDOW),
        "oracle_window": _window(oracle_lines, line_index, _DIFF_WINDOW),
    }


def _window(items: list[str], center: int, radius: int) -> list[str]:
    if not items:
        return []
    start = max(0, center - radius)
    end = min(len(items), center + radius + 1)
    return items[start:end]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _skipped_wrong_solution_stats(*, candidate_count: int, kill_rate_threshold: float) -> dict[str, Any]:
    return {
        "candidate_count": candidate_count,
        "valuable_count": 0,
        "independent_count": 0,
        "rejected_count": 0,
        "kill_rate": None,
        "kill_rate_threshold": kill_rate_threshold,
        "passed_threshold": False,
        "valid": False,
        "skip_reason": "baseline_validation_failed",
    }
