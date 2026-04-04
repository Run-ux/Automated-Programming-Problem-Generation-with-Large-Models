"""QA 验证脚本：按题型抽样调用模型，并检查输出结构与分节证据。"""

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
    INVARIANT_EVIDENCE_SOURCES,
    OBJECTIVE_LABELS,
)
from prompt_test_cases import CATEGORY_LABELS, select_problems_by_category
from prompts.prompt_constraints import (
    build_system_prompt as build_c_system,
    build_user_prompt as build_c_user,
)
from prompts.prompt_input_structure import (
    build_system_prompt as build_i_system,
    build_user_prompt as build_i_user,
)
from prompts.prompt_invariant import (
    build_system_prompt as build_v_system,
    build_user_prompt as build_v_user,
)
from prompts.prompt_objective import (
    build_system_prompt as build_o_system,
    build_user_prompt as build_o_user,
)
from prompts.prompt_sections import EMPTY_SECTION_TEXT
from qwen_client import QwenClient


OBJECTIVE_TYPES = {name for name, _ in OBJECTIVE_LABELS}


def _assert_system_prompt_sections(system_prompt: str) -> None:
    assert "科研定义：" in system_prompt, "system_prompt 缺少科研定义"
    assert "判别边界：" in system_prompt, "system_prompt 缺少判别边界"


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
        assert expected_text in user_prompt, f"user_prompt 缺少 {title} 内容"

    solution_code = problem.get("standard_solution_code", "")
    if include_code and isinstance(solution_code, str) and solution_code.strip():
        assert solution_code.strip() in user_prompt, "invariant prompt 缺少标准解法代码"


def _validate_input_structure(result: Dict[str, Any]) -> None:
    assert isinstance(result.get("type"), str)
    assert isinstance(result.get("length"), dict)
    assert isinstance(result.get("value_range"), dict)
    assert isinstance(result.get("properties"), dict)
    if "components" in result:
        assert isinstance(result["components"], list)


def _validate_constraints(result: Dict[str, Any]) -> None:
    constraints = result.get("constraints")
    assert isinstance(constraints, list)
    for constraint in constraints:
        assert isinstance(constraint.get("name"), str)
        assert isinstance(constraint.get("description"), str)
        if "formal" in constraint:
            assert isinstance(constraint["formal"], str)
        if "source_sections" in constraint:
            assert isinstance(constraint["source_sections"], list)
            for section in constraint["source_sections"]:
                assert section in CONSTRAINT_SOURCE_SECTIONS


def _validate_objective(result: Dict[str, Any]) -> None:
    assert isinstance(result.get("type"), str)
    assert result["type"] in OBJECTIVE_TYPES
    assert isinstance(result.get("description"), str)
    if "target" in result:
        assert isinstance(result["target"], str)
    if "requires_solution" in result:
        assert isinstance(result["requires_solution"], bool)


def _validate_invariant(result: Dict[str, Any]) -> None:
    invariants = result.get("invariants")
    assert isinstance(invariants, list)
    for invariant in invariants:
        assert isinstance(invariant.get("name"), str)
        assert isinstance(invariant.get("description"), str)
        assert isinstance(invariant.get("properties"), dict)
        if "evidence_source" in invariant:
            assert invariant["evidence_source"] in INVARIANT_EVIDENCE_SOURCES


def test_dimension(
    client: QwenClient,
    dimension: str,
    build_sys,
    build_usr,
    problem: Dict[str, Any],
) -> Dict[str, Any]:
    system_prompt = build_sys()
    user_prompt = build_usr(problem)
    _assert_system_prompt_sections(system_prompt)
    _assert_prompt_sections(user_prompt, problem, include_code=dimension.startswith("V"))

    result = client.chat_json(system_prompt, user_prompt)

    if dimension.startswith("I"):
        _validate_input_structure(result)
    elif dimension.startswith("C"):
        _validate_constraints(result)
    elif dimension.startswith("O"):
        _validate_objective(result)
    elif dimension.startswith("V"):
        _validate_invariant(result)

    return result


def main() -> None:
    selected_problems = select_problems_by_category(project_root)
    evidence: Dict[str, Any] = {
        "status": "success",
        "categories": [],
    }

    try:
        client = QwenClient()
    except RuntimeError as exc:
        evidence["status"] = "client_init_failed"
        evidence["error"] = str(exc)
        client = None

    dimensions = [
        ("I - Input Structure", build_i_system, build_i_user),
        ("C - Core Constraints", build_c_system, build_c_user),
        ("O - Objective", build_o_system, build_o_user),
        ("V - Invariant", build_v_system, build_v_user),
    ]

    if client is not None:
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

            for dim_name, build_sys, build_usr in dimensions:
                try:
                    result = test_dimension(client, dim_name, build_sys, build_usr, problem)
                    category_evidence["dimensions"][dim_name] = {
                        "status": "ok",
                        "result": result,
                    }
                    print(f"[OK] {dim_name}")
                except Exception as exc:
                    evidence["status"] = "partial_failure"
                    category_evidence["dimensions"][dim_name] = {
                        "status": "failed",
                        "error": str(exc),
                    }
                    print(f"[FAIL] {dim_name}: {exc}")

            evidence["categories"].append(category_evidence)

    evidence_dir = project_root / "爬取题目" / ".sisyphus" / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = evidence_dir / "task-2-prompt-samples.json"
    evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'=' * 70}")
    print(f"状态: {evidence['status']}")
    print(f"证据已保存: {evidence_path}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
