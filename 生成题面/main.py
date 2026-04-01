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
    DEFAULT_RULE_FILE,
    DEFAULT_SOURCE_DIR,
    DEFAULT_TEMPERATURE,
    DEFAULT_VARIANTS,
)
from pipeline import GenerationPipeline
from problem_generator import ProblemGenerator
from qwen_client import QwenClient
from rulebook import RuleBook, normalize_rule_id
from schema_preparer import SchemaPreparer
from variant_planner import THEMES, VariantPlanner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="基于规则与四元组生成算法竞赛题面")
    parser.add_argument(
        "--mode",
        choices=["single", "same_family"],
        required=True,
        help="运行模式：single 对应 single_seed_extension，same_family 对应 same_family_fusion",
    )
    parser.add_argument("--problem-ids", nargs="*", default=[], help="single 模式下待生成的 problem id")
    parser.add_argument("--seed-a", help="same_family 模式下的第一个种子题 problem id")
    parser.add_argument("--seed-b", help="same_family 模式下的第二个种子题 problem id")
    parser.add_argument("--variants", type=int, default=DEFAULT_VARIANTS, help="每次运行生成多少个变体")
    parser.add_argument("--theme", choices=[theme.theme_id for theme in THEMES], help="固定主题")
    parser.add_argument("--source-dir", default=str(DEFAULT_SOURCE_DIR), help="Schema JSON 目录")
    parser.add_argument(
        "--prepared-schema-dir",
        default=str(DEFAULT_PREPARED_SCHEMA_DIR),
        help="归一化后的 schema 缓存目录",
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Markdown 输出目录")
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR), help="结构化产物目录")
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR), help="过程说明 Markdown 输出目录")
    parser.add_argument("--rule-file", default=str(DEFAULT_RULE_FILE), help="规则 JSON 文件")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Qwen 模型名")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="兼容 OpenAI 的 API Base URL")
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE, help="采样温度")
    parser.add_argument("--seed", type=int, default=20260312, help="随机种子")
    parser.add_argument(
        "--rule-override",
        action="append",
        default=[],
        help="可选规则覆盖，只允许候选集中使用指定 rule id。可重复传入，也可用逗号分隔。",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    _validate_args(parser, args)

    client = QwenClient(
        api_key=DEFAULT_API_KEY,
        model=args.model,
        base_url=args.base_url,
    )
    rulebook = RuleBook.load(args.rule_file)

    prepared_source_dir = SchemaPreparer(
        source_dir=Path(args.source_dir),
        cache_dir=Path(args.prepared_schema_dir),
    ).prepare(
        problem_ids=_target_problem_ids(args),
    )

    pipeline = GenerationPipeline(
        raw_source_dir=Path(args.source_dir),
        source_dir=prepared_source_dir,
        output_dir=Path(args.output_dir),
        artifact_dir=Path(args.artifact_dir),
        report_dir=Path(args.report_dir),
        generator=ProblemGenerator(client=client, temperature=args.temperature),
        planner=VariantPlanner(client=client, rulebook=rulebook, seed=args.seed),
    )

    pipeline.run(
        mode=args.mode,
        problem_ids=args.problem_ids,
        variants=args.variants,
        theme_id=args.theme,
        seed_a=args.seed_a,
        seed_b=args.seed_b,
        allowed_rule_ids=_normalize_rule_overrides(args.rule_override),
    )


def _validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.mode == "single":
        if args.seed_a or args.seed_b:
            parser.error("single 模式不接受 --seed-a 或 --seed-b。")
        return

    if not args.seed_a or not args.seed_b:
        parser.error("same_family 模式必须同时提供 --seed-a 与 --seed-b。")
    if args.problem_ids:
        parser.error("same_family 模式不使用 --problem-ids。")


def _target_problem_ids(args: argparse.Namespace) -> list[str]:
    if args.mode == "same_family":
        return [str(args.seed_a), str(args.seed_b)]
    return list(args.problem_ids)


def _normalize_rule_overrides(values: list[str]) -> set[str] | None:
    normalized: list[str] = []
    for raw in values:
        for item in str(raw).split(","):
            token = normalize_rule_id(item)
            if token and token not in normalized:
                normalized.append(token)
    return set(normalized) if normalized else None


if __name__ == "__main__":
    main()
