from __future__ import annotations

import argparse
from pathlib import Path

from config import (
    DEFAULT_API_KEY,
    DEFAULT_BASE_URL,
    DEFAULT_KILL_RATE_THRESHOLD,
    DEFAULT_MODEL,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_REVISION_ADVISOR_API_KEY,
    DEFAULT_REVISION_ADVISOR_BASE_URL,
    DEFAULT_REVISION_ADVISOR_MODEL,
    DEFAULT_REVISION_ADVISOR_TIMEOUT_S,
    DEFAULT_ROUNDS,
    DEFAULT_STANDARD_GENERATION_TIMEOUT_S,
    DEFAULT_TIMEOUT_S,
    DEFAULT_TOOL_GENERATION_TIMEOUT_S,
)
from generators import RevisionAdvisor, StandardSolutionGenerator, ToolGenerator
from llm_client import LlmClient
from pipeline import PackageValidationPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="测试用例与标准解法共迭代题包生成验证。")
    parser.add_argument("--artifact", required=True, type=Path, help="生成题面的 artifact JSON 路径。")
    parser.add_argument("--markdown", type=Path, help="生成题面的 Markdown 题面路径。")
    parser.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS, help="最多迭代轮数。")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="题包生成验证输出目录。")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="LLM 模型名称。")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="兼容 OpenAI 的接口地址。")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S, help="LLM 请求超时秒数。")
    parser.add_argument(
        "--standard-timeout",
        type=int,
        default=DEFAULT_STANDARD_GENERATION_TIMEOUT_S,
        help="标准解生成请求超时秒数。",
    )
    parser.add_argument(
        "--tool-timeout",
        type=int,
        default=DEFAULT_TOOL_GENERATION_TIMEOUT_S,
        help="validator/checker/test_generator 生成请求超时秒数。",
    )
    parser.add_argument("--revision-advisor-model", default=DEFAULT_REVISION_ADVISOR_MODEL, help="RevisionAdvisor 使用的 LLM 模型名称。")
    parser.add_argument("--revision-advisor-base-url", default=DEFAULT_REVISION_ADVISOR_BASE_URL, help="RevisionAdvisor 使用的兼容 OpenAI 接口地址。")
    parser.add_argument("--revision-advisor-timeout", type=int, default=DEFAULT_REVISION_ADVISOR_TIMEOUT_S, help="RevisionAdvisor 请求超时秒数。")
    parser.add_argument("--kill-rate-threshold", type=float, default=DEFAULT_KILL_RATE_THRESHOLD, help="错误解杀伤率阈值。")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.rounds < 1:
        parser.error("--rounds 必须至少为 1。")
    if not args.artifact.exists():
        parser.error(f"--artifact 不存在：{args.artifact}")
    if args.markdown and not args.markdown.exists():
        parser.error(f"--markdown 不存在：{args.markdown}")

    client = LlmClient(
        api_key=DEFAULT_API_KEY or "",
        model=args.model,
        base_url=args.base_url,
        timeout_s=args.timeout,
    )
    advisor_client = LlmClient(
        api_key=DEFAULT_REVISION_ADVISOR_API_KEY or "",
        model=args.revision_advisor_model,
        base_url=args.revision_advisor_base_url,
        timeout_s=args.revision_advisor_timeout,
    )
    pipeline = PackageValidationPipeline(
        client=client,
        output_dir=args.output_dir,
        kill_rate_threshold=args.kill_rate_threshold,
        standard_generator=StandardSolutionGenerator(client, timeout_s=args.standard_timeout),
        tool_generator=ToolGenerator(client, timeout_s=args.tool_timeout),
        revision_advisor=RevisionAdvisor(advisor_client),
    )
    result = pipeline.run(
        artifact_path=args.artifact,
        markdown_path=args.markdown,
        rounds=args.rounds,
    )
    print(f"题包生成验证完成：{result['run_dir']}")
    print(f"迭代摘要：{result['summary_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
