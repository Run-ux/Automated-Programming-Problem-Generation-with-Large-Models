from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any


class QwenClient:
    def __init__(self, api_key: str, model: str, base_url: str, timeout_s: int = 180):
        if not api_key:
            raise RuntimeError(
                "缺少 API Key，请在生成题面/.env 中设置 DASHSCOPE_API_KEY 或 QWEN_API_KEY。"
            )
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }

        last_error: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                request = urllib.request.Request(
                    url=url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                    raw = response.read().decode("utf-8")
                content = json.loads(raw)["choices"][0]["message"]["content"]
                return _extract_json_object(content)
            except (urllib.error.URLError, urllib.error.HTTPError, KeyError, ValueError) as exc:
                last_error = exc
                time.sleep(1.5 * attempt)
        raise RuntimeError(f"调用 Qwen 失败: {last_error}")


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
