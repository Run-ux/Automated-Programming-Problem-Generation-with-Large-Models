"""
千问大模型 API 客户端

参考 ICPC题目提取schema/icpc_schema_extractor/qwen_client.py
修正 lstrip bug: 使用 removeprefix 替代 lstrip

用法：
    from finiteness_verification.qwen_client import QwenClient

    client = QwenClient()
    result = client.chat_json(system_prompt, user_prompt)
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests


@dataclass
class QwenConfig:
    base_url: str | None = None
    api_key: str | None = None
    model: str = "qwen-max"
    embedding_model: str = "text-embedding-v3"
    timeout_s: int = 120


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
    ) -> Dict[str, Any]:
        url = self.base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }

        last_err: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.post(
                    url, headers=headers, json=payload, timeout=self.timeout_s
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return _extract_first_json_object(content)
            except Exception as e:
                last_err = e
                time.sleep(1.5 * attempt)

        raise RuntimeError(f"调用千问失败：{last_err}")

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
            resp = requests.post(
                url, headers=headers, json=payload, timeout=self.timeout_s
            )
            resp.raise_for_status()
            data = resp.json()
            batch_embeddings = [
                item.get("embedding", []) for item in data.get("data", [])
            ]
            all_embeddings.extend(batch_embeddings)
            # 避免触发限速
            if start + batch_size < len(texts):
                time.sleep(0.3)
        return all_embeddings


def _extract_first_json_object(text: str) -> Dict[str, Any]:
    text = text.strip()

    if "```" in text:
        parts = text.split("```")
        candidate = max(parts, key=len).strip()
        candidate = candidate.removeprefix("json").strip()
        try:
            return json.loads(candidate)
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
                return json.loads(snippet)

    raise ValueError("JSON对象不完整")
