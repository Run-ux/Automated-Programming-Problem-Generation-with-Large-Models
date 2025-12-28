from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import List

from dotenv import load_dotenv

from .models import ProblemText
from .normalize import normalize_problem
from .pdf_extract import extract_pdf_text_by_page, split_into_raw_problems
from .qwen_client import QwenClient, QwenConfig
from .schema_extract import extract_schema_for_problem, load_problem_md


def _write_problem_md(problem: ProblemText, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"{problem.problem_id}.md"
    md = (
        f"# {problem.title}\n\n"
        f"## Description\n{problem.description}\n\n"
        f"## Input\n{problem.input}\n\n"
        f"## Output\n{problem.output}\n\n"
        f"## Constraints\n{problem.constraints}\n"
    )
    p.write_text(md, encoding="utf-8")
    return p


def cmd_extract(args: argparse.Namespace) -> int:
    pdf_path = Path(args.pdf)
    out_root = Path(args.out)
    problems_dir = out_root / "problems"
    problems_dir.mkdir(parents=True, exist_ok=True)

    regexes: List[str] | None = None
    if args.problem_regex:
        regexes = [args.problem_regex]
    elif args.problem_regexes:
        regexes = args.problem_regexes

    pages_text = extract_pdf_text_by_page(pdf_path)
    raw = split_into_raw_problems(pages_text, problem_regexes=regexes)

    normalized: List[ProblemText] = []
    for rp in raw:
        normalized.append(normalize_problem(rp, source_pdf=str(pdf_path)))

    index = []
    for p in normalized:
        md_path = _write_problem_md(p, problems_dir)
        index.append(
            {
                "problem_id": p.problem_id,
                "title": p.title,
                "file": str(md_path.as_posix()),
                "pages": p.pages,
            }
        )

    (problems_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"提取完成：{len(normalized)} 题，输出目录：{problems_dir}")
    if len(normalized) == 0:
        print("未识别到题目。建议调整 --problem-regex / --problem-regexes。")
    return 0


def cmd_schema(args: argparse.Namespace) -> int:
    problems_dir = Path(args.problems)
    out_root = Path(args.out)
    schemas_dir = out_root / "schemas"
    schemas_dir.mkdir(parents=True, exist_ok=True)

    schema_def_path = Path(args.schema_def)
    schema_def_md = schema_def_path.read_text(encoding="utf-8")

    client = QwenClient(QwenConfig(model=args.model, base_url=args.base_url, api_key=args.api_key))

    md_files = sorted(problems_dir.glob("*.md"))
    md_files = [p for p in md_files if p.name.lower() != "readme.md"]

    index = []
    for md_path in md_files:
        problem = load_problem_md(md_path)
        data = extract_schema_for_problem(client, schema_def_md, problem)

        out_path = schemas_dir / f"{problem.problem_id}.json"
        out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        index.append({"problem_id": problem.problem_id, "schema": str(out_path.as_posix())})
        print(f"schema完成：{problem.problem_id}")

    (schemas_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"schema提取完成：{len(index)} 题，输出目录：{schemas_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="icpc_schema_extractor")
    sub = p.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("extract", help="从PDF提取并标准化题面")
    p1.add_argument("--pdf", required=True, help="ICPC题集PDF路径")
    p1.add_argument("--out", required=True, help="输出根目录")
    p1.add_argument(
        "--problem-regex",
        default=None,
        help=(
            "单个题目标题识别正则（覆盖默认）。必须包含两个分组：(题号字母)(题目标题)"
        ),
    )
    p1.add_argument(
        "--problem-regexes",
        nargs="+",
        default=None,
        help="多个题目标题识别正则（按顺序尝试）",
    )
    p1.set_defaults(func=cmd_extract)

    p2 = sub.add_parser("schema", help="对标准化题面调用千问提取schema")
    p2.add_argument("--problems", required=True, help="problems目录（包含 A.md 等）")
    p2.add_argument("--schema-def", required=True, help="五元组定义md路径")
    p2.add_argument("--out", required=True, help="输出根目录")
    p2.add_argument("--model", default="qwen-max", help="模型名")
    p2.add_argument("--base-url", default=None, help="OpenAI兼容base_url，默认DashScope兼容端")
    p2.add_argument("--api-key", default=None, help="API Key（也可用环境变量）")
    p2.set_defaults(func=cmd_schema)

    return p


def main() -> int:
    # 自动加载工作区根目录的 .env（如果存在）
    load_dotenv()

    parser = build_parser()
    args = parser.parse_args()

    # 轻量校验：自定义正则至少要有两个捕获组
    if getattr(args, "problem_regex", None):
        try:
            c = re.compile(args.problem_regex)
            if c.groups < 2:
                raise ValueError
        except Exception as e:  # noqa: BLE001
            raise SystemExit(f"--problem-regex 无效（需要>=2个捕获组）：{e}")

    return int(args.func(args))
