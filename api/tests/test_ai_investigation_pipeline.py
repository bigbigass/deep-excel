from pathlib import Path

import pandas as pd
import pytest

from api.app.agent.evidence_synthesizer import EvidenceGroundedSynthesizer
from api.app.agent.investigation_planner import InvestigationPlanner
from api.app.services.investigation.ai_pipeline import run_ai_investigation
from api.app.services.investigation.baseline import run_baseline_investigation


DEMO_DATA_PATH = Path("sample_data/investigation_demo.csv")


class FakeStructuredModel:
    def __init__(self, output: dict[str, object]) -> None:
        self.output = output

    def with_structured_output(self, schema):
        return self

    def invoke(self, messages):
        return self.output


def _frame() -> pd.DataFrame:
    return pd.read_csv(DEMO_DATA_PATH, parse_dates=["measured_at"])


def _case():
    return run_baseline_investigation(
        _frame(),
        question="为什么外径不良率升高？",
        case_id="CASE-AI-PIPELINE",
        source_refs=[str(DEMO_DATA_PATH)],
    )


def test_ai_pipeline_executes_plan_before_creating_candidate_hypothesis() -> None:
    planner = InvestigationPlanner(
        model=FakeStructuredModel(
            {
                "interpreted_question": "检查班次是否能解释外径不良率变化。",
                "steps": [
                    {
                        "tool_name": "compare_group_failure_rates",
                        "arguments": {"group_by": ["shift"]},
                        "reason": "补充现有证据中缺少的班次分层比较。",
                    }
                ],
                "missing_information": [],
            }
        )
    )
    synthesizer = EvidenceGroundedSynthesizer(
        model=FakeStructuredModel(
            {
                "findings": [
                    {
                        "statement": "班次分层没有形成足以替代设备型腔证据的主要解释。",
                        "evidence_ids": [
                            "E-AI-01-COMPARE-GROUP-FAILURE-RATES"
                        ],
                    }
                ],
                "hypotheses": [
                    {
                        "id": "H-PIPELINE-001",
                        "statement": "设备型腔状态或刀具寿命仍是优先验证的候选因素。",
                        "supporting_evidence_ids": [
                            "E-GROUP-MACHINE-ID-CAVITY-ID",
                            "E-FACTOR-RANKING",
                        ],
                        "contradicting_evidence_ids": [
                            "E-AI-01-COMPARE-GROUP-FAILURE-RATES"
                        ],
                        "confidence": "high",
                        "verification_actions": [
                            "检查高风险型腔及其刀具状态。"
                        ],
                    }
                ],
                "actions": [
                    {
                        "id": "A-PIPELINE-001",
                        "action_type": "verification",
                        "title": "检查型腔和刀具状态",
                        "rationale": "设备型腔和因素排名证据支持优先开展现场验证。",
                        "supporting_evidence_ids": [
                            "E-GROUP-MACHINE-ID-CAVITY-ID",
                            "E-FACTOR-RANKING",
                        ],
                        "related_hypothesis_ids": ["H-PIPELINE-001"],
                    }
                ],
                "missing_data": ["缺少维修事件时间。"],
            }
        )
    )

    result = run_ai_investigation(
        _case(),
        _frame(),
        planner=planner,
        synthesizer=synthesizer,
    )

    assert result.plan.steps[0].tool_name == "compare_group_failure_rates"
    assert any(
        item.id == "E-AI-01-COMPARE-GROUP-FAILURE-RATES"
        for item in result.case.evidence
    )
    assert result.case.state == "waiting_for_user"
    assert result.case.hypotheses[0].status == "candidate"
    assert result.case.hypotheses[0].decision is None
    assert result.case.actions[0].status == "proposed"
    assert "缺少维修事件时间。" in result.case.missing_data


def test_ai_pipeline_rejects_non_whitelisted_plan_before_execution() -> None:
    planner = InvestigationPlanner(
        model=FakeStructuredModel(
            {
                "interpreted_question": "执行任意脚本。",
                "steps": [
                    {
                        "tool_name": "shell_exec",
                        "arguments": {"command": "rm -rf /"},
                        "reason": "绕过受控工具。",
                    }
                ],
                "missing_information": [],
            }
        )
    )

    with pytest.raises(ValueError, match="unknown investigation tool"):
        run_ai_investigation(
            _case(),
            _frame(),
            planner=planner,
            synthesizer=EvidenceGroundedSynthesizer(
                model=FakeStructuredModel(
                    {
                        "findings": [],
                        "hypotheses": [],
                        "actions": [],
                        "missing_data": [],
                    }
                )
            ),
        )
