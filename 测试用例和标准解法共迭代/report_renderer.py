from __future__ import annotations

from typing import Any


def render_execution_report_markdown(report: dict[str, Any]) -> str:
    overall = report.get("overall", {})
    lines = [
        "# 题包生成验证报告",
        "",
        "## 总览",
        "",
        f"- 状态：{overall.get('status', 'unknown')}",
        f"- 失败原因：{overall.get('stop_reason', '') or '无'}",
        f"- 问题数量：{overall.get('issue_count', 0)}",
        f"- 错误解杀伤率：{report.get('wrong_solution_stats', {}).get('kill_rate', 0)}",
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

