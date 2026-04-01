"""
千问大模型 API 客户端

参考 ICPC题目提取schema/icpc_schema_extractor/qwen_client.py
修正 lstrip bug: 使用 removeprefix 替代 lstrip

用法：
    from qwen_client import QwenClient

    client = QwenClient()
    result = client.chat_json(system_prompt, user_prompt)
"""

from __future__ import annotations

import ast
import json
import logging
import os
import re
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


@dataclass
class QwenConfig:
    base_url: str | None = None
    api_key: str | None = None
    model: str = "qwen-max"
    embedding_model: str = "text-embedding-v3"
    timeout_s: int = 300


class QwenJSONError(RuntimeError):
    def __init__(self, message: str, raw_text: str = ""):
        super().__init__(message)
        self.raw_text = raw_text


class QwenClient:
    def __init__(self, cfg: Optional[QwenConfig] = None):
        cfg = cfg or QwenConfig()
        base_url = cfg.base_url or os.getenv("QWEN_BASE_URL")
        api_key = (
            cfg.api_key or os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
        )

        if not api_key:
            raise RuntimeError(
                "缺少API Key：请设置环境变量 DASHSCOPE_API_KEY 或 QWEN_API_KEY"
            )

        self.base_url = base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.api_key = api_key
        self.model = cfg.model or os.getenv("QWEN_MODEL", "qwen-max")
        self.embedding_model = cfg.embedding_model or os.getenv(
            "QWEN_EMBEDDING_MODEL", "text-embedding-v3"
        )
        self.timeout_s = cfg.timeout_s

    def chat_json(
        self,
        system: str,
        user: str,
        max_retries: int = 3,
        temperature: float = 0.2,
        request_label: str = "",
    ) -> Dict[str, Any]:
        last_err: Exception | None = None
        last_raw_text = ""
        label = request_label or "unnamed-request"
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    "[Qwen] %s: 主请求第 %d/%d 次，timeout=%ss",
                    label,
                    attempt,
                    max_retries,
                    self.timeout_s,
                )
                content = self._chat_text(
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=temperature,
                )
                last_raw_text = content
                try:
                    return _extract_first_json_object(content)
                except ValueError:
                    logger.warning("[Qwen] %s: 主请求返回内容不是合法 JSON，进入 JSON 修复", label)
                    repaired = self._repair_json_content(content, request_label=label)
                    last_raw_text = repaired
                    return _extract_first_json_object(repaired)
            except (
                urllib.error.URLError,
                urllib.error.HTTPError,
                KeyError,
                ValueError,
                TimeoutError,
                socket.timeout,
            ) as e:
                last_err = e
                delay = self._retry_delay_seconds(e, attempt)
                logger.warning(
                    "[Qwen] %s: 第 %d/%d 次失败，错误=%s: %s；%s %.1f 秒后重试",
                    label,
                    attempt,
                    max_retries,
                    type(e).__name__,
                    e,
                    "检测到超时，" if isinstance(e, (TimeoutError, socket.timeout)) else "",
                    delay,
                )
                time.sleep(delay)
            except QwenJSONError as e:
                last_err = e
                last_raw_text = e.raw_text
                delay = self._retry_delay_seconds(e, attempt)
                logger.warning(
                    "[Qwen] %s: 第 %d/%d 次失败，错误=%s: %s；%.1f 秒后重试",
                    label,
                    attempt,
                    max_retries,
                    type(e).__name__,
                    e,
                    delay,
                )
                time.sleep(delay)

        raise QwenJSONError(f"调用千问失败：{last_err}", raw_text=last_raw_text)

    def embed_texts(
        self, texts: list[str], model: str | None = None, batch_size: int = 10
    ) -> list[list[float]]:
        """调用 embedding API，自动分批（DashScope 限制每批最多 10 条）。"""
        if not texts:
            return []
        url = self.base_url.rstrip("/") + "/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        use_model = model or self.embedding_model
        all_embeddings: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            payload = {
                "model": use_model,
                "input": batch,
            }
            request = urllib.request.Request(
                url=url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                data = json.loads(response.read().decode("utf-8"))
            batch_embeddings = [
                item.get("embedding", []) for item in data.get("data", [])
            ]
            all_embeddings.extend(batch_embeddings)
            # 避免触发限速
            if start + batch_size < len(texts):
                time.sleep(0.3)
        return all_embeddings

    def _chat_text(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        model: str | None = None,
    ) -> str:
        url = self.base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
        }
        request = urllib.request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]

    def _repair_json_content(self, broken_text: str, request_label: str = "") -> str:
        repair_system = (
            "你是 JSON 修复器。你的唯一任务是把用户提供的内容转换为严格合法的 JSON。"
            "不要补充解释，不要输出 Markdown 代码块，只输出一个 JSON 对象。"
        )
        repair_user = (
            "下面是一段本应为 JSON 但格式不合法的文本。"
            "请在不改变语义的前提下修复为严格 JSON：\n\n"
            f"{broken_text}"
        )
        try:
            logger.info("[Qwen] %s: 发起 JSON 修复请求，timeout=%ss", request_label or "unnamed-request", self.timeout_s)
            return self._chat_text(
                messages=[
                    {"role": "system", "content": repair_system},
                    {"role": "user", "content": repair_user},
                ],
                temperature=0.0,
            )
        except Exception as exc:
            raise QwenJSONError(f"JSON 修复失败：{exc}", raw_text=broken_text) from exc

    def _retry_delay_seconds(self, error: Exception, attempt: int) -> float:
        if isinstance(error, (TimeoutError, socket.timeout)):
            return 5.0 * attempt
        return 1.5 * attempt


def _extract_first_json_object(text: str) -> Dict[str, Any]:
    text = text.strip()

    if "```" in text:
        parts = text.split("```")
        candidate = max(parts, key=len).strip()
        candidate = candidate.removeprefix("json").strip()
        try:
            return json.loads(_normalize_json_candidate(candidate))
        except Exception:
            pass

    normalized = _normalize_json_candidate(text)
    try:
        return json.loads(normalized)
    except Exception:
        pass

    start = text.find("{")
    if start == -1:
        raise ValueError("模型输出未包含JSON对象")

    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                snippet = text[start : i + 1]
                try:
                    return json.loads(_normalize_json_candidate(snippet))
                except Exception:
                    normalized_snippet = _normalize_json_candidate(snippet)
                    return json.loads(normalized_snippet)

    raise ValueError("JSON对象不完整")


def _normalize_json_candidate(text: str) -> str:
    replacements = {
        "“": '"',
        "”": '"',
        "‘": '"',
        "’": '"',
        "，": ",",
        "：": ":",
        "\u00a0": " ",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    text = _replace_numeric_expressions(text)
    return text


def _replace_numeric_expressions(text: str) -> str:
    pattern = re.compile(r'(:\s*)(-?[0-9][0-9\s\+\-\*\/\(\)]*)(\s*[,}\]])')

    def repl(match: re.Match[str]) -> str:
        prefix, expr, suffix = match.groups()
        compact = expr.strip()
        if not compact:
            return match.group(0)
        try:
            value = _safe_eval_arithmetic(compact)
        except ValueError:
            return match.group(0)
        return f"{prefix}{value}{suffix}"

    previous = None
    while previous != text:
        previous = text
        text = pattern.sub(repl, text)
    return text


def _safe_eval_arithmetic(expr: str) -> int:
    try:
        node = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"Invalid arithmetic expression: {expr}") from exc
    return _eval_ast_node(node.body)


def _eval_ast_node(node: ast.AST) -> int:
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _eval_ast_node(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and isinstance(
        node.op, (ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Div, ast.Pow, ast.Mod)
    ):
        left = _eval_ast_node(node.left)
        right = _eval_ast_node(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Pow):
            return left**right
        if right == 0:
            raise ValueError("Division by zero")
        if isinstance(node.op, ast.Mod):
            return left % right
        if isinstance(node.op, ast.Div):
            if left % right != 0:
                raise ValueError("Non-integer division result")
            return left // right
        return left // right
    raise ValueError(f"Unsupported arithmetic node: {type(node).__name__}")
