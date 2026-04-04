from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Callable, Dict, List, Tuple

from problem_schema import prepare_problem_record


CATEGORY_ORDER = [
    "single_array",
    "graph",
    "tree_queries",
    "feasibility",
    "enumeration",
    "no_solution_code",
]


CATEGORY_LABELS = {
    "single_array": "单数组题",
    "graph": "图题",
    "tree_queries": "树加查询题",
    "feasibility": "判定题",
    "enumeration": "计数题",
    "no_solution_code": "无标准解法代码题",
}


def _load_candidate_problems(project_root: Path) -> List[dict]:
    input_dir = project_root / "爬取题目" / "output" / "imandra_curated_schema_inputs"
    problems: List[dict] = []
    for path in sorted(input_dir.glob("*.json")):
        if path.name.lower() == "manifest.json":
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        prepared = prepare_problem_record(raw, source_path=path)
        prepared["_sample_path"] = str(path)
        problems.append(prepared)
    return problems


def _full_text(problem: dict) -> str:
    parts = [
        problem.get("title", ""),
        problem.get("description", ""),
        problem.get("input", ""),
        problem.get("output", ""),
        problem.get("constraints", ""),
    ]
    return "\n".join(part for part in parts if isinstance(part, str)).lower()


def _structure_candidates(problem: dict) -> List[str]:
    heuristic_profile = problem.get("heuristic_profile")
    if not isinstance(heuristic_profile, dict):
        return []
    candidates = heuristic_profile.get("structure_candidates")
    if not isinstance(candidates, list):
        return []
    return [str(item).lower() for item in candidates]


def _has_solution_code(problem: dict) -> bool:
    code = problem.get("standard_solution_code")
    return isinstance(code, str) and bool(code.strip())


def _is_single_array(problem: dict) -> bool:
    candidates = _structure_candidates(problem)
    text = _full_text(problem)
    return (
        "array" in candidates
        and "graph" not in candidates
        and "tree" not in candidates
        and "query" not in text
    )


def _is_graph(problem: dict) -> bool:
    candidates = _structure_candidates(problem)
    text = _full_text(problem)
    return "graph" in candidates and "tree" not in candidates and "tree" not in text


def _is_tree_queries(problem: dict) -> bool:
    candidates = _structure_candidates(problem)
    text = _full_text(problem)
    return "tree" in candidates and ("query" in text or "queries" in text)


def _is_feasibility(problem: dict) -> bool:
    heuristic_profile = problem.get("heuristic_profile")
    text = _full_text(problem)
    objective_type = ""
    if isinstance(heuristic_profile, dict):
        objective_type = str(heuristic_profile.get("objective_type", "")).lower()
    feasibility_markers = [
        "whether",
        "is it possible",
        "possible",
        "can ",
        "exists",
        "exist",
    ]
    return objective_type == "decision" or any(marker in text for marker in feasibility_markers)


def _is_enumeration(problem: dict) -> bool:
    heuristic_profile = problem.get("heuristic_profile")
    text = _full_text(problem)
    objective_type = ""
    if isinstance(heuristic_profile, dict):
        objective_type = str(heuristic_profile.get("objective_type", "")).lower()
    count_markers = [
        "how many",
        "number of",
        "count",
        "ways",
    ]
    return objective_type == "count" or any(marker in text for marker in count_markers)


def _is_no_solution_code(problem: dict) -> bool:
    return not _has_solution_code(problem)


MATCHERS: Dict[str, Callable[[dict], bool]] = {
    "single_array": _is_single_array,
    "graph": _is_graph,
    "tree_queries": _is_tree_queries,
    "feasibility": _is_feasibility,
    "enumeration": _is_enumeration,
    "no_solution_code": _is_no_solution_code,
}


def _build_synthetic_tree_queries_problem() -> dict:
    return {
        "problem_id": "SYNTH_TREE_QUERY",
        "title": "Synthetic Tree Queries Fixture",
        "description": (
            "You are given a rooted tree and a sequence of path queries. "
            "Each query asks for the sum of values on the path between two nodes."
        ),
        "source": "synthetic",
        "input": (
            "The first line contains n and q. "
            "The next n-1 lines describe the tree edges. "
            "The next line contains node values. "
            "The next q lines each contain a query u v."
        ),
        "output": "For each query, print the path sum.",
        "constraints": (
            "1 <= n, q <= 2 * 10^5\n"
            "The graph is a rooted tree.\n"
            "Queries are answered independently."
        ),
        "standard_solution_code": (
            "build_parent(); build_depth(); build_prefix();\n"
            "for each query(u, v):\n"
            "    l = lca(u, v)\n"
            "    answer = prefix[u] + prefix[v] - 2 * prefix[l] + value[l]"
        ),
        "_sample_path": "<synthetic-tree-query>",
    }


def _build_synthetic_no_code_problem(base_problem: dict | None) -> dict:
    if base_problem is not None:
        cloned = copy.deepcopy(base_problem)
        cloned["problem_id"] = f"{base_problem['problem_id']}_NO_CODE"
        cloned["title"] = f"{base_problem['title']} No Code Fixture"
        cloned.pop("standard_solution_code", None)
        cloned["_sample_path"] = "<synthetic-no-code>"
        return cloned

    return {
        "problem_id": "SYNTH_NO_CODE",
        "title": "Synthetic No Code Fixture",
        "description": "Given an array, determine whether it can be partitioned into two equal-sum subsets.",
        "source": "synthetic",
        "input": "The first line contains n. The second line contains the array.",
        "output": "Print YES if such a partition exists, otherwise print NO.",
        "constraints": "1 <= n <= 2000\n1 <= a_i <= 10^5",
        "_sample_path": "<synthetic-no-code>",
    }


def select_problems_by_category(project_root: Path) -> List[Tuple[str, dict]]:
    problems = _load_candidate_problems(project_root)
    selected: Dict[str, dict] = {}
    used_problem_ids: set[str] = set()

    for category in CATEGORY_ORDER:
        matcher = MATCHERS[category]
        for problem in problems:
            problem_id = problem.get("problem_id")
            if problem_id in used_problem_ids:
                continue
            if matcher(problem):
                selected[category] = problem
                used_problem_ids.add(problem_id)
                break

    for category in CATEGORY_ORDER:
        if category in selected:
            continue
        matcher = MATCHERS[category]
        for problem in problems:
            if matcher(problem):
                selected[category] = problem
                break

    if "tree_queries" not in selected:
        selected["tree_queries"] = _build_synthetic_tree_queries_problem()

    if "no_solution_code" not in selected:
        base_problem = selected.get("single_array") or (problems[0] if problems else None)
        selected["no_solution_code"] = _build_synthetic_no_code_problem(base_problem)

    return [
        (category, selected[category])
        for category in CATEGORY_ORDER
        if category in selected
    ]
