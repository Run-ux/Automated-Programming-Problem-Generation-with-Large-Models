from __future__ import annotations

import json
import re
from typing import Any

from models import GeneratedProblem, VariantPlan
from prompt_builder import build_system_prompt, build_user_prompt
from qwen_client import QwenClient


class ProblemGenerator:
    def __init__(
        self,
        client: QwenClient | None,
        temperature: float = 0.7,
        max_validation_attempts: int = 4,
    ):
        self.client = client
        self.temperature = temperature
        self.max_validation_attempts = max_validation_attempts

    def generate(self, schema: dict[str, Any], plan: VariantPlan) -> GeneratedProblem:
        if self.client is None:
            raise RuntimeError("未初始化 LLM 客户端，无法执行真实生成。")

        system_prompt = build_system_prompt()
        user_prompt = build_user_prompt(schema, plan)
        last_errors: list[str] = []
        base_temperature = min(self.temperature, 0.3)

        for attempt in range(1, self.max_validation_attempts + 1):
            payload = self.client.chat_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=max(0.1, base_temperature - 0.05 * (attempt - 1)),
            )
            problem = self._normalize_payload(payload, plan)
            if problem.status == "schema_insufficient":
                raise RuntimeError(
                    "上游 schema 信息不足，已被模型标记为不可可靠生成："
                    f"{problem.error_reason or '未提供具体原因。'}"
                    + (f" 反馈：{problem.feedback}" if problem.feedback else "")
                )
            self._repair_problem(problem, schema)
            errors = self._validate_problem(problem, schema)
            if not errors:
                return problem

            last_errors = errors
            if attempt == self.max_validation_attempts:
                break
            user_prompt = self._build_retry_prompt(schema, plan, payload, errors, attempt + 1)

        raise RuntimeError(
            "模型连续返回不合法题面，校验失败："
            + "；".join(last_errors[:5])
        )

    def _normalize_payload(
        self, payload: dict[str, Any], plan: VariantPlan
    ) -> GeneratedProblem:
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
        self, problem: GeneratedProblem, schema: dict[str, Any]
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

        return errors

    def _repair_problem(self, problem: GeneratedProblem, schema: dict[str, Any]) -> None:
        expected_sample_lines = self._infer_expected_sample_lines(schema)
        if expected_sample_lines is None:
            return

        for sample in problem.samples:
            repaired_input = self._repair_sample_input(
                sample.get("input", ""),
                expected_sample_lines,
            )
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

    def _contains_html_artifact(self, text: str) -> bool:
        lowered = text.lower()
        return bool(re.search(r"<[^>]+>", text)) or "class=" in lowered or "style=" in lowered

    def _clean_text(self, text: str) -> str:
        cleaned = text.strip()
        cleaned = cleaned.replace("\\n", "\n")
        cleaned = re.sub(r"\\+$", "", cleaned)
        return cleaned.strip()

    def _repair_sample_input(self, text: str, expected_lines: int) -> str | None:
        stripped = text.strip()
        actual_lines = [line for line in stripped.splitlines() if line.strip()]
        if len(actual_lines) == expected_lines:
            return None

        combined_candidate = (
            stripped.replace('",["', "\n")
            .replace('", [', "\n")
            .replace('","', "\n")
            .replace('", "', "\n")
            .replace('["', "")
            .replace('"]', "")
            .replace("[", "")
            .replace("]", "")
        )
        candidates = [
            combined_candidate,
            stripped.replace('",["', "\n"),
            stripped.replace('", [ "', "\n"),
            stripped.replace('","', "\n"),
            stripped.replace('", "', "\n"),
            stripped.replace('],[', "\n"),
            stripped.replace('], [', "\n"),
            stripped.replace('")("', "\n"),
            stripped.replace('")(', "\n"),
            stripped.replace(')("', "\n"),
            stripped.replace(')(', "\n"),
            re.sub(r'"\s*,\s*"', "\n", stripped),
            re.sub(r'"\s*;\s*"', "\n", stripped),
            re.sub(r'"\s*\|\s*"', "\n", stripped),
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
        schema: dict[str, Any],
        plan: VariantPlan,
        payload: dict[str, Any],
        errors: list[str],
        next_attempt: int,
    ) -> str:
        base_prompt = build_user_prompt(schema, plan)
        error_lines = "\n".join(f"- {error}" for error in errors)
        invalid_payload = json.dumps(payload, ensure_ascii=False, indent=2)
        return (
            f"{base_prompt}\n\n"
            f"上一次返回未通过校验，请重新生成完整 JSON。当前是第 {next_attempt} 次尝试。\n"
            "必须修复以下问题：\n"
            f"{error_lines}\n\n"
            "额外要求：\n"
            "- 如果你判断 schema 本身不足以可靠生成题面，不要继续补全，直接返回 `status=\"schema_insufficient\"`，并说明原因与所需补充信息。\n"
            "- 样例输入必须是纯文本，不要包含引号拼接残留、HTML 片段或 Markdown 标记。\n"
            "- 样例输入的行数必须与 schema 的输入结构一致。\n"
            "- 如果 schema 表示固定长度数组，就按固定行数逐行给出样例输入。\n"
            "- 重新生成整份 JSON，不要只修补局部字段。\n\n"
            "上一次的错误 JSON 如下，仅用于定位问题，不可复用：\n"
            f"{invalid_payload}"
        )
