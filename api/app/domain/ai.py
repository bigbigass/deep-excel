"""Evidence-grounded AI planning and synthesis models."""

from __future__ import annotations

import re
from collections import Counter
from typing import Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from api.app.domain.evidence import EvidenceConfidence, EvidenceItem
from api.app.domain.investigation import Hypothesis, InvestigationAction

FindingType = Literal["fact", "association"]
ToolAvailability = Literal["available", "unavailable"]

_EVIDENCE_ID_PATTERN = re.compile(r"^E-[A-Za-z0-9][A-Za-z0-9-]*$")


def _required_text(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        raise ValueError("text must not be empty")
    return candidate


def _unique_text(values: list[str], *, label: str, require_one: bool = False) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        candidate = value.strip()
        if not candidate:
            continue
        if candidate in seen:
            raise ValueError(f"duplicate {label}: {candidate}")
        seen.add(candidate)
        result.append(candidate)
    if require_one and not result:
        raise ValueError(f"{label} must contain at least one value")
    return result


def _evidence_ids(values: list[str], *, label: str, require_one: bool = False) -> list[str]:
    normalized = _unique_text(values, label=label, require_one=require_one)
    invalid = [value for value in normalized if not _EVIDENCE_ID_PATTERN.fullmatch(value)]
    if invalid:
        raise ValueError(f"invalid {label}: {invalid}")
    return normalized


class InvestigationToolDescription(BaseModel):
    """A safe tool capability exposed to the planning model."""

    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    description: str = Field(min_length=1)
    output_evidence_type: str = Field(min_length=1)
    availability: ToolAvailability = "available"
    unavailable_reason: str | None = None
    argument_schema: dict[str, object] = Field(default_factory=dict)

    @field_validator("description", "output_evidence_type")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("unavailable_reason")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = value.strip()
        return candidate or None

    @model_validator(mode="after")
    def validate_availability(self) -> Self:
        if self.availability == "unavailable" and not self.unavailable_reason:
            raise ValueError("unavailable tools require unavailable_reason")
        if self.availability == "available" and self.unavailable_reason is not None:
            raise ValueError("available tools must not define unavailable_reason")
        return self


class InvestigationToolCall(BaseModel):
    """One whitelisted deterministic analysis step selected by AI."""

    tool_name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    arguments: dict[str, object] = Field(default_factory=dict)
    reason: str = Field(min_length=1)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        return _required_text(value)


class InvestigationPlan(BaseModel):
    """Structured, bounded investigation plan produced by the model."""

    interpreted_question: str = Field(min_length=1)
    steps: list[InvestigationToolCall] = Field(default_factory=list, max_length=6)
    missing_information: list[str] = Field(default_factory=list)

    @field_validator("interpreted_question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("missing_information")
    @classmethod
    def normalize_missing_information(cls, values: list[str]) -> list[str]:
        return _unique_text(values, label="missing information")


class InvestigationFindingDraft(BaseModel):
    """Model-proposed finding before code assigns a stable identifier."""

    finding_type: FindingType
    statement: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    confidence: EvidenceConfidence = "medium"

    @field_validator("statement")
    @classmethod
    def normalize_statement(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("evidence_ids")
    @classmethod
    def normalize_evidence_ids(cls, values: list[str]) -> list[str]:
        return _evidence_ids(values, label="finding evidence id", require_one=True)


class InvestigationFinding(BaseModel):
    """A synthesized finding that remains explicitly linked to evidence."""

    id: str = Field(pattern=r"^F-[A-Za-z0-9][A-Za-z0-9-]*$")
    finding_type: FindingType
    statement: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    confidence: EvidenceConfidence = "medium"

    @field_validator("statement")
    @classmethod
    def normalize_statement(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("evidence_ids")
    @classmethod
    def normalize_evidence_ids(cls, values: list[str]) -> list[str]:
        return _evidence_ids(values, label="finding evidence id", require_one=True)


class HypothesisDraft(BaseModel):
    """A candidate root-cause hypothesis; final status is assigned by code."""

    key: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    statement: str = Field(min_length=1)
    supporting_evidence_ids: list[str] = Field(min_length=1)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    confidence: EvidenceConfidence = "medium"
    verification_actions: list[str] = Field(min_length=1)

    @field_validator("statement")
    @classmethod
    def normalize_statement(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("supporting_evidence_ids")
    @classmethod
    def normalize_supporting_ids(cls, values: list[str]) -> list[str]:
        return _evidence_ids(values, label="supporting evidence id", require_one=True)

    @field_validator("contradicting_evidence_ids")
    @classmethod
    def normalize_contradicting_ids(cls, values: list[str]) -> list[str]:
        return _evidence_ids(values, label="contradicting evidence id")

    @field_validator("verification_actions")
    @classmethod
    def normalize_verification_actions(cls, values: list[str]) -> list[str]:
        return _unique_text(values, label="verification action", require_one=True)

    @model_validator(mode="after")
    def validate_evidence_roles(self) -> Self:
        overlap = set(self.supporting_evidence_ids) & set(self.contradicting_evidence_ids)
        if overlap:
            raise ValueError(f"evidence cannot both support and contradict a hypothesis: {sorted(overlap)}")
        return self


class ContainmentActionDraft(BaseModel):
    """Immediate containment action suggested from current evidence."""

    title: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    supporting_evidence_ids: list[str] = Field(min_length=1)

    @field_validator("title", "rationale")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("supporting_evidence_ids")
    @classmethod
    def normalize_evidence_ids(cls, values: list[str]) -> list[str]:
        return _evidence_ids(values, label="action supporting evidence id", require_one=True)


class InvestigationSynthesisDraft(BaseModel):
    """Structured AI synthesis before grounding validation and ID assignment."""

    findings: list[InvestigationFindingDraft] = Field(default_factory=list, max_length=8)
    hypotheses: list[HypothesisDraft] = Field(default_factory=list, max_length=4)
    containment_actions: list[ContainmentActionDraft] = Field(default_factory=list, max_length=4)
    missing_data: list[str] = Field(default_factory=list)

    @field_validator("missing_data")
    @classmethod
    def normalize_missing_data(cls, values: list[str]) -> list[str]:
        return _unique_text(values, label="missing data item")

    @model_validator(mode="after")
    def validate_hypothesis_keys(self) -> Self:
        keys = [item.key for item in self.hypotheses]
        duplicates = sorted(value for value, count in Counter(keys).items() if count > 1)
        if duplicates:
            raise ValueError(f"duplicate hypothesis keys: {duplicates}")
        return self


class EvidenceGroundedInvestigationResult(BaseModel):
    """Validated output of the bounded AI investigation stage."""

    plan: InvestigationPlan
    added_evidence: list[EvidenceItem] = Field(default_factory=list)
    findings: list[InvestigationFinding] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    actions: list[InvestigationAction] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)

    @field_validator("missing_data")
    @classmethod
    def normalize_missing_data(cls, values: list[str]) -> list[str]:
        return _unique_text(values, label="missing data item")
