from __future__ import annotations

from models import GeneratedProblem, VariantPlan


def render_problem_markdown(problem: GeneratedProblem, plan: VariantPlan) -> str:
    if problem.status != "ok":
        return _render_generation_failure(problem, plan)

    lines: list[str] = [
        f"# {problem.title}",
        "",
        f"> Variant: `{plan.problem_id}` / `v{plan.variant_index}` / theme `{plan.theme.theme_id}`",
        "",
        "## 题目描述",
        "",
        problem.description or "暂无描述。",
        "",
        "## 输入格式",
        "",
        problem.input_format or "暂无输入格式。",
        "",
        "## 输出格式",
        "",
        problem.output_format or "暂无输出格式。",
        "",
        "## 数据范围与限制",
        "",
    ]

    constraints = problem.constraints or ["Time Limit: 1 second", "Memory Limit: 256 megabytes"]
    for item in constraints:
        lines.append(f"- {item}")

    if problem.samples:
        lines.extend(["", "## 样例"])
        for index, sample in enumerate(problem.samples, start=1):
            lines.extend(
                [
                    "",
                    f"### 样例 {index}",
                    "",
                    "**输入**",
                    "",
                    "```text",
                    sample.get("input", ""),
                    "```",
                    "",
                    "**输出**",
                    "",
                    "```text",
                    sample.get("output", ""),
                    "```",
                ]
            )
            explanation = sample.get("explanation", "")
            if explanation:
                lines.extend(["", "**说明**", "", explanation])

    if problem.notes:
        lines.extend(["", "## 说明", "", problem.notes])

    return "\n".join(lines).rstrip() + "\n"


def _render_generation_failure(problem: GeneratedProblem, plan: VariantPlan) -> str:
    return (
        f"# {plan.problem_id} / v{plan.variant_index}\n\n"
        f"> 状态：`{problem.status}`\n\n"
        "## 生成中止原因\n\n"
        f"{problem.error_reason or '未提供具体原因。'}\n\n"
        "## 反馈\n\n"
        f"{problem.feedback or '无'}\n"
    )
