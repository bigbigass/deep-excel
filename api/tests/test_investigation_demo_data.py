from pathlib import Path

import pandas as pd


DEMO_DATA_PATH = Path("sample_data/investigation_demo.csv")
CHANGE_POINT = pd.Timestamp("2026-08-13T10:40:00")


def _load_demo_data() -> pd.DataFrame:
    frame = pd.read_csv(DEMO_DATA_PATH, parse_dates=["measured_at"])
    frame["is_out_of_spec"] = (frame["measurement_value"] < frame["lsl"]) | (
        frame["measurement_value"] > frame["usl"]
    )
    return frame


def test_investigation_demo_has_required_quality_context() -> None:
    frame = _load_demo_data()

    assert len(frame) == 96
    assert {
        "sample_id",
        "measured_at",
        "quality_feature",
        "measurement_value",
        "target",
        "usl",
        "lsl",
        "machine_id",
        "cavity_id",
        "shift",
        "material_lot",
        "tool_id",
        "tool_cycles",
    }.issubset(frame.columns)
    assert frame["sample_id"].is_unique
    assert frame["measurement_value"].notna().all()


def test_investigation_demo_contains_a_detectable_mean_shift() -> None:
    frame = _load_demo_data()
    before = frame.loc[frame["measured_at"] < CHANGE_POINT, "measurement_value"]
    after = frame.loc[frame["measured_at"] >= CHANGE_POINT, "measurement_value"]

    assert len(before) == 32
    assert len(after) == 64
    assert after.mean() - before.mean() > 0.01


def test_investigation_demo_localizes_failures_to_m02_cavity_4() -> None:
    frame = _load_demo_data()
    cavity = frame["cavity_id"].astype(str)
    problem_mask = (frame["machine_id"] == "M02") & (cavity == "4")

    problem_rate = frame.loc[problem_mask, "is_out_of_spec"].mean()
    comparison_rate = frame.loc[~problem_mask, "is_out_of_spec"].mean()

    assert problem_rate > 0.60
    assert comparison_rate == 0.0


def test_investigation_demo_does_not_confound_material_lot_with_failures() -> None:
    frame = _load_demo_data()
    failure_rates = frame.groupby("material_lot")["is_out_of_spec"].mean()

    assert set(failure_rates.index) == {"LOT-A", "LOT-B"}
    assert abs(failure_rates["LOT-A"] - failure_rates["LOT-B"]) < 0.01


def test_investigation_demo_exposes_tool_life_as_a_candidate_factor() -> None:
    frame = _load_demo_data()
    cavity = frame["cavity_id"].astype(str)
    problem_mask = (frame["machine_id"] == "M02") & (cavity == "4")

    assert frame.loc[problem_mask, "tool_cycles"].min() > frame.loc[~problem_mask, "tool_cycles"].max()
    assert frame.loc[problem_mask, "tool_cycles"].max() > 9_000
