from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from typing import Any


class LlmClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout_s: int = 360,
    ):
        if not api_key:
            raise RuntimeError("缺少 API Key，请在题包生成验证/.env 中设置 LLM_API_KEY。")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    def chat_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_retries: int = 3,
        timeout_s: int | None = None,
        request_name: str = "chat_json",
    ) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        raw = self._post_json(
            url=f"{self.base_url}/chat/completions",
            payload=payload,
            max_retries=max_retries,
            timeout_s=timeout_s or self.timeout_s,
            request_name=request_name,
        )
        try:
            response_payload = json.loads(raw)
            content = response_payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            preview = raw[:500].replace("\n", "\\n")
            raise RuntimeError(
                f"LLM 返回解析失败：request={request_name}; model={self.model}; "
                f"response_preview={preview}; error={exc}"
            ) from exc
        return _extract_json_object(content)

    def chat_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_retries: int = 3,
        timeout_s: int | None = None,
        request_name: str = "chat_text",
    ) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        }
        raw = self._post_json(
            url=f"{self.base_url}/chat/completions",
            payload=payload,
            max_retries=max_retries,
            timeout_s=timeout_s or self.timeout_s,
            request_name=request_name,
        )
        try:
            response_payload = json.loads(raw)
            return str(response_payload["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            preview = raw[:500].replace("\n", "\\n")
            raise RuntimeError(
                f"LLM 文本返回解析失败：request={request_name}; model={self.model}; "
                f"response_preview={preview}; error={exc}"
            ) from exc

    def _post_json(
        self,
        *,
        url: str,
        payload: dict[str, Any],
        max_retries: int,
        timeout_s: int,
        request_name: str,
    ) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload_json = json.dumps(payload, ensure_ascii=False)
        last_error: Exception | None = None
        last_error_kind = "unknown"
        payload_bytes = len(payload_json.encode("utf-8"))
        for attempt in range(1, max_retries + 1):
            started_at = time.perf_counter()
            self._log(
                f"[LLM] request={request_name} model={self.model} attempt={attempt}/{max_retries} "
                f"timeout_s={timeout_s} payload_bytes={payload_bytes} url={url}"
            )
            try:
                request = urllib.request.Request(
                    url=url,
                    data=payload_json.encode("utf-8"),
                    headers=headers,
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=timeout_s) as response:
                    body = response.read().decode("utf-8")
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                self._log(
                    f"[LLM] success request={request_name} model={self.model} attempt={attempt}/{max_retries} "
                    f"elapsed_ms={elapsed_ms} response_bytes={len(body.encode('utf-8'))}"
                )
                return body
            except (TimeoutError, socket.timeout) as exc:
                last_error = exc
                last_error_kind = "timeout"
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                self._log(
                    f"[LLM] timeout request={request_name} model={self.model} attempt={attempt}/{max_retries} "
                    f"elapsed_ms={elapsed_ms} timeout_s={timeout_s} error={exc}"
                )
            except urllib.error.HTTPError as exc:
                last_error = exc
                last_error_kind = "http_error"
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                body = ""
                try:
                    body = exc.read().decode("utf-8", errors="replace")
                except Exception:
                    body = ""
                preview = body[:500].replace("\n", "\\n")
                self._log(
                    f"[LLM] http_error request={request_name} model={self.model} attempt={attempt}/{max_retries} "
                    f"elapsed_ms={elapsed_ms} status={exc.code} reason={exc.reason} body_preview={preview}"
                )
            except (
                urllib.error.URLError,
                KeyError,
                ValueError,
            ) as exc:
                last_error = exc
                last_error_kind = type(exc).__name__
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                self._log(
                    f"[LLM] failure request={request_name} model={self.model} attempt={attempt}/{max_retries} "
                    f"elapsed_ms={elapsed_ms} error_type={type(exc).__name__} error={exc}"
                )
                time.sleep(1.5 * attempt)
                continue
            time.sleep(1.5 * attempt)
        raise RuntimeError(
            f"调用 LLM 失败：request={request_name}; model={self.model}; url={url}; "
            f"timeout_s={timeout_s}; max_retries={max_retries}; payload_bytes={payload_bytes}; "
            f"error_kind={last_error_kind}; error={last_error}"
        )

    def _log(self, message: str) -> None:
        print(message, flush=True)


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("{"):
        return json.loads(text)
    if "```" in text:
        for block in text.split("```"):
            candidate = block.strip().removeprefix("json").strip()
            if candidate.startswith("{"):
                return json.loads(candidate)
    start = text.find("{")
    if start < 0:
        raise ValueError("模型返回内容中未找到 JSON 对象。")
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : index + 1])
    raise ValueError("模型返回的 JSON 对象不完整。")
