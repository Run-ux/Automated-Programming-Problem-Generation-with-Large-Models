from __future__ import annotations

import copy
from typing import Any

from execution_spec import normalize_execution_spec
from models import ExecutionSpec, GeneratedCodeArtifact, WrongSolution, to_dict
from prompt_builder import (
    build_code_system_prompt,
    build_oracle_prompt,
    build_spec_system_prompt,
    build_spec_user_prompt,
    build_standard_solution_prompt,
    build_tools_prompt,
    build_weak_player_prompt,
)


class SpecExtractor:
    def __init__(self, client: Any):
        self.client = client

    def generate(self, context: dict[str, Any], revision_context: dict[str, Any] | None = None) -> ExecutionSpec:
        payload = self.client.chat_json(
            system_prompt=build_spec_system_prompt(),
            user_prompt=build_spec_user_prompt(context, revision_context),
            temperature=0.1,
        )
        return normalize_execution_spec(payload)


class StandardSolutionGenerator:
    def __init__(self, client: Any):
        self.client = client

    def generate(
        self,
        context: dict[str, Any],
        spec: ExecutionSpec,
        revision_context: dict[str, Any] | None = None,
    ) -> GeneratedCodeArtifact:
        payload = self.client.chat_json(
            system_prompt=build_code_system_prompt("StandardSolutionGenerator"),
            user_prompt=build_standard_solution_prompt(context, to_dict(spec), revision_context),
            temperature=0.15,
        )
        return GeneratedCodeArtifact(
            name="standard_solution",
            role="standard_solution",
            code=_clean_code(str(payload.get("code", ""))),
            metadata={
                "algorithm": payload.get("algorithm", ""),
                "correctness": payload.get("correctness", ""),
                "time_complexity": payload.get("time_complexity", ""),
                "space_complexity": payload.get("space_complexity", ""),
                "notes": payload.get("notes", ""),
            },
        )


class OracleGenerator:
    def __init__(self, client: Any):
        self.client = client

    def generate(
        self,
        context: dict[str, Any],
        spec: ExecutionSpec,
        revision_context: dict[str, Any] | None = None,
    ) -> GeneratedCodeArtifact:
        payload = self.client.chat_json(
            system_prompt=build_code_system_prompt("OracleGenerator"),
            user_prompt=build_oracle_prompt(context, to_dict(spec), revision_context),
            temperature=0.1,
        )
        return GeneratedCodeArtifact(
            name="oracle_solution",
            role="oracle_solution",
            code=_clean_code(str(payload.get("code", ""))),
            metadata={
                "oracle_scope": payload.get("oracle_scope", {}),
                "method": payload.get("method", ""),
                "notes": payload.get("notes", ""),
            },
        )


class ToolGenerator:
    def __init__(self, client: Any):
        self.client = client

    def generate(
        self,
        context: dict[str, Any],
        spec: ExecutionSpec,
        revision_context: dict[str, Any] | None = None,
    ) -> dict[str, GeneratedCodeArtifact]:
        payload = self.client.chat_json(
            system_prompt=build_code_system_prompt("ToolGenerator"),
            user_prompt=build_tools_prompt(context, to_dict(spec), revision_context),
            temperature=0.1,
        )
        return {
            "validator": GeneratedCodeArtifact(
                name="validator",
                role="validator",
                code=_clean_code(str(payload.get("validator_code", ""))),
                metadata={"notes": payload.get("notes", "")},
            ),
            "checker": GeneratedCodeArtifact(
                name="checker",
                role="checker",
                code=_clean_code(str(payload.get("checker_code", ""))),
                metadata={"notes": payload.get("notes", "")},
            ),
            "test_generator": GeneratedCodeArtifact(
                name="test_generator",
                role="test_generator",
                code=_clean_code(str(payload.get("test_generator_code", ""))),
                metadata={"notes": payload.get("notes", "")},
            ),
        }


class WeakPlayerGenerator:
    def __init__(self, client: Any):
        self.client = client

    def generate(
        self,
        statement_only_context: dict[str, Any],
        revision_context: dict[str, Any] | None = None,
    ) -> list[WrongSolution]:
        payload = self.client.chat_json(
            system_prompt=build_code_system_prompt("WeakPlayerGenerator"),
            user_prompt=build_weak_player_prompt(statement_only_context, revision_context),
            temperature=0.75,
        )
        return [
            WrongSolution(
                solution_id=str(item.get("solution_id", f"weak_player_{index}")),
                code=_clean_code(str(item.get("code", ""))),
                source=str(item.get("source", "weak_llm_player")),
                bug_type=str(item.get("bug_type", "unknown")),
                expected_failure=str(item.get("expected_failure", "")),
                metadata={"raw": copy.deepcopy(item)},
            )
            for index, item in enumerate(payload.get("wrong_solutions", []), start=1)
            if isinstance(item, dict)
        ]


def build_rule_based_wrong_solutions(spec: ExecutionSpec, standard_code: str = "") -> list[WrongSolution]:
    del standard_code
    empty_output = """def solve(input_str: str) -> str:
    return ""
"""
    first_token = """def solve(input_str: str) -> str:
    data = input_str.strip().split()
    return data[0] if data else ""
"""
    sample_only = """def solve(input_str: str) -> str:
    # 低价值但常见的样例拟合错误：忽略输入结构，只返回固定答案。
    return "0"
"""
    return [
        WrongSolution(
            solution_id=f"{spec.problem_id}_empty_output",
            code=empty_output,
            source="rule_based",
            bug_type="empty_output",
            expected_failure="输出合同通常不允许空输出。",
        ),
        WrongSolution(
            solution_id=f"{spec.problem_id}_first_token",
            code=first_token,
            source="rule_based",
            bug_type="format_misread",
            expected_failure="误把输入首个 token 当成答案。",
        ),
        WrongSolution(
            solution_id=f"{spec.problem_id}_sample_only",
            code=sample_only,
            source="rule_based",
            bug_type="sample_fitting",
            expected_failure="只返回固定答案，无法通过真实测试。",
        ),
    ]


def _clean_code(text: str) -> str:
    cleaned = text.strip()
    if "```" not in cleaned:
        return cleaned
    for block in cleaned.split("```"):
        candidate = block.strip()
        if candidate.startswith("python"):
            return candidate[len("python") :].strip()
        if candidate.startswith("py"):
            return candidate[len("py") :].strip()
        if candidate.startswith("def ") or candidate.startswith("import ") or candidate.startswith("from "):
            return candidate
    return cleaned.replace("```python", "").replace("```", "").strip()
