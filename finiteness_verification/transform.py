from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, TYPE_CHECKING

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from .problem_repository import ProblemRepository
from .prompts import prompt_transform_space
from 生成题面.transform_space_tools import expand_transform_space

if TYPE_CHECKING:
    from .qwen_client import QwenClient


LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"


def setup_logging() -> logging.Logger:
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, stream=sys.stdout)
    return logging.getLogger(__name__)


def build_schema_context(schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "input_structure": schema.get("input_structure", {}),
        "core_constraints": schema.get("core_constraints", {}),
        "objective": schema.get("objective", {}),
        "invariant": schema.get("invariant", {}),
    }


def extract_transform_space(
    client: QwenClient,
    problem: dict[str, Any],
    schema: dict[str, Any],
) -> dict[str, Any]:
    system_prompt = prompt_transform_space.build_system_prompt()
    user_prompt = prompt_transform_space.build_user_prompt(
        problem=problem,
        schema=build_schema_context(schema),
    )
    request_label = schema.get("problem_id") or problem.get("problem_id") or "unknown"
    return client.chat_json(
        system_prompt,
        user_prompt,
        temperature=0.1,
        request_label=request_label,
    )


def enrich_schema_with_transform_space(
    schema: dict[str, Any],
    problem: dict[str, Any],
    client: QwenClient,
) -> dict[str, Any]:
    enriched = dict(schema)
    enriched["transform_space"] = extract_transform_space(client, problem, schema)
    return upgrade_schema_transform_space(enriched)


def upgrade_schema_transform_space(schema: dict[str, Any]) -> dict[str, Any]:
    upgraded = dict(schema)
    upgraded["transform_space"] = expand_transform_space(schema)
    return upgraded


def process_directory(
    input_dir: Path,
    output_dir: Path,
    repository: ProblemRepository,
    client: QwenClient,
    overwrite: bool,
    logger: logging.Logger,
    problem_ids: list[str] | None = None,
    reset_failures: bool = False,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    failure_dir = output_dir / "_failures"
    failure_dir.mkdir(parents=True, exist_ok=True)
    if reset_failures:
        cleared = 0
        for path in failure_dir.glob("*.json"):
            path.unlink()
            cleared += 1
        logger.info("已清空旧失败记录: %d", cleared)
    schema_files = sorted(input_dir.glob("*.json"))
    if problem_ids:
        wanted = set(problem_ids)
        schema_files = [path for path in schema_files if path.stem in wanted]

    logger.info("待处理 schema 数量: %d", len(schema_files))
    success_count = 0
    failure_count = 0
    for schema_file in schema_files:
        data = json.loads(schema_file.read_text(encoding="utf-8"))
        problem_id = data.get("problem_id", schema_file.stem)
        source = data.get("source", "")
        output_file = output_dir / schema_file.name
        failure_file = failure_dir / f"{problem_id}.json"

        if output_file.exists() and not overwrite:
            logger.info("跳过已存在文件: %s", output_file.name)
            continue

        if data.get("transform_space"):
            logger.info("已存在 transform_space，执行兼容升级后复制: %s", problem_id)
            upgraded = upgrade_schema_transform_space(data)
            output_file.write_text(
                json.dumps(upgraded, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            if failure_file.exists():
                failure_file.unlink()
            success_count += 1
            continue

        try:
            logger.info("生成 transform_space: %s", problem_id)
            problem = repository.get_problem(source=source, problem_id=problem_id)
            enriched = enrich_schema_with_transform_space(data, problem, client)
            output_file.write_text(
                json.dumps(enriched, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            if failure_file.exists():
                failure_file.unlink()
            success_count += 1
        except Exception as exc:
            failure_count += 1
            logger.exception("生成失败: %s", problem_id)
            _write_failure_artifact(
                failure_dir=failure_dir,
                problem_id=problem_id,
                source=source,
                schema=data,
                error=exc,
            )

    logger.info("处理完成: 成功 %d, 失败 %d", success_count, failure_count)


def load_problem_ids_from_failure_dir(failure_dir: Path) -> list[str]:
    if not failure_dir.exists():
        raise FileNotFoundError(f"失败目录不存在: {failure_dir}")

    problem_ids: list[str] = []
    for path in sorted(failure_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            problem_ids.append(path.stem)
            continue
        problem_id = data.get("problem_id") or path.stem
        problem_ids.append(problem_id)
    return sorted(set(problem_ids))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="为四维 Schema 补全 transform_space")
    parser.add_argument(
        "--input",
        required=True,
        help="输入 schema 目录，例如 finiteness_verification/output/pilot/voted",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="输出目录，写入补全 transform_space 后的 schema",
    )
    parser.add_argument(
        "--problem-ids",
        nargs="*",
        default=[],
        help="只处理指定的 problem id",
    )
    parser.add_argument(
        "--index-root",
        default="爬取题目/output",
        help="原题索引根目录，目录下应包含 codeforces/index.json 等文件",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="覆盖已存在的输出文件",
    )
    parser.add_argument(
        "--retry-failures-from",
        default=None,
        help="只重跑指定 _failures 目录中的题目，例如 output/phase1/voted_with_transform/_failures",
    )
    parser.add_argument(
        "--reset-failures",
        action="store_true",
        help="运行前清空输出目录下已有的 _failures 记录，便于只保留本轮失败项",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    logger = setup_logging()

    input_dir = Path(args.input)
    output_dir = Path(args.output)
    if not input_dir.exists():
        logger.error("输入目录不存在: %s", input_dir)
        raise SystemExit(1)

    retry_problem_ids: list[str] | None = None
    if args.retry_failures_from:
        retry_problem_ids = load_problem_ids_from_failure_dir(
            Path(args.retry_failures_from)
        )
        logger.info("从失败目录读取到 %d 个待重跑题目", len(retry_problem_ids))

    from .qwen_client import QwenClient

    repository = ProblemRepository(index_root=Path(args.index_root))
    client = QwenClient()

    selected_problem_ids: list[str] | None = None
    if args.problem_ids and retry_problem_ids is not None:
        selected_problem_ids = sorted(set(args.problem_ids) & set(retry_problem_ids))
    elif args.problem_ids:
        selected_problem_ids = args.problem_ids
    elif retry_problem_ids is not None:
        selected_problem_ids = retry_problem_ids

    process_directory(
        input_dir=input_dir,
        output_dir=output_dir,
        repository=repository,
        client=client,
        overwrite=args.overwrite,
        logger=logger,
        problem_ids=selected_problem_ids,
        reset_failures=args.reset_failures,
    )
    logger.info("transform_space 补全完成，输出目录: %s", output_dir)


def _write_failure_artifact(
    failure_dir: Path,
    problem_id: str,
    source: str,
    schema: dict[str, Any],
    error: Exception,
) -> None:
    raw_text = getattr(error, "raw_text", "")
    payload = {
        "problem_id": problem_id,
        "source": source,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "raw_response": raw_text,
        "schema_context": build_schema_context(schema),
    }
    (failure_dir / f"{problem_id}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
