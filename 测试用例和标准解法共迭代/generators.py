from __future__ import annotations

import copy
from typing import Any

from artifact_context import normalize_small_challenge_tests
from models import GeneratedCodeArtifact, WrongSolution
from prompts import prompt_revision_advisor, prompt_sections
from prompts.bruteforce_solution import prompt_bruteforce_solution
from prompts.standard_solution import prompt_standard_solution
from prompts.tool_generation import (
    prompt_adversarial_test_input,
    prompt_checker,
    prompt_random_test_input,
    prompt_small_challenge_test_input,
    prompt_validator,
)
from prompts.wrong_solution import (
    prompt_fixed_category_wrong_solution,
    prompt_schema_mistake_analysis,
    prompt_strategy_wrong_solution,
)


class RevisionAdvisor:
    def __init__(self, client: Any):
        self.client = client

    def generate(self, failure_packet: dict[str, Any]) -> dict[str, Any]:
        payload = self.client.chat_json(
            system_prompt=prompt_revision_advisor.build_system_prompt(),
            user_prompt=prompt_revision_advisor.build_user_prompt(failure_packet),
            temperature=0.1,
        )
        return _normalize_advisor_revision(payload, failure_packet)


class StandardSolutionGenerator:
    def __init__(self, client: Any, timeout_s: int | None = None):
        self.client = client
        self.timeout_s = timeout_s

    def generate(
        self,
        context: dict[str, Any],
        revision_context: dict[str, Any] | None = None,
    ) -> GeneratedCodeArtifact:
        payload = self.client.chat_json(
            system_prompt=prompt_standard_solution.build_system_prompt(),
            user_prompt=prompt_standard_solution.build_user_prompt(context, revision_context),
            temperature=0.15,
            timeout_s=self.timeout_s,
            request_name="standard_solution_generation",
        )
        return GeneratedCodeArtifact(
            name="standard_solution",
            role="standard_solution",
            code=_clean_code(str(payload.get("code", ""))),
            metadata={
                "solution_markdown": payload.get("solution_markdown", ""),
                "time_complexity": payload.get("time_complexity", ""),
                "space_complexity": payload.get("space_complexity", ""),
                "notes": payload.get("notes", ""),
            },
        )


class BruteForceSolutionGenerator:
    def __init__(self, client: Any, timeout_s: int | None = None):
        self.client = client
        self.timeout_s = timeout_s

    def generate(
        self,
        context: dict[str, Any],
        revision_context: dict[str, Any] | None = None,
    ) -> GeneratedCodeArtifact:
        payload = self.client.chat_json(
            system_prompt=prompt_bruteforce_solution.build_system_prompt(),
            user_prompt=prompt_bruteforce_solution.build_user_prompt(context, revision_context),
            temperature=0.1,
            timeout_s=self.timeout_s,
            request_name="bruteforce_solution_generation",
        )
        return GeneratedCodeArtifact(
            name="bruteforce_solution",
            role="bruteforce_solution",
            code=_clean_code(str(payload.get("code", ""))),
            metadata={
                "bruteforce_markdown": payload.get("bruteforce_markdown", ""),
                "time_complexity": payload.get("time_complexity", ""),
                "space_complexity": payload.get("space_complexity", ""),
                "notes": payload.get("notes", ""),
            },
        )


class ToolGenerator:
    def __init__(self, client: Any, timeout_s: int | None = None):
        self.client = client
        self.timeout_s = timeout_s

    def generate(
        self,
        context: dict[str, Any],
        revision_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        validator = self.generate_validator(context, revision_context)
        checker = self.generate_checker(context, validator, revision_context)
        random_generator = self.generate_random_test_generator(context, revision_context)
        adversarial_generator = self.generate_adversarial_test_generator(context, revision_context)
        small_challenge_tests = self.generate_small_challenge_tests(context, revision_context)
        return {
            "validator": validator,
            "checker": checker,
            "random_test_generator": random_generator,
            "adversarial_test_generator": adversarial_generator,
            "small_challenge_tests": small_challenge_tests,
        }

    def generate_validator(
        self,
        context: dict[str, Any],
        revision_context: dict[str, Any] | None = None,
    ) -> GeneratedCodeArtifact:
        payload = self.client.chat_json(
            system_prompt=prompt_validator.build_system_prompt(),
            user_prompt=prompt_validator.build_user_prompt(context, revision_context),
            temperature=0.1,
            timeout_s=self.timeout_s,
            request_name="validator_generation",
        )
        return GeneratedCodeArtifact(
            name="validator",
            role="validator",
            code=_clean_code(str(payload.get("validator_code", ""))),
            metadata={"notes": payload.get("notes", ""), "stage": "validator"},
        )

    def generate_checker(
        self,
        context: dict[str, Any],
        validator: GeneratedCodeArtifact,
        revision_context: dict[str, Any] | None = None,
    ) -> GeneratedCodeArtifact:
        payload = self.client.chat_json(
            system_prompt=prompt_checker.build_system_prompt(),
            user_prompt=prompt_checker.build_user_prompt(context, _artifact_dict(validator), revision_context),
            temperature=0.1,
            timeout_s=self.timeout_s,
            request_name="checker_generation",
        )
        return GeneratedCodeArtifact(
            name="checker",
            role="checker",
            code=_clean_code(str(payload.get("checker_code", ""))),
            metadata={"notes": payload.get("notes", ""), "stage": "checker"},
        )

    def generate_random_test_generator(
        self,
        context: dict[str, Any],
        revision_context: dict[str, Any] | None = None,
    ) -> GeneratedCodeArtifact:
        payload = self.client.chat_json(
            system_prompt=prompt_random_test_input.build_system_prompt(),
            user_prompt=prompt_random_test_input.build_user_prompt(context, revision_context),
            temperature=0.25,
            timeout_s=self.timeout_s,
            request_name="random_test_input_generation",
        )
        return GeneratedCodeArtifact(
            name="random_test_generator",
            role="test_input_generator",
            code=_clean_code(str(payload.get("test_generator_code", ""))),
            metadata={"notes": payload.get("notes", ""), "stage": "random_test_input"},
        )

    def generate_adversarial_test_generator(
        self,
        context: dict[str, Any],
        revision_context: dict[str, Any] | None = None,
    ) -> GeneratedCodeArtifact:
        payload = self.client.chat_json(
            system_prompt=prompt_adversarial_test_input.build_system_prompt(),
            user_prompt=prompt_adversarial_test_input.build_user_prompt(context, revision_context),
            temperature=0.25,
            timeout_s=self.timeout_s,
            request_name="adversarial_test_input_generation",
        )
        return GeneratedCodeArtifact(
            name="adversarial_test_generator",
            role="test_input_generator",
            code=_clean_code(str(payload.get("test_generator_code", ""))),
            metadata={"notes": payload.get("notes", ""), "stage": "adversarial_test_input"},
        )

    def generate_small_challenge_tests(
        self,
        context: dict[str, Any],
        revision_context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        payload = self.client.chat_json(
            system_prompt=prompt_small_challenge_test_input.build_system_prompt(),
            user_prompt=prompt_small_challenge_test_input.build_user_prompt(context, revision_context),
            temperature=0.2,
            timeout_s=self.timeout_s,
            request_name="small_challenge_test_input_generation",
        )
        return normalize_small_challenge_tests(payload.get("tests", []))


class FixedCategoryWrongSolutionGenerator:
    def __init__(self, client: Any):
        self.client = client

    def generate(
        self,
        context: dict[str, Any],
        revision_context: dict[str, Any] | None = None,
    ) -> list[WrongSolution]:
        del revision_context
        if self.client is None:
            return []
        wrong_solutions: list[WrongSolution] = []
        for index, category in enumerate(prompt_sections.FIXED_WRONG_CATEGORIES, start=1):
            code = self.client.chat_text(
                system_prompt=prompt_fixed_category_wrong_solution.build_system_prompt(),
                user_prompt=prompt_fixed_category_wrong_solution.build_user_prompt(context, category),
                temperature=0.65,
                request_name=f"fixed_wrong_solution_{index}",
            )
            wrong_solutions.append(
                WrongSolution(
                    solution_id=f"fixed_wrong_{index}_{_safe_id(category)}",
                    code=_clean_code(code),
                    source="fixed_category_llm_player",
                    bug_type=category,
                    expected_failure=f"固定错误策略类别：{category}",
                    metadata={
                        "source_kind": "fixed_category",
                        "strategy_category": category,
                        "strategy_text": f"按固定错误策略类别生成：{category}",
                        "expected_failure_feature": f"固定错误策略类别：{category}",
                    },
                )
            )
        return wrong_solutions


class SchemaMistakeAnalyzer:
    def __init__(self, client: Any):
        self.client = client

    def generate(
        self,
        context: dict[str, Any],
        revision_context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if not (context.get("new_schema") or context.get("new_schema_snapshot")) or self.client is None:
            return []

        payload = self.client.chat_json(
            system_prompt=prompt_schema_mistake_analysis.build_system_prompt(),
            user_prompt=prompt_schema_mistake_analysis.build_user_prompt(context, revision_context),
            temperature=0.35,
            request_name="schema_mistake_analysis",
        )
        mistake_points = payload.get("mistake_points", [])
        if not isinstance(mistake_points, list):
            return []
        return [
            _normalize_mistake_point(item, index)
            for index, item in enumerate(mistake_points, start=1)
            if isinstance(item, dict)
        ]


class StrategyWrongSolutionGenerator:
    def __init__(self, client: Any):
        self.client = client

    def generate(
        self,
        context: dict[str, Any],
        mistake_points: list[dict[str, Any]],
        revision_context: dict[str, Any] | None = None,
    ) -> list[WrongSolution]:
        del revision_context
        if not mistake_points or self.client is None:
            return []
        wrong_solutions: list[WrongSolution] = []
        for index, mistake in enumerate(mistake_points, start=1):
            code = self.client.chat_text(
                system_prompt=prompt_strategy_wrong_solution.build_system_prompt(),
                user_prompt=prompt_strategy_wrong_solution.build_user_prompt(context, mistake),
                temperature=0.65,
                request_name=f"strategy_wrong_solution_{index}",
            )
            strategy_id = str(mistake.get("strategy_id") or f"free_strategy_{index}").strip()
            wrong_solutions.append(
                WrongSolution(
                    solution_id=f"free_wrong_{index}_{_safe_id(strategy_id)}",
                    code=_clean_code(code),
                    source="free_strategy_llm_player",
                    bug_type=str(mistake.get("category", "free_strategy")),
                    expected_failure=str(mistake.get("failure_reason") or mistake.get("trigger_shape") or ""),
                    metadata={
                        "source_kind": "free_strategy",
                        "strategy_category": str(mistake.get("category", "free_strategy")),
                        "strategy_text": str(mistake.get("wrong_strategy", "")),
                        "expected_failure_feature": str(mistake.get("failure_reason") or mistake.get("trigger_shape") or ""),
                        "strategy": copy.deepcopy(mistake),
                    },
                )
            )
        return wrong_solutions


def _normalize_mistake_point(item: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "strategy_id": str(item.get("strategy_id", f"free_strategy_{index}")).strip() or f"free_strategy_{index}",
        "category": str(item.get("category", "")).strip(),
        "title": str(item.get("title", "")).strip(),
        "wrong_strategy": str(item.get("wrong_strategy", "")).strip(),
        "plausible_reason": str(item.get("plausible_reason", "")).strip(),
        "failure_reason": str(item.get("failure_reason", "")).strip(),
        "trigger_shape": str(item.get("trigger_shape", "")).strip(),
        "raw": copy.deepcopy(item),
    }


def _artifact_dict(artifact: GeneratedCodeArtifact) -> dict[str, Any]:
    return {
        "name": artifact.name,
        "role": artifact.role,
        "code": artifact.code,
        "metadata": artifact.metadata,
    }


def _normalize_advisor_revision(payload: dict[str, Any], failure_packet: dict[str, Any]) -> dict[str, Any]:
    diagnostic = failure_packet.get("diagnostic") if isinstance(failure_packet.get("diagnostic"), dict) else {}
    allowed_roles = {str(role) for role in diagnostic.get("target_roles", [])}
    target_roles = [role for role in _normalize_string_list(payload.get("target_roles")) if role in allowed_roles]
    if not target_roles:
        target_roles = sorted(allowed_roles)
    confidence = str(payload.get("confidence", "medium")).strip().lower()
    if confidence not in {"low", "medium", "high"}:
        confidence = "medium"
    return {
        "root_cause": str(payload.get("root_cause", "")).strip(),
        "revision_advice": str(payload.get("revision_advice", "")).strip(),
        "target_roles": target_roles,
        "evidence_used": _normalize_string_list(payload.get("evidence_used")),
        "confidence": confidence,
        "risk_notes": str(payload.get("risk_notes", "")).strip(),
    }


def _normalize_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


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


def _safe_id(text: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "_" for char in str(text))
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_") or "wrong"
