from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from config import (
    DEFAULT_API_KEY,
    DEFAULT_ARTIFACT_DIR,
    DEFAULT_BASE_URL,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_MODEL,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_REPORT_DIR,
    DEFAULT_RULE_FILE,
    DEFAULT_SOURCE_DIR,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT_S,
    DEFAULT_VARIANTS,
)
from pipeline import GenerationPipeline
from problem_generator import ProblemGenerator
from qwen_client import QwenClient
from rulebook import RuleBook, normalize_rule_id
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
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Markdown 输出目录")
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR), help="结构化产物目录")
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR), help="过程说明 Markdown 输出目录")
    parser.add_argument("--rule-file", default=str(DEFAULT_RULE_FILE), help="规则 JSON 文件")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S, help="模型接口请求超时秒数")
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE, help="采样温度")
    parser.add_argument("--seed", type=int, default=20260312, help="随机种子")
    parser.add_argument(
        "--quality-iterations",
        type=int,
        default=0,
        help="质量闭环迭代轮数，可选 0、1、2、3；0 表示关闭质量回流。",
    )
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
    _emit_progress("[main] 开始校验命令行参数。")
    _validate_args(parser, args)
    target_problem_ids = _target_problem_ids(args)
    batch_source_dir = Path(args.source_dir) if _is_batch_run(args) else None
    _emit_progress(
        f"[main] 参数校验完成；mode={args.mode}；target_problem_count={len(target_problem_ids)}。"
    )

    _emit_progress("[main] 初始化模型客户端与规则文件。")
    client = QwenClient(
        api_key=DEFAULT_API_KEY,
        model=DEFAULT_MODEL,
        base_url=DEFAULT_BASE_URL,
        timeout_s=args.timeout,
        embedding_model=DEFAULT_EMBEDDING_MODEL,
    )
    rulebook = RuleBook.load(args.rule_file)

    pipeline = GenerationPipeline(
        source_dir=Path(args.source_dir),
        output_dir=Path(args.output_dir),
        artifact_dir=Path(args.artifact_dir),
        report_dir=Path(args.report_dir),
        generator=ProblemGenerator(client=client, temperature=args.temperature),
        planner=VariantPlanner(client=client, rulebook=rulebook, seed=args.seed),
        progress_writer=_emit_progress,
    )

    _emit_progress("[main] 进入生成流水线。")
    pipeline.run(
        mode=args.mode,
        problem_ids=target_problem_ids,
        variants=args.variants,
        theme_id=args.theme,
        seed_a=args.seed_a,
        seed_b=args.seed_b,
        allowed_rule_ids=_normalize_rule_overrides(args.rule_override),
        batch_source_dir=batch_source_dir,
        quality_iterations=args.quality_iterations,
    )
    _emit_progress("[main] 流水线执行完成。")


def _validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.timeout <= 0:
        parser.error("--timeout 必须是正整数。")
    if args.quality_iterations not in {0, 1, 2, 3}:
        parser.error("--quality-iterations 只支持 0、1、2、3。")
    if args.mode == "single":
        if args.seed_a or args.seed_b:
            parser.error("single 模式不接受 --seed-a 或 --seed-b。")
        if _is_batch_run(args):
            try:
                _load_batch_problem_ids(Path(args.source_dir))
            except ValueError as exc:
                parser.error(str(exc))
        return

    if not args.seed_a or not args.seed_b:
        parser.error("same_family 模式必须同时提供 --seed-a 与 --seed-b。")
    if args.problem_ids:
        parser.error("same_family 模式不使用 --problem-ids。")
    if args.quality_iterations:
        parser.error("same_family 模式暂不支持质量闭环迭代。")


def _target_problem_ids(args: argparse.Namespace) -> list[str]:
    if args.mode == "same_family":
        return [str(args.seed_a), str(args.seed_b)]
    return _resolve_single_problem_ids(Path(args.source_dir), list(args.problem_ids))


def _is_batch_run(args: argparse.Namespace) -> bool:
    return args.mode == "single" and not args.problem_ids


def _resolve_single_problem_ids(source_dir: Path, explicit_problem_ids: list[str]) -> list[str]:
    if explicit_problem_ids:
        return list(explicit_problem_ids)
    return _load_batch_problem_ids(source_dir)


def _load_batch_problem_ids(source_dir: Path) -> list[str]:
    if not source_dir.exists():
        raise ValueError(f"批量模式下 source-dir 不存在：{source_dir}")
    if not source_dir.is_dir():
        raise ValueError(f"批量模式下 source-dir 不是目录：{source_dir}")

    schema_paths = sorted(source_dir.glob("*.json"))
    if not schema_paths:
        raise ValueError(f"批量模式下 source-dir 中没有 schema 文件：{source_dir}")

    problem_ids: list[str] = []
    for path in schema_paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"批量模式读取 schema 失败：{path}；{exc.msg}") from exc

        if not isinstance(payload, dict):
            raise ValueError(f"批量模式要求 schema 顶层是 JSON 对象：{path}")

        problem_id = str(payload.get("problem_id", "")).strip()
        if not problem_id:
            raise ValueError(f"批量模式要求每个 schema 文件显式提供 problem_id：{path}")
        if problem_id != path.stem:
            raise ValueError(
                "批量模式要求 schema 的 problem_id 与文件名一致："
                f"{path}；文件名={path.stem}；problem_id={problem_id}"
            )
        problem_ids.append(problem_id)
    return problem_ids


def _normalize_rule_overrides(values: list[str]) -> set[str] | None:
    normalized: list[str] = []
    for raw in values:
        for item in str(raw).split(","):
            token = normalize_rule_id(item)
            if token and token not in normalized:
                normalized.append(token)
    return set(normalized) if normalized else None


def _emit_progress(message: str) -> None:
    text = f"{message}\n"
    stream = sys.stdout
    encoding = getattr(stream, "encoding", None) or "utf-8"
    buffer = getattr(stream, "buffer", None)
    if buffer is not None:
        buffer.write(text.encode(encoding, errors="replace"))
        buffer.flush()
        return
    stream.write(text.encode(encoding, errors="replace").decode(encoding, errors="replace"))
    stream.flush()


if __name__ == "__main__":
    main()
