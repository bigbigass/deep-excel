"""质量异常调查领域模型。

这组模型把系统的核心从“生成一份报告”转成“管理一次有证据约束的调查”：
证据支持或反驳假设，验证动作推动假设状态变化，最终结论必须保留追溯关系。
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime
from typing import Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from api.app.domain.evidence import EvidenceConfidence, EvidenceItem

InvestigationState = Literal[
    "created",
    "mapping_required",
    "ready",
    "investigating",
    "waiting_for_user",
    "completed",
    "failed",
]
HypothesisStatus = Literal[
    "candidate",
    "under_verification",
    "confirmed",
    "rejected",
]
ActionType = Literal["containment", "verification", "corrective"]
ActionStatus = Literal["proposed", "accepted", "in_progress", "completed", "dismissed"]

_EVIDENCE_ID_PATTERN = re.compile(r"^E-[A-Za-z0-9][A-Za-z0-9-]*$")
_HYPOTHESIS_ID_PATTERN = re.compile(r"^H-[A-Za-z0-9][A-Za-z0-9-]*$")


def _strip_required_text(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        raise ValueError("text must not be empty")
    return candidate


def _strip_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.strip()
    return candidate or None


def _normalize_unique_strings(
    values: list[str],
    *,
    label: str,
    pattern: re.Pattern[str] | None = None,
    require_one: bool = False,
) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        candidate = value.strip()
        if not candidate:
            continue
        if pattern is not None and not pattern.fullmatch(candidate):
            raise ValueError(f"invalid {label}: {candidate}")
        if candidate in seen:
            raise ValueError(f"duplicate {label}: {candidate}")
        seen.add(candidate)
        normalized.append(candidate)
    if require_one and not normalized:
        raise ValueError(f"{label} must contain at least one value")
    return normalized


class InvestigationScope(BaseModel):
    """一次调查所覆盖的质量特征、时间范围和业务过滤条件。"""

    quality_feature: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    filters: dict[str, object] = Field(default_factory=dict)

    @field_validator("quality_feature")
    @classmethod
    def normalize_quality_feature(cls, value: str | None) -> str | None:
        return _strip_optional_text(value)

    @model_validator(mode="after")
    def validate_time_range(self) -> Self:
        if self.start_at is not None and self.end_at is not None and self.end_at < self.start_at:
            raise ValueError("end_at must not be earlier than start_at")
        return self


class HypothesisDecision(BaseModel):
    """人工对候选根因作出的最终确认或排除决定。

    第一版明确禁止 AI 或普通统计工具直接确认根因，因此 actor_type 只允许 human。
    """

    outcome: Literal["confirmed", "rejected"]
    actor_type: Literal["human"] = "human"
    actor_id: str = Field(min_length=1)
    note: str = Field(min_length=1)
    decided_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("actor_id", "note")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        return _strip_required_text(value)


class Hypothesis(BaseModel):
    """由证据支持、仍需要验证的候选根因。"""

    id: str = Field(pattern=r"^H-[A-Za-z0-9][A-Za-z0-9-]*$")
    statement: str = Field(min_length=1)
    supporting_evidence_ids: list[str] = Field(min_length=1)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    confidence: EvidenceConfidence = "medium"
    status: HypothesisStatus = "candidate"
    verification_actions: list[str] = Field(default_factory=list)
    decision: HypothesisDecision | None = None

    @field_validator("statement")
    @classmethod
    def normalize_statement(cls, value: str) -> str:
        return _strip_required_text(value)

    @field_validator("supporting_evidence_ids")
    @classmethod
    def normalize_supporting_evidence_ids(cls, values: list[str]) -> list[str]:
        return _normalize_unique_strings(
            values,
            label="supporting evidence id",
            pattern=_EVIDENCE_ID_PATTERN,
            require_one=True,
        )

    @field_validator("contradicting_evidence_ids")
    @classmethod
    def normalize_contradicting_evidence_ids(cls, values: list[str]) -> list[str]:
        return _normalize_unique_strings(
            values,
            label="contradicting evidence id",
            pattern=_EVIDENCE_ID_PATTERN,
        )

    @field_validator("verification_actions")
    @classmethod
    def normalize_verification_actions(cls, values: list[str]) -> list[str]:
        return _normalize_unique_strings(values, label="verification action")

    @model_validator(mode="after")
    def validate_decision_and_evidence_roles(self) -> Self:
        supporting = set(self.supporting_evidence_ids)
        contradicting = set(self.contradicting_evidence_ids)
        overlap = supporting & contradicting
        if overlap:
            raise ValueError(f"evidence cannot both support and contradict a hypothesis: {sorted(overlap)}")

        terminal_status = self.status in {"confirmed", "rejected"}
        if terminal_status and self.decision is None:
            raise ValueError("confirmed or rejected hypotheses require a human decision")
        if not terminal_status and self.decision is not None:
            raise ValueError("candidate hypotheses must not contain a final decision")
        if self.decision is not None and self.decision.outcome != self.status:
            raise ValueError("hypothesis status must match the decision outcome")
        return self


class InvestigationAction(BaseModel):
    """调查中的围堵、验证或纠正动作。"""

    id: str = Field(pattern=r"^A-[A-Za-z0-9][A-Za-z0-9-]*$")
    action_type: ActionType
    title: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    status: ActionStatus = "proposed"
    related_hypothesis_ids: list[str] = Field(default_factory=list)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    owner: str | None = None
    due_at: datetime | None = None
    completed_at: datetime | None = None

    @field_validator("title", "rationale")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        return _strip_required_text(value)

    @field_validator("owner")
    @classmethod
    def normalize_owner(cls, value: str | None) -> str | None:
        return _strip_optional_text(value)

    @field_validator("related_hypothesis_ids")
    @classmethod
    def normalize_related_hypothesis_ids(cls, values: list[str]) -> list[str]:
        return _normalize_unique_strings(
            values,
            label="related hypothesis id",
            pattern=_HYPOTHESIS_ID_PATTERN,
        )

    @field_validator("supporting_evidence_ids")
    @classmethod
    def normalize_supporting_evidence_ids(cls, values: list[str]) -> list[str]:
        return _normalize_unique_strings(
            values,
            label="action supporting evidence id",
            pattern=_EVIDENCE_ID_PATTERN,
        )

    @model_validator(mode="after")
    def validate_completion(self) -> Self:
        if self.status == "completed" and self.completed_at is None:
            raise ValueError("completed actions require completed_at")
        if self.status != "completed" and self.completed_at is not None:
            raise ValueError("completed_at is only allowed for completed actions")
        return self


class InvestigationCase(BaseModel):
    """一次完整、可持久化、可追溯的质量异常调查。"""

    case_id: str = Field(pattern=r"^CASE-[A-Za-z0-9][A-Za-z0-9-]*$")
    question: str = Field(min_length=1)
    scope: InvestigationScope = Field(default_factory=InvestigationScope)
    state: InvestigationState = "created"
    source_refs: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    actions: list[InvestigationAction] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    conclusion: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        return _strip_required_text(value)

    @field_validator("source_refs")
    @classmethod
    def normalize_source_refs(cls, values: list[str]) -> list[str]:
        return _normalize_unique_strings(values, label="source reference")

    @field_validator("missing_data")
    @classmethod
    def normalize_missing_data(cls, values: list[str]) -> list[str]:
        return _normalize_unique_strings(values, label="missing data item")

    @field_validator("conclusion", "error")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return _strip_optional_text(value)

    @model_validator(mode="after")
    def validate_case_integrity(self) -> Self:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not be earlier than created_at")

        evidence_ids = [item.id for item in self.evidence]
        hypothesis_ids = [item.id for item in self.hypotheses]
        action_ids = [item.id for item in self.actions]
        self._require_unique_ids(evidence_ids, "evidence")
        self._require_unique_ids(hypothesis_ids, "hypothesis")
        self._require_unique_ids(action_ids, "action")

        known_evidence_ids = set(evidence_ids)
        known_hypothesis_ids = set(hypothesis_ids)
        for hypothesis in self.hypotheses:
            referenced = set(hypothesis.supporting_evidence_ids) | set(hypothesis.contradicting_evidence_ids)
            unknown = referenced - known_evidence_ids
            if unknown:
                raise ValueError(
                    f"hypothesis {hypothesis.id} references unknown evidence ids: {sorted(unknown)}"
                )

        for action in self.actions:
            unknown_evidence = set(action.supporting_evidence_ids) - known_evidence_ids
            if unknown_evidence:
                raise ValueError(f"action {action.id} references unknown evidence ids: {sorted(unknown_evidence)}")
            unknown_hypotheses = set(action.related_hypothesis_ids) - known_hypothesis_ids
            if unknown_hypotheses:
                raise ValueError(
                    f"action {action.id} references unknown hypothesis ids: {sorted(unknown_hypotheses)}"
                )

        if self.state == "completed" and not self.conclusion:
            raise ValueError("completed investigations require a conclusion")
        if self.state == "failed" and not self.error:
            raise ValueError("failed investigations require an error")
        if self.state != "failed" and self.error is not None:
            raise ValueError("error is only allowed when the investigation state is failed")
        return self

    @staticmethod
    def _require_unique_ids(values: list[str], label: str) -> None:
        duplicates = sorted(value for value, count in Counter(values).items() if count > 1)
        if duplicates:
            raise ValueError(f"duplicate {label} ids: {duplicates}")
