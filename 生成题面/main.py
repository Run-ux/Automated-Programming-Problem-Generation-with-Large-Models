from __future__ import annotations

import argparse
from pathlib import Path

from config import (
    DEFAULT_API_KEY,
    DEFAULT_ARTIFACT_DIR,
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PREPARED_SCHEMA_DIR,
    DEFAULT_REPORT_DIR,
    DEFAULT_SOURCE_DIR,
    DEFAULT_TEMPERATURE,
    DEFAULT_VARIANTS,
)
from pipeline import GenerationPipeline
from problem_generator import ProblemGenerator
from qwen_client import QwenClient
from schema_preparer import SchemaPreparer
from variant_planner import THEMES, VariantPlanner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="基于 Problem Schema 生成算法竞赛题面")
    parser.add_argument("--problem-ids", nargs="*", default=[], help="待生成的 problem id")
    parser.add_argument("--variants", type=int, default=DEFAULT_VARIANTS, help="每题生成多少个变体")
    parser.add_argument("--theme", choices=[theme.theme_id for theme in THEMES], help="固定主题")
    parser.add_argument("--source-dir", default=str(DEFAULT_SOURCE_DIR), help="Schema JSON 目录")
    parser.add_argument(
        "--prepared-schema-dir",
        default=str(DEFAULT_PREPARED_SCHEMA_DIR),
        help="补全 transform_space 后的 schema 缓存目录",
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Markdown 输出目录")
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR), help="结构化产物目录")
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR), help="过程说明 Markdown 输出目录")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Qwen 模型名")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="兼容 OpenAI 的 API Base URL")
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE, help="采样温度")
    parser.add_argument("--seed", type=int, default=20260312, help="随机种子")
    parser.add_argument(
        "--skip-transform-enrich",
        action="store_true",
        help="缺少 transform_space 时不自动补全，直接报错",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    client = QwenClient(
        api_key=DEFAULT_API_KEY,
        model=args.model,
        base_url=args.base_url,
    )

    prepared_source_dir = SchemaPreparer(
        source_dir=Path(args.source_dir),
        cache_dir=Path(args.prepared_schema_dir),
    ).prepare(
        problem_ids=args.problem_ids,
        allow_llm_enrich=not args.skip_transform_enrich,
    )

    pipeline = GenerationPipeline(
        raw_source_dir=Path(args.source_dir),
        source_dir=prepared_source_dir,
        output_dir=Path(args.output_dir),
        artifact_dir=Path(args.artifact_dir),
        report_dir=Path(args.report_dir),
        generator=ProblemGenerator(client=client, temperature=args.temperature),
        planner=VariantPlanner(seed=args.seed),
    )

    pipeline.run(
        problem_ids=args.problem_ids,
        variants=args.variants,
        theme_id=args.theme,
    )


if __name__ == "__main__":
    main()
