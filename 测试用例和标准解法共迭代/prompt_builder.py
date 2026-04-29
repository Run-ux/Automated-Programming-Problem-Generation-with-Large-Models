"""旧 prompt 聚合入口已迁移。

Prompt 现在按生成模块拆分到 ``prompts/prompt_*.py``：
每个模块统一暴露 ``build_system_prompt()`` 和 ``build_user_prompt(...)``。
本文件只保留迁移说明，不提供旧函数兼容包装。
"""

from __future__ import annotations

__all__: list[str] = []
