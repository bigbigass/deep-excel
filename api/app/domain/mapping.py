"""客户质量数据的语义字段映射模型。"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator

ColumnRole = Literal[
    "sample_id",
    "batch_id",
    "measured_at",
    "sequence_index",
    "quality_feature",
    "measurement_value",
    "target",
    "usl",
    "lsl",
    "machine_id",
    "station_id",
    "cavity_id",
    "shift",
    "operator_id",
    "material_lot",
    "tool_id",
    "tool_cycles",
    "ignore",
]
MappingOrigin = Literal["canonical", "rule", "ai", "human"]
MappingStatus = Literal["pending", "confirmed"]
MappingGeneratedBy = Literal["canonical", "deterministic", "ai", "hybrid", "human"]

_REQUIRED_ROLES: set[ColumnRole] = {"measurement_value"}


def _required_text(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        raise ValueError("text must not be empty")
    return candidate


def _unique_text(values: list[str], *, label: str) -> list[str]:
    normalized = [_required_text(value) for value in values]
    duplicates = sorted(value for value, count in Counter(normalized).items() if count > 1)
    if duplicates:
        raise ValueError(f"duplicate {label}: {duplicates}")
    return normalized


class ColumnMapping(BaseModel):
    """一个源字段到调查标准字段的语义映射。"""

    source_column: str = Field(min_length=1)
    role: ColumnRole
    confidence: float = Field(ge=0, le=1)
    reasoning: str = Field(min_length=1)
    origin: MappingOrigin

    @field_validator("source_column", "reasoning")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        return _required_text(value)


class SchemaMappingProposal(BaseModel):
    """一份可审阅、可人工修订并最终确认的字段映射。"""

    file_name: str = Field(min_length=1)
    source_columns: list[str] = Field(min_length=1)
    mappings: list[ColumnMapping] = Field(min_length=1)
    status: MappingStatus = "pending"
    generated_by: MappingGeneratedBy = "deterministic"
    missing_required_roles: list[ColumnRole] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None
    revision: int = Field(default=1, ge=1)

    @field_validator("file_name")
    @classmethod
    def normalize_file_name(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("source_columns")
    @classmethod
    def normalize_source_columns(cls, values: list[str]) -> list[str]:
        return _unique_text(values, label="source column")

    @field_validator("warnings")
    @classmethod
    def normalize_warnings(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            candidate = value.strip()
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            normalized.append(candidate)
        return normalized

    @field_validator("confirmed_by")
    @classmethod
    def normalize_confirmed_by(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = value.strip()
        return candidate or None

    @model_validator(mode="after")
    def validate_mapping_integrity(self) -> Self:
        source_set = set(self.source_columns)
        mapped_sources = [item.source_column for item in self.mappings]
        if set(mapped_sources) != source_set:
            missing = sorted(source_set - set(mapped_sources))
            unknown = sorted(set(mapped_sources) - source_set)
            raise ValueError(
                f"mapping must cover every source column exactly once; missing={missing}, unknown={unknown}"
            )
        duplicate_sources = sorted(
            value for value, count in Counter(mapped_sources).items() if count > 1
        )
        if duplicate_sources:
            raise ValueError(f"duplicate mapped source columns: {duplicate_sources}")

        assigned_roles = [item.role for item in self.mappings if item.role != "ignore"]
        duplicate_roles = sorted(
            value for value, count in Counter(assigned_roles).items() if count > 1
        )
        if duplicate_roles:
            raise ValueError(f"each supported role may be mapped only once: {duplicate_roles}")

        actual_missing = sorted(_REQUIRED_ROLES - set(assigned_roles))
        declared_missing = sorted(set(self.missing_required_roles))
        if actual_missing != declared_missing:
            raise ValueError(
                f"missing_required_roles must match actual mappings: expected {actual_missing}"
            )

        if self.status == "confirmed":
            if actual_missing:
                raise ValueError("confirmed mappings require all required roles")
            if not self.confirmed_by or self.confirmed_at is None:
                raise ValueError("confirmed mappings require confirmed_by and confirmed_at")
        elif self.confirmed_by is not None or self.confirmed_at is not None:
            raise ValueError("pending mappings must not contain confirmation metadata")
        return self

    def mapping_for_role(self, role: ColumnRole) -> ColumnMapping | None:
        return next((item for item in self.mappings if item.role == role), None)

    @property
    def requires_confirmation(self) -> bool:
        if self.status == "confirmed" or self.missing_required_roles:
            return self.status != "confirmed"
        return any(
            item.role != "ignore"
            and (
                item.origin != "canonical"
                or item.source_column != item.role
                or item.confidence < 1.0
            )
            for item in self.mappings
        )


class MappingAssignment(BaseModel):
    source_column: str = Field(min_length=1)
    role: ColumnRole

    @field_validator("source_column")
    @classmethod
    def normalize_source_column(cls, value: str) -> str:
        return _required_text(value)


class SchemaMappingConfirmation(BaseModel):
    """用户提交的最终字段角色和责任记录。"""

    mappings: list[MappingAssignment] = Field(min_length=1)
    actor_id: str = Field(min_length=1)

    @field_validator("actor_id")
    @classmethod
    def normalize_actor_id(cls, value: str) -> str:
        return _required_text(value)

    @model_validator(mode="after")
    def validate_assignments(self) -> Self:
        sources = [item.source_column for item in self.mappings]
        duplicate_sources = sorted(value for value, count in Counter(sources).items() if count > 1)
        if duplicate_sources:
            raise ValueError(f"duplicate mapping assignments: {duplicate_sources}")
        roles = [item.role for item in self.mappings if item.role != "ignore"]
        duplicate_roles = sorted(value for value, count in Counter(roles).items() if count > 1)
        if duplicate_roles:
            raise ValueError(f"each supported role may be assigned only once: {duplicate_roles}")
        return self


def confirmed_at_now() -> datetime:
    return datetime.now(UTC)
