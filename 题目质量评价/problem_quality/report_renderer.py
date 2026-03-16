from __future__ import annotations

from typing import Any


def render_report_markdown(report: dict[str, Any]) -> str:
    overall = report.get("overall", {})
    quality = report.get("quality", {})
    divergence = report.get("divergence", {})
    hard_checks = report.get("hard_checks", [])
    issues = report.get("issues", [])
    snapshots = report.get("snapshots", {})

    lines: list[str] = [
        "# 题目质量与反换皮评估报告",
        "",
        "## 总览",
        f"- status: {overall.get('status', '')}",
        f"- quality_score: {overall.get('quality_score', '')}",
        f"- divergence_score: {overall.get('divergence_score', '')}",
        f"- schema_distance: {overall.get('schema_distance', '')}",
        f"- generated_status: {overall.get('generated_status', '')}",
        "",
        "## 质量维度",
    ]

    for item in quality.get("dimension_scores", []):
        lines.append(
            f"- {item.get('dimension')}: {item.get('score')} / 5"
            + (f" | {item.get('rationale')}" if item.get("rationale") else "")
        )
    strengths = quality.get("strengths", [])
    if strengths:
        lines.extend(["", "## 优点"])
        for item in strengths:
            lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "## 与原题差异分析",
            f"- changed_axes_planned: {', '.join(divergence.get('changed_axes_planned', [])) or '无'}",
            f"- changed_axes_realized: {', '.join(divergence.get('changed_axes_realized', [])) or '无'}",
            f"- semantic_difference: {divergence.get('semantic_difference', '')}",
            f"- solution_transfer_risk: {divergence.get('solution_transfer_risk', '')}",
            f"- surface_retheme_risk: {divergence.get('surface_retheme_risk', '')}",
            f"- verdict: {divergence.get('verdict', '')}",
            f"- rationale: {divergence.get('rationale', '')}",
            "",
            "## 硬检查",
        ]
    )
    for item in hard_checks:
        marker = "PASS" if item.get("passed") else "FAIL"
        lines.append(
            f"- [{marker}] {item.get('check_id')} ({item.get('severity')}/{item.get('category')}): {item.get('message')}"
        )

    if issues:
        lines.extend(["", "## 问题清单"])
        for item in issues:
            lines.append(
                f"- [{item.get('severity')}] {item.get('issue_type')}: {item.get('title')} | {item.get('detail')}"
            )
            if item.get("fix_hint"):
                lines.append(f"  修复建议: {item.get('fix_hint')}")

    revisions = report.get("suggested_revisions", [])
    if revisions:
        lines.extend(["", "## 建议修改"])
        for item in revisions:
            lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "## 快照",
            f"- original_problem: {snapshots.get('original_problem', {}).get('title', '')}",
            f"- difference_plan_rationale: {snapshots.get('difference_plan', {}).get('rationale', '')}",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
