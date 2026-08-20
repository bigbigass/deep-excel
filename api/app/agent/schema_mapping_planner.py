"""AI 语义字段映射规划器；所有输出仍需代码校验和人工确认。"""

from __future__ import annotations

import json
from collections import Counter
from typing import Protocol

import pandas as pd
from pydantic import BaseModel, Field, field_validator, model_validator

from api.app.agent.factory import build_agent_model
from api.app.config import get_settings
from api.app.domain.mapping import ColumnMapping, ColumnRole, SchemaMappingProposal
from api.app.services.report_localization import has_cjk_text


class AiColumnMapping(BaseModel):
    source_column: str = Field(min_length=1)
    role: ColumnRole
    confidence: float = Field(ge=0, le=1)
    reasoning: str = Field(min_length=1)

    @field_validator("source_column", "reasoning")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        candidate = value.strip()
        if not candidate:
            raise ValueError("text must not be empty")
        return candidate

    @field_validator("reasoning")
    @classmethod
    def require_chinese_reasoning(cls, value: str) -> str:
        if not has_cjk_text(value):
            raise ValueError("mapping reasoning must contain Chinese text")
        return value


class AiSchemaMappingResponse(BaseModel):
    mappings: list[AiColumnMapping] = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("warnings")
    @classmethod
    def normalize_warnings(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            candidate = value.strip()
            if not candidate or candidate in seen:
                continue
            if not has_cjk_text(candidate):
                raise ValueError("mapping warnings must contain Chinese text")
            seen.add(candidate)
            result.append(candidate)
        return result

    @model_validator(mode="after")
    def validate_unique_sources_and_roles(self):
        sources = [item.source_column for item in self.mappings]
        duplicate_sources = sorted(value for value, count in Counter(sources).items() if count > 1)
        if duplicate_sources:
            raise ValueError(f"duplicate source columns in AI mapping: {duplicate_sources}")
        roles = [item.role for item in self.mappings if item.role != "ignore"]
        duplicate_roles = sorted(value for value, count in Counter(roles).items() if count > 1)
        if duplicate_roles:
            raise ValueError(f"duplicate semantic roles in AI mapping: {duplicate_roles}")
        return self


class StructuredOutputInvoker(Protocol):
    def invoke(self, messages: list[dict[str, str]]) -> object:
        ...


class StructuredOutputModel(Protocol):
    def with_structured_output(self, schema: type[AiSchemaMappingResponse]) -> StructuredOutputInvoker:
        ...


def _build_mapping_messages(
    frame: pd.DataFrame,
    *,
    file_name: str,
    deterministic_proposal: SchemaMappingProposal,
) -> list[dict[str, str]]:
    columns = [
        {
            "name": str(column),
            "dtype": str(frame[column].dtype),
            "non_null_count": int(frame[column].notna().sum()),
            "sample_values": [str(value) for value in frame[column].dropna().head(5).tolist()],
        }
        for column in frame.columns
    ]
    existing = [item.model_dump(mode="json") for item in deterministic_proposal.mappings]
    payload = {
        "file_name": file_name,
        "row_count": len(frame),
        "columns": columns,
        "deterministic_suggestions": existing,
        "allowed_roles": [
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
            "ignore",
        ],
    }
    return [
        {
            "role": "system",
            "content": (
                "你负责识别制造业质量数据表的字段语义。"
                "必须为每个源列返回且仅返回一个映射，source_column 必须逐字复制。"
                "一个非 ignore 角色最多分配给一个源列。"
                "measurement_value 是测量结果，不要把序号、规格限、目标值或刀具次数当成测量值。"
                "无法确定时使用 ignore，不要猜测。"
                "confidence 表示语义置信度，reasoning 必须是简短中文。"
                "你只提出建议，最终映射必须由代码校验并由用户确认。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        },
    ]


def _role_is_compatible(frame: pd.DataFrame, item: AiColumnMapping) -> tuple[bool, str | None]:
    series = frame[item.source_column]
    if item.role in {"measurement_value", "target", "usl", "lsl", "sequence_index", "tool_cycles"}:
        non_null = series.dropna()
        if non_null.empty:
            return False, f"{item.source_column} 没有可用于 {item.role} 的非空值。"
        convertible = pd.to_numeric(non_null, errors="coerce").notna().mean()
        if convertible < 0.8:
            return False, f"{item.source_column} 的数值可转换比例不足，不能映射为 {item.role}。"
    if item.role == "measured_at":
        non_null = series.dropna()
        if non_null.empty:
            return False, f"{item.source_column} 没有可用于 measured_at 的非空值。"
        convertible = pd.to_datetime(non_null, errors="coerce").notna().mean()
        if convertible < 0.8:
            return False, f"{item.source_column} 的时间可解析比例不足，不能映射为 measured_at。"
    return True, None


def merge_ai_mapping_proposal(
    frame: pd.DataFrame,
    deterministic: SchemaMappingProposal,
    response: AiSchemaMappingResponse,
) -> SchemaMappingProposal:
    """锁定高置信规则结果，只让 AI 补充未解释字段。"""
    source_set = set(deterministic.source_columns)
    ai_source_set = {item.source_column for item in response.mappings}
    if ai_source_set != source_set:
        missing = sorted(source_set - ai_source_set)
        unknown = sorted(ai_source_set - source_set)
        raise ValueError(f"AI mapping must cover exact source columns; missing={missing}, unknown={unknown}")

    deterministic_by_source = {item.source_column: item for item in deterministic.mappings}
    ai_by_source = {item.source_column: item for item in response.mappings}
    locked_roles = {
        item.role
        for item in deterministic.mappings
        if item.role != "ignore" and item.confidence >= 0.95
    }
    chosen_roles: set[ColumnRole] = set(locked_roles)
    merged: list[ColumnMapping] = []
    warnings = [*deterministic.warnings, *response.warnings]

    for source_column in deterministic.source_columns:
        deterministic_item = deterministic_by_source[source_column]
        if deterministic_item.role != "ignore" and deterministic_item.confidence >= 0.95:
            merged.append(deterministic_item)
            continue

        ai_item = ai_by_source[source_column]
        compatible, warning = _role_is_compatible(frame, ai_item)
        if warning:
            warnings.append(warning)
        if not compatible or ai_item.role == "ignore":
            merged.append(
                ColumnMapping(
                    source_column=source_column,
                    role="ignore",
                    confidence=0.0,
                    reasoning=warning or ai_item.reasoning,
                    origin="ai",
                )
            )
            continue
        if ai_item.role in chosen_roles:
            warnings.append(
                f"AI 将 {source_column} 映射为已占用角色 {ai_item.role}，该建议已忽略。"
            )
            merged.append(
                ColumnMapping(
                    source_column=source_column,
                    role="ignore",
                    confidence=0.0,
                    reasoning="AI 建议与已有高置信映射冲突，等待人工确认。",
                    origin="ai",
                )
            )
            continue

        chosen_roles.add(ai_item.role)
        merged.append(
            ColumnMapping(
                source_column=source_column,
                role=ai_item.role,
                confidence=ai_item.confidence,
                reasoning=ai_item.reasoning,
                origin="ai",
            )
        )

    assigned_roles = {item.role for item in merged if item.role != "ignore"}
    missing_required_roles: list[ColumnRole] = []
    if "measurement_value" not in assigned_roles:
        missing_required_roles.append("measurement_value")
        warnings.append("AI 仍未识别测量值列，必须由用户指定。")
    if ("usl" in assigned_roles) != ("lsl" in assigned_roles):
        warnings.append("AI 只识别到一侧规格限，合格率与过程能力将不可完整计算。")

    generated_by = "hybrid" if any(item.origin == "ai" and item.role != "ignore" for item in merged) else deterministic.generated_by
    return SchemaMappingProposal(
        file_name=deterministic.file_name,
        source_columns=deterministic.source_columns,
        mappings=merged,
        status="pending",
        generated_by=generated_by,
        missing_required_roles=missing_required_roles,
        warnings=warnings,
        revision=deterministic.revision,
    )


class SchemaMappingPlanner:
    """调用模型理解非标准表头，但不自动确认结果。"""

    def __init__(self, model: StructuredOutputModel | None = None) -> None:
        self.model = model or build_agent_model()

    def plan(
        self,
        frame: pd.DataFrame,
        *,
        file_name: str,
        deterministic_proposal: SchemaMappingProposal,
    ) -> SchemaMappingProposal:
        structured_model = self.model.with_structured_output(AiSchemaMappingResponse)
        raw_response = structured_model.invoke(
            _build_mapping_messages(
                frame,
                file_name=file_name,
                deterministic_proposal=deterministic_proposal,
            )
        )
        response = AiSchemaMappingResponse.model_validate(raw_response)
        return merge_ai_mapping_proposal(frame, deterministic_proposal, response)


def build_schema_mapping_planner() -> SchemaMappingPlanner:
    settings = get_settings()
    if not settings.openai_api_key:
        raise ValueError("DEEPEXCEL_OPENAI_API_KEY is required for AI schema mapping")
    return SchemaMappingPlanner()
