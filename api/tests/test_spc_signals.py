import json
from pathlib import Path

import pandas as pd

from api.app.services.investigation import detect_spc_signals


DEMO_DATA_PATH = Path("sample_data/investigation_demo.csv")


def test_detect_spc_signals_finds_demo_control_limit_points() -> None:
    frame = pd.read_csv(DEMO_DATA_PATH, parse_dates=["measured_at"])

    evidence = detect_spc_signals(
        frame,
        source_refs=[str(DEMO_DATA_PATH)],
    )

    assert evidence.id == "E-SPC-SIGNALS"
    assert evidence.evidence_type == "spc_signal"
    assert evidence.confidence == "high"
    assert evidence.metrics["signal_detected"] is True
    assert evidence.metrics["beyond_control_limit_point_count"] == 8
    assert evidence.metrics["ucl"] < 20.045
    assert any(
        signal["rule"] == "beyond_3_sigma"
        for signal in evidence.metrics["signals"]
    )
    json.dumps(evidence.model_dump(mode="json"), allow_nan=False)


def test_detect_spc_signals_returns_negative_evidence_for_constant_process() -> None:
    frame = pd.DataFrame(
        {
            "measurement_value": [10.0] * 20,
            "sequence_index": range(1, 21),
        }
    )

    evidence = detect_spc_signals(frame, order_column="missing_time")

    assert evidence.metrics["signal_detected"] is False
    assert evidence.metrics["signal_count"] == 0
    assert evidence.metrics["ucl"] is None
    assert evidence.metrics["lcl"] is None
    assert evidence.metrics["order_column"] == "sequence_index"


def test_detect_spc_signals_reports_same_side_and_trend_rules() -> None:
    frame = pd.DataFrame(
        {
            "sample_id": [f"S-{index:02d}" for index in range(1, 17)],
            "measurement_value": [0.0] * 8 + [1.0] * 8,
            "sequence_index": range(1, 17),
        }
    )

    evidence = detect_spc_signals(
        frame,
        order_column="sequence_index",
        same_side_run_length=8,
    )
    rules = [signal["rule"] for signal in evidence.metrics["signals"]]

    assert rules.count("same_side_run") == 2
    assert all(
        signal["point_count"] == 8
        for signal in evidence.metrics["signals"]
        if signal["rule"] == "same_side_run"
    )

    trend_frame = pd.DataFrame(
        {
            "measurement_value": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            "sequence_index": range(1, 7),
        }
    )
    trend_evidence = detect_spc_signals(
        trend_frame,
        order_column="sequence_index",
        trend_point_count=6,
    )

    assert any(
        signal["rule"] == "monotonic_trend"
        and signal["direction"] == "increasing"
        and signal["point_count"] == 6
        for signal in trend_evidence.metrics["signals"]
    )
