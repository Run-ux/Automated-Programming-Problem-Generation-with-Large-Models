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
        f"- 语义门禁：{overall.get('semantic_gate_status', 'not_evaluated')}",
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
    semantic_issues = report.get("semantic_gate_issues", [])
    if semantic_issues:
        lines.extend(["", "## 语义门禁", ""])
        for issue in semantic_issues:
            lines.append(f"- [{issue.get('severity', '')}] {issue.get('category', '')}：{issue.get('title', '')}")
    component_results = report.get("component_gate_results", {})
    if component_results:
        lines.extend(["", "## 组件晋级门禁", ""])
        for name, result in component_results.items():
            status = "通过" if result.get("passed") else "未通过"
            lines.append(f"- {name}: {status}")
    candidate_package_results = report.get("candidate_package_gate_results", {})
    if candidate_package_results:
        lines.extend(["", "## 候选包级门禁", ""])
        for name, result in candidate_package_results.items():
            status = "通过" if result.get("passed") else "未通过"
            reasons = result.get("rejection_reasons", [])
            reason_text = "；".join(str(item) for item in reasons) if reasons else "无"
            lines.append(f"- {name}: {status}，原因：{reason_text}")
    known_good = report.get("known_good_results", {})
    if known_good:
        lines.extend(
            [
                "",
                "## Known-good 用例",
                "",
                f"- 配置数量：{known_good.get('configured_count', 0)}",
                f"- 执行数量：{known_good.get('executed_count', 0)}",
                f"- 失败数量：{known_good.get('failed_count', 0)}",
            ]
        )
    regression = report.get("regression_results", {})
    if regression:
        lines.extend(
            [
                "",
                "## 回归反例",
                "",
                f"- 配置数量：{regression.get('configured_count', 0)}",
                f"- 执行数量：{regression.get('executed_count', 0)}",
            ]
        )
    lines.extend(["", "## 回流摘要", ""])
    revision = report.get("revision_context", {})
    for key, value in revision.items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines).rstrip() + "\n"
