from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

from .normalize import normalize_problem
from .pdf_extract import extract_pdf_text_by_page, split_into_raw_problems
from .qwen_client import QwenClient, QwenConfig
from .schema_extract import extract_schema_for_problem


@dataclass
class PipelineConfig:
    pdf_path: Path
    out_root: Path
    schema_def_path: Path

    # PDF 分题规则（可按题集格式调整）
    problem_regexes: Optional[List[str]] = None

    # 千问模型配置（建议放 .env）
    model: str = "qwen-max"
    base_url: str | None = None
    api_key: str | None = None

    # 运行阶段开关
    run_extract: bool = True
    run_schema: bool = True


def run_pipeline(cfg: PipelineConfig) -> None:
    # 允许用 .env 配置 base_url / key / model（即使 VS Code 终端注入关闭也能生效）
    load_dotenv()

    problems_dir = cfg.out_root / "problems"
    schemas_dir = cfg.out_root / "schemas"
    problems_dir.mkdir(parents=True, exist_ok=True)
    schemas_dir.mkdir(parents=True, exist_ok=True)

    schema_def_md = cfg.schema_def_path.read_text(encoding="utf-8")

    # 1) PDF -> 标准化题面
    problems = []
    if cfg.run_extract:
        pages_text = extract_pdf_text_by_page(cfg.pdf_path)
        raw = split_into_raw_problems(pages_text, problem_regexes=cfg.problem_regexes)

        for rp in raw:
            problems.append(normalize_problem(rp, source_pdf=str(cfg.pdf_path)))

        import json

        index = []
        for p in problems:
            md_path = problems_dir / f"{p.problem_id}.md"
            md = (
                f"# {p.title}\n\n"
                f"## Description\n{p.description}\n\n"
                f"## Input\n{p.input}\n\n"
                f"## Output\n{p.output}\n\n"
                f"## Constraints\n{p.constraints}\n"
            )
            md_path.write_text(md, encoding="utf-8")
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
        print(f"提取完成：{len(problems)} 题，输出目录：{problems_dir}")

    # 2) 标准化题面 -> schema
    if cfg.run_schema:
        client = QwenClient(QwenConfig(model=cfg.model, base_url=cfg.base_url, api_key=cfg.api_key))

        import json

        index = []
        if not problems:
            # 如果未运行 extract，则从磁盘读取 problems/*.md
            from .schema_extract import load_problem_md

            md_files = sorted(problems_dir.glob("*.md"))
            md_files = [p for p in md_files if p.name.lower() != "readme.md"]
            for md_path in md_files:
                problem = load_problem_md(md_path)
                data = extract_schema_for_problem(client, schema_def_md, problem)
                out_path = schemas_dir / f"{problem.problem_id}.json"
                out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                index.append({"problem_id": problem.problem_id, "schema": str(out_path.as_posix())})
                print(f"schema完成：{problem.problem_id}")
        else:
            for problem in problems:
                data = extract_schema_for_problem(client, schema_def_md, problem)
                out_path = schemas_dir / f"{problem.problem_id}.json"
                out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                index.append({"problem_id": problem.problem_id, "schema": str(out_path.as_posix())})
                print(f"schema完成：{problem.problem_id}")

        (schemas_dir / "index.json").write_text(
            json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"schema提取完成：{len(index)} 题，输出目录：{schemas_dir}")
