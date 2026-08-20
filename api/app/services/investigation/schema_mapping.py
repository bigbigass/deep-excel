"""调查数据的确定性字段建议、人工确认与标准化。"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import pandas as pd

from api.app.domain.mapping import (
    ColumnMapping,
    ColumnRole,
    SchemaMappingConfirmation,
    SchemaMappingProposal,
    confirmed_at_now,
)

_INVESTIGATION_COLUMNS: list[ColumnRole] = [
    "sample_id",
    "batch_id",
    "measured_at",
    "sequence_index",
    "quality_feature",
    "measurement_value",
    "target",
    "usl",
    "lsl",
    "machine_id",
    "station_id",
    "cavity_id",
    "shift",
    "operator_id",
    "material_lot",
    "tool_id",
    "tool_cycles",
]
_NUMERIC_ROLES: set[ColumnRole] = {
    "measurement_value",
    "target",
    "usl",
    "lsl",
    "sequence_index",
    "tool_cycles",
}

_ROLE_ALIASES: dict[ColumnRole, set[str]] = {
    "sample_id": {
        "sample_id",
        "sample",
        "sample_no",
        "sample_number",
        "serial_number",
        "sn",
        "样本编号",
        "样品编号",
        "序列号",
        "产品序列号",
    },
    "batch_id": {
        "batch_id",
        "batch",
        "batch_no",
        "lot_no",
        "批次",
        "批次号",
        "生产批次",
    },
    "measured_at": {
        "measured_at",
        "timestamp",
        "datetime",
        "measurement_time",
        "inspection_time",
        "检测时间",
        "测量时间",
        "检验时间",
        "采集时间",
    },
    "sequence_index": {
        "sequence_index",
        "sequence",
        "row_index",
        "sample_index",
        "序号",
        "顺序",
        "采样序号",
    },
    "quality_feature": {
        "quality_feature",
        "inspection_item",
        "characteristic",
        "feature_name",
        "检测项目",
        "检验项目",
        "质量特性",
        "测量项目",
    },
    "measurement_value": {
        "measurement_value",
        "measurement",
        "measured_value",
        "inspection_value",
        "result_value",
        "value",
        "diameter_mm",
        "outer_diameter_value",
        "测量值",
        "实测值",
        "检测值",
        "检验值",
        "结果值",
        "外径实测值",
        "内径实测值",
        "尺寸实测值",
    },
    "target": {
        "target",
        "target_value",
        "nominal",
        "nominal_value",
        "center_value",
        "目标值",
        "标称值",
        "中心值",
    },
    "usl": {
        "usl",
        "upper_spec_limit",
        "upper_limit",
        "spec_upper",
        "max_limit",
        "规格上限",
        "上规格限",
        "上限",
        "最大允许值",
    },
    "lsl": {
        "lsl",
        "lower_spec_limit",
        "lower_limit",
        "spec_lower",
        "min_limit",
        "规格下限",
        "下规格限",
        "下限",
        "最小允许值",
    },
    "machine_id": {
        "machine_id",
        "machine",
        "equipment_id",
        "equipment",
        "设备编号",
        "设备号",
        "机台编号",
        "机台",
    },
    "station_id": {
        "station_id",
        "station",
        "workstation",
        "工位编号",
        "工位",
        "工作站",
    },
    "cavity_id": {
        "cavity_id",
        "cavity",
        "mold_cavity",
        "型腔编号",
        "型腔",
        "模穴",
        "穴号",
    },
    "shift": {
        "shift",
        "work_shift",
        "班次",
        "班组",
        "白夜班",
    },
    "operator_id": {
        "operator_id",
        "operator",
        "employee_id",
        "操作员",
        "操作工",
        "员工编号",
    },
    "material_lot": {
        "material_lot",
        "material_batch",
        "raw_material_lot",
        "物料批次",
        "材料批次",
        "原料批次",
    },
    "tool_id": {
        "tool_id",
        "tool",
        "cutter_id",
        "fixture_id",
        "刀具编号",
        "刀具",
        "工装编号",
        "夹具编号",
    },
    "tool_cycles": {
        "tool_cycles",
        "tool_life",
        "cycle_count",
        "usage_count",
        "刀具次数",
        "刀具寿命",
        "使用次数",
        "加工次数",
    },
}


def normalize_column_label(value: object) -> str:
    """把中英文列名压成稳定的比较键。"""
    text = unicodedata.normalize("NFKC", str(value)).strip().lower()
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", text)


_NORMALIZED_ALIASES: dict[ColumnRole, set[str]] = {
    role: {normalize_column_label(alias) for alias in aliases | {role}}
    for role, aliases in _ROLE_ALIASES.items()
}
_ALIAS_TO_ROLES: dict[str, set[ColumnRole]] = defaultdict(set)
for _role, _aliases in _NORMALIZED_ALIASES.items():
    for _alias in _aliases:
        _ALIAS_TO_ROLES[_alias].add(_role)


def _candidate_from_label(source_column: str) -> tuple[ColumnRole, float, str, str] | None:
    normalized = normalize_column_label(source_column)
    roles = _ALIAS_TO_ROLES.get(normalized, set())
    if len(roles) != 1:
        return None
    role = next(iter(roles))
    canonical_match = source_column.strip().lower() == role
    if canonical_match:
        return role, 1.0, "源列名与调查标准字段完全一致。", "canonical"
    return role, 0.95, "源列名命中受控的中英文质量字段别名。", "rule"


def _resolve_duplicate_roles(mappings: list[ColumnMapping]) -> tuple[list[ColumnMapping], list[str]]:
    by_role: dict[ColumnRole, list[ColumnMapping]] = defaultdict(list)
    for item in mappings:
        if item.role != "ignore":
            by_role[item.role].append(item)

    warnings: list[str] = []
    winners: dict[ColumnRole, ColumnMapping] = {}
    for role, candidates in by_role.items():
        ordered = sorted(
            candidates,
            key=lambda item: (
                item.confidence,
                item.origin == "canonical",
                -mappings.index(item),
            ),
            reverse=True,
        )
        winners[role] = ordered[0]
        if len(ordered) > 1:
            warnings.append(
                f"多个源列被识别为 {role}，暂保留 {ordered[0].source_column}，其余列需人工复核。"
            )

    resolved: list[ColumnMapping] = []
    for item in mappings:
        if item.role == "ignore" or winners.get(item.role) is item:
            resolved.append(item)
        else:
            resolved.append(
                ColumnMapping(
                    source_column=item.source_column,
                    role="ignore",
                    confidence=0.0,
                    reasoning=f"与 {winners[item.role].source_column} 竞争同一角色，等待人工确认。",
                    origin="rule",
                )
            )
    return resolved, warnings


def build_rule_mapping_proposal(frame: pd.DataFrame, file_name: str) -> SchemaMappingProposal:
    """先用透明规则产生映射；不确定内容保留给 AI 或用户。"""
    source_columns = [str(column) for column in frame.columns]
    mappings: list[ColumnMapping] = []
    warnings: list[str] = []

    for source_column in source_columns:
        candidate = _candidate_from_label(source_column)
        if candidate is None:
            mappings.append(
                ColumnMapping(
                    source_column=source_column,
                    role="ignore",
                    confidence=0.0,
                    reasoning="未命中受控别名，等待 AI 或人工判断。",
                    origin="rule",
                )
            )
            continue
        role, confidence, reasoning, origin = candidate
        mappings.append(
            ColumnMapping(
                source_column=source_column,
                role=role,
                confidence=confidence,
                reasoning=reasoning,
                origin=origin,
            )
        )

    mappings, duplicate_warnings = _resolve_duplicate_roles(mappings)
    warnings.extend(duplicate_warnings)
    assigned_roles = {item.role for item in mappings if item.role != "ignore"}

    if "measurement_value" not in assigned_roles:
        ignored_numeric_columns = [
            item.source_column
            for item in mappings
            if item.role == "ignore" and pd.api.types.is_numeric_dtype(frame[item.source_column])
        ]
        if len(ignored_numeric_columns) == 1:
            candidate_column = ignored_numeric_columns[0]
            mappings = [
                ColumnMapping(
                    source_column=item.source_column,
                    role="measurement_value" if item.source_column == candidate_column else item.role,
                    confidence=0.6 if item.source_column == candidate_column else item.confidence,
                    reasoning=(
                        "文件仅有一个尚未解释的数值列，暂建议作为测量值；必须人工确认。"
                        if item.source_column == candidate_column
                        else item.reasoning
                    ),
                    origin="rule" if item.source_column == candidate_column else item.origin,
                )
                for item in mappings
            ]
            assigned_roles.add("measurement_value")
            warnings.append(f"{candidate_column} 仅根据数值类型被建议为测量值。")

    if ("usl" in assigned_roles) != ("lsl" in assigned_roles):
        warnings.append("规格上限和规格下限只识别到一项，合格率与过程能力将无法完整计算。")

    missing_required_roles: list[ColumnRole] = []
    if "measurement_value" not in assigned_roles:
        missing_required_roles.append("measurement_value")
        warnings.append("尚未识别测量值列，必须由用户指定后才能开始调查。")

    non_ignored = [item for item in mappings if item.role != "ignore"]
    generated_by = "canonical" if non_ignored and all(item.origin == "canonical" for item in non_ignored) else "deterministic"
    return SchemaMappingProposal(
        file_name=Path(file_name).name,
        source_columns=source_columns,
        mappings=mappings,
        status="pending",
        generated_by=generated_by,
        missing_required_roles=missing_required_roles,
        warnings=warnings,
    )


def auto_confirm_canonical_mapping(proposal: SchemaMappingProposal) -> SchemaMappingProposal | None:
    """只对完全同名的标准字段自动确认，别名和猜测都必须人工复核。"""
    if proposal.missing_required_roles:
        return None
    assigned = [item for item in proposal.mappings if item.role != "ignore"]
    if not assigned or any(
        item.origin != "canonical" or item.source_column.strip().lower() != item.role
        for item in assigned
    ):
        return None
    return proposal.model_copy(
        update={
            "status": "confirmed",
            "generated_by": "canonical",
            "confirmed_by": "system:canonical-schema",
            "confirmed_at": confirmed_at_now(),
        }
    )


def confirm_schema_mapping(
    proposal: SchemaMappingProposal,
    confirmation: SchemaMappingConfirmation,
) -> SchemaMappingProposal:
    """用用户提交的完整角色表替换建议映射，并保留责任记录。"""
    if proposal.status == "confirmed":
        raise ValueError("schema mapping is already confirmed")
    source_set = set(proposal.source_columns)
    assignment_set = {item.source_column for item in confirmation.mappings}
    if assignment_set != source_set:
        missing = sorted(source_set - assignment_set)
        unknown = sorted(assignment_set - source_set)
        raise ValueError(
            f"mapping confirmation must cover every source column; missing={missing}, unknown={unknown}"
        )

    mappings = [
        ColumnMapping(
            source_column=item.source_column,
            role=item.role,
            confidence=1.0,
            reasoning="用户已确认该源列的业务语义。",
            origin="human",
        )
        for item in confirmation.mappings
    ]
    assigned_roles = {item.role for item in mappings if item.role != "ignore"}
    missing_required_roles: list[ColumnRole] = []
    if "measurement_value" not in assigned_roles:
        missing_required_roles.append("measurement_value")
    if missing_required_roles:
        raise ValueError("measurement_value must be assigned before confirmation")

    warnings: list[str] = []
    if ("usl" in assigned_roles) != ("lsl" in assigned_roles):
        warnings.append("仅映射了一侧规格限，合格率与过程能力将不可用。")

    return SchemaMappingProposal(
        file_name=proposal.file_name,
        source_columns=proposal.source_columns,
        mappings=mappings,
        status="confirmed",
        generated_by="human",
        missing_required_roles=[],
        warnings=warnings,
        confirmed_by=confirmation.actor_id,
        confirmed_at=confirmed_at_now(),
        revision=proposal.revision + 1,
    )


def _convert_numeric_series(
    frame: pd.DataFrame,
    source_column: str,
    *,
    role: ColumnRole,
) -> pd.Series:
    original = frame[source_column]
    converted = pd.to_numeric(original, errors="coerce")
    invalid_mask = original.notna() & converted.isna()
    if invalid_mask.any():
        example_values = original.loc[invalid_mask].astype(str).head(3).tolist()
        raise ValueError(
            f"source column {source_column} mapped to {role} contains non-numeric values: {example_values}"
        )
    return converted


def normalize_investigation_frame(
    frame: pd.DataFrame,
    proposal: SchemaMappingProposal,
) -> pd.DataFrame:
    """按已确认映射生成调查工具统一消费的标准 DataFrame。"""
    if proposal.status != "confirmed":
        raise ValueError("schema mapping must be confirmed before normalization")
    if list(map(str, frame.columns)) != proposal.source_columns:
        raise ValueError("source columns changed after the schema mapping was proposed")

    by_role = {
        item.role: item.source_column
        for item in proposal.mappings
        if item.role != "ignore"
    }
    measurement_source = by_role.get("measurement_value")
    if measurement_source is None:
        raise ValueError("measurement_value mapping is required")

    normalized = pd.DataFrame(index=frame.index)
    for role in _INVESTIGATION_COLUMNS:
        source_column = by_role.get(role)
        if source_column is None:
            continue
        if role in _NUMERIC_ROLES:
            normalized[role] = _convert_numeric_series(frame, source_column, role=role)
        elif role == "measured_at":
            parsed = pd.to_datetime(frame[source_column], errors="coerce")
            invalid_mask = frame[source_column].notna() & parsed.isna()
            if invalid_mask.any():
                examples = frame.loc[invalid_mask, source_column].astype(str).head(3).tolist()
                raise ValueError(
                    f"source column {source_column} mapped to measured_at contains invalid timestamps: {examples}"
                )
            normalized[role] = parsed
        else:
            normalized[role] = frame[source_column]

    if "sample_id" not in normalized:
        normalized["sample_id"] = [f"S-{index:06d}" for index in range(1, len(frame) + 1)]
    else:
        generated = pd.Series(
            [f"S-{index:06d}" for index in range(1, len(frame) + 1)],
            index=frame.index,
        )
        normalized["sample_id"] = normalized["sample_id"].where(
            normalized["sample_id"].notna(),
            generated,
        )

    if "sequence_index" not in normalized:
        normalized["sequence_index"] = range(1, len(frame) + 1)
    if "quality_feature" not in normalized:
        normalized["quality_feature"] = "measurement"
    if "measured_at" not in normalized:
        normalized["measured_at"] = pd.NaT

    for role in ("usl", "lsl"):
        if role in normalized:
            normalized[role] = normalized[role].ffill().bfill()
        else:
            normalized[role] = None
    if "target" not in normalized:
        normalized["target"] = None

    for role in _INVESTIGATION_COLUMNS:
        if role not in normalized:
            normalized[role] = None

    ordered_columns = [role for role in _INVESTIGATION_COLUMNS if role in normalized]
    return normalized[ordered_columns]
