from pathlib import Path

import pandas as pd
import pytest

from api.app.agent.evidence_synthesizer import EvidenceGroundedSynthesizer
from api.app.agent.investigation_planner import InvestigationPlanner
from api.app.config import get_settings
from api.app.services.investigation.ai_cases import run_persisted_ai_investigation
from api.app.services.investigation.baseline import run_baseline_investigation
from api.app.services.investigation.decisions import decide_hypothesis
from api.app.services.investigation.repository import InvestigationRepository


DEMO_DATA_PATH = Path("sample_data/investigation_demo.csv")


class FakeStructuredModel:
    def __init__(self, output: dict[str, object]) -> None:
        self.output = output

    def with_structured_output(self, schema):
        return self

    def invoke(self, messages):
        return self.output


def _repository(monkeypatch, tmp_path: Path) -> InvestigationRepository:
    monkeypatch.setenv("DEEPEXCEL_OUTPUTS_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    return InvestigationRepository()


def _ready_case(repository: InvestigationRepository):
    frame = pd.read_csv(DEMO_DATA_PATH, parse_dates=["measured_at"])
    case = run_baseline_investigation(
        frame,
        question="为什么外径不良率升高？",
        case_id="CASE-PERSISTED-AI",
        source_refs=[str(DEMO_DATA_PATH)],
    )
    repository.save(case)
    return case


def _planner() -> InvestigationPlanner:
    return InvestigationPlanner(
        model=FakeStructuredModel(
            {
                "interpreted_question": "根据现有证据形成待验证假设。",
                "steps": [],
                "missing_information": [],
            }
        )
    )


def _synthesizer() -> EvidenceGroundedSynthesizer:
    return EvidenceGroundedSynthesizer(
        model=FakeStructuredModel(
            {
                "findings": [
                    {
                        "statement": "异常具有明确的时间变化和生产组合集中性。",
                        "evidence_ids": [
                            "E-CHANGE-POINT",
                            "E-GROUP-MACHINE-ID-CAVITY-ID",
                        ],
                    }
                ],
                "hypotheses": [
                    {
                        "id": "H-PERSISTED-001",
                        "statement": "设备型腔或刀具状态是优先验证的候选因素。",
                        "supporting_evidence_ids": [
                            "E-GROUP-MACHINE-ID-CAVITY-ID",
                            "E-FACTOR-RANKING",
                        ],
                        "contradicting_evidence_ids": [
                            "E-GROUP-MATERIAL-LOT"
                        ],
                        "confidence": "high",
                        "verification_actions": ["检查型腔定位和刀具磨损。"],
                    }
                ],
                "actions": [
                    {
                        "id": "A-PERSISTED-001",
                        "action_type": "verification",
                        "title": "开展现场检查",
                        "rationale": "现有分组和因素证据支持优先检查设备型腔与刀具。",
                        "supporting_evidence_ids": [
                            "E-GROUP-MACHINE-ID-CAVITY-ID",
                            "E-FACTOR-RANKING",
                        ],
                        "related_hypothesis_ids": ["H-PERSISTED-001"],
                    }
                ],
                "missing_data": ["缺少维修事件时间。"],
            }
        )
    )


def test_persisted_ai_run_saves_waiting_for_user_case(monkeypatch, tmp_path: Path) -> None:
    repository = _repository(monkeypatch, tmp_path)
    case = _ready_case(repository)

    result = run_persisted_ai_investigation(
        case.case_id,
        repository=repository,
        planner=_planner(),
        synthesizer=_synthesizer(),
    )

    persisted = repository.load(case.case_id)
    assert result.case.state == "waiting_for_user"
    assert persisted.state == "waiting_for_user"
    assert persisted.hypotheses[0].id == "H-PERSISTED-001"
    assert persisted.hypotheses[0].status == "candidate"
    assert persisted.hypotheses[0].decision is None


def test_human_can_confirm_candidate_with_auditable_decision(monkeypatch, tmp_path: Path) -> None:
    repository = _repository(monkeypatch, tmp_path)
    case = _ready_case(repository)
    run_persisted_ai_investigation(
        case.case_id,
        repository=repository,
        planner=_planner(),
        synthesizer=_synthesizer(),
    )

    updated = decide_hypothesis(
        case.case_id,
        "H-PERSISTED-001",
        outcome="confirmed",
        actor_id="quality-engineer-01",
        note="现场检查确认型腔定位块松动，调整后复测恢复正常。",
        repository=repository,
    )

    hypothesis = updated.hypotheses[0]
    assert hypothesis.status == "confirmed"
    assert hypothesis.decision is not None
    assert hypothesis.decision.actor_type == "human"
    assert hypothesis.decision.actor_id == "quality-engineer-01"
    assert repository.load(case.case_id).hypotheses[0].status == "confirmed"


def test_final_hypothesis_decision_cannot_be_overwritten(monkeypatch, tmp_path: Path) -> None:
    repository = _repository(monkeypatch, tmp_path)
    case = _ready_case(repository)
    run_persisted_ai_investigation(
        case.case_id,
        repository=repository,
        planner=_planner(),
        synthesizer=_synthesizer(),
    )
    decide_hypothesis(
        case.case_id,
        "H-PERSISTED-001",
        outcome="rejected",
        actor_id="quality-engineer-01",
        note="现场检查和复测未支持该假设。",
        repository=repository,
    )

    with pytest.raises(ValueError, match="already has a final decision"):
        decide_hypothesis(
            case.case_id,
            "H-PERSISTED-001",
            outcome="confirmed",
            actor_id="quality-engineer-02",
            note="尝试覆盖既有决定。",
            repository=repository,
        )
