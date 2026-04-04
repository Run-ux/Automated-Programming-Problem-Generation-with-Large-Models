from __future__ import annotations

from dataclasses import asdict
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

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
    ):
        self.raw_loader = SchemaLoader(raw_source_dir)
        self.loader = SchemaLoader(source_dir)
        self.output_dir = output_dir
        self.artifact_dir = artifact_dir
        self.report_dir = report_dir
        self.generator = generator
        self.planner = planner
        self.problem_repository = problem_repository or ProblemRepository()
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
    ) -> list[dict[str, Any]]:
        canonical_mode = _canonical_mode(mode)
        if canonical_mode == "single_seed_extension":
            return self._run_single(
                problem_ids=problem_ids,
                variants=variants,
                theme_id=theme_id,
                allowed_rule_ids=allowed_rule_ids,
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
    ) -> list[dict[str, Any]]:
        target_problem_ids = list(problem_ids) or self.loader.list_problem_ids()
        records: list[dict[str, Any]] = []

        for problem_id in target_problem_ids:
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
                generated = self.generator.generate(
                    {"seed_schema": prepared_schema},
                    plan,
                    original_problems=[item for item in [original_problem] if item],
                )
                markdown = render_problem_markdown(generated, plan)
                record = self._save_outputs(
                    stem=stem,
                    plan=plan,
                    payload=generated.__dict__,
                    markdown=markdown,
                )
                records.append(record)
                problem_records.append(record)
                report_sections.extend(
                    self._build_variant_report_sections(
                        plan=plan,
                        record=record,
                        generated=generated.__dict__,
                    )
                )

            report_path = self._write_problem_report(problem_id, report_sections)
            for record in problem_records:
                record["report_path"] = str(report_path)

        return records

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
            "auxiliary_moves": plan.auxiliary_moves,
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
            + ", ".join(
                f"{name}={value}" for name, value in _normalize_distance_breakdown(plan.distance_breakdown).items()
            ),
            f"- difference_plan_summary: {plan.difference_plan.summary or '无'}",
            f"- difference_plan_rationale: {plan.difference_plan.rationale or '无'}",
        ]
        lines.extend(self._render_auxiliary_moves(plan.auxiliary_moves))
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

    def _render_auxiliary_moves(self, moves: list[str]) -> list[str]:
        return [
            "- auxiliary_moves: " + (", ".join(moves) if moves else "无"),
        ]

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


def _normalize_distance_breakdown(distance_breakdown: dict[str, float]) -> dict[str, float]:
    normalized = {
        "I": round(float(distance_breakdown.get("I", 0.0)), 4),
        "C": round(float(distance_breakdown.get("C", 0.0)), 4),
        "O": round(float(distance_breakdown.get("O", 0.0)), 4),
        "V": round(float(distance_breakdown.get("V", 0.0)), 4),
        "total": round(float(distance_breakdown.get("total", 0.0)), 4),
    }
    return normalized


def _slugify(text: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in str(text))
    return cleaned.strip("_") or "variant"
