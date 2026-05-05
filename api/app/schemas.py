"""接口层和服务层共用的数据模型。"""

from typing import Literal

from pydantic import BaseModel

JobTaskStatus = Literal["pending", "running", "completed", "failed"]


class FieldMapping(BaseModel):
    """源数据列名到标准字段的映射关系。"""

    sample_id_column: str | None = None
    batch_column: str | None = None
    measurement_column: str
    lsl_column: str | None = None
    usl_column: str | None = None
    target_column: str | None = None
    timestamp_column: str | None = None
    sequence_column: str | None = None


class JobTask(BaseModel):
    """前端任务进度条中的单个步骤。"""

    id: str
    label: str
    status: JobTaskStatus
    error: str | None = None
    reasoning: str | None = None


class DatasetProfile(BaseModel):
    """标准化数据集的基础画像，用于模板和分析决策。"""

    row_count: int
    has_spec_limits: bool
    has_timestamp: bool
    has_sequence: bool
