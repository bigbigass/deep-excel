"""质量调查证据模型。

证据是调查系统的最小可信单元。统计工具、知识检索和人工录入都必须先
形成结构化证据，AI 才能基于这些证据生成调查结论或候选假设。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

EvidenceType = Literal[
    "data_quality",
    "spc_signal",
    "change_point",
    "group_difference",
    "factor_association",
    "event_comparison",
    "historical_case",
    "knowledge_document",
]
EvidenceConfidence = Literal["low", "medium", "high"]
EvidenceOrigin = Literal["deterministic_tool", "knowledge_source", "human"]


class EvidenceItem(BaseModel):
    """一条可引用、可追溯的质量调查证据。"""

    id: str = Field(pattern=r"^E-[A-Za-z0-9][A-Za-z0-9-]*$")
    evidence_type: EvidenceType
    title: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    metrics: dict[str, object] = Field(default_factory=dict)
    sample_size: int | None = Field(default=None, ge=0)
    filters: dict[str, object] = Field(default_factory=dict)
    source_refs: list[str] = Field(default_factory=list)
    confidence: EvidenceConfidence = "medium"
    origin: EvidenceOrigin = "deterministic_tool"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("title", "statement")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        candidate = value.strip()
        if not candidate:
            raise ValueError("text must not be empty")
        return candidate

    @field_validator("source_refs")
    @classmethod
    def deduplicate_source_refs(cls, values: list[str]) -> list[str]:
        """保留来源顺序，同时去掉空值和重复引用。"""
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            candidate = value.strip()
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            result.append(candidate)
        return result
