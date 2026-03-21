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
        system_prompt = """你是一名算法竞赛题面审稿人。请根据实例化后的 schema、生成题面和 hard_checks，评估题面质量。

评分时使用以下统一 rubric：

1. variant_fidelity
- 定义：看 instantiated_schema 中已经确定的任务变体、输入对象、目标函数、结构选项，是否真实落地到 generated_problem 的 description、input_format、output_format、constraints、samples。
- 不要看：它和原题像不像；这里只评估“实例化后的 schema 是否被准确实现”。

2. spec_completeness
- 定义：看题面是否提供了独立做题所需的关键信息，尤其是任务说明、输入格式、输出格式、约束、必要说明是否齐全。
- 如果读者仍需要自行猜测核心规则、边界条件或输出对象，则应降低分数。

3. cross_section_consistency
- 定义：看 description、input_format、output_format、constraints、samples 之间是否互相一致，是否出现字段数量、目标定义、样例格式、符号含义的冲突。
- 如果某一部分与另一部分矛盾，优先降这一维。

4. sample_quality
- 定义：看样例数量是否基本充足，样例输入输出是否与题意和格式匹配，解释是否有助于理解任务。
- 样例少、样例不能覆盖关键结构、样例解释缺失或误导，都应扣分。

5. oj_readability
- 定义：看题面是否符合正常 OJ 题面的表达习惯，结构清楚、措辞明确、噪声少、无明显来源污染或无关文本。
- 不要求文采，只看是否便于参赛者快速准确理解。

评分锚点：
- 5 分：该维度表现稳定，基本无明显问题，只有轻微可忽略瑕疵。
- 3 分：该维度存在明确但可修复的问题，不至于完全影响做题。
- 1 分：该维度存在严重问题，明显影响理解、实现或正确判题。

使用 hard_checks 的规则：
- hard_checks 是强证据。若某项 hard_check 明确失败，相关维度通常不能给高分。
- rationale 和 issues 必须尽量引用 hard_checks 或输入中的字段路径作为证据。
- 只依据给定字段路径做判断，不要臆测缺失信息。

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

输出要求：
- 五个 scores 字段都必须返回。
- score 只能是 1 到 5 的整数。
- evidence_refs 只填输入中出现的字段路径或 hard_checks 中的 evidence_refs。
- 不要输出 JSON 之外的任何解释。"""
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

你要综合 original_problem、original_schema、instantiated_schema、generated_problem、hard_checks 和 schema_distance 进行判断。

评分 rubric：

1. semantic_difference
- 定义：原题与新题在任务语义上的真实差异程度，取值 0.0 到 1.0。
- 高分表示：输入对象、约束结构、目标函数、求解关注点发生了实质变化，熟悉原题的选手不能只靠替换变量名或故事映射就直接套解。
- 低分表示：核心任务、状态定义、决策对象、最优性目标基本没变，只是换背景或轻微改写表述。

2. solution_transfer_risk
- 定义：熟悉原题标准解的选手，能否几乎原样迁移思路、状态设计、关键性质和实现框架到新题，取值 0.0 到 1.0。
- 高分表示：只需改命名、实体映射或很小的边角逻辑就能沿用原解。
- 低分表示：必须重新建模或重新选择关键算法，原题解法不能直接迁移。

3. surface_retheme_risk
- 定义：新题是否主要做了表层换皮，取值 0.0 到 1.0。
- 高分表示：标题、叙事、句式、任务定义、样例套路、名词映射与原题高度对应，文本或结构复用明显。
- 低分表示：即使主题相关，表述组织、任务展开和样例设计也没有明显复用痕迹。

判断时的重点：
- 先看 instantiated_schema 相比 original_schema 是否真的改变了关键轴，再看 generated_problem 是否把这些变化真实落地。
- schema_distance 是强结构信号，但不是唯一依据；如果 schema_distance 不低，但新题语义和解法迁移风险仍然很接近原题，仍应判为换皮。
- hard_checks 中与 source_leakage、结构落地失败相关的失败项，是重要负面证据。
- 不要因为背景故事不同就高估 semantic_difference；关键看“会不会迫使解题者改变问题建模和解法”。

分数锚点：
- semantic_difference: 0.8-1.0 表示实质差异明显；0.4-0.6 表示有变化但核心求解框架仍较接近；0.0-0.2 表示基本只是换皮。
- solution_transfer_risk: 0.8-1.0 表示原解几乎可直接迁移；0.4-0.6 表示可部分复用但需要明显调整；0.0-0.2 表示原解基本不能直接迁移。
- surface_retheme_risk: 0.8-1.0 表示文本/叙事/样例复用明显；0.4-0.6 表示有局部复用；0.0-0.2 表示表层重合很少。

verdict 规则：
- 若新题主要是表层重主题、原题解法可直接迁移、或 semantic_difference 明显偏低，应返回 reject_as_retheme。
- 只有在“语义差异真实成立”且“解法迁移风险不高”时，才返回 pass。
- 当证据冲突时，宁可保守，不要轻易放过疑似换皮题。

必须返回严格 JSON：
{
  "semantic_difference": 0.0-1.0,
  "solution_transfer_risk": 0.0-1.0,
  "surface_retheme_risk": 0.0-1.0,
  "verdict": "pass|reject_as_retheme",
  "rationale": string,
  "evidence_refs": string[]
}

输出要求：
- 三个分数都必须是 0.0 到 1.0 的浮点数。
- rationale 要明确说明“哪些轴真的变了，哪些地方仍然高度可迁移/可复用”。
- evidence_refs 只填输入中出现的字段路径或 hard_checks 中的 evidence_refs。
- 不要输出 JSON 之外的任何解释。"""
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
