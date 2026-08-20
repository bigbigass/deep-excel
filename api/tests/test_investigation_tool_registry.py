from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError

from api.app.domain.ai import InvestigationPlan, InvestigationToolCall
from api.app.services.investigation.tool_registry import build_default_tool_registry


DEMO_DATA_PATH = Path("sample_data/investigation_demo.csv")


def _load_demo_data() -> pd.DataFrame:
    return pd.read_csv(DEMO_DATA_PATH, parse_dates=["measured_at"])


def test_default_tool_registry_exposes_only_whitelisted_tools() -> None:
    registry = build_default_tool_registry()

    assert registry.names == (
        "compare_group_failure_rates",
        "detect_mean_change_point",
        "detect_spc_signals",
        "profile_dataset",
        "rank_failure_associations",
    )


def test_registry_rejects_unknown_model_selected_tool() -> None:
    registry = build_default_tool_registry()
    call = InvestigationToolCall(
        tool_name="execute_python",
        arguments={"code": "print('unsafe')"},
        reason="尝试执行任意代码。",
    )

    with pytest.raises(ValueError, match="unknown investigation tool"):
        registry.validate_call(call, _load_demo_data())


def test_registry_rejects_hidden_control_arguments() -> None:
    registry = build_default_tool_registry()
    call = InvestigationToolCall(
        tool_name="profile_dataset",
        arguments={"evidence_id": "E-HACKED"},
        reason="重新检查数据质量。",
    )

    with pytest.raises(ValidationError, match="extra_forbidden"):
        registry.validate_call(call, _load_demo_data())


def test_registry_rejects_columns_not_present_in_dataset() -> None:
    registry = build_default_tool_registry()
    call = InvestigationToolCall(
        tool_name="compare_group_failure_rates",
        arguments={"group_by": ["nonexistent_dimension"]},
        reason="检查不存在的维度。",
    )

    with pytest.raises(ValueError, match="unavailable columns"):
        registry.validate_call(call, _load_demo_data())


def test_registry_executes_valid_plan_with_generated_evidence_ids() -> None:
    registry = build_default_tool_registry()
    plan = InvestigationPlan(
        interpreted_question="进一步确认设备与型腔差异。",
        steps=[
            InvestigationToolCall(
                tool_name="compare_group_failure_rates",
                arguments={"group_by": ["machine_id", "cavity_id"]},
                reason="验证不良是否集中于特定设备与型腔。",
            )
        ],
        missing_information=[],
    )

    evidence = registry.execute_plan(
        plan,
        _load_demo_data(),
        existing_evidence_ids={"E-AI-TOOL-001"},
        source_refs=[str(DEMO_DATA_PATH)],
    )

    assert len(evidence) == 1
    assert evidence[0].id == "E-AI-TOOL-002"
    assert evidence[0].evidence_type == "group_difference"
    assert evidence[0].metrics["planned_tool_name"] == "compare_group_failure_rates"
    assert evidence[0].metrics["plan_reason"] == "验证不良是否集中于特定设备与型腔。"
    assert evidence[0].source_refs == [str(DEMO_DATA_PATH)]


def test_tool_descriptions_mark_missing_specification_tools_unavailable() -> None:
    frame = pd.DataFrame({"measurement_value": [1.0, 1.1, 1.2]})
    descriptions = {
        item.name: item
        for item in build_default_tool_registry().describe(frame)
    }

    assert descriptions["profile_dataset"].availability == "available"
    assert descriptions["detect_spc_signals"].availability == "available"
    assert descriptions["compare_group_failure_rates"].availability == "unavailable"
    assert "lsl" in (descriptions["compare_group_failure_rates"].unavailable_reason or "")
