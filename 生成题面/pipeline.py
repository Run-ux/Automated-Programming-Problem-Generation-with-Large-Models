from __future__ import annotations

from dataclasses import asdict
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from markdown_renderer import render_problem_markdown
from models import VariantPlan
from problem_generator import ProblemGenerator
from rulebook import normalize_mode_name
from schema_loader import SchemaLoader
from variant_planner import VariantPlanner

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from finiteness_verification.problem_repository import ProblemRepository


class GenerationPipeline:
    def __init__(
        self,
        raw_source_dir: Path,
        source_dir: Path,
        output_dir: Path,
        artifact_dir: Path,
        report_dir: Path,
        generator: ProblemGenerator,
        planner: VariantPlanner,
        problem_repository: ProblemRepository | None = None,
        progress_writer: Callable[[str], None] | None = None,
    ):
        self.raw_loader = SchemaLoader(raw_source_dir)
        self.loader = SchemaLoader(source_dir)
        self.output_dir = output_dir
        self.artifact_dir = artifact_dir
        self.report_dir = report_dir
        self.generator = generator
        self.planner = planner
        self.problem_repository = problem_repository or ProblemRepository()
        self.progress_writer = progress_writer or _default_progress_writer
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def run(
        self,
        *,
        mode: str,
        problem_ids: list[str],
        variants: int = 1,
        theme_id: str | None = None,
        seed_a: str | None = None,
        seed_b: str | None = None,
        allowed_rule_ids: set[str] | None = None,
        batch_source_dir: Path | None = None,
    ) -> list[dict[str, Any]]:
        canonical_mode = _canonical_mode(mode)
        if canonical_mode == "single_seed_extension":
            return self._run_single(
                problem_ids=problem_ids,
                variants=variants,
                theme_id=theme_id,
                allowed_rule_ids=allowed_rule_ids,
                batch_source_dir=batch_source_dir,
            )
        return self._run_same_family(
            seed_a=seed_a,
            seed_b=seed_b,
            variants=variants,
            theme_id=theme_id,
            allowed_rule_ids=allowed_rule_ids,
        )

    def _run_single(
        self,
        *,
        problem_ids: list[str],
        variants: int,
        theme_id: str | None,
        allowed_rule_ids: set[str] | None,
        batch_source_dir: Path | None,
    ) -> list[dict[str, Any]]:
        target_problem_ids = list(problem_ids) or self.loader.list_problem_ids()
        records: list[dict[str, Any]] = []
        if batch_source_dir is None:
            self._emit_progress(f"[single] 开始生成，共 {len(target_problem_ids)} 题。")
            for problem_id in target_problem_ids:
                records.extend(
                    self._run_single_problem(
                        problem_id=problem_id,
                        variants=variants,
                        theme_id=theme_id,
                        allowed_rule_ids=allowed_rule_ids,
                    )
                )
            self._emit_progress(f"[single] 全部完成，共生成 {len(records)} 个产物。")
            return records

        batch_started_at = datetime.now()
        batch_stem = self._build_batch_stem(batch_started_at)
        batch_items: list[dict[str, Any]] = []
        self._emit_progress(
            f"[batch] 开始批量生成，共 {len(target_problem_ids)} 题；source_dir={batch_source_dir}"
        )

        for order, problem_id in enumerate(target_problem_ids, start=1):
            try:
                self._emit_progress(
                    f"[batch] 第 {order}/{len(target_problem_ids)} 题：{problem_id}"
                )
                problem_records = self._run_single_problem(
                    problem_id=problem_id,
                    variants=variants,
                    theme_id=theme_id,
                    allowed_rule_ids=allowed_rule_ids,
                )
            except Exception as exc:
                batch_items.append(
                    {
                        "order": order,
                        "problem_id": problem_id,
                        "status": "failed",
                        "error_reason": str(exc),
                        "variant_records": [],
                    }
                )
                self._emit_progress(f"[batch] {problem_id} 失败：{exc}")
                continue

            records.extend(problem_records)
            batch_items.append(
                {
                    "order": order,
                    "problem_id": problem_id,
                    "status": "completed",
                    "error_reason": "",
                    "variant_records": problem_records,
                }
            )
            self._emit_progress(
                f"[batch] {problem_id} 完成，生成 {len(problem_records)} 个产物。"
            )

        batch_paths = self._write_batch_summary(
            stem=batch_stem,
            started_at=batch_started_at,
            finished_at=datetime.now(),
            source_dir=batch_source_dir,
            target_problem_ids=target_problem_ids,
            batch_items=batch_items,
        )
        for record in records:
            record["batch_artifact_path"] = str(batch_paths["artifact_path"])
            record["batch_report_path"] = str(batch_paths["report_path"])
        self._emit_progress(
            f"[batch] 全部完成；batch_artifact={batch_paths['artifact_path']}；batch_report={batch_paths['report_path']}"
        )
        return records

    def _run_single_problem(
        self,
        *,
        problem_id: str,
        variants: int,
        theme_id: str | None,
        allowed_rule_ids: set[str] | None,
    ) -> list[dict[str, Any]]:
        self._emit_progress(f"[problem] {problem_id}：读取 schema 与原题信息。")
        original_schema = self.raw_loader.load(problem_id)
        prepared_schema = self.loader.load(problem_id)
        original_problem = self._safe_get_problem(prepared_schema, problem_id)
        report_sections = self._build_single_report_header(
            problem_id=problem_id,
            original_problem=original_problem,
            original_schema=original_schema,
            prepared_schema=prepared_schema,
        )

        problem_records: list[dict[str, Any]] = []
        for variant_index in range(1, variants + 1):
            self._emit_progress(f"[problem] {problem_id}：variant {variant_index} 进入规划。")
            plan = self.planner.build_plan(
                mode="single_seed_extension",
                variant_index=variant_index,
                theme_id=theme_id,
                original_schema=original_schema,
                prepared_schema=prepared_schema,
                original_problem=original_problem,
                allowed_rule_ids=allowed_rule_ids,
            )
            stem = self._build_stem(plan.source_problem_ids, plan.variant_index, plan.theme.theme_id)
            self._emit_progress(
                f"[problem] {problem_id}：variant {variant_index} 规划完成，规则={plan.applied_rule or '无'}。"
            )
            self._emit_progress(f"[problem] {problem_id}：variant {variant_index} 进入题面生成。")
            generated = self.generator.generate(
                {"seed_schema": prepared_schema},
                plan,
                original_problems=[item for item in [original_problem] if item],
            )
            self._emit_progress(
                f"[problem] {problem_id}：variant {variant_index} 生成完成，status={generated.status}。"
            )
            markdown = render_problem_markdown(generated, plan)
            self._emit_progress(f"[problem] {problem_id}：variant {variant_index} 写入产物。")
            record = self._save_outputs(
                stem=stem,
                plan=plan,
                payload=generated.__dict__,
                markdown=markdown,
            )
            problem_records.append(record)
            report_sections.extend(
                self._build_variant_report_sections(
                    plan=plan,
                    record=record,
                    generated=generated.__dict__,
                )
            )

        self._emit_progress(f"[problem] {problem_id}：写入过程报告。")
        report_path = self._write_problem_report(problem_id, report_sections)
        for record in problem_records:
            record["report_path"] = str(report_path)
        self._emit_progress(f"[problem] {problem_id}：完成。report={report_path}")
        return problem_records

    def _run_same_family(
        self,
        *,
        seed_a: str | None,
        seed_b: str | None,
        variants: int,
        theme_id: str | None,
        allowed_rule_ids: set[str] | None,
    ) -> list[dict[str, Any]]:
        if not seed_a or not seed_b:
            raise ValueError("same_family_fusion 模式必须显式提供 seed_a 和 seed_b。")

        original_schema_a = self.raw_loader.load(seed_a)
        original_schema_b = self.raw_loader.load(seed_b)
        prepared_schema_a = self.loader.load(seed_a)
        prepared_schema_b = self.loader.load(seed_b)
        original_problem_a = self._safe_get_problem(prepared_schema_a, seed_a)
        original_problem_b = self._safe_get_problem(prepared_schema_b, seed_b)

        report_key = f"{seed_a}__{seed_b}"
        report_sections = self._build_same_family_report_header(
            seed_a=seed_a,
            seed_b=seed_b,
            original_problem_a=original_problem_a,
            original_problem_b=original_problem_b,
            original_schema_a=original_schema_a,
            original_schema_b=original_schema_b,
            prepared_schema_a=prepared_schema_a,
            prepared_schema_b=prepared_schema_b,
        )

        records: list[dict[str, Any]] = []
        for variant_index in range(1, variants + 1):
            plan = self.planner.build_plan(
                mode="same_family_fusion",
                variant_index=variant_index,
                theme_id=theme_id,
                seed_a_schema=prepared_schema_a,
                seed_b_schema=prepared_schema_b,
                seed_a_original_schema=original_schema_a,
                seed_b_original_schema=original_schema_b,
                seed_a_problem=original_problem_a or {},
                seed_b_problem=original_problem_b or {},
                allowed_rule_ids=allowed_rule_ids,
            )
            stem = self._build_stem(plan.source_problem_ids, plan.variant_index, plan.theme.theme_id)
            generated = self.generator.generate(
                {
                    "seed_a_schema": prepared_schema_a,
                    "seed_b_schema": prepared_schema_b,
                },
                plan,
                original_problems=[item for item in [original_problem_a, original_problem_b] if item],
            )
            markdown = render_problem_markdown(generated, plan)
            record = self._save_outputs(
                stem=stem,
                plan=plan,
                payload=generated.__dict__,
                markdown=markdown,
            )
            records.append(record)
            report_sections.extend(
                self._build_variant_report_sections(
                    plan=plan,
                    record=record,
                    generated=generated.__dict__,
                )
            )

        report_path = self._write_problem_report(report_key, report_sections)
        for record in records:
            record["report_path"] = str(report_path)
        return records

    def _save_outputs(
        self,
        *,
        stem: str,
        plan: VariantPlan,
        payload: dict[str, Any],
        markdown: str,
    ) -> dict[str, Any]:
        json_path = self.artifact_dir / f"{stem}.json"
        md_path = self.output_dir / f"{stem}.md"

        artifact = {
            "problem_id": plan.problem_id,
            "source_problem_ids": list(plan.source_problem_ids),
            "variant_index": plan.variant_index,
            "seed": plan.seed,
            "mode": plan.mode,
            "rule_version": plan.rule_version,
            "theme": {
                "id": plan.theme.theme_id,
                "name": plan.theme.name,
            },
            "difference_plan": asdict(plan.difference_plan),
            "predicted_schema_distance": plan.predicted_schema_distance,
            "distance_breakdown": _normalize_distance_breakdown(plan.distance_breakdown),
            "changed_axes_realized": list(plan.changed_axes_realized),
            "objective": plan.objective,
            "rule_selection_reason": plan.rule_selection_reason,
            "instantiated_schema_snapshot": asdict(plan.instantiated_schema_snapshot),
            "applied_rule": plan.applied_rule,
            "rejected_candidates": plan.rejected_candidates,
            "algorithmic_delta_claim": plan.algorithmic_delta_claim,
            "shared_core_summary": plan.shared_core_summary,
            "shared_core_anchors": plan.shared_core_anchors,
            "seed_contributions": plan.seed_contributions,
            "fusion_ablation": plan.fusion_ablation,
            "applied_helpers": plan.applied_helpers,
            "planning_status": plan.planning_status,
            "planning_error_reason": plan.planning_error_reason,
            "planning_feedback": plan.planning_feedback,
            "selection_trace": plan.selection_trace,
            "validation_trace": plan.validation_trace,
            "candidate_attempts": plan.candidate_attempts,
            "generated_problem": payload,
        }

        with json_path.open("w", encoding="utf-8") as handle:
            json.dump(artifact, handle, ensure_ascii=False, indent=2)

        with md_path.open("w", encoding="utf-8") as handle:
            handle.write(markdown)

        return {
            "problem_id": plan.problem_id,
            "source_problem_ids": list(plan.source_problem_ids),
            "mode": plan.mode,
            "variant_index": plan.variant_index,
            "markdown_path": str(md_path),
            "artifact_path": str(json_path),
            "generated_status": payload.get("status", "ok"),
        }

    def _build_single_report_header(
        self,
        *,
        problem_id: str,
        original_problem: dict[str, Any] | None,
        original_schema: dict[str, Any],
        prepared_schema: dict[str, Any],
    ) -> list[str]:
        return [
            f"# {problem_id} 生成过程说明",
            "",
            "## 运行模式",
            "- mode: single_seed_extension",
            f"- seed_problem_ids: {problem_id}",
            "",
            "## 原题信息",
            *self._render_problem_reference(original_problem),
            "",
            "## 原始四元组摘要",
            *self._render_schema_summary(original_schema),
            "",
            "## 归一化四元组摘要",
            *self._render_schema_summary(prepared_schema),
            "",
        ]

    def _build_same_family_report_header(
        self,
        *,
        seed_a: str,
        seed_b: str,
        original_problem_a: dict[str, Any] | None,
        original_problem_b: dict[str, Any] | None,
        original_schema_a: dict[str, Any],
        original_schema_b: dict[str, Any],
        prepared_schema_a: dict[str, Any],
        prepared_schema_b: dict[str, Any],
    ) -> list[str]:
        return [
            f"# {seed_a}__{seed_b} 生成过程说明",
            "",
            "## 运行模式",
            "- mode: same_family_fusion",
            f"- seed_problem_ids: {seed_a}, {seed_b}",
            "",
            "## 种子题 A",
            *self._render_problem_reference(original_problem_a),
            "",
            "### 原始四元组",
            *self._render_schema_summary(original_schema_a),
            "",
            "### 归一化四元组",
            *self._render_schema_summary(prepared_schema_a),
            "",
            "## 种子题 B",
            *self._render_problem_reference(original_problem_b),
            "",
            "### 原始四元组",
            *self._render_schema_summary(original_schema_b),
            "",
            "### 归一化四元组",
            *self._render_schema_summary(prepared_schema_b),
            "",
        ]

    def _build_variant_report_sections(
        self,
        *,
        plan: VariantPlan,
        record: dict[str, Any],
        generated: dict[str, Any],
    ) -> list[str]:
        lines = [
            f"## Variant {plan.variant_index}",
            "",
            "### 规则规划",
            f"- mode: {plan.mode}",
            f"- planning_status: {plan.planning_status}",
            f"- rule_version: {plan.rule_version or '无'}",
            f"- source_problem_ids: {', '.join(plan.source_problem_ids)}",
            f"- applied_rule: {plan.applied_rule or '无'}",
            f"- rule_selection_reason: {plan.rule_selection_reason or '无'}",
            f"- theme: {plan.theme.theme_id} / {plan.theme.name}",
            f"- shared_core_summary: {plan.shared_core_summary or '无'}",
            f"- predicted_schema_distance: {plan.predicted_schema_distance}",
            "- changed_axes_realized: " + (", ".join(plan.changed_axes_realized) or "无"),
            "- distance_breakdown: "
            + json.dumps(_normalize_distance_breakdown(plan.distance_breakdown), ensure_ascii=False),
            f"- difference_plan_summary: {plan.difference_plan.summary or '无'}",
            f"- difference_plan_rationale: {plan.difference_plan.rationale or '无'}",
        ]
        lines.extend(self._render_applied_helpers(plan.applied_helpers))
        lines.extend(self._render_rejected_candidates(plan.rejected_candidates))
        lines.extend(self._render_candidate_attempts(plan.candidate_attempts))
        lines.extend(
            [
                "",
                "### 解法变化说明",
                *self._render_algorithmic_delta(plan.algorithmic_delta_claim),
            ]
        )
        lines.extend(
            [
                "",
                "### 审计轨迹",
                *self._render_trace_summary(plan.selection_trace, plan.validation_trace),
            ]
        )
        if plan.mode == "same_family_fusion":
            lines.extend(
                [
                    "",
                "### 同族融合论证",
                    *self._render_same_family_fusion(plan),
                ]
            )
        lines.extend(
            [
                "",
                "### 实例化四元组",
                *self._render_instantiated_schema(plan),
                "",
                "### 生成结果",
                f"- generated_status: {generated.get('status', 'ok')}",
                f"- title: {generated.get('title', '') or '无'}",
                f"- error_reason: {generated.get('error_reason', '') or '无'}",
                f"- feedback: {generated.get('feedback', '') or '无'}",
                f"- markdown_path: {record['markdown_path']}",
                f"- artifact_path: {record['artifact_path']}",
                "",
            ]
        )
        return lines

    def _write_problem_report(self, report_name: str, lines: list[str]) -> Path:
        report_path = self.report_dir / f"{report_name}.md"
        report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        return report_path

    def _write_batch_summary(
        self,
        *,
        stem: str,
        started_at: datetime,
        finished_at: datetime,
        source_dir: Path,
        target_problem_ids: list[str],
        batch_items: list[dict[str, Any]],
    ) -> dict[str, Path]:
        artifact_path = self.artifact_dir / f"{stem}.json"
        report_path = self.report_dir / f"{stem}.md"
        failed_item = next((item for item in batch_items if item.get("status") == "failed"), None)
        summary_payload = {
            "batch_id": stem,
            "mode": "single_seed_extension",
            "source_dir": str(source_dir),
            "task_order": list(target_problem_ids),
            "task_count": len(target_problem_ids),
            "completed_count": sum(1 for item in batch_items if item.get("status") == "completed"),
            "failed_count": sum(1 for item in batch_items if item.get("status") == "failed"),
            "status": "failed" if failed_item else "completed",
            "failed_problem_id": failed_item.get("problem_id", "") if failed_item else "",
            "failed_reason": failed_item.get("error_reason", "") if failed_item else "",
            "started_at": started_at.isoformat(timespec="seconds"),
            "finished_at": finished_at.isoformat(timespec="seconds"),
            "items": batch_items,
        }
        artifact_path.write_text(
            json.dumps(summary_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        report_path.write_text(
            "\n".join(self._build_batch_report_lines(summary_payload)).rstrip() + "\n",
            encoding="utf-8",
        )
        return {
            "artifact_path": artifact_path,
            "report_path": report_path,
        }

    def _safe_get_problem(
        self,
        schema: dict[str, Any],
        fallback_problem_id: str,
    ) -> dict[str, Any] | None:
        try:
            return self.problem_repository.get_problem(
                source=schema.get("source", ""),
                problem_id=schema.get("problem_id", fallback_problem_id),
            )
        except Exception:
            return None

    def _build_stem(self, source_problem_ids: list[str], variant_index: int, theme_id: str) -> str:
        base = "__".join(_slugify(problem_id) for problem_id in source_problem_ids if problem_id)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{base}_v{variant_index}_{theme_id}_{timestamp}"

    def _build_batch_stem(self, started_at: datetime) -> str:
        return f"batch_{started_at.strftime('%Y%m%d_%H%M%S')}"

    def _build_batch_report_lines(self, summary_payload: dict[str, Any]) -> list[str]:
        lines = [
            "# 批量生成过程说明",
            "",
            "## 运行概览",
            f"- batch_id: {summary_payload.get('batch_id', '')}",
            f"- mode: {summary_payload.get('mode', '')}",
            f"- source_dir: {summary_payload.get('source_dir', '')}",
            f"- task_count: {summary_payload.get('task_count', 0)}",
            f"- completed_count: {summary_payload.get('completed_count', 0)}",
            f"- failed_count: {summary_payload.get('failed_count', 0)}",
            f"- status: {summary_payload.get('status', '')}",
            f"- started_at: {summary_payload.get('started_at', '')}",
            f"- finished_at: {summary_payload.get('finished_at', '')}",
            f"- failed_problem_id: {summary_payload.get('failed_problem_id', '') or '无'}",
            f"- failed_reason: {summary_payload.get('failed_reason', '') or '无'}",
            "",
            "## 任务列表",
        ]
        for item in summary_payload.get("items", []):
            lines.extend(
                [
                    "",
                    f"### {item.get('order', '')}. {item.get('problem_id', '')}",
                    f"- status: {item.get('status', '')}",
                    f"- error_reason: {item.get('error_reason', '') or '无'}",
                ]
            )
            variant_records = item.get("variant_records", [])
            if not variant_records:
                lines.append("- variant_records: 无")
                continue
            lines.append("- variant_records:")
            for record in variant_records:
                lines.append(
                    "  - "
                    + f"variant_index={record.get('variant_index', '')}; "
                    + f"generated_status={record.get('generated_status', '')}; "
                    + f"markdown_path={record.get('markdown_path', '')}; "
                    + f"artifact_path={record.get('artifact_path', '')}; "
                    + f"report_path={record.get('report_path', '') or '无'}"
                )
        return lines

    def _emit_progress(self, message: str) -> None:
        self.progress_writer(message)

    def _render_problem_reference(self, problem: dict[str, Any] | None) -> list[str]:
        if not problem:
            return [
                "- problem_id: 无",
                "- title: 无",
                "- source: 无",
                "- url: 无",
                "- difficulty: 无",
                "- tags: 无",
            ]
        return [
            f"- problem_id: {problem.get('problem_id', '')}",
            f"- title: {problem.get('title', '') or '无'}",
            f"- source: {problem.get('source', '') or '无'}",
            f"- url: {problem.get('url', '') or '无'}",
            f"- difficulty: {problem.get('difficulty', '') or '无'}",
            f"- tags: {', '.join(problem.get('tags', [])) or '无'}",
        ]

    def _render_schema_summary(self, schema: dict[str, Any]) -> list[str]:
        return [
            f"- problem_id: {schema.get('problem_id', '')}",
            f"- source: {schema.get('source', '')}",
            f"- input_structure: {self._describe_input_structure(schema.get('input_structure', {}))}",
            f"- objective: {self._describe_objective(schema.get('objective', {}))}",
            "- constraints:",
            *self._render_named_items(
                schema.get("core_constraints", {}).get("constraints", []),
                empty_text="  - 无",
            ),
            "- invariants:",
            *self._render_named_items(
                schema.get("invariant", {}).get("invariants", []),
                empty_text="  - 无",
            ),
        ]

    def _render_applied_helpers(self, helpers: list[dict[str, Any]]) -> list[str]:
        lines = ["- applied_helpers:"]
        if not helpers:
            lines.append("  - 无")
            return lines
        for helper in helpers:
            lines.append(
                "  - "
                + f"id={helper.get('id', '') or '无'}; "
                + f"affected_axes={', '.join(helper.get('affected_axes', [])) or '无'}; "
                + f"selection_reason={helper.get('selection_reason', '') or '无'}; "
                + f"innovation_reason={helper.get('innovation_reason', '') or '无'}; "
                + f"difficulty_reason={helper.get('difficulty_reason', '') or '无'}; "
                + f"schema_changes={', '.join(helper.get('schema_changes', [])) or '无'}"
            )
        return lines

    def _render_rejected_candidates(self, rejected_candidates: list[dict[str, Any]]) -> list[str]:
        lines = ["- rejected_candidates:"]
        if not rejected_candidates:
            lines.append("  - 无")
            return lines
        for item in rejected_candidates:
            lines.append(
                "  - "
                + f"rule_id={item.get('rule_id', '')}; "
                + f"status={item.get('status', '') or 'difference_insufficient'}; "
                + f"reason={item.get('reason', '') or '无'}"
            )
        return lines

    def _render_candidate_attempts(self, candidate_attempts: list[dict[str, Any]]) -> list[str]:
        lines = ["- candidate_attempts:"]
        if not candidate_attempts:
            lines.append("  - 无")
            return lines
        for item in candidate_attempts:
            lines.append(
                "  - "
                + f"attempt_index={item.get('attempt_index', '')}; "
                + f"rule_id={item.get('rule_id', '')}; "
                + f"score={item.get('score', '')}; "
                + f"accepted={item.get('accepted', False)}; "
                + f"reason_code={item.get('reason_code', '') or '无'}; "
                + f"reason={item.get('reason', '') or '无'}"
            )
        return lines

    def _render_algorithmic_delta(self, claim: dict[str, Any]) -> list[str]:
        if not claim:
            return ["- 无"]
        return [
            f"- seed_solver_core: {claim.get('seed_solver_core', '') or '无'}",
            f"- reusable_subroutines: {claim.get('reusable_subroutines', '') or '无'}",
            f"- new_solver_core: {claim.get('new_solver_core', '') or '无'}",
            f"- 新增正确性证明: {claim.get('new_proof_obligation', '') or '无'}",
            f"- why_direct_reuse_fails: {claim.get('why_direct_reuse_fails', '') or '无'}",
        ]

    def _render_same_family_fusion(self, plan: VariantPlan) -> list[str]:
        return [
            f"- shared_state: {plan.shared_core_anchors.get('shared_state', '') or '无'}",
            f"- shared_transition: {plan.shared_core_anchors.get('shared_transition', '') or '无'}",
            f"- shared_decision_basis: {plan.shared_core_anchors.get('shared_decision_basis', '') or '无'}",
            f"- seed_a_contribution: {plan.seed_contributions.get('seed_a', '') or '无'}",
            f"- seed_b_contribution: {plan.seed_contributions.get('seed_b', '') or '无'}",
            f"- without_seed_a: {plan.fusion_ablation.get('without_seed_a', '') or '无'}",
            f"- without_seed_b: {plan.fusion_ablation.get('without_seed_b', '') or '无'}",
        ]

    def _render_trace_summary(
        self,
        selection_trace: list[dict[str, Any]],
        validation_trace: list[dict[str, Any]],
    ) -> list[str]:
        lines = [
            f"- selection_trace_count: {len(selection_trace)}",
            f"- validation_trace_count: {len(validation_trace)}",
        ]
        if selection_trace:
            for item in selection_trace[:3]:
                lines.append(
                    "  - "
                    + f"rule_id={item.get('rule_id', '')}; "
                    + f"accepted={item.get('accepted', False)}; "
                    + f"score={item.get('score', '')}; "
                    + f"reason_code={item.get('reason_code', '') or '无'}"
                )
        if validation_trace:
            for item in validation_trace[:5]:
                lines.append(
                    "  - "
                    + f"stage={item.get('stage', '')}; "
                    + f"rule_id={item.get('rule_id', '')}; "
                    + f"outcome={item.get('outcome', '')}; "
                    + f"reason_code={item.get('reason_code', '') or '无'}"
                )
        return lines

    def _render_instantiated_schema(self, plan: VariantPlan) -> list[str]:
        snapshot = asdict(plan.instantiated_schema_snapshot)
        return [
            f"- problem_id: {snapshot.get('problem_id', '')}",
            f"- source: {snapshot.get('source', '')}",
            f"- input_structure: {self._describe_input_structure(snapshot.get('input_structure', {}))}",
            f"- objective: {self._describe_objective(snapshot.get('objective', {}))}",
            f"- difficulty: {snapshot.get('difficulty', '') or '无'}",
            "- constraints:",
            *self._render_named_items(
                snapshot.get("core_constraints", {}).get("constraints", []),
                empty_text="  - 无",
            ),
            "- invariants:",
            *self._render_named_items(
                snapshot.get("invariant", {}).get("invariants", []),
                empty_text="  - 无",
            ),
        ]

    def _describe_input_structure(self, input_structure: dict[str, Any]) -> str:
        length = input_structure.get("length", {})
        value_range = input_structure.get("value_range", {})
        properties = input_structure.get("properties", {})
        parts = [f"type={input_structure.get('type', 'unknown')}"]
        if input_structure.get("confidence"):
            parts.append(f"confidence={input_structure.get('confidence')}")
        if length:
            parts.append(f"length=[{length.get('min')}..{length.get('max')}]")
        if value_range:
            parts.append(f"value_range=[{value_range.get('min')}..{value_range.get('max')}]")
        if properties:
            parts.append(
                "properties=" + ", ".join(f"{key}={value}" for key, value in properties.items())
            )
        return "; ".join(parts)

    def _describe_objective(self, objective: dict[str, Any]) -> str:
        parts = [f"type={objective.get('type', '')}"]
        if objective.get("description"):
            parts.append(f"description={objective.get('description')}")
        if objective.get("confidence"):
            parts.append(f"confidence={objective.get('confidence')}")
        return "; ".join(parts)

    def _render_named_items(self, items: list[dict[str, Any]], empty_text: str) -> list[str]:
        if not items:
            return [empty_text]
        lines: list[str] = []
        for item in items:
            parts = []
            if item.get("name"):
                parts.append(f"name={item.get('name')}")
            if item.get("description"):
                parts.append(f"description={item.get('description')}")
            if item.get("confidence"):
                parts.append(f"confidence={item.get('confidence')}")
            lines.append("  - " + "; ".join(parts))
        return lines


def _canonical_mode(mode: str) -> str:
    return normalize_mode_name(mode)


def _normalize_distance_breakdown(distance_breakdown: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(distance_breakdown, dict):
        return {
            "distance_version": "v2",
            "backend": "lexical_fallback",
            "total": 0.0,
            "axis_scores": {"I": 0.0, "C": 0.0, "O": 0.0, "V": 0.0},
            "components": {
                "input_tree_distance": 0.0,
                "constraint_match_distance": 0.0,
                "objective_type_distance": 0.0,
                "objective_text_distance": 0.0,
                "invariant_match_distance": 0.0,
            },
        }

    return {
        "distance_version": str(distance_breakdown.get("distance_version", "v2")),
        "backend": str(distance_breakdown.get("backend", "lexical_fallback")),
        "total": round(float(distance_breakdown.get("total", 0.0)), 4),
        "axis_scores": {
            axis: round(float(distance_breakdown.get("axis_scores", {}).get(axis, 0.0)), 4)
            for axis in ("I", "C", "O", "V")
        },
        "components": {
            key: round(float(value), 4)
            for key, value in dict(distance_breakdown.get("components", {})).items()
        },
    }


def _slugify(text: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in str(text))
    return cleaned.strip("_") or "variant"


def _default_progress_writer(message: str) -> None:
    text = f"{message}\n"
    stream = sys.stdout
    encoding = getattr(stream, "encoding", None) or "utf-8"
    buffer = getattr(stream, "buffer", None)
    if buffer is not None:
        buffer.write(text.encode(encoding, errors="replace"))
        buffer.flush()
        return
    stream.write(text.encode(encoding, errors="replace").decode(encoding, errors="replace"))
    stream.flush()
