from pathlib import Path

import pandas as pd

from api.app.schemas import DatasetProfile, FieldMapping

CSV_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030")

CANONICAL_COLUMNS = [
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
]


def load_source_dataframe(file_path: Path) -> pd.DataFrame:
    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        frame = _read_csv_with_fallback_encodings(file_path)
    elif suffix in {".xlsx", ".xlsm"}:
        frame = pd.read_excel(file_path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")

    if frame.empty:
        raise ValueError("No measurement rows found in source file")

    return frame


def _read_csv_with_fallback_encodings(file_path: Path) -> pd.DataFrame:
    last_decode_error: UnicodeDecodeError | None = None

    for encoding in CSV_ENCODINGS:
        try:
            return pd.read_csv(file_path, encoding=encoding)
        except UnicodeDecodeError as exc:
            last_decode_error = exc

    if last_decode_error is not None:
        raise ValueError(
            "Unsupported CSV encoding. Please upload a UTF-8 or GB18030 encoded CSV file."
        ) from last_decode_error

    raise ValueError("Unable to read CSV source file")


def infer_field_mapping(frame: pd.DataFrame) -> FieldMapping:
    lowered = {str(column).strip().lower(): column for column in frame.columns}

    measurement_column = (
        lowered.get("value")
        or lowered.get("measurement")
        or lowered.get("measurement_value")
    )
    if measurement_column is None:
        numeric_candidates = frame.select_dtypes(include="number").columns.tolist()
        if not numeric_candidates:
            raise ValueError("No numeric measurement column found")
        measurement_column = numeric_candidates[0]

    return FieldMapping(
        sample_id_column=lowered.get("sample_id") or lowered.get("sample"),
        batch_column=lowered.get("batch_id") or lowered.get("batch"),
        measurement_column=measurement_column,
        lsl_column=lowered.get("lsl") or lowered.get("lower_spec_limit"),
        usl_column=lowered.get("usl") or lowered.get("upper_spec_limit"),
        target_column=lowered.get("target") or lowered.get("target_value"),
        timestamp_column=(
            lowered.get("measured_at")
            or lowered.get("timestamp")
            or lowered.get("time")
        ),
        sequence_column=(
            lowered.get("sequence_index")
            or lowered.get("sequence")
            or lowered.get("index")
        ),
    )


def normalize_measurements(frame: pd.DataFrame, mapping: FieldMapping) -> pd.DataFrame:
    def normalize_spec_limit(column_name: str | None) -> pd.Series | None:
        if not column_name:
            return None
        normalized_limit = pd.to_numeric(frame[column_name], errors="coerce").ffill().bfill()
        if normalized_limit.notna().any():
            first_non_null_limit = normalized_limit.dropna().iloc[0]
            return pd.Series(first_non_null_limit, index=frame.index)
        return normalized_limit

    normalized = pd.DataFrame(index=frame.index, columns=CANONICAL_COLUMNS)
    normalized["sample_id"] = (
        frame[mapping.sample_id_column]
        if mapping.sample_id_column
        else frame.index.astype(str)
    )
    normalized["batch_id"] = (
        frame[mapping.batch_column] if mapping.batch_column else "DEMO-BATCH"
    )
    normalized["part_number"] = "6205"
    normalized["inspection_item"] = "Outer Diameter"
    normalized["measurement_value"] = frame[mapping.measurement_column].astype(float)
    normalized["target_value"] = (
        frame[mapping.target_column].astype(float) if mapping.target_column else None
    )
    normalized["usl"] = normalize_spec_limit(mapping.usl_column)
    normalized["lsl"] = normalize_spec_limit(mapping.lsl_column)
    normalized["unit"] = "mm"
    normalized["measured_at"] = (
        pd.to_datetime(frame[mapping.timestamp_column])
        if mapping.timestamp_column
        else pd.NaT
    )

    if mapping.sequence_column:
        normalized["sequence_index"] = frame[mapping.sequence_column].astype(int)
    else:
        normalized["sequence_index"] = range(1, len(frame) + 1)

    normalized["operator_name"] = "demo-operator"
    normalized["device_name"] = "demo-gauge"
    return normalized


def build_dataset_profile(normalized: pd.DataFrame) -> DatasetProfile:
    if normalized.empty:
        return DatasetProfile(
            row_count=0,
            has_spec_limits=False,
            has_timestamp=False,
            has_sequence=False,
        )

    has_spec_limits = normalized["usl"].notna().all() and normalized["lsl"].notna().all()
    has_timestamp = normalized["measured_at"].notna().any()
    has_sequence = normalized["sequence_index"].notna().any()
    return DatasetProfile(
        row_count=len(normalized),
        has_spec_limits=bool(has_spec_limits),
        has_timestamp=bool(has_timestamp),
        has_sequence=bool(has_sequence),
    )
