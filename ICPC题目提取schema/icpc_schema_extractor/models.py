from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ProblemText(BaseModel):
    problem_id: str = Field(description="题目编号/字母，如 A")
    title: str
    description: str
    input: str
    output: str
    constraints: str
    source_pdf: Optional[str] = None
    pages: Optional[List[int]] = None


class SchemaOutput(BaseModel):
    name: str
    input_structure: Dict[str, Any]
    core_constraints: List[Dict[str, Any]]
    objective: Dict[str, Any]
    invariant: Dict[str, Any]
    transform_params: Dict[str, Any]
