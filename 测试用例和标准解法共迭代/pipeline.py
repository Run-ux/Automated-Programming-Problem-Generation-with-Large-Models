from __future__ import annotations

import json
import shutil
import copy
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from config import (
    DEFAULT_KILL_RATE_THRESHOLD,
    DEFAULT_LARGE_RUN_TIMEOUT_S,
    DEFAULT_MAX_REVISION_CONTEXT_BYTES,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_RUN_TIMEOUT_S,
    DEFAULT_STALLING_BASELINE_ROUNDS,
)
from artifact_context import build_problem_context, normalize_tests
from curation import WrongSolutionCurator
from generators import (
    BruteForceSolutionGenerator,
    FixedCategoryWrongSolutionGenerator,
    RevisionAdvisor,
    SchemaMistakeAnalyzer,
    StandardSolutionGenerator,
    StrategyWrongSolutionGenerator,
    ToolGenerator,
)
from models import (
    FailureIssue,
    GeneratedCodeArtifact,
    IterationSummary,
    ProblemContext,
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
        standard_generator: StandardSolutionGenerator | None = None,
        bruteforce_generator: BruteForceSolutionGenerator | None = None,
        tool_generator: ToolGenerator | None = None,
        fixed_wrong_solution_generator: FixedCategoryWrongSolutionGenerator | None = None,
        schema_mistake_analyzer: SchemaMistakeAnalyzer | None = None,
        strategy_wrong_solution_generator: StrategyWrongSolutionGenerator | None = None,
        revision_advisor: Any | None = None,
        progress_writer: Any | None = None,
        max_revision_context_bytes: int = DEFAULT_MAX_REVISION_CONTEXT_BYTES,
        stalling_baseline_rounds: int = DEFAULT_STALLING_BASELINE_ROUNDS,
    ):
        self.client = client
        self.output_dir = output_dir
        self.runner = runner or CodeRunner(timeout_s=run_timeout_s)
        self.kill_rate_threshold = kill_rate_threshold
        self.run_timeout_s = run_timeout_s
        self.large_run_timeout_s = large_run_timeout_s
        self.standard_generator = standard_generator or StandardSolutionGenerator(client)
        self.bruteforce_generator = bruteforce_generator or BruteForceSolutionGenerator(client)
        self.tool_generator = tool_generator or ToolGenerator(client)
        self.fixed_wrong_solution_generator = fixed_wrong_solution_generator or FixedCategoryWrongSolutionGenerator(client)
        self.schema_mistake_analyzer = schema_mistake_analyzer or SchemaMistakeAnalyzer(client)
        self.strategy_wrong_solution_generator = strategy_wrong_solution_generator or StrategyWrongSolutionGenerator(client)
        self.revision_advisor = revision_advisor if revision_advisor is not None else (RevisionAdvisor(client) if client is not None else None)
        self.progress_writer = progress_writer or (lambda message: print(message, flush=True))
        self.max_revision_context_bytes = max_revision_context_bytes
        self.stalling_baseline_rounds = max(1, stalling_baseline_rounds)
        self._regression_cases: list[TestCase] = []
        self._known_good_cases: list[TestCase] = []
        self._component_gate_results: dict[str, Any] = {}
        self._component_gate_issues: list[FailureIssue] = []
        self._candidate_package_gate_results: dict[str, Any] = {}
        self._candidate_gate_history: list[dict[str, Any]] = []
        self._previous_report: ValidationReport | None = None
        self._candidate_gate_rejection_count = 0
        self._regression_prevention_count = 0

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
        baseline_repair_mode = False
        baseline_failure_streak = 0
        previous_concrete_baseline_fingerprints: set[str] = set()
        previous_baseline_signature = ""
        prompt_payload_bytes_by_round: list[dict[str, Any]] = []
        semantic_gate_status = "not_evaluated"
        deliverable_dir = ""
        last_attempt_dir = ""
        self._regression_cases = []
        self._known_good_cases = []
        self._component_gate_results = {}
        self._component_gate_issues = []
        self._candidate_package_gate_results = {}
        self._candidate_gate_history = []
        self._previous_report = None
        self._candidate_gate_rejection_count = 0
        self._regression_prevention_count = 0
        previous_report: ValidationReport | None = None

        for round_index in range(1, rounds + 1):
            self._emit(f"[轮次] 第 {round_index}/{rounds} 轮：准备修订上下文。")
            round_dir = run_dir / f"round{round_index}"
            round_dir.mkdir(parents=True, exist_ok=True)
            self._component_gate_results = {}
            self._component_gate_issues = []
            self._candidate_package_gate_results = {}
            self._previous_report = previous_report
            generation_revision_context = _build_generation_revision_context(
                active_revision_context=active_revision_context,
                revision_audit_history=revision_audit_history,
                current_package=current_package,
                round_index=round_index,
                baseline_repair_mode=baseline_repair_mode,
                regression_cases=self._regression_cases,
                known_good_cases=self._known_good_cases,
            )
            prompt_payload_size = _json_size(generation_revision_context)
            prompt_payload_bytes_by_round.append(
                {"round_index": round_index, "revision_context_bytes": prompt_payload_size}
            )
            if prompt_payload_size > self.max_revision_context_bytes:
                self._component_gate_issues.append(
                    FailureIssue(
                        category="revision_payload_too_large",
                        severity="high",
                        title="修订上下文过大",
                        detail=(
                            f"当前 revision_context 约 {prompt_payload_size} 字节，"
                            f"超过阈值 {self.max_revision_context_bytes}。"
                        ),
                        fix_hint="压缩 active 诊断、历史审计和当前产物摘要后再进入下一轮生成。",
                    )
                )
            if current_package is None:
                self._emit(f"[生成] 第 {round_index}/{rounds} 轮：全量生成题包组件。")
                package = self._generate_round_package(context, generation_revision_context, include_wrong_solutions=False)
            else:
                self._emit(f"[生成] 第 {round_index}/{rounds} 轮：基于上一轮结果增量修订题包。")
                package = self._generate_incremental_round_package(context, current_package, generation_revision_context)
            self._emit(f"[写入] 第 {round_index}/{rounds} 轮：写入题包产物。")
            self._write_round_package(round_dir, package)

            self._emit(f"[验证] 第 {round_index}/{rounds} 轮：执行验证矩阵。")
            report = self._validate_package(package, previous_active_context=active_revision_context)
            if report.base_consistency.get("passed") and not package.get("wrong_solutions"):
                self._emit(f"[生成] 第 {round_index}/{rounds} 轮：基础自洽已通过，生成错误解池。")
                package = self._generate_wrong_solution_components(context, package, generation_revision_context)
                self._write_round_package(round_dir, package)
                self._emit(f"[验证] 第 {round_index}/{rounds} 轮：错误解池生成后重新执行验证矩阵。")
                report = self._validate_package(package, previous_active_context=active_revision_context)
            self._emit(f"[写入] 第 {round_index}/{rounds} 轮：写入执行报告。")
            self._write_report(round_dir, report)
            self._known_good_cases = _merge_known_good_cases(
                self._known_good_cases,
                _extract_known_good_cases(report),
            )
            self._regression_cases = _merge_regression_cases(
                self._regression_cases,
                _extract_regression_cases(report),
            )
            (run_dir / "known_good_cases.json").write_text(
                json.dumps([to_dict(item) for item in self._known_good_cases], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (run_dir / "regression_cases.json").write_text(
                json.dumps([to_dict(item) for item in self._regression_cases], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (run_dir / "candidate_gate_history.json").write_text(
                json.dumps(self._candidate_gate_history, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            revision_audit_history.append({"round_index": round_index, "revision_context": report.revision_context})
            active_revision_context, context_stats = _update_active_revision_context(
                active_revision_context,
                report.revision_context,
            )
            baseline_passed = bool(report.base_consistency.get("passed", False))
            baseline_failed_categories = _dedupe([str(item) for item in report.base_consistency.get("failed_categories", [])])
            semantic_gate_status = report.overall.get("semantic_gate_status", semantic_gate_status)
            if baseline_passed:
                baseline_failure_streak = 0
                previous_concrete_baseline_fingerprints = set()
                previous_baseline_signature = ""
            else:
                concrete_fingerprints = _concrete_baseline_fingerprints(report)
                baseline_signature = _baseline_stall_signature(report)
                if concrete_fingerprints == previous_concrete_baseline_fingerprints or baseline_signature == previous_baseline_signature:
                    baseline_failure_streak += 1
                else:
                    baseline_failure_streak = 1
                previous_concrete_baseline_fingerprints = concrete_fingerprints
                previous_baseline_signature = baseline_signature
            baseline_repair_mode = not baseline_passed
            self._emit(
                f"[回流] 第 {round_index}/{rounds} 轮：active={context_stats['active_issue_count']}，"
                f"新增={context_stats['new_issue_count']}，解决={context_stats['resolved_issue_count']}，"
                f"延续={context_stats['carried_issue_count']}。"
            )

            final_round_index = round_index
            current_package = package
            round_record = {
                "round_index": round_index,
                "round_dir": str(round_dir),
                "status": report.overall["status"],
                "issue_count": report.overall["issue_count"],
                "kill_rate": report.wrong_solution_stats.get("kill_rate", 0.0),
                "baseline_passed": baseline_passed,
                "baseline_failed_categories": baseline_failed_categories,
                "baseline_failure_streak": baseline_failure_streak,
                "semantic_gate_status": report.overall.get("semantic_gate_status", "not_evaluated"),
                "regression_case_count": len(self._regression_cases),
                "known_good_case_count": len(self._known_good_cases),
                "candidate_gate_rejection_count": self._candidate_gate_rejection_count,
                "regression_prevention_count": self._regression_prevention_count,
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
            if report.semantic_gate_issues:
                final_status = "not_deliverable"
                stop_reason = "semantic_gate_failed"
                self._emit(f"[停止] 第 {round_index}/{rounds} 轮：语义门禁未通过，停止盲目迭代。")
                break
            if baseline_failure_streak >= self.stalling_baseline_rounds and report.wrong_solution_stats.get("kill_rate") is None:
                final_status = "not_deliverable"
                stop_reason = "stalled_on_baseline"
                self._emit(f"[停止] 第 {round_index}/{rounds} 轮：基础自洽问题连续两轮无实质变化。")
                break
            previous_report = report

        if current_package is not None:
            if final_status == "pass":
                final_dir = run_dir / "final"
                deliverable_dir = str(final_dir)
                self._emit(f"[写入] 写入最终题包产物：{final_dir}。")
                self._write_round_package(final_dir, current_package)
            else:
                last_attempt = run_dir / "last_attempt"
                last_attempt_dir = str(last_attempt)
                self._emit(f"[写入] 写入未交付最后尝试产物：{last_attempt}。")
                self._write_round_package(last_attempt, current_package)
                (run_dir / "NOT_DELIVERABLE.md").write_text(
                    _render_not_deliverable_note(
                        final_status=final_status,
                        stop_reason=stop_reason,
                        final_round_index=final_round_index,
                        regression_case_count=len(self._regression_cases),
                    ),
                    encoding="utf-8",
                )
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
            deliverable_dir=deliverable_dir,
            last_attempt_dir=last_attempt_dir,
            semantic_gate_status=semantic_gate_status,
            prompt_payload_bytes_by_round=prompt_payload_bytes_by_round,
            regression_case_count=len(self._regression_cases),
            known_good_case_count=len(self._known_good_cases),
            candidate_gate_rejection_count=self._candidate_gate_rejection_count,
            regression_prevention_count=self._regression_prevention_count,
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

        if "ProblemContextBuilder" in roles:
            roles.update(
                {
                    "StandardSolutionGenerator",
                    "BruteForceSolutionGenerator",
                    "ValidatorGenerator",
                    "CheckerGenerator",
                    "TestGenerator",
                    "SchemaMistakeAnalyzer",
                    "FixedCategoryWrongSolutionGenerator",
                    "StrategyWrongSolutionGenerator",
                }
            )
            self._emit("[生成] 增量修订：重建 artifact 题面上下文，并级联重生成依赖组件。")
            package["problem_context"] = build_problem_context(context)

        if "StandardSolutionGenerator" in roles:
            self._emit("[生成] 增量修订：重生成标准解。")
            candidate = self.standard_generator.generate(
                context,
                _revision_context_for_roles(revision_context, {"StandardSolutionGenerator"}, current_package),
            )
            self._promote_component_candidate(package, current_package, "standard_solution", candidate, revision_context)
        if "BruteForceSolutionGenerator" in roles:
            self._emit("[生成] 增量修订：重生成正确暴力解。")
            candidate = self.bruteforce_generator.generate(
                context,
                _revision_context_for_roles(revision_context, {"BruteForceSolutionGenerator"}, current_package),
            )
            self._promote_component_candidate(package, current_package, "bruteforce_solution", candidate, revision_context)
        if "ToolGenerator" in roles:
            self._emit("[生成] 增量修订：重生成 validator、checker 和三类测试输入。")
            tools = self.tool_generator.generate(
                context,
                _revision_context_for_roles(revision_context, {"ToolGenerator"}, current_package),
            )
            self._promote_component_candidate(package, current_package, "validator", tools["validator"], revision_context)
            self._promote_component_candidate(package, current_package, "checker", tools["checker"], revision_context)
            self._promote_component_candidate(package, current_package, "random_test_generator", tools["random_test_generator"], revision_context)
            self._promote_component_candidate(package, current_package, "adversarial_test_generator", tools["adversarial_test_generator"], revision_context)
            package["small_challenge_tests"] = tools["small_challenge_tests"]
        else:
            if "ValidatorGenerator" in roles:
                self._emit("[生成] 增量修订：只重生成 validator。")
                candidate = self._generate_validator_component(
                    context,
                    _revision_context_for_roles(revision_context, {"ValidatorGenerator"}, current_package),
                )
                self._promote_component_candidate(package, current_package, "validator", candidate, revision_context)
            if "CheckerGenerator" in roles:
                self._emit("[生成] 增量修订：只重生成 checker。")
                candidate = self._generate_checker_component(
                    context,
                    package["validator"],
                    _revision_context_for_roles(revision_context, {"CheckerGenerator"}, current_package),
                )
                self._promote_component_candidate(package, current_package, "checker", candidate, revision_context)
            if "TestGenerator" in roles:
                self._emit("[生成] 增量修订：重生成三类测试输入。")
                tools = self.tool_generator.generate(
                    context,
                    _revision_context_for_roles(revision_context, {"TestGenerator"}, current_package),
                )
                self._promote_component_candidate(package, current_package, "random_test_generator", tools["random_test_generator"], revision_context)
                self._promote_component_candidate(package, current_package, "adversarial_test_generator", tools["adversarial_test_generator"], revision_context)
                package["small_challenge_tests"] = tools["small_challenge_tests"]

        fixed_wrong, strategy_wrong = _split_wrong_solutions(package.get("wrong_solutions", []))
        skip_wrong_revision = bool(revision_context.get("baseline_repair_mode", False))
        if "FixedCategoryWrongSolutionGenerator" in roles and not skip_wrong_revision:
            self._emit("[生成] 增量修订：重生成固定五类错误解。")
            fixed_wrong = self.fixed_wrong_solution_generator.generate(
                context,
                _revision_context_for_roles(revision_context, {"FixedCategoryWrongSolutionGenerator"}, current_package),
            )
            self._emit(f"[生成] 增量修订：固定五类错误解 {len(fixed_wrong)} 个。")
        if "SchemaMistakeAnalyzer" in roles and not skip_wrong_revision:
            self._emit("[生成] 增量修订：重新分析自由错误策略。")
            package["schema_mistake_points"] = self.schema_mistake_analyzer.generate(
                context,
                _revision_context_for_roles(revision_context, {"SchemaMistakeAnalyzer"}, current_package),
            )
            self._emit(f"[生成] 增量修订：自由错误策略 {len(package['schema_mistake_points'])} 个。")
            roles.add("StrategyWrongSolutionGenerator")
        if "StrategyWrongSolutionGenerator" in roles and not skip_wrong_revision:
            self._emit("[生成] 增量修订：逐策略重生成错误解。")
            strategy_wrong = self.strategy_wrong_solution_generator.generate(
                context,
                package.get("schema_mistake_points", []),
                _revision_context_for_roles(revision_context, {"StrategyWrongSolutionGenerator"}, current_package),
            )
            self._emit(f"[生成] 增量修订：自由策略错误解 {len(strategy_wrong)} 个。")
        if skip_wrong_revision:
            self._emit("[生成] 增量修订：当前处于基础自洽修复模式，跳过错误解池改动。")
        package["wrong_solutions"] = [*fixed_wrong, *strategy_wrong]
        self._emit(f"[生成] 增量修订完成：错误解候选共 {len(package['wrong_solutions'])} 个。")
        return package

    def _generate_round_package(
        self,
        context: dict[str, Any],
        revision_context: dict[str, Any],
        *,
        include_wrong_solutions: bool = True,
    ) -> dict[str, Any]:
        self._emit("[生成] 构造 artifact 题面上下文。")
        problem_context = build_problem_context(context)
        self._emit("[生成] 生成标准解。")
        standard = self.standard_generator.generate(context, revision_context)
        self._emit("[生成] 生成正确暴力解。")
        bruteforce = self.bruteforce_generator.generate(context, revision_context)
        self._emit("[生成] 生成 validator、checker 和三类测试输入。")
        tools = self.tool_generator.generate(context, revision_context)
        package = {
            "context": context,
            "problem_context": problem_context,
            "standard_solution": standard,
            "bruteforce_solution": bruteforce,
            "validator": tools["validator"],
            "checker": tools["checker"],
            "random_test_generator": tools["random_test_generator"],
            "adversarial_test_generator": tools["adversarial_test_generator"],
            "small_challenge_tests": tools["small_challenge_tests"],
            "schema_mistake_points": [],
            "wrong_solutions": [],
        }
        if include_wrong_solutions:
            package = self._generate_wrong_solution_components(context, package, revision_context)
        else:
            self._emit("[生成] 基础组件生成完成；错误解池将在基础自洽通过后生成。")
        return package

    def _generate_wrong_solution_components(
        self,
        context: dict[str, Any],
        package: dict[str, Any],
        revision_context: dict[str, Any],
    ) -> dict[str, Any]:
        package = copy.deepcopy(package)
        self._emit("[生成] 生成固定五类错误解。")
        fixed_wrong = self.fixed_wrong_solution_generator.generate(context, revision_context)
        self._emit(f"[生成] 固定五类错误解 {len(fixed_wrong)} 个。")
        self._emit("[生成] 分析自由错误策略。")
        mistake_points = self.schema_mistake_analyzer.generate(context, revision_context)
        self._emit(f"[生成] 自由错误策略 {len(mistake_points)} 个。")
        self._emit("[生成] 逐策略生成错误解。")
        strategy_wrong = self.strategy_wrong_solution_generator.generate(context, mistake_points, revision_context)
        self._emit(f"[生成] 自由策略错误解 {len(strategy_wrong)} 个。")
        package["schema_mistake_points"] = mistake_points
        package["wrong_solutions"] = [*fixed_wrong, *strategy_wrong]
        self._emit(f"[生成] 错误解池生成完成：候选共 {len(package['wrong_solutions'])} 个。")
        return package

    def _generate_validator_component(
        self,
        context: dict[str, Any],
        revision_context: dict[str, Any],
    ) -> GeneratedCodeArtifact:
        generator = getattr(self.tool_generator, "generate_validator", None)
        if callable(generator):
            return generator(context, revision_context)
        return self.tool_generator.generate(context, revision_context)["validator"]

    def _generate_checker_component(
        self,
        context: dict[str, Any],
        validator: GeneratedCodeArtifact,
        revision_context: dict[str, Any],
    ) -> GeneratedCodeArtifact:
        generator = getattr(self.tool_generator, "generate_checker", None)
        if callable(generator):
            return generator(context, validator, revision_context)
        return self.tool_generator.generate(context, revision_context)["checker"]

    def _promote_component_candidate(
        self,
        package: dict[str, Any],
        current_package: dict[str, Any],
        component_key: str,
        candidate: GeneratedCodeArtifact,
        revision_context: dict[str, Any],
    ) -> None:
        passed, result, issue = self._gate_component_candidate(package, component_key, candidate)
        self._component_gate_results[component_key] = result
        if not passed:
            self._candidate_gate_rejection_count += 1
            package[component_key] = current_package[component_key]
            if issue is not None:
                self._component_gate_issues.append(issue)
            return

        candidate_package = copy.deepcopy(package)
        candidate_package[component_key] = candidate
        package_gate_result, package_gate_issue = self._gate_candidate_package(
            candidate_package,
            component_key=component_key,
            revision_context=revision_context,
        )
        self._candidate_package_gate_results[component_key] = package_gate_result
        self._candidate_gate_history.append(copy.deepcopy(package_gate_result))
        if package_gate_result.get("passed"):
            package[component_key] = candidate
            return

        self._candidate_gate_rejection_count += 1
        if package_gate_result.get("regression_detected"):
            self._regression_prevention_count += 1
        package[component_key] = current_package[component_key]
        if package_gate_issue is not None:
            self._component_gate_issues.append(package_gate_issue)

    def _gate_component_candidate(
        self,
        package: dict[str, Any],
        component_key: str,
        candidate: GeneratedCodeArtifact,
    ) -> tuple[bool, dict[str, Any], FailureIssue | None]:
        candidate_package = copy.deepcopy(package)
        candidate_package[component_key] = candidate
        checks = _component_gate_inputs(candidate_package, self._regression_cases)
        result: dict[str, Any] = {
            "component": component_key,
            "passed": True,
            "checks": [],
        }

        def fail(detail: str, execution: Any | None = None) -> tuple[bool, dict[str, Any], FailureIssue]:
            result["passed"] = False
            if execution is not None:
                result["checks"].append(to_dict(execution))
            issue = FailureIssue(
                category="component_gate_failed",
                severity="blocker",
                title=f"{component_key} 候选组件未通过晋级门禁",
                detail=detail,
                evidence={"component": component_key, "gate_result": result},
                fix_hint="保留上一轮组件，并将该候选失败原因回流给对应生成器。",
            )
            return False, result, issue

        if component_key in {"standard_solution", "bruteforce_solution"}:
            artifact_name = candidate.name
            for test in checks:
                if component_key == "bruteforce_solution" and (test.is_large or not test.expect_bruteforce):
                    continue
                execution = self.runner.run_solve(
                    artifact_name=artifact_name,
                    code=candidate.code,
                    input_data=test.input,
                    test_source=test.source,
                    timeout_s=self.large_run_timeout_s if test.is_large else self.run_timeout_s,
                )
                result["checks"].append(to_dict(execution))
                if execution.status != "ok":
                    return fail(f"{component_key} 在门禁用例 {test.source} 上执行失败：{execution.error_reason or execution.status}")
            return True, result, None

        if component_key == "validator":
            for test in checks:
                execution = self.runner.run_validate(
                    artifact_name=candidate.name,
                    code=candidate.code,
                    input_data=test.input,
                    test_source=test.source,
                    timeout_s=self.run_timeout_s,
                )
                result["checks"].append(to_dict(execution))
                if execution.status != "ok" or execution.result is not True:
                    return fail(f"validator 候选拒绝门禁用例 {test.source}。")
            return True, result, None

        if component_key == "checker":
            for test in checks:
                expected_output = str((test.metadata or {}).get("sample_output", "")).strip()
                if not expected_output:
                    continue
                execution = self.runner.run_check(
                    artifact_name=candidate.name,
                    code=candidate.code,
                    input_data=test.input,
                    output_data=expected_output,
                    expected_data=expected_output,
                    test_source=test.source,
                    timeout_s=self.run_timeout_s,
                )
                result["checks"].append(to_dict(execution))
                if execution.status != "ok" or execution.result is not True:
                    return fail(f"checker 候选拒绝样例门禁输出 {test.source}。")
            if not result["checks"]:
                syntax_check = self.runner.run_check(
                    artifact_name=candidate.name,
                    code=candidate.code,
                    input_data="",
                    output_data="",
                    expected_data=None,
                    test_source="component_gate_syntax",
                    timeout_s=self.run_timeout_s,
                )
                result["checks"].append(to_dict(syntax_check))
                if syntax_check.status == "compile_error" or syntax_check.status == "invalid_interface":
                    return fail(f"checker 候选接口或语法错误：{syntax_check.error_reason or syntax_check.status}")
            return True, result, None

        if component_key in {"random_test_generator", "adversarial_test_generator"}:
            execution = self.runner.run_generate_test_input(
                artifact_name=candidate.name,
                code=candidate.code,
                timeout_s=self.run_timeout_s,
            )
            result["checks"].append(to_dict(execution))
            if execution.status != "ok":
                return fail(f"{component_key} 候选执行失败：{execution.error_reason or execution.status}")
            try:
                problem = candidate_package["problem_context"]
                generated_tests = normalize_tests(
                    [
                        {
                            "input": str(execution.result),
                            "source": candidate.name,
                            "purpose": "候选测试输入门禁",
                            "expect_bruteforce": True,
                            "is_large": False,
                        }
                    ],
                    problem,
                )
            except ValueError as exc:
                return fail(f"{component_key} 候选返回结构非法：{exc}")
            if not generated_tests:
                return fail(f"{component_key} 候选未生成任何可执行测试。")
            validator = candidate_package["validator"]
            for test in generated_tests[:3]:
                validation = self.runner.run_validate(
                    artifact_name=validator.name,
                    code=validator.code,
                    input_data=test.input,
                    test_source=test.source,
                    timeout_s=self.run_timeout_s,
                )
                result["checks"].append(to_dict(validation))
                if validation.status != "ok" or validation.result is not True:
                    return fail(f"{component_key} 候选生成了 validator 拒绝的用例 {test.source}。")
            return True, result, None

        return True, result, None

    def _gate_candidate_package(
        self,
        candidate_package: dict[str, Any],
        *,
        component_key: str,
        revision_context: dict[str, Any],
    ) -> tuple[dict[str, Any], FailureIssue | None]:
        previous_report = self._previous_report
        if previous_report is None:
            result = {
                "component": component_key,
                "passed": True,
                "status": "skipped_no_previous_report",
                "rejection_reasons": [],
                "regression_detected": False,
            }
            return result, None

        active_cases = _extract_active_failure_cases(previous_report)
        candidate_report = self._validate_package(
            candidate_package,
            previous_active_context=previous_report.revision_context,
            regression_cases=self._regression_cases,
            known_good_cases=self._known_good_cases,
            active_cases=active_cases,
            component_gate_issues=[],
            component_gate_results={},
            candidate_package_gate_results={},
            build_revision_advice=False,
        )
        score = _score_candidate_package(
            previous_report=previous_report,
            candidate_report=candidate_report,
        )
        result = {
            "component": component_key,
            "passed": score["passed"],
            "status": "passed" if score["passed"] else "rejected",
            "rejection_reasons": score["rejection_reasons"],
            "regression_detected": score["regression_detected"],
            "fixed_issue_fingerprints": score["fixed_issue_fingerprints"],
            "introduced_blocker_high_categories": score["introduced_blocker_high_categories"],
            "known_good_failed_sources": score["known_good_failed_sources"],
            "previous_overall": copy.deepcopy(previous_report.overall),
            "candidate_overall": copy.deepcopy(candidate_report.overall),
            "previous_wrong_solution_stats": copy.deepcopy(previous_report.wrong_solution_stats),
            "candidate_wrong_solution_stats": copy.deepcopy(candidate_report.wrong_solution_stats),
            "candidate_known_good_results": copy.deepcopy(candidate_report.known_good_results),
            "candidate_semantic_gate_issue_count": len(candidate_report.semantic_gate_issues),
            "previous_semantic_gate_issue_count": len(previous_report.semantic_gate_issues),
            "active_case_count": len(active_cases),
        }
        if score["passed"]:
            return result, None
        return result, _build_candidate_gate_issue(component_key, result)

    def _collect_generated_tests(
        self,
        package: dict[str, Any],
    ) -> tuple[list[TestCase], list[FailureIssue], list[dict[str, Any]]]:
        problem: ProblemContext = package["problem_context"]
        issues: list[FailureIssue] = []
        matrix: list[dict[str, Any]] = []
        raw_tests: list[dict[str, Any]] = []

        for key, source, purpose in [
            ("random_test_generator", "random_test_input", "随机测试输入"),
            ("adversarial_test_generator", "adversarial_test_input", "边界与最坏情况测试输入"),
        ]:
            artifact = package.get(key)
            if not isinstance(artifact, GeneratedCodeArtifact):
                issues.append(
                    FailureIssue(
                        category="test_generator_failed",
                        severity="blocker",
                        title="测试输入生成器缺失",
                        detail=f"缺少 {key} 产物。",
                        fix_hint="回流 TestGenerator，重新生成三类测试输入产物。",
                    )
                )
                continue
            execution = self.runner.run_generate_test_input(
                artifact_name=artifact.name,
                code=artifact.code,
                timeout_s=self.run_timeout_s,
            )
            matrix.append(to_dict(execution))
            if execution.status != "ok":
                issues.append(
                    FailureIssue(
                        category="test_generator_failed",
                        severity="blocker",
                        title="测试输入生成器执行失败",
                        detail=f"{key} 执行失败：{execution.error_reason or execution.status}",
                        fix_hint="回流 TestGenerator，修复 generate_test_input 接口或运行错误。",
                    )
                )
                continue
            input_text = str(execution.result).strip()
            if not input_text:
                issues.append(
                    FailureIssue(
                        category="test_generator_failed",
                        severity="blocker",
                        title="测试输入生成器返回空输入",
                        detail=f"{key} 返回空字符串。",
                        fix_hint="回流 TestGenerator，要求 generate_test_input 返回完整合法输入。",
                    )
                )
                continue
            validate_func = self.runner.run_validate_test_input(
                artifact_name=artifact.name,
                code=artifact.code,
                input_data=input_text,
                timeout_s=self.run_timeout_s,
            )
            matrix.append(to_dict(validate_func))
            if validate_func.status == "ok" and validate_func.result is not True:
                issues.append(
                    FailureIssue(
                        category="test_generator_failed",
                        severity="high",
                        title="测试输入生成器自校验失败",
                        detail=f"{key} 生成的输入未通过自身 validate_test_input。",
                        fix_hint="回流 TestGenerator，统一生成逻辑与校验逻辑。",
                    )
                )
                continue
            raw_tests.append(
                {
                    "input": input_text,
                    "source": source,
                    "purpose": purpose,
                    "expect_bruteforce": source != "adversarial_test_input",
                    "is_large": source == "adversarial_test_input",
                    "metadata": {"generator": key},
                }
            )

        small_tests = package.get("small_challenge_tests", [])
        if isinstance(small_tests, list):
            raw_tests.extend(small_tests)
        else:
            issues.append(
                FailureIssue(
                    category="test_generator_failed",
                    severity="blocker",
                    title="小规模挑战输入结构非法",
                    detail="small_challenge_tests 必须是列表。",
                    fix_hint="回流 TestGenerator，重新生成小规模挑战输入列表。",
                )
            )

        try:
            tests = normalize_tests(raw_tests, problem)
        except ValueError as exc:
            issues.append(
                FailureIssue(
                    category="test_generator_failed",
                    severity="blocker",
                    title="测试输入归一化失败",
                    detail=str(exc),
                    fix_hint="回流 TestGenerator，修正测试输入产物结构。",
                )
            )
            tests = []
        return tests, issues, matrix

    def _validate_package(
        self,
        package: dict[str, Any],
        previous_active_context: dict[str, Any] | None = None,
        *,
        regression_cases: list[TestCase] | None = None,
        known_good_cases: list[TestCase] | None = None,
        active_cases: list[TestCase] | None = None,
        component_gate_issues: list[FailureIssue] | None = None,
        component_gate_results: dict[str, Any] | None = None,
        candidate_package_gate_results: dict[str, Any] | None = None,
        build_revision_advice: bool = True,
    ) -> ValidationReport:
        problem: ProblemContext = package["problem_context"]
        standard: GeneratedCodeArtifact = package["standard_solution"]
        bruteforce: GeneratedCodeArtifact = package["bruteforce_solution"]
        validator: GeneratedCodeArtifact = package["validator"]
        checker: GeneratedCodeArtifact = package["checker"]
        wrong_solutions: list[WrongSolution] = package["wrong_solutions"]

        effective_regression_cases = self._regression_cases if regression_cases is None else regression_cases
        effective_known_good_cases = self._known_good_cases if known_good_cases is None else known_good_cases
        effective_active_cases = active_cases or []
        effective_component_gate_issues = self._component_gate_issues if component_gate_issues is None else component_gate_issues
        effective_component_gate_results = (
            self._component_gate_results if component_gate_results is None else component_gate_results
        )
        effective_candidate_package_gate_results = (
            self._candidate_package_gate_results
            if candidate_package_gate_results is None
            else candidate_package_gate_results
        )

        issues: list[FailureIssue] = list(effective_component_gate_issues)
        matrix: list[dict[str, Any]] = []
        expected_outputs: dict[str, str] = {}
        regression_results: dict[str, Any] = {
            "configured_count": len(effective_regression_cases),
            "executed_count": 0,
            "sources": [item.source for item in effective_regression_cases[:10]],
        }
        known_good_results: dict[str, Any] = {
            "configured_count": len(effective_known_good_cases),
            "executed_count": 0,
            "passed_count": 0,
            "failed_count": 0,
            "sources": [item.source for item in effective_known_good_cases[:10]],
            "failed_sources": [],
            "passed_cases": [],
        }
        semantic_gate_issues = _evaluate_semantic_gate(problem, checker)
        issues.extend(semantic_gate_issues)
        base_checks: dict[str, Any] = {
            "passed": True,
            "failed_categories": [],
            "validated_test_count": 0,
            "standard_checked_count": 0,
            "bruteforce_checked_count": 0,
            "wrong_solution_curation_skipped": False,
        }

        self._emit("[验证] 运行三类测试输入生成器，生成测试用例。")
        tests, generation_issues, generation_matrix = self._collect_generated_tests(package)
        issues.extend(generation_issues)
        matrix.extend(generation_matrix)
        if effective_regression_cases:
            tests = _prepend_priority_cases(_mark_case_group(effective_regression_cases, "regression"), tests)
            regression_results["executed_count"] = len(effective_regression_cases)
        if effective_active_cases:
            tests = _prepend_priority_cases(_mark_case_group(effective_active_cases, "active"), tests)
        if effective_known_good_cases:
            tests = _prepend_priority_cases(_mark_case_group(effective_known_good_cases, "known_good"), tests)
        self._emit(f"[验证] 可执行测试用例数量：{len(tests)}。")
        if not tests:
            issues.append(
                FailureIssue(
                    category="test_suite_empty",
                    severity="blocker",
                    title="测试生成器未产出有效测试",
                    detail="三类测试输入产物未返回任何可执行输入，无法验证标准解、正确暴力解和错误解池。",
                    fix_hint="回流 TestGenerator，要求至少生成样例、边界和基础随机测试。",
                )
            )

        known_good_failure_keys: set[str] = set()

        def append_issue_for_test(issue: FailureIssue, test: TestCase, *, failed: bool = True) -> bool:
            issues.append(issue)
            if failed and _is_known_good_case(test):
                key = _case_identity(test)
                if key not in known_good_failure_keys:
                    known_good_failure_keys.add(key)
                    issues.append(_build_known_good_failure_issue(test, issue))
            return True

        def finalize_case(test: TestCase, *, failed: bool) -> None:
            if _is_known_good_case(test):
                known_good_results["executed_count"] += 1
                if failed:
                    known_good_results["failed_count"] += 1
                    known_good_results["failed_sources"].append(test.source)
                else:
                    known_good_results["passed_count"] += 1
            if not failed and _should_record_known_good_case(test):
                known_good_results["passed_cases"].append(to_dict(_as_known_good_case(test)))

        for test_index, test in enumerate(tests, start=1):
            test_failed = False
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
                test_failed = append_issue_for_test(
                    FailureIssue(
                        category="validator_rejects_generated_case",
                        severity="high",
                        title="validator 拒绝生成测试",
                        detail=f"测试 {test.source} 未通过输入合法性检查。",
                        evidence_refs=[test.source],
                        evidence=_build_failure_evidence(test=test, validator_result=validation),
                        fix_hint="回流 ToolGenerator 或测试生成器，修正输入约束或测试生成逻辑。",
                    ),
                    test,
                )
                finalize_case(test, failed=test_failed)
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
                test_failed = append_issue_for_test(
                    FailureIssue(
                        category="performance_failure" if standard_result.status == "timeout" or test.is_large else "standard_solution_failed",
                        severity="blocker",
                        title="标准解执行失败",
                        detail=standard_result.error_reason or standard_result.status,
                        evidence_refs=[test.source],
                        evidence=_build_failure_evidence(test=test, standard_result=standard_result),
                        fix_hint="回流 StandardSolutionGenerator，修正实现或复杂度。",
                    ),
                    test,
                )
                finalize_case(test, failed=test_failed)
                continue
            expected_outputs[test.source] = str(standard_result.result)

            bruteforce_expected: str | None = None
            bruteforce_mismatch = False
            if test.expect_bruteforce and not test.is_large:
                self._emit(f"[验证] 测试 {test_index}/{len(tests)}（{test_label}）：运行正确暴力解。")
                bruteforce_result = self.runner.run_solve(
                    artifact_name=bruteforce.name,
                    code=bruteforce.code,
                    input_data=test.input,
                    test_source=test.source,
                    timeout_s=self.run_timeout_s,
                )
                matrix.append(to_dict(bruteforce_result))
                if bruteforce_result.status != "ok":
                    test_failed = append_issue_for_test(
                        FailureIssue(
                            category="bruteforce_failed",
                            severity="high",
                            title="正确暴力解执行失败",
                            detail=bruteforce_result.error_reason or bruteforce_result.status,
                            evidence_refs=[test.source],
                            evidence=_build_failure_evidence(
                                test=test,
                                standard_output=standard_result.result,
                                bruteforce_result=bruteforce_result,
                            ),
                            fix_hint="回流 BruteForceSolutionGenerator，修正暴力逻辑或适用范围。",
                        ),
                        test,
                    )
                else:
                    bruteforce_expected = str(bruteforce_result.result)
                    if problem.judge_type == "exact" and _normalize_output(bruteforce_expected) != _normalize_output(str(standard_result.result)):
                        bruteforce_mismatch = True

            self._emit(f"[验证] 测试 {test_index}/{len(tests)}（{test_label}）：运行 checker 校验标准解输出。")
            checker_result = self.runner.run_check(
                artifact_name=checker.name,
                code=checker.code,
                input_data=test.input,
                output_data=str(standard_result.result),
                expected_data=bruteforce_expected,
                test_source=test.source,
                timeout_s=self.run_timeout_s,
            )
            matrix.append(to_dict(checker_result))
            if bruteforce_mismatch:
                test_failed = append_issue_for_test(
                    FailureIssue(
                        category="standard_bruteforce_mismatch",
                        severity="blocker",
                        title="标准解与正确暴力解不一致",
                        detail=f"测试 {test.source} 上标准解输出与正确暴力解输出不同。",
                        evidence_refs=[test.source],
                        evidence=_build_failure_evidence(
                            test=test,
                            standard_output=standard_result.result,
                            bruteforce_output=bruteforce_expected,
                            checker_result=checker_result,
                        ),
                        fix_hint="回流 StandardSolutionGenerator 与 BruteForceSolutionGenerator，定位反例。",
                    ),
                    test,
                )
            if checker_result.status != "ok" or checker_result.result is not True:
                test_failed = append_issue_for_test(
                    FailureIssue(
                        category="checker_rejects_standard_output",
                        severity="blocker",
                        title="checker 拒绝标准解输出",
                        detail=_checker_reject_detail(problem, checker_result.error_reason or f"测试 {test.source} 的标准输出未被 checker 接受。"),
                        evidence_refs=[test.source],
                            evidence=_build_failure_evidence(
                                test=test,
                                standard_output=standard_result.result,
                                bruteforce_output=bruteforce_expected,
                                checker_result=checker_result,
                            ),
                        fix_hint="回流 ToolGenerator 和 StandardSolutionGenerator，确认 checker 合法性谓词与标准解输出。",
                    ),
                    test,
                )
            else:
                base_checks["standard_checked_count"] += 1

            if problem.judge_type == "checker" and bruteforce_expected is not None:
                self._emit(f"[验证] 测试 {test_index}/{len(tests)}（{test_label}）：运行 checker 校验正确暴力解输出。")
                bruteforce_checker_result = self.runner.run_check(
                    artifact_name=checker.name,
                    code=checker.code,
                    input_data=test.input,
                    output_data=bruteforce_expected,
                    expected_data=bruteforce_expected,
                    test_source=test.source,
                    timeout_s=self.run_timeout_s,
                )
                matrix.append(to_dict(bruteforce_checker_result))
                if bruteforce_checker_result.status != "ok" or bruteforce_checker_result.result is not True:
                    test_failed = append_issue_for_test(
                        FailureIssue(
                            category="bruteforce_output_rejected_by_checker",
                            severity="blocker",
                            title="checker 拒绝正确暴力解输出",
                            detail=_checker_reject_detail(
                                problem,
                                bruteforce_checker_result.error_reason or f"测试 {test.source} 的正确暴力解输出未被 checker 接受。",
                            ),
                            evidence_refs=[test.source],
                            evidence=_build_failure_evidence(
                                test=test,
                                standard_output=standard_result.result,
                                bruteforce_output=bruteforce_expected,
                                checker_result=bruteforce_checker_result,
                            ),
                            fix_hint="回流 ToolGenerator 和 BruteForceSolutionGenerator，确认 checker 合法性谓词与暴力解输出。",
                        ),
                        test,
                    )
                else:
                    base_checks["bruteforce_checked_count"] += 1

            finalize_case(test, failed=test_failed)

        baseline_issues = [
            item
            for item in issues
            if item.severity in {"blocker", "high"} and item.category not in CANDIDATE_GATE_DIAGNOSTIC_CATEGORIES
        ]
        if baseline_issues:
            base_checks["passed"] = False
            base_checks["failed_categories"] = [item.category for item in baseline_issues]
            base_checks["wrong_solution_curation_skipped"] = True
            curation = {
                "independent_solutions": [],
                "high_value_survivors": [],
                "unexpected_correct_candidates": [],
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
                    detail="validator、标准解、正确暴力解或 checker 的基础自洽检查未通过，本轮杀伤率不可作为可信指标。",
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
            high_value_survivors = list(curation.get("high_value_survivors", []))
            unexpected_correct_candidates = list(curation.get("unexpected_correct_candidates", []))
            if high_value_survivors or not wrong_stats["passed_threshold"]:
                issues.append(
                    FailureIssue(
                        category="wrong_solution_survived",
                        severity="high",
                        title="错误解筛选未满足严格通过条件",
                        detail=_build_wrong_solution_gate_detail(
                            wrong_stats=wrong_stats,
                            high_value_survivors=high_value_survivors,
                            unexpected_correct_candidates=unexpected_correct_candidates,
                        ),
                        fix_hint="回流测试生成器，针对幸存错误解补充反例。",
                    )
                )

        status = "pass" if not [item for item in issues if item.severity in {"blocker", "high"}] else "revise"
        semantic_gate_status = "failed" if semantic_gate_issues else "passed"
        revision_context = _build_revision_context(
            issues,
            curation,
            revision_advisor=self.revision_advisor if build_revision_advice else None,
            current_package=package,
            previous_active_context=previous_active_context,
        )
        report = ValidationReport(
            overall={
                "status": status,
                "issue_count": len(issues),
                "stop_reason": "" if status == "pass" else "validation_failed",
                "semantic_gate_status": semantic_gate_status,
            },
            issues=[to_dict(item) for item in issues],
            execution_matrix=matrix,
            wrong_solution_stats=wrong_stats,
            revision_context=revision_context,
            base_consistency=base_checks,
            component_gate_results=copy.deepcopy(effective_component_gate_results),
            regression_results=regression_results,
            semantic_gate_issues=[to_dict(item) for item in semantic_gate_issues],
            candidate_package_gate_results=copy.deepcopy(effective_candidate_package_gate_results),
            known_good_results=known_good_results,
            candidate_delta_summary=_candidate_delta_summary_from_gate_results(effective_candidate_package_gate_results),
        )
        return report

    def _write_round_package(self, round_dir: Path, package: dict[str, Any]) -> None:
        round_dir.mkdir(parents=True, exist_ok=True)
        (round_dir / "problem_context.json").write_text(
            json.dumps(to_dict(package["problem_context"]), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (round_dir / "schema_mistake_points.json").write_text(
            json.dumps(to_dict(package.get("schema_mistake_points", [])), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _write_code_artifact(round_dir / "standard_solution.py", package["standard_solution"])
        _write_code_artifact(round_dir / "bruteforce_solution.py", package["bruteforce_solution"])
        _write_code_artifact(round_dir / "validator.py", package["validator"])
        _write_code_artifact(round_dir / "checker.py", package["checker"])
        test_input_dir = round_dir / "test_inputs"
        test_input_dir.mkdir(parents=True, exist_ok=True)
        _write_code_artifact(test_input_dir / "random_generator.py", package["random_test_generator"])
        _write_code_artifact(test_input_dir / "adversarial_generator.py", package["adversarial_test_generator"])
        (test_input_dir / "small_challenge_inputs.json").write_text(
            json.dumps(to_dict(package.get("small_challenge_tests", [])), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
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
        "new_schema_snapshot": new_schema,
        "new_schema": new_schema,
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


def _json_size(value: Any) -> int:
    return len(json.dumps(to_dict(value), ensure_ascii=False, sort_keys=True).encode("utf-8"))


def _compact_text(text: Any, *, limit: int = 1200) -> str:
    value = "" if text is None else str(text)
    if len(value) <= limit:
        return value
    edge = max(200, limit // 2)
    return value[:edge] + "\n...<truncated>...\n" + value[-edge:]


def _compact_revision_context(revision_context: Any) -> dict[str, Any]:
    if not isinstance(revision_context, dict) or not revision_context:
        return {}
    diagnostics = [_compact_diagnostic(item) for item in _flatten_diagnostics(revision_context)]
    compact_by_category: dict[str, list[dict[str, Any]]] = {}
    for item in diagnostics:
        category = str(item.get("category", ""))
        if not category:
            continue
        compact_by_category.setdefault(category, [])
        if len(compact_by_category[category]) < _ROLE_DIAGNOSTIC_LIMIT_PER_CATEGORY:
            compact_by_category[category].append(item)
    role_diagnostics: dict[str, list[dict[str, Any]]] = {}
    for items in compact_by_category.values():
        for item in items:
            if _is_non_routing_diagnostic(item):
                continue
            for role in item.get("target_roles", []):
                role_diagnostics.setdefault(str(role), []).append(copy.deepcopy(item))
    return {
        "summary": copy.deepcopy(revision_context.get("summary", []))[:6],
        "diagnostics_by_category": compact_by_category,
        "role_diagnostics": role_diagnostics,
        "failed_hard_checks": copy.deepcopy(revision_context.get("failed_hard_checks", []))[:8],
        "surviving_wrong_solution_details": copy.deepcopy(revision_context.get("surviving_wrong_solution_details", []))[:5],
        "context_management": copy.deepcopy(revision_context.get("context_management", {})),
    }


def _compact_diagnostic(diagnostic: dict[str, Any]) -> dict[str, Any]:
    evidence = diagnostic.get("evidence") if isinstance(diagnostic.get("evidence"), dict) else {}
    compact = {
        "category": diagnostic.get("category", ""),
        "severity": diagnostic.get("severity", ""),
        "title": diagnostic.get("title", ""),
        "detail": _compact_text(diagnostic.get("detail", ""), limit=600),
        "fix_hint": _compact_text(diagnostic.get("fix_hint", ""), limit=600),
        "target_roles": list(diagnostic.get("target_roles", [])),
        "issue_fingerprint": diagnostic.get("issue_fingerprint", ""),
        "evidence": _compact_evidence_for_prompt(evidence),
    }
    if diagnostic.get("diff"):
        compact["diff"] = copy.deepcopy(diagnostic.get("diff"))
    if diagnostic.get("advisor_revision"):
        advisor = copy.deepcopy(diagnostic.get("advisor_revision"))
        if isinstance(advisor, dict):
            advisor["revision_advice"] = _compact_text(advisor.get("revision_advice", ""), limit=1200)
            advisor["root_cause"] = _compact_text(advisor.get("root_cause", ""), limit=800)
        compact["advisor_revision"] = advisor
    return compact


def _compact_evidence_for_prompt(evidence: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key in ("test", "test_source"):
        if key in evidence:
            compact[key] = copy.deepcopy(evidence[key])
    for key in ("input", "standard_output", "bruteforce_output"):
        if key in evidence:
            compact[key] = _compact_text(evidence[key], limit=1000)
    for key, value in evidence.items():
        if key.endswith("_result") and isinstance(value, dict):
            compact[key] = {
                "status": value.get("status", ""),
                "result": value.get("result", None),
                "error_reason": _compact_text(value.get("error_reason", ""), limit=600),
                "elapsed_ms": value.get("elapsed_ms", 0),
            }
    return compact


def _compact_revision_history(revision_audit_history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    history = []
    for item in revision_audit_history[-3:]:
        revision_context = item.get("revision_context", {}) if isinstance(item, dict) else {}
        history.append(
            {
                "round_index": item.get("round_index", 0) if isinstance(item, dict) else 0,
                "summary": copy.deepcopy(revision_context.get("summary", []))[:6]
                if isinstance(revision_context, dict)
                else [],
                "failed_hard_checks": copy.deepcopy(revision_context.get("failed_hard_checks", []))[:8]
                if isinstance(revision_context, dict)
                else [],
            }
        )
    return history


def _regression_case_summaries(regression_cases: list[TestCase]) -> list[dict[str, Any]]:
    summaries = []
    for case in regression_cases[:5]:
        summaries.append(
            {
                "source": case.source,
                "purpose": case.purpose,
                "is_large": case.is_large,
                "expect_bruteforce": case.expect_bruteforce,
                "metadata": dict(case.metadata),
                "input_excerpt": _compact_text(case.input, limit=500),
            }
        )
    return summaries


def _known_good_case_summaries(known_good_cases: list[TestCase]) -> list[dict[str, Any]]:
    summaries = []
    for case in known_good_cases[:5]:
        summaries.append(
            {
                "source": case.source,
                "purpose": case.purpose,
                "is_sample": case.is_sample,
                "is_large": case.is_large,
                "expect_bruteforce": case.expect_bruteforce,
                "metadata": dict(case.metadata),
                "input_excerpt": _compact_text(case.input, limit=500),
            }
        )
    return summaries


def _build_generation_revision_context(
    *,
    active_revision_context: dict[str, Any],
    revision_audit_history: list[dict[str, Any]],
    current_package: dict[str, Any] | None,
    round_index: int,
    baseline_repair_mode: bool = False,
    regression_cases: list[TestCase] | None = None,
    known_good_cases: list[TestCase] | None = None,
) -> dict[str, Any]:
    if not active_revision_context:
        return {}
    context = _compact_revision_context(active_revision_context)
    context.update(
        {
            "active_revision_context": _compact_revision_context(active_revision_context),
            "latest_revision": _compact_revision_context(revision_audit_history[-1]["revision_context"]) if revision_audit_history else {},
            "revision_history": _compact_revision_history(revision_audit_history),
            "revision_mode": "incremental_patch",
            "baseline_repair_mode": bool(baseline_repair_mode),
            "baseline_round": 1,
            "current_round": round_index,
            "current_artifact": _current_artifact_summary(current_package, None),
            "frozen_contract_summary": _frozen_contract_summary(current_package),
            "regression_case_summaries": _regression_case_summaries(regression_cases or []),
            "known_good_case_summaries": _known_good_case_summaries(known_good_cases or []),
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
    roles: set[str] = set()
    for role, diagnostics in role_diagnostics.items():
        if not isinstance(diagnostics, list):
            continue
        if any(isinstance(item, dict) and not _is_non_routing_diagnostic(item) for item in diagnostics):
            roles.add(str(role))
    return roles


def _concrete_baseline_fingerprints(report: ValidationReport) -> set[str]:
    failed_categories = {
        str(category)
        for category in report.base_consistency.get("failed_categories", [])
        if str(category) and str(category) not in DERIVED_NON_ROUTING_CATEGORIES
    }
    fingerprints: set[str] = set()
    for diagnostic in _flatten_diagnostics(report.revision_context):
        category = str(diagnostic.get("category", ""))
        if category not in failed_categories or _is_non_routing_diagnostic(diagnostic):
            continue
        fingerprint = str(diagnostic.get("issue_fingerprint", "")).strip()
        if fingerprint:
            fingerprints.add(fingerprint)
    return fingerprints


def _baseline_stall_signature(report: ValidationReport) -> str:
    categories = sorted(
        str(category)
        for category in report.base_consistency.get("failed_categories", [])
        if str(category) and str(category) not in DERIVED_NON_ROUTING_CATEGORIES
    )
    diagnostics = []
    for item in _flatten_diagnostics(report.revision_context):
        category = str(item.get("category", ""))
        if category not in categories:
            continue
        evidence = item.get("evidence", {}) if isinstance(item.get("evidence"), dict) else {}
        test = evidence.get("test") if isinstance(evidence.get("test"), dict) else {}
        diagnostics.append(
            {
                "category": category,
                "status": {
                    key: value.get("status")
                    for key, value in evidence.items()
                    if key.endswith("_result") and isinstance(value, dict)
                },
                "diff": _fingerprint_diff_shape(item.get("diff", {})),
            }
        )
    basis = {"categories": categories, "diagnostics": diagnostics[:12]}
    return hashlib.sha1(json.dumps(basis, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def _revision_context_for_roles(
    revision_context: dict[str, Any],
    roles: set[str],
    current_package: dict[str, Any] | None,
) -> dict[str, Any]:
    diagnostics = [
        diagnostic
        for diagnostic in _flatten_diagnostics(revision_context)
        if not _is_non_routing_diagnostic(diagnostic) and roles & {str(role) for role in diagnostic.get("target_roles", [])}
    ]
    filtered = _revision_context_from_diagnostics(
        diagnostics,
        revision_context.get("surviving_wrong_solution_details", []),
    )
    filtered.update(
        {
            "active_revision_context": copy.deepcopy(filtered),
            "latest_revision": _compact_revision_context(revision_context.get("latest_revision", {})),
            "revision_history": copy.deepcopy(revision_context.get("revision_history", []))[:3],
            "revision_mode": revision_context.get("revision_mode", "incremental_patch"),
            "baseline_repair_mode": bool(revision_context.get("baseline_repair_mode", False)),
            "baseline_round": revision_context.get("baseline_round", 1),
            "current_round": revision_context.get("current_round", 0),
            "current_artifact": _current_artifact_summary(current_package, roles),
            "frozen_contract_summary": _frozen_contract_summary(current_package),
            "regression_case_summaries": copy.deepcopy(revision_context.get("regression_case_summaries", []))[:3],
            "known_good_case_summaries": copy.deepcopy(revision_context.get("known_good_case_summaries", []))[:3],
        }
    )
    return filtered


def _split_wrong_solutions(wrong_solutions: list[WrongSolution]) -> tuple[list[WrongSolution], list[WrongSolution]]:
    fixed_wrong: list[WrongSolution] = []
    strategy_wrong: list[WrongSolution] = []
    for item in wrong_solutions:
        if item.source == "fixed_category_llm_player":
            fixed_wrong.append(item)
        else:
            strategy_wrong.append(item)
    return fixed_wrong, strategy_wrong


def _current_artifact_summary(current_package: dict[str, Any] | None, roles: set[str] | None) -> dict[str, Any]:
    if not current_package:
        return {}
    include_all = roles is None
    summary: dict[str, Any] = {}
    if include_all or "ProblemContextBuilder" in roles:
        summary["problem_context"] = to_dict(current_package.get("problem_context"))
    if include_all or "StandardSolutionGenerator" in roles:
        summary["standard_solution"] = _code_artifact_for_context(current_package.get("standard_solution"))
    if include_all or "BruteForceSolutionGenerator" in roles:
        summary["bruteforce_solution"] = _code_artifact_for_context(current_package.get("bruteforce_solution"))
    if include_all or {"ToolGenerator", "ValidatorGenerator"} & roles:
        summary["validator"] = _code_artifact_for_context(current_package.get("validator"))
    if include_all or {"ToolGenerator", "CheckerGenerator"} & roles:
        summary["checker"] = _code_artifact_for_context(current_package.get("checker"))
    if include_all or {"ToolGenerator", "TestGenerator"} & roles:
        summary["random_test_generator"] = _code_artifact_for_context(current_package.get("random_test_generator"))
        summary["adversarial_test_generator"] = _code_artifact_for_context(current_package.get("adversarial_test_generator"))
        summary["small_challenge_tests"] = to_dict(current_package.get("small_challenge_tests", []))
    if include_all or "SchemaMistakeAnalyzer" in roles:
        summary["schema_mistake_points"] = to_dict(current_package.get("schema_mistake_points", []))
    if include_all or {"FixedCategoryWrongSolutionGenerator", "StrategyWrongSolutionGenerator"} & roles:
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
        "code_excerpt": _compact_text(value.code, limit=6000),
        "code_length": len(value.code),
        "code_truncated": len(value.code) > 6000,
        "metadata": value.metadata,
    }


def _frozen_contract_summary(current_package: dict[str, Any] | None) -> dict[str, Any]:
    if not current_package:
        return {}
    problem = current_package.get("problem_context")
    if not isinstance(problem, ProblemContext):
        return {}
    return {
        "problem_id": problem.problem_id,
        "judge_type": problem.judge_type,
        "generated_problem": problem.generated_problem,
        "schema_snapshot": problem.schema_snapshot,
    }


_SEVERITY_RANK = {"info": 0, "low": 1, "medium": 2, "high": 3, "blocker": 4}

_TARGET_ROLES_BY_CATEGORY = {
    "test_generator_failed": ["TestGenerator"],
    "test_suite_empty": ["TestGenerator"],
    "validator_rejects_generated_case": ["ValidatorGenerator", "TestGenerator"],
    "checker_rejects_standard_output": ["CheckerGenerator", "StandardSolutionGenerator"],
    "standard_solution_failed": ["StandardSolutionGenerator"],
    "performance_failure": ["StandardSolutionGenerator"],
    "bruteforce_failed": ["BruteForceSolutionGenerator"],
    "bruteforce_output_rejected_by_checker": ["CheckerGenerator", "BruteForceSolutionGenerator"],
    "standard_bruteforce_mismatch": ["StandardSolutionGenerator", "BruteForceSolutionGenerator"],
    "wrong_solution_survived": ["TestGenerator", "FixedCategoryWrongSolutionGenerator", "SchemaMistakeAnalyzer", "StrategyWrongSolutionGenerator"],
    "kill_rate_skipped_due_to_invalid_baseline": ["TestGenerator", "StandardSolutionGenerator", "BruteForceSolutionGenerator"],
    "component_gate_failed": ["ValidatorGenerator", "CheckerGenerator", "TestGenerator", "StandardSolutionGenerator", "BruteForceSolutionGenerator"],
    "revision_payload_too_large": ["TestGenerator", "StandardSolutionGenerator", "BruteForceSolutionGenerator"],
    "semantic_kernel_required": ["CheckerGenerator", "ProblemContextBuilder"],
    "statement_revision_required": ["ProblemContextBuilder"],
    "candidate_regression_detected": ["ValidatorGenerator", "CheckerGenerator", "TestGenerator", "StandardSolutionGenerator", "BruteForceSolutionGenerator"],
    "known_good_case_failed": ["ValidatorGenerator", "CheckerGenerator", "TestGenerator", "StandardSolutionGenerator", "BruteForceSolutionGenerator"],
    "candidate_not_better_than_current": ["ValidatorGenerator", "CheckerGenerator", "TestGenerator", "StandardSolutionGenerator", "BruteForceSolutionGenerator"],
}

DERIVED_NON_ROUTING_CATEGORIES = {"kill_rate_skipped_due_to_invalid_baseline"}
CANDIDATE_GATE_DIAGNOSTIC_CATEGORIES = {"candidate_regression_detected", "candidate_not_better_than_current"}

_ROLE_DIAGNOSTIC_LIMIT_PER_CATEGORY = 3
_ADVISOR_DIAGNOSTIC_LIMIT_PER_CATEGORY = 3
_FULL_EVIDENCE_TEXT_LIMIT = 1800
_TRUNCATED_TEXT_EDGE = 700
_DIFF_WINDOW = 3


def _is_non_routing_diagnostic(diagnostic: dict[str, Any]) -> bool:
    return str(diagnostic.get("category", "")) in DERIVED_NON_ROUTING_CATEGORIES


def _advisor_target_roles(diagnostic: dict[str, Any]) -> list[str]:
    advisor_revision = diagnostic.get("advisor_revision")
    if not isinstance(advisor_revision, dict):
        return []
    target_roles = advisor_revision.get("target_roles")
    if not isinstance(target_roles, list):
        return []
    return [str(role) for role in target_roles if str(role)]


def _apply_advisor_target_roles(diagnostics_by_category: dict[str, list[dict[str, Any]]]) -> None:
    for diagnostics in diagnostics_by_category.values():
        for diagnostic in diagnostics:
            advisor_roles = _advisor_target_roles(diagnostic)
            if advisor_roles:
                diagnostic["target_roles"] = advisor_roles


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
    _apply_advisor_target_roles(diagnostics_by_category)

    role_diagnostics: dict[str, list[dict[str, Any]]] = {}
    for diagnostics in diagnostics_by_category.values():
        by_role_category_count: dict[tuple[str, str], int] = {}
        for diagnostic in diagnostics:
            if _is_non_routing_diagnostic(diagnostic):
                continue
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
        "failed_hard_checks": _dedupe(
            [
                issue.category
                for issue in issues
                if issue.severity == "blocker" and issue.category not in DERIVED_NON_ROUTING_CATEGORIES
            ]
        ),
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
            if _is_non_routing_diagnostic(diagnostic):
                continue
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
                if str(item.get("severity", "")) == "blocker" and str(item.get("category", "")) and not _is_non_routing_diagnostic(item)
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


def _component_gate_inputs(package: dict[str, Any], regression_cases: list[TestCase]) -> list[TestCase]:
    cases: list[TestCase] = []
    problem = package.get("problem_context")
    if isinstance(problem, ProblemContext):
        for index, sample in enumerate(problem.sample_tests[:3], start=1):
            if not isinstance(sample, dict) or not str(sample.get("input", "")).strip():
                continue
            cases.append(
                TestCase(
                    input=str(sample.get("input", "")),
                    source=str(sample.get("source") or f"sample_{index}"),
                    purpose=str(sample.get("purpose") or "样例门禁"),
                    expect_bruteforce=True,
                    is_sample=True,
                    is_large=False,
                    metadata={"sample_output": str(sample.get("output", ""))},
                )
            )
    cases.extend(regression_cases[:5])
    return _dedupe_tests(cases)


def _prepend_regression_cases(regression_cases: list[TestCase], tests: list[TestCase]) -> list[TestCase]:
    return _dedupe_tests([*regression_cases, *tests])


def _prepend_priority_cases(priority_cases: list[TestCase], tests: list[TestCase]) -> list[TestCase]:
    return _dedupe_tests([*priority_cases, *tests])


def _mark_case_group(cases: list[TestCase], group: str) -> list[TestCase]:
    marked: list[TestCase] = []
    for case in cases:
        metadata = dict(case.metadata)
        metadata[group] = True
        metadata["case_group"] = group
        marked.append(
            TestCase(
                input=case.input,
                source=case.source,
                purpose=case.purpose,
                expect_bruteforce=case.expect_bruteforce,
                is_sample=case.is_sample,
                is_large=case.is_large,
                metadata=metadata,
            )
        )
    return marked


def _is_known_good_case(test: TestCase) -> bool:
    return bool(test.metadata.get("known_good"))


def _should_record_known_good_case(test: TestCase) -> bool:
    return bool(
        test.is_sample
        or test.is_large
        or test.expect_bruteforce
        or test.metadata.get("regression")
        or test.metadata.get("active")
    )


def _as_known_good_case(test: TestCase) -> TestCase:
    metadata = dict(test.metadata)
    metadata["known_good"] = True
    metadata["known_good_source"] = metadata.get("case_group") or "validated"
    return TestCase(
        input=test.input,
        source=f"known_good:{_normalize_test_source(test.source)}",
        purpose=test.purpose or "历史已通过用例",
        expect_bruteforce=test.expect_bruteforce,
        is_sample=test.is_sample,
        is_large=test.is_large,
        metadata=metadata,
    )


def _build_known_good_failure_issue(test: TestCase, source_issue: FailureIssue) -> FailureIssue:
    evidence = copy.deepcopy(source_issue.evidence)
    evidence["known_good_case"] = {
        "source": test.source,
        "purpose": test.purpose,
        "is_sample": test.is_sample,
        "is_large": test.is_large,
        "expect_bruteforce": test.expect_bruteforce,
        "metadata": dict(test.metadata),
    }
    evidence["source_failure_category"] = source_issue.category
    return FailureIssue(
        category="known_good_case_failed",
        severity="blocker",
        title="候选包破坏已通过用例",
        detail=f"已记录为 known-good 的用例 {test.source} 在当前验证中失败，原始失败类别为 {source_issue.category}。",
        evidence_refs=[test.source],
        evidence=evidence,
        fix_hint="保留上一轮组件；下一轮只能修复 active 问题，不能破坏 known-good 路径。",
    )


def _case_identity(test: TestCase) -> str:
    return hashlib.sha1(test.input.encode("utf-8")).hexdigest()[:16]


def _dedupe_tests(tests: list[TestCase]) -> list[TestCase]:
    seen: set[str] = set()
    result: list[TestCase] = []
    for test in tests:
        key = test.input
        if key in seen:
            continue
        seen.add(key)
        result.append(test)
    return result


def _extract_regression_cases(report: ValidationReport) -> list[TestCase]:
    cases: list[TestCase] = []
    for issue in report.issues:
        if not isinstance(issue, dict):
            continue
        evidence = issue.get("evidence") if isinstance(issue.get("evidence"), dict) else {}
        test = evidence.get("test") if isinstance(evidence.get("test"), dict) else {}
        input_data = evidence.get("input")
        if not isinstance(input_data, str) or not input_data.strip():
            continue
        source = _normalize_test_source(str(test.get("source") or evidence.get("test_source") or issue.get("category") or "regression"))
        metadata = dict(test.get("metadata", {}) or {}) if isinstance(test.get("metadata"), dict) else {}
        metadata.update(
            {
                "regression": True,
                "source_issue_category": issue.get("category", ""),
                "source_issue_title": issue.get("title", ""),
            }
        )
        cases.append(
            TestCase(
                input=input_data,
                source=f"regression:{source}",
                purpose=str(test.get("purpose") or issue.get("title") or "历史失败反例"),
                expect_bruteforce=_bool_with_legacy(test, "expect_bruteforce", "expect_oracle", False),
                is_sample=bool(test.get("is_sample", False)),
                is_large=bool(test.get("is_large", False)),
                metadata=metadata,
            )
        )
    return cases


def _extract_active_failure_cases(report: ValidationReport, *, limit: int = 20) -> list[TestCase]:
    cases: list[TestCase] = []
    for issue in report.issues:
        if not isinstance(issue, dict):
            continue
        severity = str(issue.get("severity", ""))
        if severity not in {"blocker", "high"}:
            continue
        evidence = issue.get("evidence") if isinstance(issue.get("evidence"), dict) else {}
        input_data = evidence.get("input")
        if not isinstance(input_data, str) or not input_data.strip():
            continue
        test = evidence.get("test") if isinstance(evidence.get("test"), dict) else {}
        metadata = dict(test.get("metadata", {}) or {}) if isinstance(test.get("metadata"), dict) else {}
        metadata.update(
            {
                "active": True,
                "source_issue_category": issue.get("category", ""),
                "source_issue_title": issue.get("title", ""),
            }
        )
        cases.append(
            TestCase(
                input=input_data,
                source=f"active:{_normalize_test_source(str(test.get('source') or issue.get('category') or 'active'))}",
                purpose=str(test.get("purpose") or issue.get("title") or "active 失败反例"),
                expect_bruteforce=_bool_with_legacy(
                    test,
                    "expect_bruteforce",
                    "expect_oracle",
                    not bool(test.get("is_large", False)),
                ),
                is_sample=bool(test.get("is_sample", False)),
                is_large=bool(test.get("is_large", False)),
                metadata=metadata,
            )
        )
    return _dedupe_tests(cases)[:limit]


def _merge_regression_cases(existing: list[TestCase], new_cases: list[TestCase], *, limit: int = 50) -> list[TestCase]:
    return _dedupe_tests([*existing, *new_cases])[:limit]


def _extract_known_good_cases(report: ValidationReport) -> list[TestCase]:
    cases: list[TestCase] = []
    for item in report.known_good_results.get("passed_cases", []):
        if not isinstance(item, dict):
            continue
        input_text = str(item.get("input", "")).strip()
        if not input_text:
            continue
        metadata = dict(item.get("metadata", {}) or {}) if isinstance(item.get("metadata"), dict) else {}
        metadata["known_good"] = True
        cases.append(
            TestCase(
                input=input_text,
                source=str(item.get("source") or "known_good"),
                purpose=str(item.get("purpose") or "历史已通过用例"),
                expect_bruteforce=_bool_with_legacy(item, "expect_bruteforce", "expect_oracle", True),
                is_sample=bool(item.get("is_sample", False)),
                is_large=bool(item.get("is_large", False)),
                metadata=metadata,
            )
        )
    return cases


def _merge_known_good_cases(existing: list[TestCase], new_cases: list[TestCase], *, limit: int = 80) -> list[TestCase]:
    return _dedupe_tests([*existing, *new_cases])[:limit]


def _score_candidate_package(
    *,
    previous_report: ValidationReport,
    candidate_report: ValidationReport,
) -> dict[str, Any]:
    previous_active_fingerprints = _high_issue_fingerprints(previous_report)
    candidate_fingerprints = _high_issue_fingerprints(candidate_report)
    fixed_fingerprints = sorted(previous_active_fingerprints - candidate_fingerprints)
    previous_high_categories = _high_issue_categories(previous_report)
    candidate_high_categories = _high_issue_categories(candidate_report)
    introduced_categories = sorted(candidate_high_categories - previous_high_categories)
    previous_high_count = len(previous_active_fingerprints)
    candidate_high_count = len(candidate_fingerprints)
    active_improved = bool(fixed_fingerprints) or candidate_high_count < previous_high_count or not previous_active_fingerprints

    known_good_results = candidate_report.known_good_results or {}
    known_good_failed_sources = list(known_good_results.get("failed_sources", []))
    known_good_passed = int(known_good_results.get("failed_count", 0) or 0) == 0

    semantic_not_increased = len(candidate_report.semantic_gate_issues) <= len(previous_report.semantic_gate_issues)
    kill_rate_not_decreased = _kill_rate_not_decreased(previous_report, candidate_report)

    rejection_reasons: list[str] = []
    if not active_improved:
        rejection_reasons.append("candidate_not_better_than_current")
    if introduced_categories:
        rejection_reasons.append("new_blocker_high_category")
    if not known_good_passed:
        rejection_reasons.append("known_good_case_failed")
    if not semantic_not_increased:
        rejection_reasons.append("semantic_gate_issues_increased")
    if not kill_rate_not_decreased:
        rejection_reasons.append("kill_rate_decreased")

    regression_detected = bool(
        introduced_categories
        or known_good_failed_sources
        or not semantic_not_increased
        or not kill_rate_not_decreased
    )
    return {
        "passed": not rejection_reasons,
        "rejection_reasons": rejection_reasons,
        "regression_detected": regression_detected,
        "fixed_issue_fingerprints": fixed_fingerprints,
        "introduced_blocker_high_categories": introduced_categories,
        "known_good_failed_sources": known_good_failed_sources,
        "active_high_before": previous_high_count,
        "active_high_after": candidate_high_count,
        "active_improved": active_improved,
        "known_good_passed": known_good_passed,
        "semantic_not_increased": semantic_not_increased,
        "kill_rate_not_decreased": kill_rate_not_decreased,
    }


def _high_issue_fingerprints(report: ValidationReport) -> set[str]:
    fingerprints: set[str] = set()
    for diagnostic in _flatten_diagnostics(report.revision_context):
        if str(diagnostic.get("severity", "")) not in {"blocker", "high"}:
            continue
        if str(diagnostic.get("category", "")) in CANDIDATE_GATE_DIAGNOSTIC_CATEGORIES:
            continue
        if _is_non_routing_diagnostic(diagnostic):
            continue
        fingerprints.add(str(diagnostic.get("issue_fingerprint", "") or _issue_fingerprint(diagnostic)))
    return fingerprints


def _high_issue_categories(report: ValidationReport) -> set[str]:
    categories: set[str] = set()
    for issue in report.issues:
        if not isinstance(issue, dict):
            continue
        severity = str(issue.get("severity", ""))
        category = str(issue.get("category", ""))
        if (
            severity in {"blocker", "high"}
            and category
            and category not in DERIVED_NON_ROUTING_CATEGORIES
            and category not in CANDIDATE_GATE_DIAGNOSTIC_CATEGORIES
        ):
            categories.add(category)
    return categories


def _kill_rate_not_decreased(previous_report: ValidationReport, candidate_report: ValidationReport) -> bool:
    if not previous_report.base_consistency.get("passed") or not candidate_report.base_consistency.get("passed"):
        return True
    previous_stats = previous_report.wrong_solution_stats or {}
    candidate_stats = candidate_report.wrong_solution_stats or {}
    if previous_stats.get("valid") is not True or candidate_stats.get("valid") is not True:
        return True
    previous_kill_rate = previous_stats.get("kill_rate")
    candidate_kill_rate = candidate_stats.get("kill_rate")
    if not isinstance(previous_kill_rate, (int, float)) or not isinstance(candidate_kill_rate, (int, float)):
        return True
    return float(candidate_kill_rate) >= float(previous_kill_rate)


def _build_candidate_gate_issue(component_key: str, result: dict[str, Any]) -> FailureIssue:
    reasons = [str(item) for item in result.get("rejection_reasons", [])]
    regression_detected = bool(result.get("regression_detected"))
    category = "candidate_regression_detected" if regression_detected else "candidate_not_better_than_current"
    title = "候选包触发不退化门禁" if regression_detected else "候选包未优于当前题包"
    detail_parts = [
        f"组件 {component_key} 的候选通过轻量门禁，但包级验证未晋级。",
        f"拒绝原因：{', '.join(reasons) if reasons else '未知'}。",
    ]
    fixed = result.get("fixed_issue_fingerprints", [])
    introduced = result.get("introduced_blocker_high_categories", [])
    known_good_failed = result.get("known_good_failed_sources", [])
    if fixed:
        detail_parts.append(f"已修复 issue_fingerprint：{', '.join(str(item) for item in fixed[:5])}。")
    if introduced:
        detail_parts.append(f"新增 blocker/high 类别：{', '.join(str(item) for item in introduced)}。")
    if known_good_failed:
        detail_parts.append(f"被 known-good 用例拦下：{', '.join(str(item) for item in known_good_failed[:5])}。")
    return FailureIssue(
        category=category,
        severity="blocker",
        title=title,
        detail=" ".join(detail_parts),
        evidence={"component": component_key, "candidate_gate_result": result},
        fix_hint="保留上一轮组件；下一轮候选必须同时减少 active 问题且不破坏 known-good、语义门禁和杀伤率。",
    )


def _candidate_delta_summary_from_gate_results(gate_results: dict[str, Any]) -> dict[str, Any]:
    if not gate_results:
        return {}
    rejected = {
        name: result
        for name, result in gate_results.items()
        if isinstance(result, dict) and not result.get("passed")
    }
    return {
        "candidate_count": len(gate_results),
        "accepted_count": len(gate_results) - len(rejected),
        "rejected_count": len(rejected),
        "rejected_components": sorted(rejected),
        "rejection_reasons": sorted(
            {
                str(reason)
                for result in rejected.values()
                for reason in result.get("rejection_reasons", [])
            }
        ),
    }


def _evaluate_semantic_gate(problem: ProblemContext, checker: GeneratedCodeArtifact) -> list[FailureIssue]:
    if problem.judge_type != "checker":
        return []
    contract_text = json.dumps(
        {
            "generated_problem": problem.generated_problem,
            "schema_snapshot": problem.schema_snapshot,
        },
        ensure_ascii=False,
        sort_keys=True,
    ).lower()
    minimal_markers = ("字典序最小", "最小冲突", "lexicographically smallest", "lexicographic", "smallest")
    if not any(marker in contract_text for marker in minimal_markers):
        return []

    checker_code = checker.code.lower()
    checker_mentions_minimal = any(
        marker in checker_code
        for marker in ("字典序", "lexicographic", "smallest", "minimal", "min_l", "min_r", "best_l", "best_r")
    )
    enumerates_prior_candidates = (
        ("for" in checker_code and ("range(l" in checker_code or "range(0" in checker_code))
        or "expected_str" in checker_code
    )
    if checker_mentions_minimal and enumerates_prior_candidates:
        return []
    return [
        FailureIssue(
            category="semantic_kernel_required",
            severity="blocker",
            title="checker 未证明最小证书语义",
            detail=(
                "题面或 schema 要求输出字典序最小或最小冲突证书，但 checker 代码未体现最小性校验。"
                "该类证书往往需要共享可审计的语义内核，否则标准解、正确暴力解和 checker 会产生不同判定口径。"
            ),
            evidence={
                "judge_type": problem.judge_type,
                "generated_problem": problem.generated_problem,
                "checker_metadata": checker.metadata,
            },
            fix_hint="为 checker/正确暴力解/标准解提供共享的最小证书校验语义内核，或回到题面生成流程澄清/降低证书要求。",
        )
    ]


def _render_not_deliverable_note(
    *,
    final_status: str,
    stop_reason: str,
    final_round_index: int,
    regression_case_count: int,
) -> str:
    return "\n".join(
        [
            "# NOT DELIVERABLE",
            "",
            f"- final_status: {final_status}",
            f"- stop_reason: {stop_reason}",
            f"- final_round_index: {final_round_index}",
            f"- regression_case_count: {regression_case_count}",
            "",
            "当前运行未通过严格交付门禁，`last_attempt/` 仅用于排查，不应作为最终题包使用。",
        ]
    )


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


def _checker_reject_detail(problem: ProblemContext, detail: str) -> str:
    if problem.judge_type != "checker":
        return detail
    return f"{detail} checker 题允许多解，不能用字符串相等判断合法性。"


def _build_failure_evidence(
    *,
    test: TestCase,
    validator_result: Any | None = None,
    standard_result: Any | None = None,
    standard_output: Any | None = None,
    bruteforce_result: Any | None = None,
    bruteforce_output: Any | None = None,
    checker_result: Any | None = None,
) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "test": {
            "source": test.source,
            "purpose": test.purpose,
            "expect_bruteforce": test.expect_bruteforce,
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
    if bruteforce_result is not None:
        evidence["bruteforce_result"] = _result_evidence(bruteforce_result)
    if bruteforce_output is not None:
        evidence["bruteforce_output"] = str(bruteforce_output)
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
    target_roles = list(_TARGET_ROLES_BY_CATEGORY.get(issue.category, []))
    if issue.category in {"component_gate_failed", "candidate_regression_detected", "candidate_not_better_than_current"}:
        component = str((issue.evidence or {}).get("component", "")).strip()
        target_roles = {
            "standard_solution": ["StandardSolutionGenerator"],
            "bruteforce_solution": ["BruteForceSolutionGenerator"],
            "validator": ["ValidatorGenerator"],
            "checker": ["CheckerGenerator"],
            "random_test_generator": ["TestGenerator"],
            "adversarial_test_generator": ["TestGenerator"],
            "small_challenge_tests": ["TestGenerator"],
        }.get(component, target_roles)
    diagnostic = {
        "category": issue.category,
        "severity": issue.severity,
        "title": issue.title,
        "detail": issue.detail,
        "fix_hint": issue.fix_hint,
        "target_roles": target_roles,
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
        "test_source": _normalize_test_source(str(test.get("source") or evidence.get("test_source") or "")),
        "title": diagnostic.get("title", ""),
        "diff_shape": _fingerprint_diff_shape(diagnostic.get("diff", {})),
        "result_statuses": result_statuses,
    }
    raw = json.dumps(basis, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _normalize_test_source(source: str) -> str:
    value = str(source or "")
    for _ in range(10):
        matched = False
        for prefix in ("regression:", "active:", "known_good:"):
            if value.startswith(prefix):
                value = value.removeprefix(prefix)
                matched = True
        if not matched:
            break
    return value


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
    survivors = curation.get("high_value_survivors")
    if not isinstance(survivors, list):
        survivors = curation.get("independent_solutions", [])
    for item in survivors:
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


def _build_wrong_solution_gate_detail(
    *,
    wrong_stats: dict[str, Any],
    high_value_survivors: list[dict[str, Any]],
    unexpected_correct_candidates: list[dict[str, Any]],
) -> str:
    kill_rate = wrong_stats.get("kill_rate")
    threshold = wrong_stats.get("kill_rate_threshold")
    high_value_survivor_count = len(high_value_survivors)
    unexpected_correct_count = len(unexpected_correct_candidates)
    only_unexpected_correct_left = high_value_survivor_count == 0 and unexpected_correct_count > 0
    detail_parts = [
        f"当前杀伤率 {kill_rate}，阈值 {threshold}。",
        f"高价值幸存错误解 {high_value_survivor_count} 个。",
        f"unexpected_correct 候选 {unexpected_correct_count} 个。",
        f"是否仅剩 unexpected_correct 候选：{'是' if only_unexpected_correct_left else '否'}。",
    ]
    if kill_rate is not None and threshold is not None and kill_rate < threshold:
        detail_parts.append("当前杀伤率尚未达标。")
    if high_value_survivor_count > 0:
        detail_parts.append("当前仍有应被测试击穿但未被杀掉的高价值幸存错误解。")
    return " ".join(detail_parts)


def _summarize_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    if not evidence:
        return {}
    test = evidence.get("test", {}) if isinstance(evidence.get("test"), dict) else {}
    is_large = bool(test.get("is_large"))
    summarized: dict[str, Any] = {}
    for key, value in evidence.items():
        if key == "input":
            summarized[key] = _summarize_text(
                value,
                is_large=is_large,
                prefer_full=_bool_with_legacy(test, "expect_bruteforce", "expect_oracle", False) and not is_large,
            )
        elif key in {"standard_output", "bruteforce_output", "oracle_output"}:
            summarized[key] = _summarize_text(
                value,
                is_large=is_large,
                prefer_full=_bool_with_legacy(test, "expect_bruteforce", "expect_oracle", False) and not is_large,
            )
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
    bruteforce = evidence.get("bruteforce_output", evidence.get("oracle_output"))
    if standard is None or bruteforce is None:
        return {}
    standard_text = str(standard)
    bruteforce_text = str(bruteforce)
    if _normalize_output(standard_text) == _normalize_output(bruteforce_text):
        return {}
    standard_tokens = standard_text.split()
    bruteforce_tokens = bruteforce_text.split()
    token_index = 0
    while token_index < min(len(standard_tokens), len(bruteforce_tokens)) and standard_tokens[token_index] == bruteforce_tokens[token_index]:
        token_index += 1
    standard_lines = standard_text.splitlines()
    bruteforce_lines = bruteforce_text.splitlines()
    line_index = 0
    while line_index < min(len(standard_lines), len(bruteforce_lines)) and standard_lines[line_index].rstrip() == bruteforce_lines[line_index].rstrip():
        line_index += 1
    return {
        "first_different_token": {
            "index": token_index,
            "standard": standard_tokens[token_index] if token_index < len(standard_tokens) else None,
            "bruteforce": bruteforce_tokens[token_index] if token_index < len(bruteforce_tokens) else None,
        },
        "first_different_line": {
            "index": line_index,
            "standard": standard_lines[line_index] if line_index < len(standard_lines) else None,
            "bruteforce": bruteforce_lines[line_index] if line_index < len(bruteforce_lines) else None,
        },
        "standard_window": _window(standard_lines, line_index, _DIFF_WINDOW),
        "bruteforce_window": _window(bruteforce_lines, line_index, _DIFF_WINDOW),
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


def _bool_with_legacy(item: dict[str, Any], key: str, legacy_key: str, default: bool) -> bool:
    if key in item:
        return bool(item.get(key))
    if legacy_key in item:
        return bool(item.get(legacy_key))
    return bool(default)


def _skipped_wrong_solution_stats(*, candidate_count: int, kill_rate_threshold: float) -> dict[str, Any]:
    return {
        "candidate_count": candidate_count,
        "valuable_count": 0,
        "independent_count": 0,
        "high_value_survivor_count": 0,
        "unexpected_correct_count": 0,
        "rejected_count": 0,
        "kill_rate": None,
        "kill_rate_threshold": kill_rate_threshold,
        "passed_threshold": False,
        "valid": False,
        "skip_reason": "baseline_validation_failed",
    }
