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
QUALITY_EVAL_DIR = PROJECT_ROOT / "题目质量评价"
if str(QUALITY_EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(QUALITY_EVAL_DIR))

from finiteness_verification.problem_repository import ProblemRepository
from problem_quality import ProblemEvaluator
from problem_quality.report_renderer import render_report_markdown as render_quality_report_markdown


class GenerationPipeline:
    def __init__(
        self,
        source_dir: Path,
        output_dir: Path,
        artifact_dir: Path,
        report_dir: Path,
        generator: ProblemGenerator,
        planner: VariantPlanner,
        problem_repository: ProblemRepository | None = None,
        quality_evaluator: Any | None = None,
        quality_report_renderer: Callable[[dict[str, Any]], str] | None = None,
        progress_writer: Callable[[str], None] | None = None,
    ):
        self.loader = SchemaLoader(source_dir)
        self.output_dir = output_dir
        self.artifact_dir = artifact_dir
        self.report_dir = report_dir
        self.generator = generator
        self.planner = planner
        self.problem_repository = problem_repository or ProblemRepository()
        self.quality_evaluator = quality_evaluator
        self.quality_report_renderer = quality_report_renderer or render_quality_report_markdown
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
        quality_iterations: int = 0,
    ) -> list[dict[str, Any]]:
        canonical_mode = _canonical_mode(mode)
        if quality_iterations and canonical_mode != "single_seed_extension":
            raise ValueError("质量闭环迭代当前只支持 single_seed_extension。")
        if canonical_mode == "single_seed_extension":
            return self._run_single(
                problem_ids=problem_ids,
                variants=variants,
                theme_id=theme_id,
                allowed_rule_ids=allowed_rule_ids,
                batch_source_dir=batch_source_dir,
                quality_iterations=quality_iterations,
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
        quality_iterations: int,
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
                        quality_iterations=quality_iterations,
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
                    quality_iterations=quality_iterations,
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
        self._emit_progress(f"[batch] 全部完成；batch_artifact={batch_paths['artifact_path']}")
        return records

    def _run_single_problem(
        self,
        *,
        problem_id: str,
        variants: int,
        theme_id: str | None,
        allowed_rule_ids: set[str] | None,
        quality_iterations: int,
    ) -> list[dict[str, Any]]:
        self._emit_progress(f"[problem] {problem_id}：读取 schema 与原题信息。")
        seed_schema = self.loader.load(problem_id)
        original_problem = self._safe_get_problem(seed_schema, problem_id)
        report_sections = self._build_single_report_header(problem_id=problem_id)

        problem_records: list[dict[str, Any]] = []
        for variant_index in range(1, variants + 1):
            if quality_iterations <= 0:
                plan, generated, record = self._run_single_variant_once(
                    problem_id=problem_id,
                    variant_index=variant_index,
                    theme_id=theme_id,
                    seed_schema=seed_schema,
                    original_problem=original_problem,
                    allowed_rule_ids=allowed_rule_ids,
                )
            else:
                plan, generated, record = self._run_single_variant_with_quality_iterations(
                    problem_id=problem_id,
                    variant_index=variant_index,
                    theme_id=theme_id,
                    seed_schema=seed_schema,
                    original_problem=original_problem,
                    allowed_rule_ids=allowed_rule_ids,
                    requested_rounds=quality_iterations,
                )
            problem_records.append(record)
            report_sections.extend(
                self._build_single_variant_report_sections(
                    problem_id=problem_id,
                    seed_schema=seed_schema,
                    plan=plan,
                    record=record,
                    generated=generated.__dict__,
                )
            )

        self._emit_progress(f"[problem] {problem_id}：写入过程报告。")
        report_path = self._write_problem_report(report_group=problem_id, report_name=problem_id, lines=report_sections)
        for record in problem_records:
            record["report_path"] = str(report_path)
        self._emit_progress(f"[problem] {problem_id}：完成。report={report_path}")
        return problem_records

    def _run_single_variant_once(
        self,
        *,
        problem_id: str,
        variant_index: int,
        theme_id: str | None,
        seed_schema: dict[str, Any],
        original_problem: dict[str, Any] | None,
        allowed_rule_ids: set[str] | None,
    ) -> tuple[VariantPlan, Any, dict[str, Any]]:
        self._emit_progress(f"[problem] {problem_id}：variant {variant_index} 进入规划。")
        plan = self.planner.build_plan(
            mode="single_seed_extension",
            variant_index=variant_index,
            theme_id=theme_id,
            seed_schema=seed_schema,
            original_problem=original_problem,
            allowed_rule_ids=allowed_rule_ids,
        )
        stem = self._build_stem(plan.source_problem_ids, plan.variant_index, plan.theme.theme_id)
        self._emit_progress(
            f"[problem] {problem_id}：variant {variant_index} 规划完成，规则={plan.applied_rule or '无'}。"
        )
        self._emit_progress(f"[problem] {problem_id}：variant {variant_index} 进入题面生成。")
        generated = self.generator.generate(
            {"seed_schema": seed_schema},
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
        return plan, generated, record

    def _run_single_variant_with_quality_iterations(
        self,
        *,
        problem_id: str,
        variant_index: int,
        theme_id: str | None,
        seed_schema: dict[str, Any],
        original_problem: dict[str, Any] | None,
        allowed_rule_ids: set[str] | None,
        requested_rounds: int,
    ) -> tuple[VariantPlan, Any, dict[str, Any]]:
        base_stem = ""
        run_id = ""
        previous_artifact_path = ""
        previous_quality_report_path = ""
        revision_context: dict[str, Any] | None = None
        round_records: list[dict[str, Any]] = []
        stop_reason = "reached_requested_rounds"
        last_plan: VariantPlan | None = None
        last_generated: Any | None = None
        final_record: dict[str, Any] | None = None

        for round_index in range(1, requested_rounds + 1):
            self._emit_progress(f"[problem] {problem_id}：variant {variant_index} 第 {round_index} 轮进入规划。")
            plan = self.planner.build_plan(
                mode="single_seed_extension",
                variant_index=variant_index,
                theme_id=theme_id,
                seed_schema=seed_schema,
                original_problem=original_problem,
                allowed_rule_ids=allowed_rule_ids,
                revision_context=revision_context,
            )
            if not base_stem:
                base_stem = self._build_stem(plan.source_problem_ids, plan.variant_index, plan.theme.theme_id)
                run_id = base_stem
            self._emit_progress(
                f"[problem] {problem_id}：variant {variant_index} 第 {round_index} 轮规划完成，规则={plan.applied_rule or '无'}。"
            )
            self._emit_progress(f"[problem] {problem_id}：variant {variant_index} 第 {round_index} 轮进入题面生成。")
            generated = self.generator.generate(
                {"seed_schema": seed_schema},
                plan,
                original_problems=[item for item in [original_problem] if item],
                revision_context=revision_context,
            )
            self._emit_progress(
                f"[problem] {problem_id}：variant {variant_index} 第 {round_index} 轮生成完成，status={generated.status}。"
            )
            markdown = render_problem_markdown(generated, plan)
            self._emit_progress(f"[problem] {problem_id}：variant {variant_index} 第 {round_index} 轮写入产物。")
            record = self._save_outputs(
                stem=base_stem,
                plan=plan,
                payload=generated.__dict__,
                markdown=markdown,
                round_index=round_index,
                iteration_metadata={
                    "run_id": run_id,
                    "round_index": round_index,
                    "requested_rounds": requested_rounds,
                    "previous_artifact_path": previous_artifact_path,
                    "previous_quality_report_path": previous_quality_report_path,
                    "revision_context_snapshot": json.loads(
                        json.dumps(revision_context or {}, ensure_ascii=False)
                    ),
                },
            )
            self._emit_progress(f"[problem] {problem_id}：variant {variant_index} 第 {round_index} 轮进入质量评测。")
            quality_result = self._evaluate_quality_round(
                problem_id=problem_id,
                round_index=round_index,
                schema_path=self.loader.source_dir / f"{problem_id}.json",
                artifact_path=Path(record["artifact_path"]),
                markdown_path=Path(record["markdown_path"]),
                original_problem=original_problem,
            )

            round_record = {
                "round_index": round_index,
                "artifact_path": record["artifact_path"],
                "markdown_path": record["markdown_path"],
                "quality_report_json_path": quality_result["json_path"],
                "quality_report_md_path": quality_result["md_path"],
                "overall_status": quality_result["report"]["overall"]["status"],
                "generated_status": quality_result["report"]["overall"]["generated_status"],
                "quality_score": quality_result["report"]["overall"]["quality_score"],
                "divergence_score": quality_result["report"]["overall"]["divergence_score"],
            }
            round_records.append(round_record)

            record["quality_report_json_path"] = quality_result["json_path"]
            record["quality_report_md_path"] = quality_result["md_path"]
            record["final_round_index"] = round_index
            record["round_records"] = list(round_records)

            previous_artifact_path = record["artifact_path"]
            previous_quality_report_path = quality_result["json_path"]
            last_plan = plan
            last_generated = generated
            final_record = record

            stop_reason = self._determine_quality_iteration_stop_reason(
                generated_status=generated.status,
                overall_status=str(quality_result["report"]["overall"]["status"]),
                round_index=round_index,
                requested_rounds=requested_rounds,
            )
            if stop_reason:
                break
            revision_context = quality_result["report"].get("revision_brief", {})

        if last_plan is None or last_generated is None or final_record is None:
            raise RuntimeError("质量闭环迭代未生成任何轮次产物。")

        summary_path = self._write_iteration_summary(
            stem=base_stem,
            problem_group=self._build_problem_group(last_plan.source_problem_ids),
            run_id=run_id,
            requested_rounds=requested_rounds,
            rounds=round_records,
            final_round_index=int(final_record.get("final_round_index", 1)),
            stop_reason=stop_reason,
        )
        final_record["iteration_summary_path"] = str(summary_path)
        return last_plan, last_generated, final_record

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

        seed_schema_a = self.loader.load(seed_a)
        seed_schema_b = self.loader.load(seed_b)
        original_problem_a = self._safe_get_problem(seed_schema_a, seed_a)
        original_problem_b = self._safe_get_problem(seed_schema_b, seed_b)

        report_key = f"{seed_a}__{seed_b}"
        report_sections = self._build_same_family_report_header(
            seed_a=seed_a,
            seed_b=seed_b,
            original_problem_a=original_problem_a,
            original_problem_b=original_problem_b,
            seed_schema_a=seed_schema_a,
            seed_schema_b=seed_schema_b,
        )

        records: list[dict[str, Any]] = []
        for variant_index in range(1, variants + 1):
            plan = self.planner.build_plan(
                mode="same_family_fusion",
                variant_index=variant_index,
                theme_id=theme_id,
                seed_a_schema=seed_schema_a,
                seed_b_schema=seed_schema_b,
                seed_a_problem=original_problem_a or {},
                seed_b_problem=original_problem_b or {},
                allowed_rule_ids=allowed_rule_ids,
            )
            stem = self._build_stem(plan.source_problem_ids, plan.variant_index, plan.theme.theme_id)
            generated = self.generator.generate(
                {
                    "seed_a_schema": seed_schema_a,
                    "seed_b_schema": seed_schema_b,
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

        report_path = self._write_problem_report(
            report_group=report_key,
            report_name=report_key,
            lines=report_sections,
        )
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
        round_index: int | None = None,
        iteration_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        stem_with_round = f"{stem}_round{round_index}" if round_index is not None else stem
        problem_group = self._build_problem_group(plan.source_problem_ids)
        json_path = self._resolve_problem_group_dir(self.artifact_dir, problem_group) / f"{stem_with_round}.json"
        md_path = self._resolve_problem_group_dir(self.output_dir, problem_group) / f"{stem_with_round}.md"

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
            "new_schema_snapshot": asdict(plan.new_schema_snapshot),
            "applied_rule": plan.applied_rule,
            "rejected_candidates": plan.rejected_candidates,
            "algorithmic_delta_claim": plan.algorithmic_delta_claim,
            "anti_shallow_rationale": plan.anti_shallow_rationale,
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
        if iteration_metadata is not None:
            artifact["iteration"] = json.loads(json.dumps(iteration_metadata, ensure_ascii=False))

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
    ) -> list[str]:
        return [
            f"# {problem_id} 生成报告",
            "",
        ]

    def _build_single_variant_report_sections(
        self,
        *,
        problem_id: str,
        seed_schema: dict[str, Any],
        plan: VariantPlan,
        record: dict[str, Any],
        generated: dict[str, Any],
    ) -> list[str]:
        status = str(generated.get("status", "ok") or "ok")
        lines = [f"## Variant {plan.variant_index}", ""]
        if status == "ok":
            lines.extend(
                self._build_single_success_report_sections(
                    problem_id=problem_id,
                    seed_schema=seed_schema,
                    plan=plan,
                    record=record,
                    generated=generated,
                )
            )
        else:
            lines.extend(
                self._build_single_failure_report_sections(
                    seed_schema=seed_schema,
                    plan=plan,
                    record=record,
                    generated=generated,
                )
            )
        lines.append("")
        return lines

    def _build_single_success_report_sections(
        self,
        *,
        problem_id: str,
        seed_schema: dict[str, Any],
        plan: VariantPlan,
        record: dict[str, Any],
        generated: dict[str, Any],
    ) -> list[str]:
        lines = [
            "### 生成结论",
            f"- status: {generated.get('status', 'ok')}",
            f"- title: {generated.get('title', '') or '无'}",
            f"- applied_rule: {plan.applied_rule or '无'}",
            f"- theme: {plan.theme.theme_id} / {plan.theme.name}",
            f"- predicted_schema_distance: {plan.predicted_schema_distance}",
            "",
            "### 核心判断",
            f"- changed_axes_realized: {', '.join(plan.changed_axes_realized) or '无'}",
            f"- difference_summary: {plan.difference_plan.summary or '无'}",
            f"- rule_selection_reason: {plan.rule_selection_reason or '无'}",
            f"- anti_shallow_rationale: {plan.anti_shallow_rationale or '无'}",
            "",
            "### 四元组对比",
            "",
            "#### 输入结构",
            *self._render_markdown_table(
                headers=["项目", "原题", "新题", "变化判断"],
                rows=self._build_input_structure_compare_rows(
                    seed_schema.get("input_structure", {}),
                    asdict(plan.new_schema_snapshot).get("input_structure", {}),
                ),
            ),
            "",
            "#### 核心约束",
            *self._render_markdown_table(
                headers=["项目", "原题", "新题", "变化判断"],
                rows=self._build_named_item_compare_rows(
                    seed_schema.get("core_constraints", {}).get("constraints", []),
                    asdict(plan.new_schema_snapshot).get("core_constraints", {}).get("constraints", []),
                    label_prefix="约束",
                ),
            ),
            "",
            "#### 求解目标",
            *self._render_markdown_table(
                headers=["项目", "原题", "新题", "变化判断"],
                rows=self._build_objective_compare_rows(
                    seed_schema.get("objective", {}),
                    asdict(plan.new_schema_snapshot).get("objective", {}),
                ),
            ),
            "",
            "#### 关键不变量",
            *self._render_markdown_table(
                headers=["项目", "原题", "新题", "变化判断"],
                rows=self._build_named_item_compare_rows(
                    seed_schema.get("invariant", {}).get("invariants", []),
                    asdict(plan.new_schema_snapshot).get("invariant", {}).get("invariants", []),
                    label_prefix="不变量",
                ),
            ),
            "",
            "### 解法变化",
            f"- seed_solver_core: {plan.algorithmic_delta_claim.get('seed_solver_core', '') or '无'}",
            f"- new_solver_core: {plan.algorithmic_delta_claim.get('new_solver_core', '') or '无'}",
            f"- new_proof_obligation: {plan.algorithmic_delta_claim.get('new_proof_obligation', '') or '无'}",
            "",
            "### 输出产物",
            f"- markdown_path: {record['markdown_path']}",
            f"- artifact_path: {record['artifact_path']}",
        ]
        return lines

    def _build_single_failure_report_sections(
        self,
        *,
        seed_schema: dict[str, Any],
        plan: VariantPlan,
        record: dict[str, Any],
        generated: dict[str, Any],
    ) -> list[str]:
        failure_reason = (
            generated.get("error_reason")
            or plan.planning_error_reason
            or plan.difference_plan.rationale
            or "无"
        )
        feedback = generated.get("feedback") or plan.planning_feedback or "无"
        lines = [
            "### 生成结论",
            f"- status: {generated.get('status', 'ok')}",
            f"- applied_rule: {plan.applied_rule or '无'}",
            f"- theme: {plan.theme.theme_id} / {plan.theme.name}",
            f"- planning_status: {plan.planning_status or '无'}",
            f"- predicted_schema_distance: {plan.predicted_schema_distance}",
            "",
            "### 失败原因",
            f"- error_reason: {failure_reason}",
            f"- feedback: {feedback}",
            "",
            "### 原题四元组",
            "#### 输入结构",
            *self._render_readable_input_structure(seed_schema.get("input_structure", {})),
            "",
            "#### 核心约束",
            *self._render_readable_named_items(
                seed_schema.get("core_constraints", {}).get("constraints", []),
                empty_text="- 无",
            ),
            "",
            "#### 求解目标",
            *self._render_readable_objective(seed_schema.get("objective", {})),
            "",
            "#### 关键不变量",
            *self._render_readable_named_items(
                seed_schema.get("invariant", {}).get("invariants", []),
                empty_text="- 无",
            ),
            "",
            "### 候选规则结论",
            *self._render_candidate_outcome_summary(plan),
            "",
            "### 建议方向",
            f"- {feedback}",
            "",
            "### 输出产物",
            f"- markdown_path: {record['markdown_path']}",
            f"- artifact_path: {record['artifact_path']}",
        ]
        return lines

    def _build_same_family_report_header(
        self,
        *,
        seed_a: str,
        seed_b: str,
        original_problem_a: dict[str, Any] | None,
        original_problem_b: dict[str, Any] | None,
        seed_schema_a: dict[str, Any],
        seed_schema_b: dict[str, Any],
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
            "### 四元组摘要",
            *self._render_schema_summary(seed_schema_a),
            "",
            "## 种子题 B",
            *self._render_problem_reference(original_problem_b),
            "",
            "### 四元组摘要",
            *self._render_schema_summary(seed_schema_b),
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
                *self._render_new_schema(plan),
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

    def _build_problem_group(self, source_problem_ids: list[str]) -> str:
        group = "__".join(problem_id for problem_id in source_problem_ids if problem_id)
        return group or "unknown_problem"

    def _resolve_problem_group_dir(self, base_dir: Path, problem_group: str) -> Path:
        group_dir = base_dir / problem_group
        group_dir.mkdir(parents=True, exist_ok=True)
        return group_dir

    def _write_problem_report(self, *, report_group: str, report_name: str, lines: list[str]) -> Path:
        report_path = self._resolve_problem_group_dir(self.report_dir, report_group) / f"{report_name}.md"
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
        return {"artifact_path": artifact_path}

    def _get_quality_evaluator(self) -> Any:
        if self.quality_evaluator is None:
            self.quality_evaluator = ProblemEvaluator()
        return self.quality_evaluator

    def _evaluate_quality_round(
        self,
        *,
        problem_id: str,
        round_index: int,
        schema_path: Path,
        artifact_path: Path,
        markdown_path: Path,
        original_problem: dict[str, Any] | None,
    ) -> dict[str, Any]:
        report = self._get_quality_evaluator().evaluate_problem(
            schema_path=schema_path,
            artifact_path=artifact_path,
            original_problem_override=original_problem,
            markdown_path=markdown_path,
            round_index=round_index,
        )
        report_group_dir = self._resolve_problem_group_dir(self.report_dir, problem_id)
        report_stem = artifact_path.stem + "_quality_report"
        json_path = report_group_dir / f"{report_stem}.json"
        md_path = report_group_dir / f"{report_stem}.md"
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        md_path.write_text(self.quality_report_renderer(report), encoding="utf-8")
        self._emit_progress(
            f"[problem] {problem_id}：第 {round_index} 轮质量评测完成，status={report['overall']['status']}。"
        )
        return {
            "report": report,
            "json_path": str(json_path),
            "md_path": str(md_path),
        }

    def _determine_quality_iteration_stop_reason(
        self,
        *,
        generated_status: str,
        overall_status: str,
        round_index: int,
        requested_rounds: int,
    ) -> str:
        if generated_status in {"schema_insufficient", "difference_insufficient"}:
            return generated_status
        if overall_status == "pass":
            return "pass"
        if overall_status == "reject_invalid":
            return "reject_invalid"
        if round_index >= requested_rounds:
            return "reached_requested_rounds"
        if overall_status in {"revise_quality", "reject_as_retheme"} and generated_status == "ok":
            return ""
        return "reached_requested_rounds"

    def _write_iteration_summary(
        self,
        *,
        stem: str,
        problem_group: str,
        run_id: str,
        requested_rounds: int,
        rounds: list[dict[str, Any]],
        final_round_index: int,
        stop_reason: str,
    ) -> Path:
        summary_path = self._resolve_problem_group_dir(self.artifact_dir, problem_group) / f"{stem}_iteration_summary.json"
        payload = {
            "run_id": run_id,
            "requested_rounds": requested_rounds,
            "final_round_index": final_round_index,
            "stop_reason": stop_reason,
            "rounds": list(rounds),
        }
        summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary_path

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

    def _render_new_schema(self, plan: VariantPlan) -> list[str]:
        snapshot = asdict(plan.new_schema_snapshot)
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

    def _render_markdown_table(
        self,
        *,
        headers: list[str],
        rows: list[list[str]],
    ) -> list[str]:
        safe_rows = rows or [["无", "无", "无", "无"]]
        lines = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join(["---"] * len(headers)) + " |",
        ]
        for row in safe_rows:
            lines.append("| " + " | ".join(self._escape_markdown_cell(item) for item in row) + " |")
        return lines

    def _build_input_structure_compare_rows(
        self,
        source: dict[str, Any],
        target: dict[str, Any],
    ) -> list[list[str]]:
        source_type = str(source.get("type", "") or "无")
        target_type = str(target.get("type", "") or "无")
        source_length = self._format_range(source.get("length", {}), empty_text="无")
        target_length = self._format_range(target.get("length", {}), empty_text="无")
        source_value_range = self._format_range(
            source.get("value_range", {}),
            none_text="无显式数值范围",
            empty_text="无显式数值范围",
        )
        target_value_range = self._format_range(
            target.get("value_range", {}),
            none_text="无显式数值范围",
            empty_text="无显式数值范围",
        )
        source_properties = self._format_properties(source.get("properties", {}))
        target_properties = self._format_properties(target.get("properties", {}))
        return [
            ["类型", source_type, target_type, self._compare_report_values(source_type, target_type)],
            ["规模范围", source_length, target_length, self._compare_report_values(source_length, target_length)],
            ["数值范围", source_value_range, target_value_range, self._compare_report_values(source_value_range, target_value_range)],
            ["结构性质", source_properties, target_properties, self._compare_report_values(source_properties, target_properties)],
        ]

    def _build_named_item_compare_rows(
        self,
        source_items: list[dict[str, Any]],
        target_items: list[dict[str, Any]],
        *,
        label_prefix: str,
    ) -> list[list[str]]:
        row_count = max(len(source_items), len(target_items), 1)
        rows: list[list[str]] = []
        for index in range(row_count):
            source_item = source_items[index] if index < len(source_items) else {}
            target_item = target_items[index] if index < len(target_items) else {}
            label = (
                str(source_item.get("name", "") or target_item.get("name", "")).strip()
                or f"{label_prefix}{index + 1}"
            )
            source_text = self._format_named_item(source_item)
            target_text = self._format_named_item(target_item)
            rows.append(
                [
                    label,
                    source_text,
                    target_text,
                    self._compare_report_values(source_text, target_text),
                ]
            )
        return rows

    def _build_objective_compare_rows(
        self,
        source: dict[str, Any],
        target: dict[str, Any],
    ) -> list[list[str]]:
        source_type = str(source.get("type", "") or "无")
        target_type = str(target.get("type", "") or "无")
        source_description = str(source.get("description", "") or "无")
        target_description = str(target.get("description", "") or "无")
        source_solution = self._format_boolean_flag(source.get("requires_solution"))
        target_solution = self._format_boolean_flag(target.get("requires_solution"))
        return [
            ["目标类型", source_type, target_type, self._compare_report_values(source_type, target_type)],
            ["目标描述", source_description, target_description, self._compare_report_values(source_description, target_description)],
            ["输出责任", source_solution, target_solution, self._compare_report_values(source_solution, target_solution)],
        ]

    def _render_readable_input_structure(self, input_structure: dict[str, Any]) -> list[str]:
        return [
            f"- 类型：{input_structure.get('type', '') or '无'}",
            f"- 规模范围：{self._format_range(input_structure.get('length', {}), empty_text='无')}",
            "- 数值范围："
            + self._format_range(
                input_structure.get("value_range", {}),
                none_text="无显式数值范围",
                empty_text="无显式数值范围",
            ),
            f"- 结构性质：{self._format_properties(input_structure.get('properties', {}))}",
        ]

    def _render_readable_objective(self, objective: dict[str, Any]) -> list[str]:
        return [
            f"- 类型：{objective.get('type', '') or '无'}",
            f"- 描述：{objective.get('description', '') or '无'}",
            f"- 输出责任：{self._format_boolean_flag(objective.get('requires_solution'))}",
        ]

    def _render_readable_named_items(
        self,
        items: list[dict[str, Any]],
        *,
        empty_text: str,
    ) -> list[str]:
        if not items:
            return [empty_text]
        return [f"- {self._format_named_item(item)}" for item in items]

    def _render_candidate_outcome_summary(self, plan: VariantPlan) -> list[str]:
        lines: list[str] = []
        attempt_by_rule = {
            str(item.get("rule_id", "")): item
            for item in plan.candidate_attempts
            if str(item.get("rule_id", "")).strip()
        }
        rejected_by_rule = {
            str(item.get("rule_id", "")): item
            for item in plan.rejected_candidates
            if str(item.get("rule_id", "")).strip()
        }
        covered_rules: set[str] = set()
        for item in plan.selection_trace:
            rule_id = str(item.get("rule_id", "")).strip()
            if not rule_id:
                continue
            covered_rules.add(rule_id)
            reason_code = str(
                attempt_by_rule.get(rule_id, {}).get("reason_code")
                or item.get("reason_code", "")
                or "无"
            )
            reason = str(
                rejected_by_rule.get(rule_id, {}).get("reason")
                or attempt_by_rule.get(rule_id, {}).get("reason")
                or item.get("selection_reason", "")
                or "无"
            )
            accepted = "资格通过" if bool(item.get("accepted")) else "资格未通过"
            if rule_id in rejected_by_rule:
                accepted = "规划未通过"
            lines.append(f"- {rule_id}：{accepted}；reason_code={reason_code}；{reason}")
        for item in plan.rejected_candidates:
            rule_id = str(item.get("rule_id", "")).strip()
            if not rule_id or rule_id in covered_rules:
                continue
            reason = str(item.get("reason", "") or "无")
            status = str(item.get("status", "") or "difference_insufficient")
            lines.append(f"- {rule_id}：规划未通过；reason_code={status}；{reason}")
        return lines or ["- 无"]

    def _format_range(
        self,
        value: dict[str, Any],
        *,
        none_text: str = "无",
        empty_text: str = "无",
    ) -> str:
        if not isinstance(value, dict) or not value:
            return empty_text
        lower = value.get("min")
        upper = value.get("max")
        if lower is None and upper is None:
            return none_text
        if lower == upper and lower is not None:
            return str(lower)
        if lower is None:
            return f"不超过 {upper}"
        if upper is None:
            return f"至少 {lower}"
        return f"{lower} 到 {upper}"

    def _format_properties(self, properties: dict[str, Any]) -> str:
        if not isinstance(properties, dict) or not properties:
            return "无"
        parts: list[str] = []
        for key, value in properties.items():
            if value is True:
                parts.append(str(key))
            elif value is False:
                parts.append(f"{key}=false")
            else:
                parts.append(f"{key}={value}")
        return "、".join(parts) or "无"

    def _format_named_item(self, item: dict[str, Any]) -> str:
        if not isinstance(item, dict) or not item:
            return "无"
        name = str(item.get("name", "") or "").strip()
        description = str(item.get("description", "") or "").strip()
        if name and description:
            return f"{name}：{description}"
        return name or description or "无"

    def _format_boolean_flag(self, value: Any) -> str:
        if value is True:
            return "需要输出完整解对象"
        if value is False:
            return "只需输出结果"
        return "未显式声明"

    def _compare_report_values(self, source: str, target: str) -> str:
        if source == target:
            return "保持一致"
        if source == "无" and target != "无":
            return "新增"
        if target == "无" and source != "无":
            return "移除"
        return "发生变化"

    def _escape_markdown_cell(self, value: Any) -> str:
        text = str(value if value is not None else "无")
        return text.replace("|", "\\|").replace("\n", "<br>")

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
            "backend": "embedding",
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
        "backend": str(distance_breakdown.get("backend", "embedding")),
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
