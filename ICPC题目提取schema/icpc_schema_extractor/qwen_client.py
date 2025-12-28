from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests


@dataclass
class QwenConfig:
    # 优先使用 DashScope（官方）OpenAI兼容或自建兼容网关
    base_url: str | None = None
    api_key: str | None = None
    model: str = "qwen-max"
    timeout_s: int = 120


class QwenClient:
    def __init__(self, cfg: Optional[QwenConfig] = None):
        cfg = cfg or QwenConfig()
        base_url = cfg.base_url or os.getenv("QWEN_BASE_URL")
        api_key = cfg.api_key or os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY")

        if not api_key:
            raise RuntimeError(
                "缺少API Key：请设置环境变量 DASHSCOPE_API_KEY 或 QWEN_API_KEY"
            )

        self.base_url = base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.api_key = api_key
        self.model = cfg.model or os.getenv("QWEN_MODEL", "qwen-max")
        self.timeout_s = cfg.timeout_s

    def chat_json(self, system: str, user: str, max_retries: int = 3) -> Dict[str, Any]:
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
            "temperature": 0.2,
        }

        last_err: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout_s)
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return _extract_first_json_object(content)
            except Exception as e:  # noqa: BLE001
                last_err = e
                time.sleep(1.5 * attempt)

        raise RuntimeError(f"调用千问失败：{last_err}")


def _extract_first_json_object(text: str) -> Dict[str, Any]:
    """从模型输出中提取第一个 JSON 对象（允许包裹额外文本）。"""
    text = text.strip()

    # 常见：```json ... ```
    if "```" in text:
        parts = text.split("```")
        # 取最长的一段尝试解析
        candidate = max(parts, key=len).strip()
        # 去掉可能的语言标记
        candidate = candidate.lstrip("json").strip()
        try:
            return json.loads(candidate)
        except Exception:  # noqa: BLE001
            pass

    # 从第一个 { 到匹配的 } 做括号计数
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
