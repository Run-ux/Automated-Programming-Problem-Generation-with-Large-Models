from __future__ import annotations

import argparse
import json
from pathlib import Path

from problem_quality import ProblemEvaluator
from problem_quality.report_renderer import render_report_markdown


PROJECT_DIR = Path(__file__).resolve().parent
REPORTS_JSON_DIR = PROJECT_DIR / "reports" / "json"
REPORTS_MD_DIR = PROJECT_DIR / "reports" / "md"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="题目质量与反换皮评估器")
    parser.add_argument("--original-schema", required=True, help="原始 schema 路径")
    parser.add_argument("--prepared-schema", required=True, help="补全/变换空间 schema 路径")
    parser.add_argument("--artifact", required=True, help="生成题面的 artifact 路径")
    parser.add_argument("--markdown", help="生成题面的 Markdown 路径")
    parser.add_argument("--original-problem", help="可选：原题 JSON 覆盖路径")
    parser.add_argument("--output-json", help="评估报告 JSON 输出路径")
    parser.add_argument("--output-md", help="评估报告 Markdown 输出路径")
    parser.add_argument("--disable-llm", action="store_true", help="禁用 LLM Judge，改用启发式评估")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    evaluator = ProblemEvaluator(enable_llm=not args.disable_llm)
    report = evaluator.evaluate_problem(
        original_schema_path=args.original_schema,
        prepared_schema_path=args.prepared_schema,
        artifact_path=args.artifact,
        markdown_path=args.markdown,
        original_problem_override=args.original_problem,
    )

    artifact_path = Path(args.artifact)
    output_json = (
        Path(args.output_json)
        if args.output_json
        else REPORTS_JSON_DIR / f"{artifact_path.stem}_quality_report.json"
    )
    output_md = (
        Path(args.output_md)
        if args.output_md
        else REPORTS_MD_DIR / f"{artifact_path.stem}_quality_report.md"
    )

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)

    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    output_md.write_text(render_report_markdown(report), encoding="utf-8")

    print(f"[OK] JSON report saved to: {output_json}")
    print(f"[OK] Markdown report saved to: {output_md}")


if __name__ == "__main__":
    main()
