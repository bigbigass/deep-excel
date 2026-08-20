import json
from pathlib import Path

import pandas as pd
import pytest

from api.app.services.investigation import (
    compare_group_failure_rates,
    detect_mean_change_point,
    profile_dataset,
    rank_failure_associations,
)


DEMO_DATA_PATH = Path("sample_data/investigation_demo.csv")


def _load_demo_data() -> pd.DataFrame:
    return pd.read_csv(DEMO_DATA_PATH, parse_dates=["measured_at"])


def test_profile_dataset_reports_available_context_and_data_quality() -> None:
    evidence = profile_dataset(
        _load_demo_data(),
        source_refs=[str(DEMO_DATA_PATH)],
    )

    assert evidence.id == "E-DATA-QUALITY"
    assert evidence.evidence_type == "data_quality"
    assert evidence.confidence == "high"
    assert evidence.sample_size == 96
    assert evidence.metrics["valid_measurement_count"] == 96
    assert evidence.metrics["valid_specification_count"] == 96
    assert evidence.metrics["valid_timestamp_count"] == 96
    assert evidence.metrics["duplicate_sample_count"] == 0
    assert set(evidence.metrics["context_dimensions"]) >= {
        "machine_id",
        "cavity_id",
        "shift",
        "material_lot",
        "tool_id",
    }
    assert evidence.source_refs == [str(DEMO_DATA_PATH)]


def test_profile_dataset_rejects_missing_measurement_column() -> None:
    with pytest.raises(ValueError, match="measurement_value column is required"):
        profile_dataset(pd.DataFrame({"sample_id": ["S-001"]}))


def test_detect_mean_change_point_finds_expected_demo_shift() -> None:
    evidence = detect_mean_change_point(
        _load_demo_data(),
        source_refs=[str(DEMO_DATA_PATH)],
    )

    assert evidence.id == "E-CHANGE-POINT"
    assert evidence.evidence_type == "change_point"
    assert evidence.confidence == "high"
    assert evidence.metrics["detected"] is True
    assert evidence.metrics["split_index"] == 32
    assert str(evidence.metrics["change_at"]).startswith("2026-08-13T10:40:00")
    assert evidence.metrics["before_count"] == 32
    assert evidence.metrics["after_count"] == 64
    assert evidence.metrics["delta"] > 0.01
    assert evidence.metrics["adjusted_p_value"] < 0.01
    assert evidence.metrics["effect_size"] > 0.8


def test_detect_mean_change_point_returns_negative_evidence_for_constant_process() -> None:
    frame = pd.DataFrame(
        {
            "measurement_value": [10.0] * 30,
            "sequence_index": range(1, 31),
        }
    )

    evidence = detect_mean_change_point(
        frame,
        order_column="missing_time",
        min_segment_size=10,
    )

    assert evidence.metrics["detected"] is False
    assert evidence.metrics["order_column"] == "sequence_index"
    assert evidence.metrics["candidate_count"] == 0


def test_detect_mean_change_point_requires_enough_rows() -> None:
    frame = pd.DataFrame(
        {
            "measurement_value": [10.0, 10.1, 10.2],
            "sequence_index": [1, 2, 3],
        }
    )

    with pytest.raises(ValueError, match="valid rows are required"):
        detect_mean_change_point(frame, min_segment_size=2)


def test_compare_group_failure_rates_localizes_problem_machine_and_cavity() -> None:
    evidence = compare_group_failure_rates(
        _load_demo_data(),
        group_by=["machine_id", "cavity_id"],
        source_refs=[str(DEMO_DATA_PATH)],
    )

    assert evidence.id == "E-GROUP-DIFFERENCE"
    assert evidence.evidence_type == "group_difference"
    assert evidence.confidence == "high"
    assert evidence.metrics["difference_detected"] is True
    assert evidence.metrics["selected_group"] == {"machine_id": "M02", "cavity_id": 4}
    assert evidence.metrics["group_sample_count"] == 12
    assert evidence.metrics["group_failure_count"] == 8
    assert evidence.metrics["group_failure_rate"] > 0.60
    assert evidence.metrics["rest_failure_count"] == 0
    assert evidence.metrics["raw_risk_ratio"] is None
    assert evidence.metrics["raw_risk_ratio_is_infinite"] is True
    assert evidence.metrics["corrected_risk_ratio"] > 100
    assert evidence.metrics["p_value"] < 0.01
    assert evidence.filters == {"machine_id": "M02", "cavity_id": 4}

    # 证据必须能够写入严格 JSON，不能泄漏 Infinity 或 pandas 标量。
    json.dumps(evidence.model_dump(mode="json"), allow_nan=False)


def test_compare_group_failure_rates_does_not_blame_balanced_material_lots() -> None:
    evidence = compare_group_failure_rates(
        _load_demo_data(),
        group_by=["material_lot"],
        minimum_rate_difference=0.01,
    )

    assert evidence.metrics["difference_detected"] is False
    assert evidence.confidence == "low"
    assert abs(evidence.metrics["rate_difference"]) < 0.001


def test_compare_group_failure_rates_requires_specifications() -> None:
    frame = _load_demo_data().drop(columns=["usl"])

    with pytest.raises(ValueError, match="missing required columns"):
        compare_group_failure_rates(frame, group_by=["machine_id"])


def test_rank_failure_associations_prioritizes_tool_and_cavity_signals() -> None:
    evidence = rank_failure_associations(
        _load_demo_data(),
        candidate_columns=[
            "machine_id",
            "cavity_id",
            "shift",
            "material_lot",
            "tool_id",
            "tool_cycles",
        ],
        source_refs=[str(DEMO_DATA_PATH)],
    )

    assert evidence.id == "E-FACTOR-RANKING"
    assert evidence.evidence_type == "factor_association"
    assert evidence.confidence == "high"
    assert evidence.metrics["association_detected"] is True
    ranked = {
        item["factor"]: item
        for item in evidence.metrics["ranked_factors"]
    }
    assert evidence.metrics["ranked_factors"][0]["factor"] in {"tool_cycles", "tool_id"}
    assert ranked["tool_cycles"]["factor_type"] == "numeric"
    assert ranked["tool_cycles"]["association_detected"] is True
    assert ranked["tool_cycles"]["effect_size"] > 0.70
    assert ranked["tool_cycles"]["adjusted_p_value"] < 0.01
    assert ranked["tool_id"]["association_detected"] is True
    assert ranked["cavity_id"]["association_detected"] is True
    assert ranked["material_lot"]["association_detected"] is False
    assert ranked["material_lot"]["effect_size"] < 0.01
    assert "不能直接认定为根因" in evidence.statement

    json.dumps(evidence.model_dump(mode="json"), allow_nan=False)


def test_rank_failure_associations_returns_negative_evidence_without_failures() -> None:
    frame = _load_demo_data().copy()
    frame["measurement_value"] = 20.0

    evidence = rank_failure_associations(
        frame,
        candidate_columns=["machine_id", "cavity_id"],
    )

    assert evidence.metrics["association_detected"] is False
    assert evidence.metrics["ranked_factors"] == []
    assert evidence.confidence == "low"
