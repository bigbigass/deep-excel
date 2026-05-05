"""源数据读取与标准化服务。

这个模块解决两个核心问题：
1. 用户上传的 CSV/XLSX 列名并不统一，不能直接拿来做分析。
2. 后续分析、图表、报表模板都希望面对同一套固定字段。

所以这里会把“长得不一样的源表”收敛成统一的标准表结构。
"""

from pathlib import Path

import pandas as pd

from api.app.schemas import DatasetProfile, FieldMapping

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
# 这组列名就是系统内部约定的“标准数据协议”。
# 后面的 analytics / charts / excel 都默认输入已经被整理成这套字段。


def load_source_dataframe(file_path: Path) -> pd.DataFrame:
    """按文件后缀读取原始数据，并做最基础的空文件校验。

    这里只负责把文件读成 DataFrame，不在这里做业务字段判断，
    这样读取和业务解释两件事可以分开。
    """
    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(file_path, encoding="utf-8-sig")
    elif suffix in {".xlsx", ".xlsm"}:
        frame = pd.read_excel(file_path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")

    if frame.empty:
        raise ValueError("No measurement rows found in source file")

    return frame


def infer_field_mapping(frame: pd.DataFrame) -> FieldMapping:
    """基于常见列名约定推断字段映射，作为非 AI 场景下的兜底逻辑。

    当前主流程优先走 AI 字段识别；这个函数更像是保守规则版本，
    当未来需要降级方案或快速脚本处理时可以直接复用。
    """
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
    """将源数据整理为统一列集合，便于后续分析和报表渲染。

    `mapping` 只描述“原表哪一列对应什么业务含义”，
    而这个函数真正负责把原始列搬运、转型、补空列，输出内部标准结构。
    """
    def normalize_spec_limit(column_name: str | None) -> pd.Series | None:
        """把规格限列压平成整列常量，适配模板和统计逻辑。

        很多源表会在第一行写一次 USL/LSL，后面留空。这里通过前后填充把它补齐，
        再统一压成“整列常量”，后面算合格率和渲染明细时会更简单。
        """
        if not column_name:
            return None
        normalized_limit = pd.to_numeric(frame[column_name], errors="coerce").ffill().bfill()
        if normalized_limit.notna().any():
            first_non_null_limit = normalized_limit.dropna().iloc[0]
            return pd.Series(first_non_null_limit, index=frame.index)
        return normalized_limit

    normalized = pd.DataFrame(index=frame.index, columns=CANONICAL_COLUMNS)
    # 先填“有来源可直接映射”的字段。
    normalized["sample_id"] = (
        frame[mapping.sample_id_column]
        if mapping.sample_id_column
        else None
    )
    normalized["batch_id"] = (
        frame[mapping.batch_column] if mapping.batch_column else None
    )
    normalized["part_number"] = None
    normalized["inspection_item"] = None
    # measurement_value 是后续所有统计的核心列，所以这里直接强转为 float。
    normalized["measurement_value"] = frame[mapping.measurement_column].astype(float)
    normalized["target_value"] = (
        frame[mapping.target_column].astype(float) if mapping.target_column else None
    )
    normalized["usl"] = normalize_spec_limit(mapping.usl_column)
    normalized["lsl"] = normalize_spec_limit(mapping.lsl_column)
    normalized["unit"] = None
    normalized["measured_at"] = (
        pd.to_datetime(frame[mapping.timestamp_column])
        if mapping.timestamp_column
        else pd.NaT
    )

    if mapping.sequence_column:
        normalized["sequence_index"] = frame[mapping.sequence_column].astype(int)
    else:
        # 缺少显式序号时先留空，后续图表可根据业务需要自行补位。
        normalized["sequence_index"] = None

    # 这些字段在当前 demo 场景里没有稳定来源，但先保留在标准协议中，
    # 这样以后扩展模板或分析时不需要重新设计内部表结构。
    normalized["operator_name"] = None
    normalized["device_name"] = None
    return normalized


def build_dataset_profile(normalized: pd.DataFrame) -> DatasetProfile:
    """提取模板选择和前端展示会用到的数据画像。

    这是对标准表的“摘要判断”，不关心具体数值分布，只关心数据是否具备
    规格限、时间、序号这些能力，用于上层做展示和分支选择。
    """
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
