from __future__ import annotations

from typing import Any

from artifact_context import build_problem_context, normalize_tests
from models import ProblemContext


def normalize_problem_context(context: dict[str, Any]) -> ProblemContext:
    """兼容旧导入路径：新的流程直接从 artifact 上下文构造 ProblemContext。"""

    return build_problem_context(context)
