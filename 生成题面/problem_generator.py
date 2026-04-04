from __future__ import annotations

import json
import re
from typing import Any

from models import GeneratedProblem, VariantPlan
from prompt_builder import build_generation_system_prompt, build_generation_user_prompt
from qwen_client import QwenClient
from rule_handlers import get_rule_handler
from schema_tools import dataclass_to_dict


class ProblemGenerator:
    def __init__(
        self,
        client: QwenClient | None,
        temperature: float = 0.7,
        max_validation_attempts: int = 4,
        solver_verifier: Any | None = None,
    ):
        self.client = client
        self.temperature = temperature
        self.max_validation_attempts = max_validation_attempts
        self.solver_verifier = solver_verifier

    def generate(
        self,
        schema_context: dict[str, Any],
        plan: VariantPlan,
        original_problems: list[dict[str, Any]] | None = None,
    ) -> GeneratedProblem:
        if plan.planning_status != "ok":
            return GeneratedProblem(
                title="",
                description="",
                input_format="",
                output_format="",
                constraints=[],
                samples=[],
                notes="",
                status=plan.planning_status,
                error_reason=plan.planning_error_reason,
                feedback=plan.planning_feedback,
            )

        if (
            plan.predicted_schema_distance < plan.difference_plan.target_distance_band["min"]
            or len(plan.changed_axes_realized) < 2
        ):
            return GeneratedProblem(
                title="",
                description="",
                input_format="",
                output_format="",
                constraints=[],
                samples=[],
                notes="",
                status="difference_insufficient",
                error_reason=(
                    "规则规划未达到有效差异门槛。"
                    f" 预测距离={plan.predicted_schema_distance:.2f}，"
                    f"落地轴={', '.join(plan.changed_axes_realized) or '无'}。"
                ),
                feedback=plan.difference_plan.rationale,
            )

        if self.client is None:
            raise RuntimeError("未初始化 LLM 客户端，无法执行真实生成。")

        system_prompt = build_generation_system_prompt()
        user_prompt = build_generation_user_prompt(
            schema_context,
            plan,
            original_problem_references=original_problems or [],
        )
        last_errors: list[str] = []
        base_temperature = min(self.temperature, 0.3)
        instantiated_schema = dataclass_to_dict(plan.instantiated_schema_snapshot)

        for attempt in range(1, self.max_validation_attempts + 1):
            payload = self.client.chat_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=max(0.1, base_temperature - 0.05 * (attempt - 1)),
            )
            problem = self._normalize_payload(payload, plan)
            if problem.status in {"schema_insufficient", "difference_insufficient"}:
                return problem
            self._repair_problem(problem, instantiated_schema)
            errors = self._validate_problem(problem, instantiated_schema, plan, original_problems or [])
            if not errors:
                return problem

            last_errors = errors
            if attempt == self.max_validation_attempts:
                break
            user_prompt = self._build_retry_prompt(
                schema_context,
                plan,
                payload,
                errors,
                attempt + 1,
                original_problems or [],
            )

        raise RuntimeError("模型连续返回不合法题面，校验失败：" + "；".join(last_errors[:5]))

    def _normalize_payload(self, payload: dict[str, Any], plan: VariantPlan) -> GeneratedProblem:
        status = self._clean_text(str(payload.get("status", "ok"))) or "ok"
        samples = []
        for item in payload.get("samples", []):
            if not isinstance(item, dict):
                continue
            samples.append(
                {
                    "input": self._clean_text(str(item.get("input", ""))),
                    "output": self._clean_text(str(item.get("output", ""))),
                    "explanation": self._clean_text(str(item.get("explanation", ""))),
                }
            )
        return GeneratedProblem(
            title=self._clean_text(str(payload.get("title", f"{plan.theme.name}任务"))),
            description=self._clean_text(str(payload.get("description", ""))),
            input_format=self._clean_text(str(payload.get("input_format", ""))),
            output_format=self._clean_text(str(payload.get("output_format", ""))),
            constraints=[
                self._clean_text(str(item))
                for item in payload.get("constraints", [])
                if self._clean_text(str(item))
            ],
            samples=samples,
            notes=self._clean_text(str(payload.get("notes", ""))),
            status=status,
            error_reason=self._clean_text(str(payload.get("error_reason", ""))),
            feedback=self._clean_text(str(payload.get("feedback", ""))),
        )

    def _validate_problem(
        self,
        problem: GeneratedProblem,
        schema: dict[str, Any],
        plan: VariantPlan,
        original_problems: list[dict[str, Any]],
    ) -> list[str]:
        errors: list[str] = []

        if not problem.title:
            errors.append("title 不能为空。")
        if not problem.description:
            errors.append("description 不能为空。")
        if not problem.input_format:
            errors.append("input_format 不能为空。")
        if not problem.output_format:
            errors.append("output_format 不能为空。")

        if len(problem.constraints) < 2:
            errors.append("constraints 至少需要包含 2 条限制。")
        constraint_text = "\n".join(problem.constraints).lower()
        if "时间" not in constraint_text and "time" not in constraint_text:
            errors.append("constraints 必须包含时间限制。")
        if "空间" not in constraint_text and "memory" not in constraint_text:
            errors.append("constraints 必须包含空间限制。")

        if len(problem.samples) < 2:
            errors.append("samples 至少需要 2 组。")

        expected_sample_lines = self._infer_expected_sample_lines(schema)
        declared_line_count = self._extract_declared_line_count(
            "\n".join([problem.input_format, problem.description, problem.notes])
        )
        if expected_sample_lines is not None and declared_line_count is not None and declared_line_count != expected_sample_lines:
            errors.append(
                f"题面声明的输入项数量为 {declared_line_count}，但实例化 schema 要求为 {expected_sample_lines}。"
            )

        for index, sample in enumerate(problem.samples, start=1):
            sample_input = sample.get("input", "").strip()
            sample_output = sample.get("output", "").strip()
            explanation = sample.get("explanation", "").strip()
            if not sample_input:
                errors.append(f"样例 {index} 的 input 不能为空。")
            if not sample_output:
                errors.append(f"样例 {index} 的 output 不能为空。")
            if not explanation:
                errors.append(f"样例 {index} 的 explanation 不能为空。")
            if "```" in sample_input or "```" in sample_output:
                errors.append(f"样例 {index} 不应包含 Markdown 代码块标记。")
            if self._contains_html_artifact(sample_input) or self._contains_html_artifact(sample_output):
                errors.append(f"样例 {index} 包含疑似 HTML 污染内容。")
            if expected_sample_lines is not None:
                actual_lines = len([line for line in sample_input.splitlines() if line.strip()])
                if actual_lines != expected_sample_lines:
                    errors.append(
                        f"样例 {index} 的输入行数应为 {expected_sample_lines}，实际为 {actual_lines}。"
                    )

        errors.extend(self._validate_objective(problem, plan))
        errors.extend(self._validate_structural_commitments(problem, schema, plan))
        errors.extend(self._validate_rule_commitments(problem, plan))
        errors.extend(self._validate_source_reuse(problem, original_problems))
        return errors

    def _repair_problem(self, problem: GeneratedProblem, schema: dict[str, Any]) -> None:
        expected_sample_lines = self._infer_expected_sample_lines(schema)
        if expected_sample_lines is None:
            return
        for sample in problem.samples:
            repaired_input = self._repair_sample_input(sample.get("input", ""), expected_sample_lines)
            if repaired_input is not None:
                sample["input"] = repaired_input

    def _infer_expected_sample_lines(self, schema: dict[str, Any]) -> int | None:
        input_structure = schema.get("input_structure", {})
        if input_structure.get("type") != "array":
            return None
        length = input_structure.get("length", {})
        min_length = length.get("min")
        max_length = length.get("max")
        if not isinstance(min_length, int) or min_length != max_length:
            return None
        if min_length <= 0 or min_length > 10:
            return None
        return min_length

    def _validate_objective(self, problem: GeneratedProblem, plan: VariantPlan) -> list[str]:
        objective_type = str(plan.objective.get("type", "")).lower()
        combined = "\n".join([problem.description, problem.output_format, problem.notes]).lower()
        errors: list[str] = []
        if "count" in objective_type and not any(token in combined for token in ("方案数", "个数", "count", "模", "mod")):
            errors.append("当前 objective 是计数类，但题面没有明确说明输出的是方案数/计数结果。")
        if any(token in objective_type for token in ("decision", "feasibility")) and not any(
            token in combined for token in ("yes", "no", "是否", "存在")
        ):
            errors.append("当前 objective 是判定类，但题面没有明确说明输出判定结果。")
        if any(token in objective_type for token in ("construct", "witness")) and not any(
            token in combined for token in ("构造", "方案", "witness", "输出一个")
        ):
            errors.append("当前 objective 是构造类，但题面没有明确说明需要输出构造方案。")
        if "lexicographical" in objective_type and not any(
            token in combined for token in ("字典序", "lexicographical", "lexicographically")
        ):
            errors.append("当前 objective 要求字典序规范，但题面未明确写出字典序规则。")
        return errors

    def _validate_structural_commitments(
        self,
        problem: GeneratedProblem,
        schema: dict[str, Any],
        plan: VariantPlan,
    ) -> list[str]:
        combined = "\n".join([problem.description, problem.notes, "\n".join(problem.constraints)]).lower()
        errors: list[str] = []
        properties = schema.get("input_structure", {}).get("properties", {}) or {}
        if properties.get("ordered") and not any(token in combined for token in ("顺序", "依次", "in order")):
            errors.append("实例化 schema 带有顺序语义，但题面没有明确说明顺序约束。")
        if properties.get("cyclic") and not any(token in combined for token in ("循环", "首尾相接", "环", "cyclic")):
            errors.append("实例化 schema 带有循环语义，但题面没有明确说明循环语义。")
        return errors

    def _validate_rule_commitments(self, problem: GeneratedProblem, plan: VariantPlan) -> list[str]:
        if not plan.applied_rule:
            return []
        handler = get_rule_handler({"id": plan.applied_rule, "handler": plan.applied_rule})
        outcome = handler.validate_problem(problem=problem, plan=plan)
        if outcome.events:
            plan.validation_trace.extend(dataclass_to_dict(event) for event in outcome.events)
        return list(outcome.errors)

    def _validate_source_reuse(
        self,
        problem: GeneratedProblem,
        original_problems: list[dict[str, Any]],
    ) -> list[str]:
        combined = "\n".join(
            [problem.title, problem.description, problem.input_format, problem.output_format, problem.notes]
        ).lower()
        errors: list[str] = []
        for original_problem in original_problems:
            title = str(original_problem.get("title", "")).strip().lower()
            forbidden = [
                str(original_problem.get("problem_id", "")).strip().lower(),
                str(original_problem.get("source", "")).strip().lower(),
                title,
            ]
            for token in forbidden:
                if token and token in combined:
                    errors.append(f"题面包含不应复用的原题标识或标题片段：{token}")
                    return errors
        return errors

    def _contains_html_artifact(self, text: str) -> bool:
        lowered = text.lower()
        return bool(re.search(r"<[^>]+>", text)) or "class=" in lowered or "style=" in lowered

    def _clean_text(self, text: str) -> str:
        cleaned = text.strip().replace("\\n", "\n")
        cleaned = re.sub(r"\\+$", "", cleaned)
        return cleaned.strip()

    def _extract_declared_line_count(self, text: str) -> int | None:
        patterns = [r"输入共\s*(\d+)\s*行", r"恰好\s*(\d+)\s*行", r"exactly\s*(\d+)\s*lines", r"(\d+)\s*行"]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None

    def _repair_sample_input(self, text: str, expected_lines: int) -> str | None:
        stripped = text.strip()
        actual_lines = [line for line in stripped.splitlines() if line.strip()]
        if len(actual_lines) == expected_lines:
            return None
        candidates = [
            stripped.replace('","', "\n"),
            stripped.replace('", "', "\n"),
            stripped.replace('],[', "\n"),
            stripped.replace('] [', "\n"),
        ]
        for candidate in candidates:
            normalized = "\n".join(
                line.strip().strip('"').strip("'").strip("(").strip(")")
                for line in candidate.splitlines()
                if line.strip()
            )
            normalized_lines = [line for line in normalized.splitlines() if line.strip()]
            if len(normalized_lines) == expected_lines and not self._contains_html_artifact(normalized):
                return normalized
        return None

    def _build_retry_prompt(
        self,
        schema_context: dict[str, Any],
        plan: VariantPlan,
        payload: dict[str, Any],
        errors: list[str],
        next_attempt: int,
        original_problems: list[dict[str, Any]],
    ) -> str:
        base_prompt = build_generation_user_prompt(
            schema_context,
            plan,
            original_problem_references=original_problems,
        )
        error_lines = "\n".join(f"- {error}" for error in errors)
        invalid_payload = json.dumps(payload, ensure_ascii=False, indent=2)
        return (
            f"{base_prompt}\n\n"
            f"上一次返回未通过校验，请重新生成完整 JSON。当前是第 {next_attempt} 次尝试。\n"
            "必须修复以下问题：\n"
            f"{error_lines}\n\n"
            "额外要求：\n"
            "- 如果你判断 schema 本身不足以可靠生成题面，不要继续补全，直接返回 `status=\"schema_insufficient\"`。\n"
            "- 如果你判断差异计划无法在不复述原题任务的前提下落地，直接返回 `status=\"difference_insufficient\"`。\n"
            "- 样例输入必须是纯文本，不要包含引号拼接残留、HTML 片段或 Markdown 标记。\n"
            "- 必须按实例化后的 schema 写输入数量、目标函数和结构约束，不要退回种子题设定。\n"
            "- 重新生成整份 JSON，不要只修补局部字段。\n\n"
            "上一次的错误 JSON 如下，仅用于定位问题，不可复用：\n"
            f"{invalid_payload}"
        )
