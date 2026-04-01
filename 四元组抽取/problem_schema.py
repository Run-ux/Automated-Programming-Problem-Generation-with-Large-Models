from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


TOP_LEVEL_SECTION_NAMES = {
    "input": "input",
    "input format": "input",
    "output": "output",
    "output format": "output",
    "constraints": "constraints",
    "constraint": "constraints",
    "limits": "constraints",
}

TERMINAL_SECTION_NAMES = {
    "example",
    "examples",
    "sample",
    "sample input",
    "sample output",
    "note",
    "notes",
}

REQUIRED_RAW_FIELDS = [
    "problem_id",
    "title",
    "description",
    "source",
]


def load_problem_records(input_path: Path) -> list[dict[str, Any]]:
    if input_path.is_dir():
        problem_files = [
            path
            for path in sorted(input_path.glob("*.json"))
            if path.name.lower() != "manifest.json"
        ]
    else:
        problem_files = [input_path]

    if not problem_files:
        raise FileNotFoundError(f"未找到可用的题目 JSON 文件：{input_path}")

    problems: list[dict[str, Any]] = []
    for problem_file in problem_files:
        raw = json.loads(problem_file.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(
                f"输入文件必须是单题 JSON 对象，不再接受数组样本文件：{problem_file}"
            )
        problems.append(prepare_problem_record(raw, source_path=problem_file))
    return problems


def prepare_problem_record(
    problem: dict[str, Any],
    source_path: Path | None = None,
) -> dict[str, Any]:
    if _looks_prepared(problem):
        prepared = dict(problem)
        if source_path is not None and "schema_path" not in prepared:
            prepared["schema_path"] = str(source_path)
        return prepared

    _validate_raw_problem(problem, source_path)

    parsed_sections = split_statement_sections(str(problem.get("description", "")))
    prepared = dict(problem)

    prepared["source"] = extract_source(problem)
    prepared["title"] = str(problem.get("title", "")).strip()
    prepared["description"] = str(problem.get("description", "")).strip()
    prepared["input"] = parsed_sections["input"]
    prepared["output"] = parsed_sections["output"]
    prepared["constraints"] = _merge_constraints(
        parsed_sections["constraints"],
        problem.get("limits"),
    )

    solution_code = extract_reference_solution_code(problem)
    if solution_code:
        prepared["standard_solution_code"] = solution_code

    if source_path is not None:
        prepared["schema_path"] = str(source_path)

    return prepared


def extract_source(problem: dict[str, Any]) -> str:
    value = problem.get("source")
    if not isinstance(value, dict):
        raise ValueError("source 字段必须是对象，且包含 source_name")

    source_name = value.get("source_name")
    if not isinstance(source_name, str) or not source_name.strip():
        raise ValueError("source.source_name 缺失或为空")
    return source_name.strip().lower()


def extract_reference_solution_code(problem: dict[str, Any]) -> str:
    reference_solution = problem.get("reference_solution")
    if not isinstance(reference_solution, dict):
        return ""

    code = reference_solution.get("code")
    if isinstance(code, str) and code.strip():
        return code.strip()
    return ""


def split_statement_sections(statement: str) -> dict[str, str]:
    normalized = statement.replace("\r\n", "\n").replace("\r", "\n").strip()
    sections = {
        "description": [],
        "input": [],
        "output": [],
        "constraints": [],
    }
    if not normalized:
        return {key: "" for key in sections}

    current_section = "description"
    for raw_line in normalized.split("\n"):
        heading = _parse_section_heading(raw_line)
        if heading in TERMINAL_SECTION_NAMES:
            break
        if heading in TOP_LEVEL_SECTION_NAMES:
            current_section = TOP_LEVEL_SECTION_NAMES[heading]
            continue
        sections[current_section].append(raw_line)

    return {
        key: "\n".join(lines).strip()
        for key, lines in sections.items()
    }


def _validate_raw_problem(problem: dict[str, Any], source_path: Path | None) -> None:
    missing_fields = [field for field in REQUIRED_RAW_FIELDS if field not in problem]
    if missing_fields:
        location = str(source_path) if source_path is not None else "<memory>"
        raise ValueError(f"题目 JSON 缺少必要字段 {missing_fields}: {location}")

    if not isinstance(problem.get("description"), str):
        raise ValueError("description 字段必须是字符串")
    if not isinstance(problem.get("title"), str):
        raise ValueError("title 字段必须是字符串")


def _looks_prepared(problem: dict[str, Any]) -> bool:
    source = problem.get("source")
    return (
        isinstance(source, str)
        and all(key in problem for key in ["input", "output", "constraints"])
    )


def _parse_section_heading(line: str) -> str:
    compact = re.sub(r"\s+", " ", line.strip().rstrip(":"))
    return compact.lower()


def _pick_first_non_empty(*values: str) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _merge_constraints(
    parsed_constraints: str,
    limits: Any,
) -> str:
    parts: list[str] = []
    cleaned_constraints = parsed_constraints.strip()
    if cleaned_constraints:
        parts.append(cleaned_constraints)

    limits_text = _format_limits(limits)
    if limits_text:
        parts.append(limits_text)

    return "\n\n".join(parts)


def _format_limits(limits: Any) -> str:
    if not isinstance(limits, dict):
        return ""

    lines: list[str] = []
    time_limit = limits.get("time_limit")
    memory_limit_bytes = limits.get("memory_limit_bytes")

    if isinstance(time_limit, dict):
        seconds = time_limit.get("seconds")
        nanos = time_limit.get("nanos")
        if isinstance(seconds, int):
            if isinstance(nanos, int) and nanos:
                lines.append(f"time limit: {seconds + nanos / 1_000_000_000:.3f}s")
            else:
                lines.append(f"time limit: {seconds}s")

    if isinstance(memory_limit_bytes, int):
        memory_mb = memory_limit_bytes / (1024 * 1024)
        if memory_mb.is_integer():
            lines.append(f"memory limit: {int(memory_mb)} MB")
        else:
            lines.append(f"memory limit: {memory_mb:.1f} MB")

    return "\n".join(lines)
