"""结构验证脚本：验证 Prompt 是否携带完整分节证据与新 schema 字段。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.insert(0, str(current_dir))

from label_vocab import (
    CONSTRAINT_SOURCE_SECTIONS,
    INPUT_STRUCTURE_TYPE_LABELS,
    INVARIANT_EVIDENCE_SOURCES,
    OBJECTIVE_LABELS,
)
from prompt_test_cases import CATEGORY_LABELS, select_problems_by_category
from prompts.prompt_constraints import (
    CONSTRAINTS_SCHEMA,
    build_system_prompt as build_c_system,
    build_user_prompt as build_c_user,
)
from prompts.prompt_input_structure import (
    INPUT_STRUCTURE_SCHEMA,
    build_system_prompt as build_i_system,
    build_user_prompt as build_i_user,
)
from prompts.prompt_invariant import (
    INVARIANT_SCHEMA,
    build_system_prompt as build_v_system,
    build_user_prompt as build_v_user,
)
from prompts.prompt_objective import (
    OBJECTIVE_SCHEMA,
    build_system_prompt as build_o_system,
    build_user_prompt as build_o_user,
)
from prompts.prompt_sections import EMPTY_SECTION_TEXT


def _assert_prompt_sections(user_prompt: str, problem: Dict[str, Any], include_code: bool) -> None:
    expected_sections = {
        "标题": problem.get("title", "").strip() or EMPTY_SECTION_TEXT,
        "题面全文": problem.get("description", "").strip() or EMPTY_SECTION_TEXT,
        "Input 分节": problem.get("input", "").strip() or EMPTY_SECTION_TEXT,
        "Output 分节": problem.get("output", "").strip() or EMPTY_SECTION_TEXT,
        "Constraints 分节": problem.get("constraints", "").strip() or EMPTY_SECTION_TEXT,
    }
    for title, expected_text in expected_sections.items():
        assert f"{title}：" in user_prompt, f"user_prompt 缺少 {title}"
        assert expected_text in user_prompt, f"user_prompt 缺少 {title} 对应内容"

    solution_code = problem.get("standard_solution_code", "")
    if include_code and isinstance(solution_code, str) and solution_code.strip():
        assert "标准解法代码：" in user_prompt, "invariant prompt 缺少标准解法代码分节"
        assert solution_code.strip() in user_prompt, "invariant prompt 缺少标准解法代码内容"


def _assert_system_prompt_sections(system_prompt: str) -> None:
    assert "科研定义：" in system_prompt, "system_prompt 缺少科研定义"
    assert "判别边界：" in system_prompt, "system_prompt 缺少判别边界"


def _assert_input_structure_schema(schema: Dict[str, Any]) -> None:
    assert schema.get("required") == ["type", "length", "value_range", "properties"]
    assert schema.get("additionalProperties") is True
    properties = schema["properties"]
    type_names = [name for name, _ in INPUT_STRUCTURE_TYPE_LABELS]
    assert "components" in properties
    assert properties["type"].get("enum") == type_names
    assert {"integer", "float", "char", "boolean", "tuple"}.issubset(set(type_names))
    assert properties["length"]["properties"]["min"]["type"] == ["integer", "null"]
    assert properties["value_range"]["properties"]["max"]["type"] == ["integer", "null"]


def _assert_constraints_schema(schema: Dict[str, Any]) -> None:
    assert schema.get("required") == ["constraints"]
    item_schema = schema["properties"]["constraints"]["items"]
    assert item_schema.get("required") == ["name", "description"]
    assert "source_sections" in item_schema["properties"]
    assert item_schema["properties"]["source_sections"]["items"]["enum"] == CONSTRAINT_SOURCE_SECTIONS


def _assert_objective_schema(schema: Dict[str, Any]) -> None:
    assert schema.get("required") == ["type", "description"]
    properties = schema["properties"]
    assert "target" in properties
    assert "requires_solution" in properties
    assert properties["type"].get("enum") == [name for name, _ in OBJECTIVE_LABELS]


def _assert_invariant_schema(schema: Dict[str, Any]) -> None:
    assert schema.get("required") == ["invariants"]
    item_schema = schema["properties"]["invariants"]["items"]
    assert item_schema.get("required") == ["name", "description", "properties"]
    assert "evidence_source" in item_schema["properties"]
    assert item_schema["properties"]["evidence_source"]["enum"] == INVARIANT_EVIDENCE_SOURCES


def verify_dimension(
    dimension: str,
    build_sys,
    build_usr,
    schema: Dict[str, Any],
    problem: Dict[str, Any],
) -> Dict[str, Any]:
    system_prompt = build_sys()
    user_prompt = build_usr(problem)

    assert isinstance(system_prompt, str) and system_prompt.strip()
    assert isinstance(user_prompt, str) and user_prompt.strip()
    assert "JSON" in system_prompt or "json" in system_prompt
    _assert_system_prompt_sections(system_prompt)

    include_code = dimension.startswith("V")
    _assert_prompt_sections(user_prompt, problem, include_code=include_code)

    if dimension.startswith("I"):
        _assert_input_structure_schema(schema)
    elif dimension.startswith("C"):
        _assert_constraints_schema(schema)
    elif dimension.startswith("O"):
        _assert_objective_schema(schema)
    elif dimension.startswith("V"):
        _assert_invariant_schema(schema)

    return {
        "system_prompt_length": len(system_prompt),
        "user_prompt_length": len(user_prompt),
    }


def main() -> None:
    selected_problems = select_problems_by_category(project_root)
    dimensions = [
        ("I - Input Structure", build_i_system, build_i_user, INPUT_STRUCTURE_SCHEMA),
        ("C - Core Constraints", build_c_system, build_c_user, CONSTRAINTS_SCHEMA),
        ("O - Objective", build_o_system, build_o_user, OBJECTIVE_SCHEMA),
        ("V - Invariant", build_v_system, build_v_user, INVARIANT_SCHEMA),
    ]

    evidence = {
        "validation_status": "success",
        "categories": [],
    }

    for category, problem in selected_problems:
        print(f"\n{'#' * 70}")
        print(f"# 类别: {CATEGORY_LABELS.get(category, category)}")
        print(f"# 题目: {problem['problem_id']} - {problem['title']}")
        print(f"{'#' * 70}")

        category_evidence = {
            "category": category,
            "label": CATEGORY_LABELS.get(category, category),
            "problem_id": problem["problem_id"],
            "title": problem["title"],
            "dimensions": {},
        }

        for dim_name, build_sys, build_usr, schema in dimensions:
            try:
                result = verify_dimension(dim_name, build_sys, build_usr, schema, problem)
                category_evidence["dimensions"][dim_name] = {
                    "status": "ok",
                    **result,
                }
                print(f"[OK] {dim_name}")
            except Exception as exc:
                evidence["validation_status"] = "partial_failure"
                category_evidence["dimensions"][dim_name] = {
                    "status": "failed",
                    "error": str(exc),
                }
                print(f"[FAIL] {dim_name}: {exc}")

        evidence["categories"].append(category_evidence)

    evidence_dir = project_root / "爬取题目" / ".sisyphus" / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = evidence_dir / "task-2-prompt-validation.json"
    evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'=' * 70}")
    print(f"状态: {evidence['validation_status']}")
    print(f"证据已保存: {evidence_path}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
