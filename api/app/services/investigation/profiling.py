"""调查数据集质量画像工具。"""

from __future__ import annotations

import pandas as pd

from api.app.domain import EvidenceItem

CONTEXT_DIMENSION_COLUMNS = [
    "machine_id",
    "station_id",
    "tool_id",
    "mold_id",
    "cavity_id",
    "shift",
    "operator_id",
    "material_lot",
    "supplier",
    "work_order",
]


def profile_dataset(
    frame: pd.DataFrame,
    *,
    evidence_id: str = "E-DATA-QUALITY",
    source_refs: list[str] | None = None,
) -> EvidenceItem:
    """检查质量调查数据是否完整、可计算并具备分层分析条件。"""
    if frame.empty:
        raise ValueError("investigation dataset must contain at least one row")
    if "measurement_value" not in frame.columns:
        raise ValueError("measurement_value column is required")

    row_count = len(frame)
    measurement_values = pd.to_numeric(frame["measurement_value"], errors="coerce")
    valid_measurement_count = int(measurement_values.notna().sum())
    missing_measurement_count = row_count - valid_measurement_count
    if valid_measurement_count == 0:
        raise ValueError("investigation dataset has no valid measurement values")

    duplicate_sample_count = 0
    if "sample_id" in frame.columns:
        sample_ids = frame["sample_id"].dropna().astype(str)
        duplicate_sample_count = int(sample_ids.duplicated().sum())

    valid_specification_count = 0
    if {"usl", "lsl"}.issubset(frame.columns):
        usl = pd.to_numeric(frame["usl"], errors="coerce")
        lsl = pd.to_numeric(frame["lsl"], errors="coerce")
        valid_specification_count = int((usl.notna() & lsl.notna() & (usl > lsl)).sum())

    valid_timestamp_count = 0
    if "measured_at" in frame.columns:
        measured_at = pd.to_datetime(frame["measured_at"], errors="coerce")
        valid_timestamp_count = int(measured_at.notna().sum())

    quality_feature_count = 1
    if "quality_feature" in frame.columns:
        quality_feature_count = max(1, int(frame["quality_feature"].dropna().nunique()))

    context_dimensions = [
        column
        for column in CONTEXT_DIMENSION_COLUMNS
        if column in frame.columns and frame[column].dropna().nunique() > 1
    ]

    issues: list[str] = []
    if missing_measurement_count:
        issues.append(f"{missing_measurement_count} 条测量值缺失或无法转为数值")
    if duplicate_sample_count:
        issues.append(f"{duplicate_sample_count} 条样本编号重复")
    if valid_specification_count < row_count:
        issues.append(f"仅 {valid_specification_count}/{row_count} 条记录具备有效规格限")
    if "measured_at" not in frame.columns or valid_timestamp_count < row_count:
        issues.append(f"仅 {valid_timestamp_count}/{row_count} 条记录具备有效时间")
    if not context_dimensions:
        issues.append("缺少可用于分层调查的生产上下文字段")

    if missing_measurement_count == 0 and valid_timestamp_count == row_count and context_dimensions:
        confidence = "high"
    elif valid_measurement_count == row_count:
        confidence = "medium"
    else:
        confidence = "low"

    context_text = "、".join(context_dimensions) if context_dimensions else "无"
    statement = (
        f"数据集包含 {row_count} 条记录、{quality_feature_count} 个质量特征，"
        f"有效测量值 {valid_measurement_count} 条，可用分层维度为 {context_text}。"
    )
    if issues:
        statement += " 需要关注：" + "；".join(issues) + "。"
    else:
        statement += " 当前未发现阻断调查的数据质量问题。"

    return EvidenceItem(
        id=evidence_id,
        evidence_type="data_quality",
        title="调查数据质量画像",
        statement=statement,
        metrics={
            "row_count": row_count,
            "column_count": len(frame.columns),
            "quality_feature_count": quality_feature_count,
            "valid_measurement_count": valid_measurement_count,
            "missing_measurement_count": missing_measurement_count,
            "duplicate_sample_count": duplicate_sample_count,
            "valid_specification_count": valid_specification_count,
            "valid_timestamp_count": valid_timestamp_count,
            "context_dimensions": context_dimensions,
            "issues": issues,
        },
        sample_size=row_count,
        source_refs=source_refs or [],
        confidence=confidence,
        origin="deterministic_tool",
    )
