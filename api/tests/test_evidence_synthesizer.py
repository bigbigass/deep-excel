from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError

from api.app.agent.evidence_synthesizer import (
    EvidenceGroundedSynthesizer,
    apply_synthesis,
)
from api.app.services.investigation.baseline import run_baseline_investigation


DEMO_DATA_PATH = Path("sample_data/investigation_demo.csv")


class FakeStructuredModel:
    def __init__(self, output: dict[str, object]) -> None:
        self.output = output
        self.schema = None

    def with_structured_output(self, schema):
        self.schema = schema
        return self

    def invoke(self, messages):
        return self.output


def _build_case():
    frame = pd.read_csv(DEMO_DATA_PATH, parse_dates=["measured_at"])
    return run_baseline_investigation(
        frame,
        question="为什么外径不良率升高？",
        case_id="CASE-AI-TEST",
        source_refs=[str(DEMO_DATA_PATH)],
    )


def _valid_synthesis_output() -> dict[str, object]:
    return {
        "findings": [
            {
                "statement": "过程出现了显著均值变化，且不良集中在特定设备与型腔组合。",
                "evidence_ids": [
                    "E-CHANGE-POINT",
                    "E-GROUP-MACHINE-ID-CAVITY-ID",
                ],
            }
        ],
        "hypotheses": [
            {
                "id": "H-001",
                "statement": "设备型腔状态或其对应刀具寿命可能是优先验证的候选因素。",
                "supporting_evidence_ids": [
                    "E-GROUP-MACHINE-ID-CAVITY-ID",
                    "E-FACTOR-RANKING",
                ],
                "contradicting_evidence_ids": ["E-GROUP-MATERIAL-LOT"],
                "confidence": "high",
                "verification_actions": [
                    "检查高风险设备型腔的定位与磨损状态。",
                    "复核刀具实际使用次数，并在调整后连续复测 30 件。",
                ],
            }
        ],
        "actions": [
            {
                "id": "A-001",
                "action_type": "containment",
                "title": "隔离高风险生产组合的待检品",
                "rationale": "分组证据显示不良集中在该生产组合，应先限制风险扩散。",
                "supporting_evidence_ids": [
                    "E-GROUP-MACHINE-ID-CAVITY-ID"
                ],
                "related_hypothesis_ids": ["H-001"],
            }
        ],
        "missing_data": ["缺少精确的换刀和维修事件时间。"],
    }


def test_synthesizer_creates_candidate_hypotheses_only() -> None:
    case = _build_case()
    synthesizer = EvidenceGroundedSynthesizer(
        model=FakeStructuredModel(_valid_synthesis_output())
    )

    synthesis = synthesizer.synthesize(case)
    updated = apply_synthesis(case, synthesis)

    assert synthesis.hypotheses[0].id == "H-001"
    assert updated.state == "waiting_for_user"
    assert updated.hypotheses[0].status == "candidate"
    assert updated.hypotheses[0].decision is None
    assert updated.actions[0].status == "proposed"
    assert updated.actions[0].action_type == "containment"
    assert "缺少精确的换刀和维修事件时间。" in updated.missing_data
    assert updated.conclusion is None


def test_synthesizer_rejects_unknown_evidence_reference() -> None:
    output = _valid_synthesis_output()
    output["hypotheses"][0]["supporting_evidence_ids"] = ["E-NOT-FOUND"]
    synthesizer = EvidenceGroundedSynthesizer(
        model=FakeStructuredModel(output)
    )

    with pytest.raises(ValueError, match="unknown evidence ids"):
        synthesizer.synthesize(_build_case())


def test_synthesizer_rejects_invented_numeric_claim() -> None:
    output = _valid_synthesis_output()
    output["findings"][0] = {
        "statement": "该组合不良率为 99%。",
        "evidence_ids": ["E-GROUP-MACHINE-ID-CAVITY-ID"],
    }
    synthesizer = EvidenceGroundedSynthesizer(
        model=FakeStructuredModel(output)
    )

    with pytest.raises(ValueError, match="numeric claims absent"):
        synthesizer.synthesize(_build_case())


def test_synthesizer_rejects_model_attempt_to_confirm_root_cause() -> None:
    output = _valid_synthesis_output()
    output["hypotheses"][0]["status"] = "confirmed"
    synthesizer = EvidenceGroundedSynthesizer(
        model=FakeStructuredModel(output)
    )

    with pytest.raises(ValidationError):
        synthesizer.synthesize(_build_case())


def test_synthesizer_rejects_action_referencing_unknown_hypothesis() -> None:
    output = _valid_synthesis_output()
    output["actions"][0]["related_hypothesis_ids"] = ["H-NOT-FOUND"]
    synthesizer = EvidenceGroundedSynthesizer(
        model=FakeStructuredModel(output)
    )

    with pytest.raises(ValueError, match="unknown hypothesis ids"):
        synthesizer.synthesize(_build_case())
