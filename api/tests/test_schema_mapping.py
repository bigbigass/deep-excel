import pandas as pd
import pytest

from api.app.agent.schema_mapping_planner import SchemaMappingPlanner
from api.app.domain.mapping import (
    MappingAssignment,
    SchemaMappingConfirmation,
)
from api.app.services.investigation.schema_mapping import (
    auto_confirm_canonical_mapping,
    build_rule_mapping_proposal,
    confirm_schema_mapping,
    normalize_investigation_frame,
)


class FakeStructuredModel:
    def __init__(self, response: object) -> None:
        self.response = response

    def with_structured_output(self, schema):
        return self

    def invoke(self, messages):
        return self.response


def test_canonical_schema_is_auto_confirmed() -> None:
    frame = pd.DataFrame(
        {
            "sample_id": ["S-1", "S-2"],
            "measured_at": ["2026-08-13 08:00", "2026-08-13 08:05"],
            "measurement_value": [20.0, 20.01],
            "usl": [20.04, 20.04],
            "lsl": [19.96, 19.96],
            "machine_id": ["M01", "M01"],
        }
    )

    proposal = build_rule_mapping_proposal(frame, "canonical.csv")
    confirmed = auto_confirm_canonical_mapping(proposal)

    assert confirmed is not None
    assert confirmed.status == "confirmed"
    assert confirmed.generated_by == "canonical"
    assert confirmed.confirmed_by == "system:canonical-schema"
    assert confirmed.mapping_for_role("measurement_value").source_column == "measurement_value"


def test_chinese_aliases_are_suggested_but_require_human_confirmation() -> None:
    frame = pd.DataFrame(
        {
            "样本编号": ["S-1", "S-2"],
            "检测时间": ["2026-08-13 08:00", "2026-08-13 08:05"],
            "外径实测值": [20.0, 20.01],
            "规格上限": [20.04, 20.04],
            "规格下限": [19.96, 19.96],
            "设备号": ["M01", "M01"],
            "模穴": [1, 1],
        }
    )

    proposal = build_rule_mapping_proposal(frame, "客户外径记录.csv")

    assert proposal.status == "pending"
    assert proposal.generated_by == "deterministic"
    assert proposal.missing_required_roles == []
    assert proposal.mapping_for_role("measurement_value").source_column == "外径实测值"
    assert proposal.mapping_for_role("machine_id").source_column == "设备号"
    assert proposal.mapping_for_role("cavity_id").source_column == "模穴"
    assert auto_confirm_canonical_mapping(proposal) is None


def test_human_confirmation_normalizes_noncanonical_quality_data() -> None:
    frame = pd.DataFrame(
        {
            "样本编号": ["S-1", "S-2"],
            "检测时间": ["2026-08-13 08:00", "2026-08-13 08:05"],
            "外径实测值": [20.0, 20.01],
            "规格上限": [20.04, 20.04],
            "规格下限": [19.96, 19.96],
            "设备号": ["M01", "M02"],
            "模穴": [1, 4],
            "备注": ["首件", "复测"],
        }
    )
    proposal = build_rule_mapping_proposal(frame, "客户外径记录.csv")
    confirmation = SchemaMappingConfirmation(
        actor_id="quality-engineer-01",
        mappings=[
            MappingAssignment(source_column=item.source_column, role=item.role)
            for item in proposal.mappings
        ],
    )

    confirmed = confirm_schema_mapping(proposal, confirmation)
    normalized = normalize_investigation_frame(frame, confirmed)

    assert confirmed.status == "confirmed"
    assert confirmed.generated_by == "human"
    assert confirmed.confirmed_by == "quality-engineer-01"
    assert normalized["measurement_value"].tolist() == [20.0, 20.01]
    assert normalized["machine_id"].tolist() == ["M01", "M02"]
    assert normalized["cavity_id"].tolist() == [1, 4]
    assert normalized["sequence_index"].tolist() == [1, 2]
    assert normalized["quality_feature"].tolist() == ["measurement", "measurement"]
    assert "备注" not in normalized.columns


def test_confirmation_requires_measurement_value() -> None:
    frame = pd.DataFrame({"编号": [1, 2], "结果": [20.0, 20.1]})
    proposal = build_rule_mapping_proposal(frame, "ambiguous.csv")
    confirmation = SchemaMappingConfirmation(
        actor_id="quality-engineer-01",
        mappings=[
            MappingAssignment(source_column="编号", role="sample_id"),
            MappingAssignment(source_column="结果", role="ignore"),
        ],
    )

    with pytest.raises(ValueError, match="measurement_value must be assigned"):
        confirm_schema_mapping(proposal, confirmation)


def test_normalization_rejects_non_numeric_measurement_values() -> None:
    frame = pd.DataFrame({"检测结果": ["20.01", "bad-value"]})
    proposal = build_rule_mapping_proposal(frame, "invalid.csv")
    confirmation = SchemaMappingConfirmation(
        actor_id="quality-engineer-01",
        mappings=[MappingAssignment(source_column="检测结果", role="measurement_value")],
    )
    confirmed = confirm_schema_mapping(proposal, confirmation)

    with pytest.raises(ValueError, match="contains non-numeric values"):
        normalize_investigation_frame(frame, confirmed)


def test_ai_schema_planner_fills_unknown_columns_without_auto_confirmation() -> None:
    frame = pd.DataFrame(
        {
            "COL_A": ["S-1", "S-2"],
            "COL_B": [20.0, 20.01],
            "COL_C": [20.04, 20.04],
            "COL_D": [19.96, 19.96],
        }
    )
    deterministic = build_rule_mapping_proposal(frame, "opaque.csv")
    model = FakeStructuredModel(
        {
            "mappings": [
                {
                    "source_column": "COL_A",
                    "role": "sample_id",
                    "confidence": 0.91,
                    "reasoning": "该列值形态符合样本编号。",
                },
                {
                    "source_column": "COL_B",
                    "role": "measurement_value",
                    "confidence": 0.93,
                    "reasoning": "该数值列位于规格上下限之间，符合测量结果。",
                },
                {
                    "source_column": "COL_C",
                    "role": "usl",
                    "confidence": 0.88,
                    "reasoning": "该列为稳定的规格上边界。",
                },
                {
                    "source_column": "COL_D",
                    "role": "lsl",
                    "confidence": 0.88,
                    "reasoning": "该列为稳定的规格下边界。",
                },
            ],
            "warnings": ["列名本身不含业务语义，需要人工确认。"],
        }
    )

    proposal = SchemaMappingPlanner(model).plan(
        frame,
        file_name="opaque.csv",
        deterministic_proposal=deterministic,
    )

    assert proposal.status == "pending"
    assert proposal.generated_by == "hybrid"
    assert proposal.mapping_for_role("measurement_value").source_column == "COL_B"
    assert proposal.mapping_for_role("usl").source_column == "COL_C"
    assert proposal.mapping_for_role("lsl").source_column == "COL_D"
    assert "需要人工确认" in proposal.warnings[-1]


def test_ai_schema_planner_rejects_unknown_source_column() -> None:
    frame = pd.DataFrame({"COL_A": [1, 2]})
    deterministic = build_rule_mapping_proposal(frame, "opaque.csv")
    model = FakeStructuredModel(
        {
            "mappings": [
                {
                    "source_column": "NOT_REAL",
                    "role": "measurement_value",
                    "confidence": 0.9,
                    "reasoning": "该列被错误地引用。",
                }
            ],
            "warnings": [],
        }
    )

    with pytest.raises(ValueError, match="exact source columns"):
        SchemaMappingPlanner(model).plan(
            frame,
            file_name="opaque.csv",
            deterministic_proposal=deterministic,
        )
