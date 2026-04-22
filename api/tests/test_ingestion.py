from pathlib import Path

import pandas as pd
import pytest

from api.app.services.ingestion import (
    build_dataset_profile,
    infer_field_mapping,
    load_source_dataframe,
    normalize_measurements,
)


CSV_TEXT = """sample_id,batch_id,measured_at,value,lsl,usl
A-001,B-01,2026-04-21 08:00:00,10.010,9.950,10.050
A-002,B-01,2026-04-21 08:01:00,10.025,9.950,10.050
A-003,B-01,2026-04-21 08:02:00,10.060,9.950,10.050
"""

GB18030_CSV_BYTES = (
    b"\xd1\xf9\xb1\xbe\xcb\xb5\xc3\xf7,sample_id,batch_id,measured_at,value,lsl,usl\n"
    b"\xca\xd7\xbc\xfe,A-001,B-01,2026-04-21 08:00:00,10.010,9.950,10.050\n"
    b"\xc1\xbf\xb2\xfa,A-002,B-01,2026-04-21 08:01:00,10.025,9.950,10.050\n"
)


def test_load_source_dataframe_reads_csv(tmp_path: Path) -> None:
    source_path = tmp_path / "simple_measurements.csv"
    source_path.write_text(CSV_TEXT, encoding="utf-8")

    raw_frame = load_source_dataframe(source_path)

    assert list(raw_frame.columns) == [
        "sample_id",
        "batch_id",
        "measured_at",
        "value",
        "lsl",
        "usl",
    ]
    assert raw_frame.loc[0, "sample_id"] == "A-001"
    assert raw_frame.loc[2, "value"] == 10.06

def test_load_source_dataframe_reads_gb18030_csv(tmp_path: Path) -> None:
    label_column = "样本说明"
    source_path = tmp_path / "gb18030_measurements.csv"
    source_path.write_bytes(GB18030_CSV_BYTES)

    raw_frame = load_source_dataframe(source_path)

    assert list(raw_frame.columns) == [
        label_column,
        "sample_id",
        "batch_id",
        "measured_at",
        "value",
        "lsl",
        "usl",
    ]
    assert raw_frame.loc[0, label_column] == "首件"
    assert raw_frame.loc[1, "sample_id"] == "A-002"

def test_load_source_dataframe_rejects_unsupported_file_type(tmp_path: Path) -> None:
    source_path = tmp_path / "simple_measurements.txt"

    with pytest.raises(ValueError, match="Unsupported file type: \\.txt"):
        load_source_dataframe(source_path)


def test_load_source_dataframe_rejects_header_only_csv(tmp_path: Path) -> None:
    source_path = tmp_path / "header_only_measurements.csv"
    source_path.write_text("sample_id,batch_id,measured_at,value,lsl,usl\n", encoding="utf-8")

    with pytest.raises(ValueError, match="No measurement rows found in source file"):
        load_source_dataframe(source_path)


def test_infer_field_mapping_prefers_named_measurement_columns(tmp_path: Path) -> None:
    source_path = tmp_path / "simple_measurements.csv"
    source_path.write_text(CSV_TEXT, encoding="utf-8")

    raw_frame = load_source_dataframe(source_path)
    mapping = infer_field_mapping(raw_frame)

    assert mapping.sample_id_column == "sample_id"
    assert mapping.measurement_column == "value"
    assert mapping.lsl_column == "lsl"
    assert mapping.usl_column == "usl"
    assert mapping.batch_column == "batch_id"
    assert mapping.timestamp_column == "measured_at"


def test_infer_field_mapping_requires_numeric_measurement_column() -> None:
    raw_frame = pd.DataFrame(
        {
            "sample_id": ["A-001", "A-002"],
            "batch_id": ["B-01", "B-01"],
            "inspection_note": ["ok", "recheck"],
        }
    )

    with pytest.raises(ValueError, match="No numeric measurement column found"):
        infer_field_mapping(raw_frame)


def test_normalize_measurements_maps_measurement_and_batch_fields(tmp_path: Path) -> None:
    source_path = tmp_path / "simple_measurements.csv"
    source_path.write_text(CSV_TEXT, encoding="utf-8")

    raw_frame = load_source_dataframe(source_path)
    mapping = infer_field_mapping(raw_frame)
    normalized = normalize_measurements(raw_frame, mapping)

    assert normalized.loc[0, "measurement_value"] == 10.01
    assert normalized.loc[2, "batch_id"] == "B-01"


def test_normalize_measurements_generates_sequence_index_when_optional_columns_missing() -> None:
    raw_frame = pd.DataFrame(
        {
            "value": [10.01, 10.02, 10.03],
        }
    )
    mapping = infer_field_mapping(raw_frame)

    normalized = normalize_measurements(raw_frame, mapping)

    assert normalized["sample_id"].tolist() == ["0", "1", "2"]
    assert normalized["batch_id"].tolist() == ["DEMO-BATCH", "DEMO-BATCH", "DEMO-BATCH"]
    assert normalized["measurement_value"].tolist() == [10.01, 10.02, 10.03]
    assert normalized["measured_at"].isna().all()
    assert normalized["sequence_index"].tolist() == [1, 2, 3]


def test_normalize_measurements_fills_spec_limits_from_later_rows() -> None:
    raw_frame = pd.DataFrame(
        {
            "sample_id": ["A-001", "A-002", "A-003"],
            "value": [10.01, 10.02, 10.03],
            "lsl": [None, 9.95, None],
            "usl": [None, 10.05, None],
        }
    )
    mapping = infer_field_mapping(raw_frame)

    normalized = normalize_measurements(raw_frame, mapping)

    assert normalized["lsl"].tolist() == [9.95, 9.95, 9.95]
    assert normalized["usl"].tolist() == [10.05, 10.05, 10.05]
    assert normalized.loc[0, "lsl"] == 9.95
    assert normalized.loc[0, "usl"] == 10.05


@pytest.mark.parametrize(
    ("lsl_values", "usl_values", "expected_lsl", "expected_usl"),
    [
        ([None, 9.95, 9.95], [None, 10.05, 10.05], 9.95, 10.05),
        ([None, 9.95, 9.9], [None, 10.05, 10.1], 9.95, 10.05),
    ],
)
def test_normalize_measurements_uses_first_non_null_spec_limit_for_dataset(
    lsl_values: list[float | None],
    usl_values: list[float | None],
    expected_lsl: float,
    expected_usl: float,
) -> None:
    raw_frame = pd.DataFrame(
        {
            "sample_id": ["A-001", "A-002", "A-003"],
            "value": [10.01, 10.02, 10.03],
            "lsl": lsl_values,
            "usl": usl_values,
        }
    )
    mapping = infer_field_mapping(raw_frame)

    normalized = normalize_measurements(raw_frame, mapping)

    assert normalized["lsl"].tolist() == [expected_lsl, expected_lsl, expected_lsl]
    assert normalized["usl"].tolist() == [expected_usl, expected_usl, expected_usl]


def test_build_dataset_profile_requires_complete_spec_limits() -> None:
    normalized = pd.DataFrame(
        {
            "sample_id": ["A-001", "A-002"],
            "batch_id": ["B-01", "B-01"],
            "part_number": ["6205", "6205"],
            "inspection_item": ["Outer Diameter", "Outer Diameter"],
            "measurement_value": [10.01, 10.02],
            "target_value": [None, None],
            "usl": [10.05, None],
            "lsl": [9.95, 9.95],
            "unit": ["mm", "mm"],
            "measured_at": [pd.NaT, pd.NaT],
            "sequence_index": [None, None],
            "operator_name": ["demo-operator", "demo-operator"],
            "device_name": ["demo-gauge", "demo-gauge"],
        }
    )

    profile = build_dataset_profile(normalized)

    assert profile.row_count == 2
    assert profile.has_spec_limits is False
    assert profile.has_timestamp is False
    assert profile.has_sequence is False


def test_build_dataset_profile_uses_presence_for_timestamp_and_sequence() -> None:
    normalized = pd.DataFrame(
        {
            "sample_id": ["A-001", "A-002"],
            "batch_id": ["B-01", "B-01"],
            "part_number": ["6205", "6205"],
            "inspection_item": ["Outer Diameter", "Outer Diameter"],
            "measurement_value": [10.01, 10.02],
            "target_value": [None, None],
            "usl": [10.05, 10.05],
            "lsl": [9.95, 9.95],
            "unit": ["mm", "mm"],
            "measured_at": pd.to_datetime(["2026-04-21 08:00:00", None]),
            "sequence_index": [1, None],
            "operator_name": ["demo-operator", "demo-operator"],
            "device_name": ["demo-gauge", "demo-gauge"],
        }
    )

    profile = build_dataset_profile(normalized)

    assert profile.row_count == 2
    assert profile.has_spec_limits is True
    assert profile.has_timestamp is True
    assert profile.has_sequence is True


def test_build_dataset_profile_returns_conservative_flags_for_empty_dataset() -> None:
    normalized = pd.DataFrame(columns=[
        "sample_id",
        "batch_id",
        "part_number",
        "inspection_item",
        "measurement_value",
        "target_value",
        "usl",
        "lsl",
        "unit",
        "measured_at",
        "sequence_index",
        "operator_name",
        "device_name",
    ])

    profile = build_dataset_profile(normalized)

    assert profile.row_count == 0
    assert profile.has_spec_limits is False
    assert profile.has_timestamp is False
    assert profile.has_sequence is False
