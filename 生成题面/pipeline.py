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
    ):
        self.raw_loader = SchemaLoader(raw_source_dir)
        self.loader = SchemaLoader(source_dir)
        self.output_dir = output_dir
        self.artifact_dir = artifact_dir
        self.report_dir = report_dir
        self.generator = generator
        self.planner = planner
        self.problem_repository = ProblemRepository()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def run(
        self,
        problem_ids: list[str],
        variants: int = 1,
        theme_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if not problem_ids:
            problem_ids = self.loader.list_problem_ids()

        records: list[dict[str, Any]] = []
        for problem_id in problem_ids:
            original_schema = self.raw_loader.load(problem_id)
            prepared_schema = self.loader.load(problem_id)
            original_problem = self.problem_repository.get_problem(
                source=prepared_schema.get("source", ""),
                problem_id=prepared_schema.get("problem_id", problem_id),
            )

            report_sections = self._build_report_header(
                problem_id=problem_id,
                original_problem=original_problem,
                original_schema=original_schema,
                prepared_schema=prepared_schema,
            )

            problem_records: list[dict[str, Any]] = []
            for variant_index in range(1, variants + 1):
                plan = self.planner.build_plan(
                    schema=prepared_schema,
                    variant_index=variant_index,
                    theme_id=theme_id,
                    original_schema=original_schema,
                    original_problem=original_problem,
                )
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                stem = f"{problem_id}_v{plan.variant_index}_{plan.theme.theme_id}_{timestamp}"

                generated = self.generator.generate(
                    prepared_schema,
                    plan,
                    original_problem=original_problem,
                )
                markdown = render_problem_markdown(generated, plan)
                record = self._save_outputs(
                    stem=stem,
                    problem_id=problem_id,
                    plan=plan,
                    payload=generated.__dict__,
                    markdown=markdown,
                )
                problem_records.append(record)
                records.append(record)
                report_sections.extend(
                    self._build_variant_report_sections(
                        variant_index=variant_index,
                        original_schema=original_schema,
                        prepared_schema=prepared_schema,
                        plan=plan,
                        record=record,
                        generated=generated.__dict__,
                    )
                )

            report_path = self._write_problem_report(problem_id, report_sections)
            for record in problem_records:
                record["report_path"] = str(report_path)

        return records

    def _save_outputs(
        self,
        stem: str,
        problem_id: str,
        plan: VariantPlan,
        payload: dict[str, Any],
        markdown: str,
    ) -> dict[str, Any]:
        json_path = self.artifact_dir / f"{stem}.json"
        md_path = self.output_dir / f"{stem}.md"

        artifact = {
            "problem_id": problem_id,
            "variant_index": plan.variant_index,
            "seed": plan.seed,
            "theme": {
                "id": plan.theme.theme_id,
                "name": plan.theme.name,
            },
            "difference_plan": asdict(plan.difference_plan),
            "predicted_schema_distance": plan.predicted_schema_distance,
            "distance_breakdown": plan.distance_breakdown,
            "changed_axes_realized": plan.changed_axes_realized,
            "objective": plan.objective,
            "numerical_parameters": plan.numerical_parameters,
            "structural_options": plan.structural_options,
            "input_structure_options": plan.input_structure_options,
            "invariant_options": plan.invariant_options,
            "instantiated_schema_snapshot": asdict(plan.instantiated_schema_snapshot),
            "generated_problem": payload,
        }

        with json_path.open("w", encoding="utf-8") as handle:
            json.dump(artifact, handle, ensure_ascii=False, indent=2)

        with md_path.open("w", encoding="utf-8") as handle:
            handle.write(markdown)

        return {
            "problem_id": problem_id,
            "variant_index": plan.variant_index,
            "markdown_path": str(md_path),
            "artifact_path": str(json_path),
            "generated_status": payload.get("status", "ok"),
        }

    def _build_report_header(
        self,
        problem_id: str,
        original_problem: dict[str, Any],
        original_schema: dict[str, Any],
        prepared_schema: dict[str, Any],
    ) -> list[str]:
        return [
            f"# {problem_id} 生成过程说明",
            "",
            "## 原题信息",
            f"- 原题标题：{original_problem.get('title', '')}",
            f"- 来源：{original_problem.get('source', '')}",
            f"- 原题链接：{original_problem.get('url', '')}",
            f"- 标签：{', '.join(original_problem.get('tags', [])) or '无'}",
            f"- 难度：{original_problem.get('difficulty', '') or '无'}",
            "",
            "## 原题文本",
            f"### 标题",
            original_problem.get("title", "") or "无",
            "",
            "### Description",
            original_problem.get("description", "") or "无",
            "",
            "### Input",
            original_problem.get("input", "") or "无",
            "",
            "### Output",
            original_problem.get("output", "") or "无",
            "",
            "### Constraints",
            original_problem.get("constraints", "") or "无",
            "",
            "## 原始 Schema 摘要",
            *self._render_schema_summary(original_schema),
            "",
            "## Prepared Schema 摘要",
            *self._render_schema_summary(prepared_schema),
            "",
            "## Transform Space 参数",
            *self._render_transform_space(prepared_schema.get("transform_space", {})),
            "",
        ]

    def _build_variant_report_sections(
        self,
        variant_index: int,
        original_schema: dict[str, Any],
        prepared_schema: dict[str, Any],
        plan: VariantPlan,
        record: dict[str, Any],
        generated: dict[str, Any],
    ) -> list[str]:
        return [
            f"## Variant {variant_index}",
            "",
            "### Variant Plan",
            *self._render_variant_plan(plan),
            "",
            "### Difference Plan",
            *self._render_difference_plan(plan),
            "",
            "### 变换过程",
            *self._render_transformation_trace(original_schema, prepared_schema, plan),
            "",
            "### 变换后的新 Schema",
            *self._render_transformed_schema(prepared_schema, plan),
            "",
            "### 生成结果",
            f"- 生成状态：{generated.get('status', 'ok')}",
            f"- 生成题目标题：{generated.get('title', '') or '无'}",
            f"- error_reason：{generated.get('error_reason', '') or '无'}",
            f"- feedback：{generated.get('feedback', '') or '无'}",
            f"- 题面 Markdown：{record['markdown_path']}",
            f"- 结构化产物：{record['artifact_path']}",
            "",
        ]

    def _write_problem_report(self, problem_id: str, lines: list[str]) -> Path:
        report_path = self.report_dir / f"{problem_id}.md"
        report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        return report_path

    def _render_schema_summary(self, schema: dict[str, Any]) -> list[str]:
        transform_space = schema.get("transform_space", {})
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
            f"- has_transform_space: {'yes' if transform_space else 'no'}",
        ]

    def _render_transform_space(self, transform_space: dict[str, Any]) -> list[str]:
        lines = ["- numerical_parameters:"]
        numerical_parameters = transform_space.get("numerical_parameters", {})
        if numerical_parameters:
            for name, spec in numerical_parameters.items():
                lines.append(
                    "  - "
                    + f"{name}: range=[{spec.get('min')}..{spec.get('max')}], "
                    + f"description={spec.get('description', '')}"
                )
        else:
            lines.append("  - 无")

        lines.append(
            "- objective_options: "
            + (", ".join(transform_space.get("objective_options", [])) or "无")
        )
        lines.append(
            "- structural_options: "
            + (", ".join(transform_space.get("structural_options", [])) or "无")
        )
        input_options = transform_space.get("input_structure_options", [])
        lines.append("- input_structure_options:")
        if input_options:
            for item in input_options:
                lines.append(
                    "  - "
                    + f"{item.get('name', '')}: {item.get('description', '')}"
                )
        else:
            lines.append("  - 无")
        invariant_options = transform_space.get("invariant_options", [])
        lines.append("- invariant_options:")
        if invariant_options:
            for item in invariant_options:
                lines.append(
                    "  - "
                    + f"{item.get('name', '')}: {item.get('description', '')}"
                )
        else:
            lines.append("  - 无")
        return lines

    def _render_variant_plan(self, plan: VariantPlan) -> list[str]:
        lines = [
            f"- problem_id: {plan.problem_id}",
            f"- variant_index: {plan.variant_index}",
            f"- seed: {plan.seed}",
            f"- theme: {plan.theme.theme_id} ({plan.theme.name})",
            f"- theme_tone: {plan.theme.tone}",
            "- theme_keywords: " + ", ".join(plan.theme.keywords),
            f"- theme_mapping_hint: {plan.theme.mapping_hint}",
            f"- objective: {self._describe_objective(plan.objective)}",
            f"- difficulty: {plan.difficulty}",
            f"- input_summary: {plan.input_summary}",
            "- selected_parameters:",
        ]
        if plan.numerical_parameters:
            for name, spec in plan.numerical_parameters.items():
                lines.append(
                    "  - "
                    + f"{name}: value={spec.get('value')}, "
                    + f"range=[{spec.get('min')}..{spec.get('max')}], "
                    + f"description={spec.get('description', '')}"
                )
        else:
            lines.append("  - 无")

        lines.append(
            "- selected_structural_options: "
            + (", ".join(plan.structural_options) if plan.structural_options else "无")
        )
        lines.append(
            "- selected_input_structure_options: "
            + (
                ", ".join(plan.input_structure_options)
                if plan.input_structure_options
                else "无"
            )
        )
        lines.append(
            "- selected_invariant_options: "
            + (", ".join(plan.invariant_options) if plan.invariant_options else "无")
        )
        lines.append("- constraint_summary:")
        lines.extend(self._render_plain_list(plan.constraint_summary, empty_text="  - 无"))
        lines.append("- invariant_summary:")
        lines.extend(self._render_plain_list(plan.invariant_summary, empty_text="  - 无"))
        return lines

    def _render_difference_plan(self, plan: VariantPlan) -> list[str]:
        band = plan.difference_plan.target_distance_band
        return [
            f"- target_distance_band: [{band.get('min')}..{band.get('max')})",
            "- planned_changed_axes: "
            + (", ".join(plan.difference_plan.changed_axes) or "无"),
            "- realized_changed_axes: "
            + (", ".join(plan.changed_axes_realized) or "无"),
            f"- predicted_schema_distance: {plan.predicted_schema_distance}",
            "- distance_breakdown: "
            + ", ".join(
                f"{name}={value}" for name, value in plan.distance_breakdown.items()
            ),
            f"- same_family_allowed: {plan.difference_plan.same_family_allowed}",
            "- forbidden_reuse:",
            *self._render_plain_list(plan.difference_plan.forbidden_reuse, empty_text="  - 无"),
            f"- rationale: {plan.difference_plan.rationale}",
        ]

    def _render_transformation_trace(
        self,
        original_schema: dict[str, Any],
        prepared_schema: dict[str, Any],
        plan: VariantPlan,
    ) -> list[str]:
        original_transform_space = original_schema.get("transform_space", {})
        prepared_transform_space = prepared_schema.get("transform_space", {})
        if original_transform_space:
            resolution = "原始 schema 已包含 transform_space，直接使用。"
        elif prepared_transform_space:
            resolution = "原始 schema 不包含 transform_space，使用 prepared schema 中补全后的 transform_space。"
        else:
            resolution = "schema 中未发现 transform_space。"

        lines = [
            f"- transform_space_resolution: {resolution}",
            "- objective_selection:",
            f"  - original: {self._describe_objective(original_schema.get('objective', {}))}",
            "  - available_options: "
            + (", ".join(prepared_transform_space.get("objective_options", [])) or "无"),
            f"  - selected: {self._describe_objective(plan.objective)}",
            "- parameter_materialization:",
        ]
        if plan.numerical_parameters:
            for name, spec in plan.numerical_parameters.items():
                lines.append(
                    "  - "
                    + f"{name}: from [{spec.get('min')}..{spec.get('max')}] "
                    + f"to {spec.get('value')} ({spec.get('description', '')})"
                )
        else:
            lines.append("  - 无")
        lines.append(
            "- structural_option_selection: available="
            + (", ".join(prepared_transform_space.get("structural_options", [])) or "无")
        )
        lines.append(
            "- selected_structural_options: "
            + (", ".join(plan.structural_options) if plan.structural_options else "无")
        )
        lines.append(
            "- input_structure_option_selection: available="
            + (
                ", ".join(
                    item.get("name", "")
                    for item in prepared_transform_space.get("input_structure_options", [])
                    if item.get("name")
                )
                or "无"
            )
        )
        lines.append(
            "- selected_input_structure_options: "
            + (
                ", ".join(plan.input_structure_options)
                if plan.input_structure_options
                else "无"
            )
        )
        lines.append(
            "- invariant_option_selection: available="
            + (
                ", ".join(
                    item.get("name", "")
                    for item in prepared_transform_space.get("invariant_options", [])
                    if item.get("name")
                )
                or "无"
            )
        )
        lines.append(
            "- selected_invariant_options: "
            + (", ".join(plan.invariant_options) if plan.invariant_options else "无")
        )
        lines.append(f"- theme_mapping: {plan.theme.name} / {plan.theme.mapping_hint}")
        return lines

    def _render_transformed_schema(
        self, prepared_schema: dict[str, Any], plan: VariantPlan
    ) -> list[str]:
        snapshot = asdict(plan.instantiated_schema_snapshot)
        lines = [
            f"- problem_id: {snapshot.get('problem_id', plan.problem_id)}",
            f"- source: {snapshot.get('source', '')}",
            f"- input_structure: {self._describe_input_structure(snapshot.get('input_structure', {}))}",
            f"- objective: {self._describe_objective(plan.objective)}",
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
            f"- instantiated_theme: {plan.theme.theme_id} ({plan.theme.name})",
            f"- instantiated_difficulty: {plan.difficulty}",
            "- instantiated_parameters:",
        ]
        if plan.numerical_parameters:
            for name, spec in plan.numerical_parameters.items():
                lines.append(
                    "  - "
                    + f"{name}: value={spec.get('value')}, "
                    + f"range=[{spec.get('min')}..{spec.get('max')}], "
                    + f"description={spec.get('description', '')}"
                )
        else:
            lines.append("  - 无")
        lines.append(
            "- instantiated_structural_options: "
            + (", ".join(plan.structural_options) if plan.structural_options else "无")
        )
        lines.append(
            "- instantiated_input_structure_options: "
            + (
                ", ".join(snapshot.get("selected_input_options", []))
                if snapshot.get("selected_input_options")
                else "无"
            )
        )
        lines.append(
            "- instantiated_invariant_options: "
            + (
                ", ".join(snapshot.get("selected_invariant_options", []))
                if snapshot.get("selected_invariant_options")
                else "无"
            )
        )
        lines.append(f"- instantiated_input_summary: {plan.input_summary}")
        return lines

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
            props = ", ".join(f"{key}={value}" for key, value in properties.items())
            parts.append(f"properties={props}")
        return "; ".join(parts)

    def _describe_objective(self, objective: dict[str, Any]) -> str:
        parts = [f"type={objective.get('type', '')}"]
        if objective.get("description"):
            parts.append(f"description={objective.get('description')}")
        if objective.get("confidence"):
            parts.append(f"confidence={objective.get('confidence')}")
        return "; ".join(parts)

    def _render_named_items(
        self,
        items: list[dict[str, Any]],
        empty_text: str,
    ) -> list[str]:
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

    def _render_plain_list(self, items: list[str], empty_text: str) -> list[str]:
        if not items:
            return [empty_text]
        return [f"  - {item}" for item in items]
