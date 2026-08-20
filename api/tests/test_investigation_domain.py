from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from api.app.domain import (
    EvidenceItem,
    Hypothesis,
    HypothesisDecision,
    InvestigationAction,
    InvestigationCase,
    InvestigationScope,
)


def _evidence(evidence_id: str = "E-001") -> EvidenceItem:
    return EvidenceItem(
        id=evidence_id,
        evidence_type="change_point",
        title="过程均值发生变化",
        statement="10:40 后外径均值上移 0.011 mm。",
        metrics={"before_mean": 19.999, "after_mean": 20.010, "delta": 0.011},
        sample_size=96,
        source_refs=["sample_data/investigation_demo.csv"],
        confidence="high",
    )


def _candidate_hypothesis() -> Hypothesis:
    return Hypothesis(
        id="H-001",
        statement="M02 的 4 号型腔或对应刀具可能导致均值上移。",
        supporting_evidence_ids=["E-001"],
        confidence="medium",
        verification_actions=["检查 M02-4 型腔定位状态", "复核刀具寿命"],
    )


def test_investigation_case_accepts_evidence_grounded_candidate() -> None:
    case = InvestigationCase(
        case_id="CASE-001",
        question="为什么外径不良率升高？",
        scope=InvestigationScope(quality_feature="outer_diameter"),
        state="investigating",
        evidence=[_evidence()],
        hypotheses=[_candidate_hypothesis()],
    )

    assert case.hypotheses[0].status == "candidate"
    assert case.hypotheses[0].supporting_evidence_ids == ["E-001"]


def test_investigation_case_rejects_unknown_evidence_reference() -> None:
    hypothesis = _candidate_hypothesis().model_copy(
        update={"supporting_evidence_ids": ["E-missing"]}
    )

    with pytest.raises(ValidationError, match="unknown evidence ids"):
        InvestigationCase(
            case_id="CASE-001",
            question="为什么外径不良率升高？",
            evidence=[_evidence()],
            hypotheses=[hypothesis],
        )


def test_investigation_case_rejects_duplicate_evidence_ids() -> None:
    with pytest.raises(ValidationError, match="duplicate evidence ids"):
        InvestigationCase(
            case_id="CASE-001",
            question="为什么外径不良率升高？",
            evidence=[_evidence(), _evidence()],
        )


def test_hypothesis_cannot_use_same_evidence_as_support_and_contradiction() -> None:
    with pytest.raises(ValidationError, match="both support and contradict"):
        Hypothesis(
            id="H-001",
            statement="设备因素可能导致异常。",
            supporting_evidence_ids=["E-001"],
            contradicting_evidence_ids=["E-001"],
        )


def test_confirmed_hypothesis_requires_human_decision() -> None:
    with pytest.raises(ValidationError, match="require a human decision"):
        Hypothesis(
            id="H-001",
            statement="M02-4 型腔定位偏移是根因。",
            supporting_evidence_ids=["E-001"],
            status="confirmed",
        )


def test_non_human_actor_cannot_confirm_root_cause() -> None:
    with pytest.raises(ValidationError):
        HypothesisDecision(
            outcome="confirmed",
            actor_type="ai",
            actor_id="report-agent",
            note="模型自动确认。",
        )


def test_human_can_confirm_hypothesis_with_traceable_decision() -> None:
    hypothesis = Hypothesis(
        id="H-001",
        statement="M02-4 型腔定位偏移是根因。",
        supporting_evidence_ids=["E-001"],
        status="confirmed",
        confidence="high",
        decision=HypothesisDecision(
            outcome="confirmed",
            actor_id="quality-engineer-01",
            note="现场复测并重新定位后，尺寸恢复正常。",
        ),
    )

    case = InvestigationCase(
        case_id="CASE-001",
        question="为什么外径不良率升高？",
        state="completed",
        evidence=[_evidence()],
        hypotheses=[hypothesis],
        conclusion="经现场验证，M02-4 型腔定位偏移为本次异常根因。",
    )

    assert case.hypotheses[0].decision is not None
    assert case.hypotheses[0].decision.actor_type == "human"


def test_action_references_must_resolve_inside_case() -> None:
    action = InvestigationAction(
        id="A-001",
        action_type="verification",
        title="复测问题型腔",
        rationale="验证型腔定位假设。",
        related_hypothesis_ids=["H-missing"],
        supporting_evidence_ids=["E-001"],
    )

    with pytest.raises(ValidationError, match="unknown hypothesis ids"):
        InvestigationCase(
            case_id="CASE-001",
            question="为什么外径不良率升高？",
            evidence=[_evidence()],
            actions=[action],
        )


def test_completed_case_requires_conclusion() -> None:
    with pytest.raises(ValidationError, match="require a conclusion"):
        InvestigationCase(
            case_id="CASE-001",
            question="为什么外径不良率升高？",
            state="completed",
        )


def test_failed_case_requires_error() -> None:
    with pytest.raises(ValidationError, match="require an error"):
        InvestigationCase(
            case_id="CASE-001",
            question="为什么外径不良率升高？",
            state="failed",
        )


def test_scope_rejects_reversed_time_range() -> None:
    start = datetime.now(UTC)

    with pytest.raises(ValidationError, match="end_at must not be earlier"):
        InvestigationScope(start_at=start, end_at=start - timedelta(hours=1))
