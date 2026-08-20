from pathlib import Path

from fastapi.testclient import TestClient

from api.app.agent.evidence_synthesizer import EvidenceSynthesizer
from api.app.agent.investigation_planner import InvestigationPlanner
from api.app.main import app
from api.app.services.investigation import ai_pipeline, cases
from api.app.services.investigation.repository import InvestigationRepository


client = TestClient(app)
DEMO_DATA_PATH = Path("sample_data/investigation_demo.csv")


class FakeStructuredModel:
    def __init__(self, response: object) -> None:
        self.response = response

    def with_structured_output(self, schema):
        return self

    def invoke(self, messages):
        return self.response


def _planner() -> InvestigationPlanner:
    return InvestigationPlanner(
        FakeStructuredModel(
            {
                "interpreted_question": "定位外径不良升高的生产关联因素。",
                "steps": [],
                "missing_information": ["缺少精确换刀事件时间"],
            }
        )
    )


def _synthesizer() -> EvidenceSynthesizer:
    return EvidenceSynthesizer(
        FakeStructuredModel(
            {
                "findings": [
                    {
                        "finding_type": "association",
                        "statement": "异常主要集中于 M02 的 4 号型腔。",
                        "evidence_ids": ["E-GROUP-MACHINE-ID-CAVITY-ID"],
                        "confidence": "high",
                    }
                ],
                "hypotheses": [
                    {
                        "key": "m02_cavity_tool",
                        "statement": "M02 的 4 号型腔或其对应刀具可能是优先验证的候选因素。",
                        "supporting_evidence_ids": [
                            "E-GROUP-MACHINE-ID-CAVITY-ID",
                            "E-FACTOR-RANKING",
                        ],
                        "contradicting_evidence_ids": ["E-GROUP-MATERIAL-LOT"],
                        "confidence": "medium",
                        "verification_actions": [
                            "检查 M02 的 4 号型腔定位状态",
                            "复核对应刀具的实际使用记录",
                        ],
                    }
                ],
                "containment_actions": [
                    {
                        "title": "隔离高风险组合的待检批次",
                        "rationale": "当前不良集中于特定设备与型腔组合，需先控制风险扩散。",
                        "supporting_evidence_ids": ["E-GROUP-MACHINE-ID-CAVITY-ID"],
                    }
                ],
                "missing_data": ["缺少精确换刀事件时间"],
            }
        )
    )


def _create_ready_case(repository: InvestigationRepository) -> str:
    payload = cases.create_investigation(
        question="为什么外径不良率升高？",
        file_name=DEMO_DATA_PATH.name,
        content=DEMO_DATA_PATH.read_bytes(),
        repository=repository,
        start_background=False,
    )
    case_id = payload["case_id"]
    initial = repository.load(case_id)
    source_path = repository.resolve_source_ref(case_id, initial.source_refs[0])
    completed = cases.run_investigation(case_id, source_path, repository=repository)
    assert completed.state == "ready", completed.error
    return case_id


def test_ai_investigation_service_persists_result_and_candidate_hypothesis(tmp_path: Path) -> None:
    repository = InvestigationRepository(tmp_path / "investigations")
    case_id = _create_ready_case(repository)

    result = cases.run_ai_investigation(
        case_id,
        repository=repository,
        planner=_planner(),
        synthesizer=_synthesizer(),
    )
    persisted_result = repository.load_ai_result(case_id)
    updated_case = repository.load(case_id)

    assert result == persisted_result
    assert result.findings[0].evidence_ids == ["E-GROUP-MACHINE-ID-CAVITY-ID"]
    assert updated_case.state == "waiting_for_user"
    assert updated_case.hypotheses[0].status == "candidate"
    assert updated_case.hypotheses[0].decision is None
    assert len(updated_case.actions) == 3


def test_hypothesis_decision_service_requires_one_final_human_decision(tmp_path: Path) -> None:
    repository = InvestigationRepository(tmp_path / "investigations")
    case_id = _create_ready_case(repository)
    cases.run_ai_investigation(
        case_id,
        repository=repository,
        planner=_planner(),
        synthesizer=_synthesizer(),
    )

    decided = cases.decide_hypothesis(
        case_id,
        "H-AI-001",
        outcome="confirmed",
        actor_id="quality-engineer-01",
        note="完成现场定位检查并复测后确认。",
        repository=repository,
    )

    hypothesis = decided.hypotheses[0]
    assert hypothesis.status == "confirmed"
    assert hypothesis.decision is not None
    assert hypothesis.decision.actor_type == "human"
    assert hypothesis.decision.actor_id == "quality-engineer-01"

    try:
        cases.decide_hypothesis(
            case_id,
            "H-AI-001",
            outcome="rejected",
            actor_id="quality-engineer-02",
            note="尝试覆盖已有决定。",
            repository=repository,
        )
    except ValueError as exc:
        assert "already has a final decision" in str(exc)
    else:
        raise AssertionError("a final hypothesis decision must not be overwritten")


def test_ai_and_hypothesis_decision_api(monkeypatch, tmp_path: Path) -> None:
    repository = InvestigationRepository(tmp_path / "investigations")
    monkeypatch.setattr(cases, "_DEFAULT_REPOSITORY", repository)
    monkeypatch.setattr(ai_pipeline, "build_investigation_planner", _planner)
    monkeypatch.setattr(ai_pipeline, "build_evidence_synthesizer", _synthesizer)
    case_id = _create_ready_case(repository)

    ai_response = client.post(f"/api/v1/investigations/{case_id}/ai")

    assert ai_response.status_code == 200, ai_response.text
    ai_payload = ai_response.json()
    assert ai_payload["hypotheses"][0]["status"] == "candidate"
    assert ai_payload["findings"][0]["evidence_ids"] == [
        "E-GROUP-MACHINE-ID-CAVITY-ID"
    ]

    persisted_response = client.get(f"/api/v1/investigations/{case_id}/ai")
    assert persisted_response.status_code == 200
    assert persisted_response.json() == ai_payload

    case_response = client.get(f"/api/v1/investigations/{case_id}")
    assert case_response.status_code == 200
    assert case_response.json()["state"] == "waiting_for_user"
    assert case_response.json()["hypotheses"][0]["status"] == "candidate"

    decision_response = client.post(
        f"/api/v1/investigations/{case_id}/hypotheses/H-AI-001/decision",
        json={
            "outcome": "confirmed",
            "actor_id": "quality-engineer-01",
            "note": "现场检查和复测已完成。",
        },
    )

    assert decision_response.status_code == 200, decision_response.text
    decision_payload = decision_response.json()
    assert decision_payload["hypotheses"][0]["status"] == "confirmed"
    assert decision_payload["hypotheses"][0]["decision"]["actor_type"] == "human"

    duplicate_response = client.post(
        f"/api/v1/investigations/{case_id}/hypotheses/H-AI-001/decision",
        json={
            "outcome": "rejected",
            "actor_id": "quality-engineer-02",
            "note": "尝试覆盖。",
        },
    )
    assert duplicate_response.status_code == 409


def test_ai_result_endpoint_returns_not_found_before_ai_run(monkeypatch, tmp_path: Path) -> None:
    repository = InvestigationRepository(tmp_path / "investigations")
    monkeypatch.setattr(cases, "_DEFAULT_REPOSITORY", repository)
    case_id = _create_ready_case(repository)

    response = client.get(f"/api/v1/investigations/{case_id}/ai")

    assert response.status_code == 404
