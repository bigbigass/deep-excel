from pydantic import BaseModel


class FieldMapping(BaseModel):
    sample_id_column: str | None = None
    batch_column: str | None = None
    measurement_column: str
    lsl_column: str | None = None
    usl_column: str | None = None
    target_column: str | None = None
    timestamp_column: str | None = None
    sequence_column: str | None = None


class DatasetProfile(BaseModel):
    row_count: int
    has_spec_limits: bool
    has_timestamp: bool
    has_sequence: bool
