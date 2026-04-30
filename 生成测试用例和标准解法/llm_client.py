from __future__ import annotations

import logging
from typing import Protocol

try:  # 兼容包内导入与当前目录直接运行两种方式。
    from .llm_config import LLMConfig
except ImportError:  # pragma: no cover - 当前测试以顶层模块方式导入。
    from llm_config import LLMConfig


logger = logging.getLogger(__name__)


class LLMCallError(RuntimeError):
    """表示 LLM 调用失败或响应结构不可用。"""


class ChatLLMClient(Protocol):
    def complete_json(self, *, task_name: str, system_prompt: str, user_prompt: str) -> str:
        """调用模型并返回原始 JSON 字符串。"""


class OpenAIChatLLMClient:
    """OpenAI 兼容 Chat Completions 客户端。"""

    def __init__(self, config: LLMConfig) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - 需要真实依赖环境覆盖。
            raise LLMCallError("缺少 openai 包，请先安装 requirements.txt 中的依赖。") from exc

        self.config = config
        client_kwargs = {
            "api_key": config.api_key,
            "timeout": config.timeout_seconds,
            "max_retries": config.max_retries,
        }
        if config.base_url:
            client_kwargs["base_url"] = config.base_url
        self._client = OpenAI(**client_kwargs)

    def complete_json(self, *, task_name: str, system_prompt: str, user_prompt: str) -> str:
        logger.info(
            "开始调用 LLM: task=%s model=%s base_url_configured=%s",
            task_name,
            self.config.model,
            bool(self.config.base_url),
        )
        try:
            response = self._client.chat.completions.create(
                model=self.config.model,
                temperature=self.config.temperature,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except Exception as exc:
            logger.exception("LLM 调用失败: task=%s model=%s", task_name, self.config.model)
            raise LLMCallError(f"LLM 调用失败: {task_name}") from exc

        choices = getattr(response, "choices", None)
        if not choices:
            raise LLMCallError(f"LLM 响应缺少 choices: {task_name}")

        content = getattr(choices[0].message, "content", None)
        if not isinstance(content, str) or not content.strip():
            raise LLMCallError(f"LLM 响应内容为空: {task_name}")

        logger.info("LLM 调用成功: task=%s model=%s", task_name, self.config.model)
        return content

