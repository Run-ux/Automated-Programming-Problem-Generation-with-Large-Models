from __future__ import annotations

from typing import Any


def render_execution_report_markdown(report: dict[str, Any]) -> str:
    overall = report.get("overall", {})
    wrong_stats = report.get("wrong_solution_stats", {})
    base_consistency = report.get("base_consistency", {})
    kill_rate_text = (
        "不可用"
        if wrong_stats.get("valid") is False
        else str(wrong_stats.get("kill_rate", 0))
    )
    lines = [
        "# 题包生成验证报告",
        "",
        "## 总览",
        "",
        f"- 状态：{overall.get('status', 'unknown')}",
        f"- 失败原因：{overall.get('stop_reason', '') or '无'}",
        f"- 问题数量：{overall.get('issue_count', 0)}",
        f"- 基础自洽：{'通过' if base_consistency.get('passed') else '未通过'}",
        f"- 错误解杀伤率：{kill_rate_text}",
        "",
        "## 问题列表",
        "",
    ]
    issues = report.get("issues", [])
    if not issues:
        lines.append("- 无")
    for issue in issues:
        lines.extend(
            [
                f"- [{issue.get('severity', '')}] {issue.get('category', '')}：{issue.get('title', '')}",
                f"  详情：{issue.get('detail', '')}",
                f"  修复建议：{issue.get('fix_hint', '') or '无'}",
            ]
        )
    lines.extend(["", "## 回流摘要", ""])
    revision = report.get("revision_context", {})
    for key, value in revision.items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines).rstrip() + "\n"
