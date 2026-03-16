from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from .models import DimensionScore, Issue


class ProblemQualityJudge:
    def __init__(self, client: Any | None = None):
        self.client = client

    def evaluate(
        self,
        instantiated_schema: dict[str, Any],
        generated_problem: dict[str, Any],
        hard_checks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if self.client is not None:
            try:
                return self._evaluate_with_llm(instantiated_schema, generated_problem, hard_checks)
            except Exception:
                pass
        return self._evaluate_heuristically(instantiated_schema, generated_problem, hard_checks)

    def _evaluate_with_llm(
        self,
        instantiated_schema: dict[str, Any],
        generated_problem: dict[str, Any],
        hard_checks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        system_prompt = """你是一名算法竞赛题面审稿人。请根据实例化后的 schema 与生成题面，评估题面质量。

必须返回严格 JSON，格式如下：
{
  "scores": {
    "variant_fidelity": {"score": 1-5, "rationale": string, "evidence_refs": string[]},
    "spec_completeness": {"score": 1-5, "rationale": string, "evidence_refs": string[]},
    "cross_section_consistency": {"score": 1-5, "rationale": string, "evidence_refs": string[]},
    "sample_quality": {"score": 1-5, "rationale": string, "evidence_refs": string[]},
    "oj_readability": {"score": 1-5, "rationale": string, "evidence_refs": string[]}
  },
  "issues": [
    {
      "severity": "major|minor",
      "title": string,
      "detail": string,
      "evidence_refs": string[],
      "fix_hint": string
    }
  ],
  "strengths": string[],
  "suggested_revisions": string[]
}

只依据给定字段路径做判断，不要输出额外解释。"""
        user_prompt = json.dumps(
            {
                "instantiated_schema": instantiated_schema,
                "generated_problem": generated_problem,
                "hard_checks": hard_checks,
            },
            ensure_ascii=False,
            indent=2,
        )
        result = self.client.chat_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1,
        )
        dimension_scores = [
            asdict(
                DimensionScore(
                    dimension=dimension,
                    score=float(payload.get("score", 3.0)),
                    rationale=str(payload.get("rationale", "")),
                    evidence_refs=list(payload.get("evidence_refs", [])),
                )
            )
            for dimension, payload in result.get("scores", {}).items()
        ]
        issues = [
            asdict(
                Issue(
                    issue_type="quality_issue",
                    severity=str(item.get("severity", "minor")),
                    title=str(item.get("title", "")),
                    detail=str(item.get("detail", "")),
                    evidence_refs=list(item.get("evidence_refs", [])),
                    fix_hint=str(item.get("fix_hint", "")),
                )
            )
            for item in result.get("issues", [])
        ]
        return {
            "dimension_scores": dimension_scores,
            "issues": issues,
            "strengths": list(result.get("strengths", [])),
            "suggested_revisions": list(result.get("suggested_revisions", [])),
        }

    def _evaluate_heuristically(
        self,
        instantiated_schema: dict[str, Any],
        generated_problem: dict[str, Any],
        hard_checks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        failed = {item["check_id"]: item for item in hard_checks if not item["passed"]}
        samples = list(generated_problem.get("samples", []))
        constraints = list(generated_problem.get("constraints", []))

        dimension_scores = [
            asdict(
                DimensionScore(
                    dimension="variant_fidelity",
                    score=_clamp_score(
                        5.0
                        - 1.4 * _bool_score("input_count_alignment" in failed)
                        - 1.4 * _bool_score("objective_alignment" in failed)
                        - 1.0 * _bool_score("structural_option_alignment" in failed)
                    ),
                    rationale="重点看实例化 schema 是否真实落地到题面字段。",
                    evidence_refs=[
                        "snapshots.instantiated_schema",
                        "snapshots.generated_problem",
                    ],
                )
            ),
            asdict(
                DimensionScore(
                    dimension="spec_completeness",
                    score=_clamp_score(
                        2.0
                        + 0.5 * _nonempty(generated_problem.get("title"))
                        + 0.8 * _nonempty(generated_problem.get("description"))
                        + 0.6 * _nonempty(generated_problem.get("input_format"))
                        + 0.6 * _nonempty(generated_problem.get("output_format"))
                        + 0.5 * _bool_score(len(constraints) >= 2)
                    ),
                    rationale="检查关键段落、限制条件和任务说明是否齐全。",
                    evidence_refs=["snapshots.generated_problem"],
                )
            ),
            asdict(
                DimensionScore(
                    dimension="cross_section_consistency",
                    score=_clamp_score(
                        5.0
                        - 1.5 * _count_failed(failed, {"input_count_alignment", "sample_line_alignment"})
                        - 1.0 * _bool_score("objective_alignment" in failed)
                        - 1.0 * _bool_score("structural_option_alignment" in failed)
                    ),
                    rationale="检查 description、input/output、constraints、samples 是否互相一致。",
                    evidence_refs=[
                        "snapshots.generated_problem.input_format",
                        "snapshots.generated_problem.samples",
                    ],
                )
            ),
            asdict(
                DimensionScore(
                    dimension="sample_quality",
                    score=_clamp_score(
                        2.5
                        + 0.7 * _bool_score(len(samples) >= 2)
                        + 0.6 * _bool_score(all(sample.get("explanation") for sample in samples))
                        + 0.6 * _bool_score("sample_line_alignment" not in failed)
                        + 0.4 * _bool_score("sample_count" not in failed)
                    ),
                    rationale="检查样例数量、解释和与输入结构的匹配度。",
                    evidence_refs=["snapshots.generated_problem.samples"],
                )
            ),
            asdict(
                DimensionScore(
                    dimension="oj_readability",
                    score=_clamp_score(
                        3.0
                        + 0.5 * _length_band(generated_problem.get("description", ""), 60, 900)
                        + 0.4 * _length_band(generated_problem.get("input_format", ""), 20, 280)
                        + 0.4 * _length_band(generated_problem.get("output_format", ""), 10, 180)
                        + 0.4 * _bool_score("source_leakage" not in failed)
                    ),
                    rationale="检查题面是否具备正常 OJ 可读性且无明显污染。",
                    evidence_refs=["snapshots.generated_problem"],
                )
            ),
        ]
        issues: list[dict[str, Any]] = []
        if "input_count_alignment" in failed:
            issues.append(
                asdict(
                    Issue(
                        issue_type="quality_issue",
                        severity="major",
                        title="输入项数量与实例化 schema 不一致",
                        detail=failed["input_count_alignment"]["message"],
                        evidence_refs=failed["input_count_alignment"]["evidence_refs"],
                        fix_hint="按实例化 schema 改写 input_format、description 和样例输入的项数。",
                    )
                )
            )
        if "objective_alignment" in failed:
            issues.append(
                asdict(
                    Issue(
                        issue_type="quality_issue",
                        severity="major",
                        title="目标函数未准确落地",
                        detail=failed["objective_alignment"]["message"],
                        evidence_refs=failed["objective_alignment"]["evidence_refs"],
                        fix_hint="在 output_format 和 notes 中明确目标函数的输出对象与 tie-break 规则。",
                    )
                )
            )
        if "structural_option_alignment" in failed:
            issues.append(
                asdict(
                    Issue(
                        issue_type="quality_issue",
                        severity="major",
                        title="结构选项没有体现在题面中",
                        detail=failed["structural_option_alignment"]["message"],
                        evidence_refs=failed["structural_option_alignment"]["evidence_refs"],
                        fix_hint="把顺序约束、循环语义等结构变化显式写进描述或说明部分。",
                    )
                )
            )
        return {
            "dimension_scores": dimension_scores,
            "issues": issues,
            "strengths": _quality_strengths(dimension_scores),
            "suggested_revisions": [issue["fix_hint"] for issue in issues if issue.get("fix_hint")],
        }


class SourceDivergenceJudge:
    def __init__(self, client: Any | None = None):
        self.client = client

    def evaluate(
        self,
        original_problem: dict[str, Any],
        original_schema: dict[str, Any],
        instantiated_schema: dict[str, Any],
        generated_problem: dict[str, Any],
        hard_checks: list[dict[str, Any]],
        schema_distance: float,
    ) -> dict[str, Any]:
        if self.client is not None and schema_distance >= 0.35:
            try:
                return self._evaluate_with_llm(
                    original_problem,
                    original_schema,
                    instantiated_schema,
                    generated_problem,
                    hard_checks,
                    schema_distance,
                )
            except Exception:
                pass
        return self._evaluate_heuristically(
            original_problem,
            instantiated_schema,
            generated_problem,
            hard_checks,
            schema_distance,
        )

    def _evaluate_with_llm(
        self,
        original_problem: dict[str, Any],
        original_schema: dict[str, Any],
        instantiated_schema: dict[str, Any],
        generated_problem: dict[str, Any],
        hard_checks: list[dict[str, Any]],
        schema_distance: float,
    ) -> dict[str, Any]:
        system_prompt = """你是一名算法竞赛命题审稿人。你的任务是判断新题是否只是原题换皮。

必须返回严格 JSON：
{
  "semantic_difference": 0.0-1.0,
  "solution_transfer_risk": 0.0-1.0,
  "surface_retheme_risk": 0.0-1.0,
  "verdict": "pass|reject_as_retheme",
  "rationale": string,
  "evidence_refs": string[]
}

判断重点：
1. 熟悉原题的选手，是否几乎只需改变量名/故事映射就能解出新题。
2. 新题的输入、约束、目标是否真正改变，而不是把原题任务包了新背景。
3. 原题标题、句式、任务定义、样例套路是否被复用。"""
        user_prompt = json.dumps(
            {
                "schema_distance": schema_distance,
                "original_problem": {
                    "title": original_problem.get("title", ""),
                    "description": original_problem.get("description", ""),
                    "input": original_problem.get("input", ""),
                    "output": original_problem.get("output", ""),
                    "constraints": original_problem.get("constraints", ""),
                },
                "original_schema": original_schema,
                "instantiated_schema": instantiated_schema,
                "generated_problem": generated_problem,
                "hard_checks": hard_checks,
            },
            ensure_ascii=False,
            indent=2,
        )
        result = self.client.chat_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1,
        )
        return {
            "semantic_difference": float(result.get("semantic_difference", 0.0)),
            "solution_transfer_risk": float(result.get("solution_transfer_risk", 1.0)),
            "surface_retheme_risk": float(result.get("surface_retheme_risk", 1.0)),
            "verdict": str(result.get("verdict", "reject_as_retheme")),
            "rationale": str(result.get("rationale", "")),
            "evidence_refs": list(result.get("evidence_refs", [])),
        }

    def _evaluate_heuristically(
        self,
        original_problem: dict[str, Any],
        instantiated_schema: dict[str, Any],
        generated_problem: dict[str, Any],
        hard_checks: list[dict[str, Any]],
        schema_distance: float,
    ) -> dict[str, Any]:
        original_text = "\n".join(
            [
                str(original_problem.get("title", "")),
                str(original_problem.get("description", "")),
                str(original_problem.get("input", "")),
                str(original_problem.get("output", "")),
            ]
        )
        generated_text = "\n".join(
            [
                str(generated_problem.get("title", "")),
                str(generated_problem.get("description", "")),
                str(generated_problem.get("input_format", "")),
                str(generated_problem.get("output_format", "")),
            ]
        )
        title_overlap = _text_overlap(
            str(original_problem.get("title", "")),
            str(generated_problem.get("title", "")),
        )
        desc_overlap = _text_overlap(original_text, generated_text)
        failed = {item["check_id"]: item for item in hard_checks if not item["passed"]}

        semantic_difference = min(1.0, max(0.0, schema_distance / 0.60))
        solution_transfer_risk = max(
            0.0,
            min(
                1.0,
                1.0
                - semantic_difference * 0.85
                + desc_overlap * 0.35
                + title_overlap * 0.25
                + 0.20 * _bool_score("source_leakage" in failed),
            ),
        )
        surface_retheme_risk = max(
            title_overlap,
            min(1.0, desc_overlap + 0.20 * _bool_score("source_leakage" in failed)),
        )
        if generated_problem.get("status") == "difference_insufficient":
            surface_retheme_risk = max(surface_retheme_risk, 0.95)
            solution_transfer_risk = max(solution_transfer_risk, 0.9)

        verdict = (
            "reject_as_retheme"
            if surface_retheme_risk >= 0.75 or solution_transfer_risk >= 0.72 or semantic_difference < 0.45
            else "pass"
        )
        rationale = (
            f"schema_distance={schema_distance:.2f}, semantic_difference={semantic_difference:.2f}, "
            f"solution_transfer_risk={solution_transfer_risk:.2f}, surface_retheme_risk={surface_retheme_risk:.2f}."
        )
        return {
            "semantic_difference": semantic_difference,
            "solution_transfer_risk": solution_transfer_risk,
            "surface_retheme_risk": surface_retheme_risk,
            "verdict": verdict,
            "rationale": rationale,
            "evidence_refs": [
                "snapshots.original_problem",
                "snapshots.generated_problem",
                "snapshots.instantiated_schema",
            ],
        }


def _bool_score(value: bool) -> float:
    return 1.0 if value else 0.0


def _nonempty(value: Any) -> float:
    return 1.0 if str(value or "").strip() else 0.0


def _count_failed(failed: dict[str, Any], check_ids: set[str]) -> int:
    return sum(1 for check_id in check_ids if check_id in failed)


def _length_band(text: str, minimum: int, maximum: int) -> float:
    length = len(str(text or "").strip())
    return 1.0 if minimum <= length <= maximum else 0.0


def _clamp_score(score: float) -> float:
    return round(max(1.0, min(5.0, score)), 2)


def _quality_strengths(dimension_scores: list[dict[str, Any]]) -> list[str]:
    strengths = []
    for item in dimension_scores:
        if item["score"] >= 4.3:
            strengths.append(f"{item['dimension']} 表现稳定")
    return strengths or ["题面基础结构完整"]


def _text_overlap(left: str, right: str) -> float:
    left_tokens = set(_tokenize(left))
    right_tokens = set(_tokenize(right))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _tokenize(text: str) -> list[str]:
    import re

    return re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", str(text).lower())
