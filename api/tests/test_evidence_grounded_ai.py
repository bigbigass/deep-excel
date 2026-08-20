from pathlib import Path

import pandas as pd
import pytest

from api.app.agent.evidence_synthesizer import (
    EvidenceSynthesizer,
    materialize_synthesis,
    validate_synthesis_grounding,
)
from api.app.agent.investigation_planner import InvestigationPlanner
from api.app.domain.ai import InvestigationSynthesisDraft
from api.app.services.investigation.ai_pipeline import (
    apply_ai_result_to_case,
    run_evidence_grounded_ai,
)
from api.app.services.investigation.baseline import run_baseline_investigation


DEMO_DATA_PATH = Path("sample_data/investigation_demo.csv")


class FakeStructuredModel:
    def __init__(self, response: object) -> None:
        self.response = response
        self.schema = None
        self.messages = None
        self.invoke_count = 0

    def with_structured_output(self, schema):
        self.schema = schema
        return self

    def invoke(self, messages):
        self.messages = messages
        self.invoke_count += 1
        return self.response


def _load_demo_data() -> pd.DataFrame:
    return pd.read_csv(DEMO_DATA_PATH, parse_dates=["measured_at"])


def _baseline_case():
    return run_baseline_investigation(
        _load_demo_data(),
        question="为什么外径不良率升高？",
        case_id="CASE-AI-TEST",
        source_refs=[str(DEMO_DATA_PATH)],
    )


def _valid_synthesis_payload() -> dict[str, object]:
    return {
        "findings": [
            {
                "finding_type": "association",
                "statement": "异常主要集中于 M02 的 4 号型腔。",
                "evidence_ids": ["E-GROUP-MACHINE-ID-CAVITY-ID"],
                "confidence": "high",
            },
            {
                "finding_type": "association",
                "statement": "材料批次未显示显著差异。",
                "evidence_ids": ["E-GROUP-MATERIAL-LOT"],
                "confidence": "low",
            },
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


def test_evidence_grounded_pipeline_keeps_root_cause_as_candidate() -> None:
    frame = _load_demo_data()
    case = _baseline_case()
    planner_model = FakeStructuredModel(
        {
            "interpreted_question": "定位外径不良升高的生产关联因素。",
            "steps": [],
            "missing_information": ["缺少精确换刀事件时间"],
        }
    )
    synthesis_model = FakeStructuredModel(_valid_synthesis_payload())

    result = run_evidence_grounded_ai(
        case,
        frame,
        planner=InvestigationPlanner(planner_model),
        synthesizer=EvidenceSynthesizer(synthesis_model),
    )
    updated = apply_ai_result_to_case(case, result)

    assert result.plan.steps == []
    assert result.added_evidence == []
    assert len(result.findings) == 2
    assert result.findings[0].evidence_ids == ["E-GROUP-MACHINE-ID-CAVITY-ID"]
    assert len(result.hypotheses) == 1
    assert result.hypotheses[0].status == "candidate"
    assert result.hypotheses[0].decision is None
    assert result.hypotheses[0].supporting_evidence_ids == [
        "E-GROUP-MACHINE-ID-CAVITY-ID",
        "E-FACTOR-RANKING",
    ]
    assert [action.action_type for action in result.actions] == [
        "containment",
        "verification",
        "verification",
    ]
    assert updated.state == "waiting_for_user"
    assert updated.conclusion is None
    assert updated.hypotheses[0].status == "candidate"
    assert all(action.status == "proposed" for action in updated.actions)
    assert updated.missing_data == ["缺少精确换刀事件时间"]
    assert planner_model.invoke_count == 1
    assert synthesis_model.invoke_count == 1


def test_synthesis_rejects_unknown_evidence_reference() -> None:
    case = _baseline_case()
    payload = _valid_synthesis_payload()
    payload["findings"][0]["evidence_ids"] = ["E-NOT-REAL"]
    draft = InvestigationSynthesisDraft.model_validate(payload)

    with pytest.raises(ValueError, match="unknown evidence ids"):
        validate_synthesis_grounding(draft, evidence=case.evidence)


def test_synthesis_rejects_confirmed_root_cause_language() -> None:
    case = _baseline_case()
    payload = _valid_synthesis_payload()
    payload["hypotheses"][0]["statement"] = "已确认 M02 的 4 号型腔是根因，可能需要处理。"
    draft = InvestigationSynthesisDraft.model_validate(payload)

    with pytest.raises(ValueError, match="confirmed root-cause language"):
        validate_synthesis_grounding(draft, evidence=case.evidence)


def test_synthesis_rejects_fabricated_numeric_claim() -> None:
    case = _baseline_case()
    payload = _valid_synthesis_payload()
    payload["findings"][0]["statement"] = "M02 的 4 号型腔不良率为 99.9%。"
    draft = InvestigationSynthesisDraft.model_validate(payload)

    with pytest.raises(ValueError, match="not present in cited evidence"):
        validate_synthesis_grounding(draft, evidence=case.evidence)


def test_synthesis_requires_explicit_uncertainty_language() -> None:
    case = _baseline_case()
    payload = _valid_synthesis_payload()
    payload["hypotheses"][0]["statement"] = "M02 的 4 号型腔及其对应刀具需要立即更换。"
    draft = InvestigationSynthesisDraft.model_validate(payload)

    with pytest.raises(ValueError, match="explicit uncertainty language"):
        validate_synthesis_grounding(draft, evidence=case.evidence)


def test_materialization_avoids_existing_ids() -> None:
    case = _baseline_case()
    draft = InvestigationSynthesisDraft.model_validate(_valid_synthesis_payload())

    findings, hypotheses, actions = materialize_synthesis(
        draft,
        evidence=case.evidence,
        existing_finding_ids={"F-AI-001"},
        existing_hypothesis_ids={"H-AI-001"},
        existing_action_ids={"A-AI-001", "A-AI-002"},
    )

    assert findings[0].id == "F-AI-002"
    assert hypotheses[0].id == "H-AI-002"
    assert actions[0].id == "A-AI-003"
    assert all(hypothesis.status == "candidate" for hypothesis in hypotheses)


def test_pipeline_rejects_non_whitelisted_planner_step_before_synthesis() -> None:
    frame = _load_demo_data()
    case = _baseline_case()
    planner_model = FakeStructuredModel(
        {
            "interpreted_question": "尝试执行未授权操作。",
            "steps": [
                {
                    "tool_name": "run_shell",
                    "arguments": {"command": "rm -rf /"},
                    "reason": "尝试直接执行系统命令。",
                }
            ],
            "missing_information": [],
        }
    )
    synthesis_model = FakeStructuredModel(_valid_synthesis_payload())

    with pytest.raises(ValueError, match="unknown investigation tool"):
        run_evidence_grounded_ai(
            case,
            frame,
            planner=InvestigationPlanner(planner_model),
            synthesizer=EvidenceSynthesizer(synthesis_model),
        )

    assert synthesis_model.invoke_count == 0
