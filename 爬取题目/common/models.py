from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ProblemText(BaseModel):
    """Aligned with ICPC题目提取schema/icpc_schema_extractor/models.py
    so downstream Schema extraction pipeline works without conversion."""

    problem_id: str = Field(description="e.g. 'CF1900D' or 'ABC300_F'")
    title: str
    description: str
    input: str
    output: str
    constraints: str
    source: str = Field(default="")
    url: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    difficulty: Optional[str] = None
