"""Whitelisted deterministic tools available to the investigation planner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from api.app.domain import EvidenceItem
from api.app.domain.ai import (
    InvestigationPlan,
    InvestigationToolCall,
    InvestigationToolDescription,
)
from api.app.services.investigation.change_points import detect_mean_change_point
from api.app.services.investigation.factor_ranking import rank_failure_associations
from api.app.services.investigation.group_comparison import compare_group_failure_rates
from api.app.services.investigation.profiling import profile_dataset
from api.app.services.investigation.spc_signals import detect_spc_signals

ToolHandler = Callable[..., EvidenceItem]


class SafeToolArguments(BaseModel):
    """Base model that rejects undeclared model-generated arguments."""

    model_config = ConfigDict(extra="forbid")


class DatasetProfileArguments(SafeToolArguments):
    pass


class SpcSignalArguments(SafeToolArguments):
    value_column: str = "measurement_value"
    order_column: str = "measured_at"
    same_side_run_length: int = Field(default=8, ge=2, le=20)
    trend_point_count: int = Field(default=6, ge=3, le=20)


class MeanChangePointArguments(SafeToolArguments):
    value_column: str = "measurement_value"
    order_column: str = "measured_at"
    min_segment_size: int = Field(default=12, ge=2, le=10_000)
    alpha: float = Field(default=0.01, gt=0, lt=1)
    min_absolute_shift: float | None = Field(default=None, ge=0)


class GroupFailureRateArguments(SafeToolArguments):
    group_by: list[str] = Field(min_length=1, max_length=3)
    value_column: str = "measurement_value"
    lsl_column: str = "lsl"
    usl_column: str = "usl"
    min_group_size: int = Field(default=5, ge=1)
    alpha: float = Field(default=0.05, gt=0, lt=1)
    minimum_rate_difference: float = Field(default=0.05, ge=0, le=1)


class FactorRankingArguments(SafeToolArguments):
    candidate_columns: list[str] = Field(min_length=1, max_length=20)
    value_column: str = "measurement_value"
    lsl_column: str = "lsl"
    usl_column: str = "usl"
    categorical_columns: list[str] | None = None
    numeric_columns: list[str] | None = None
    max_categories: int = Field(default=20, ge=2, le=100)
    alpha: float = Field(default=0.05, gt=0, lt=1)
    minimum_effect_size: float = Field(default=0.10, ge=0, le=1)


@dataclass(frozen=True)
class RegisteredInvestigationTool:
    name: str
    description: str
    output_evidence_type: str
    argument_model: type[SafeToolArguments]
    handler: ToolHandler
    required_columns: tuple[str, ...] = ()
    scalar_column_arguments: tuple[str, ...] = ()
    list_column_arguments: tuple[str, ...] = ()


class InvestigationToolRegistry:
    """Validates and executes only explicitly registered analysis functions."""

    def __init__(self, tools: list[RegisteredInvestigationTool]) -> None:
        by_name = {tool.name: tool for tool in tools}
        if len(by_name) != len(tools):
            raise ValueError("investigation tool names must be unique")
        self._tools = by_name

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))

    def describe(self, frame: pd.DataFrame) -> list[InvestigationToolDescription]:
        descriptions: list[InvestigationToolDescription] = []
        available_columns = set(frame.columns)
        for tool in self._tools.values():
            missing = sorted(set(tool.required_columns) - available_columns)
            if missing:
                descriptions.append(
                    InvestigationToolDescription(
                        name=tool.name,
                        description=tool.description,
                        output_evidence_type=tool.output_evidence_type,
                        availability="unavailable",
                        unavailable_reason=f"missing required columns: {missing}",
                        argument_schema=tool.argument_model.model_json_schema(),
                    )
                )
            else:
                descriptions.append(
                    InvestigationToolDescription(
                        name=tool.name,
                        description=tool.description,
                        output_evidence_type=tool.output_evidence_type,
                        availability="available",
                        argument_schema=tool.argument_model.model_json_schema(),
                    )
                )
        return sorted(descriptions, key=lambda item: item.name)

    def validate_call(
        self,
        call: InvestigationToolCall,
        frame: pd.DataFrame,
    ) -> tuple[RegisteredInvestigationTool, SafeToolArguments]:
        tool = self._tools.get(call.tool_name)
        if tool is None:
            raise ValueError(
                f"unknown investigation tool: {call.tool_name}; allowed tools: {list(self.names)}"
            )

        missing_required = sorted(set(tool.required_columns) - set(frame.columns))
        if missing_required:
            raise ValueError(
                f"tool {tool.name} is unavailable because columns are missing: {missing_required}"
            )

        arguments = tool.argument_model.model_validate(call.arguments)
        payload = arguments.model_dump(exclude_none=True)
        referenced_columns: list[str] = []
        for argument_name in tool.scalar_column_arguments:
            value = payload.get(argument_name)
            if isinstance(value, str):
                referenced_columns.append(value)
        for argument_name in tool.list_column_arguments:
            value = payload.get(argument_name)
            if isinstance(value, list):
                referenced_columns.extend(str(item) for item in value)

        missing_references = sorted(set(referenced_columns) - set(frame.columns))
        if missing_references:
            raise ValueError(
                f"tool {tool.name} references unavailable columns: {missing_references}"
            )
        return tool, arguments

    def validate_plan(self, plan: InvestigationPlan, frame: pd.DataFrame) -> None:
        for call in plan.steps:
            self.validate_call(call, frame)

    def execute(
        self,
        call: InvestigationToolCall,
        frame: pd.DataFrame,
        *,
        evidence_id: str,
        source_refs: list[str] | None = None,
    ) -> EvidenceItem:
        tool, arguments = self.validate_call(call, frame)
        result = tool.handler(
            frame,
            **arguments.model_dump(exclude_none=True),
            evidence_id=evidence_id,
            source_refs=source_refs or [],
        )
        metrics = dict(result.metrics)
        metrics["planned_tool_name"] = tool.name
        metrics["plan_reason"] = call.reason
        return result.model_copy(update={"metrics": metrics})

    def execute_plan(
        self,
        plan: InvestigationPlan,
        frame: pd.DataFrame,
        *,
        existing_evidence_ids: set[str] | None = None,
        source_refs: list[str] | None = None,
    ) -> list[EvidenceItem]:
        self.validate_plan(plan, frame)
        used_ids = set(existing_evidence_ids or set())
        results: list[EvidenceItem] = []
        next_number = 1

        for call in plan.steps:
            while True:
                evidence_id = f"E-AI-TOOL-{next_number:03d}"
                next_number += 1
                if evidence_id not in used_ids:
                    break
            evidence = self.execute(
                call,
                frame,
                evidence_id=evidence_id,
                source_refs=source_refs,
            )
            used_ids.add(evidence.id)
            results.append(evidence)
        return results


def build_default_tool_registry() -> InvestigationToolRegistry:
    return InvestigationToolRegistry(
        [
            RegisteredInvestigationTool(
                name="profile_dataset",
                description=(
                    "Inspect row counts, missing measurements, specification coverage, timestamps, "
                    "duplicates, and available production-context dimensions."
                ),
                output_evidence_type="data_quality",
                argument_model=DatasetProfileArguments,
                handler=profile_dataset,
                required_columns=("measurement_value",),
            ),
            RegisteredInvestigationTool(
                name="detect_spc_signals",
                description=(
                    "Detect I-MR three-sigma violations, same-side runs, and monotonic trends "
                    "using deterministic SPC rules."
                ),
                output_evidence_type="spc_signal",
                argument_model=SpcSignalArguments,
                handler=detect_spc_signals,
                required_columns=("measurement_value",),
                scalar_column_arguments=("value_column",),
            ),
            RegisteredInvestigationTool(
                name="detect_mean_change_point",
                description=(
                    "Scan legal split points and compare before/after means with Welch tests, "
                    "multiple-comparison adjustment, practical shift, and effect size."
                ),
                output_evidence_type="change_point",
                argument_model=MeanChangePointArguments,
                handler=detect_mean_change_point,
                required_columns=("measurement_value",),
                scalar_column_arguments=("value_column",),
            ),
            RegisteredInvestigationTool(
                name="compare_group_failure_rates",
                description=(
                    "Compare specification-failure rates across one to three production-context "
                    "dimensions and test the highest-risk group against the remaining samples."
                ),
                output_evidence_type="group_difference",
                argument_model=GroupFailureRateArguments,
                handler=compare_group_failure_rates,
                required_columns=("measurement_value", "lsl", "usl"),
                scalar_column_arguments=("value_column", "lsl_column", "usl_column"),
                list_column_arguments=("group_by",),
            ),
            RegisteredInvestigationTool(
                name="rank_failure_associations",
                description=(
                    "Rank categorical and numeric production factors associated with specification "
                    "failure using adjusted significance and effect-size thresholds."
                ),
                output_evidence_type="factor_association",
                argument_model=FactorRankingArguments,
                handler=rank_failure_associations,
                required_columns=("measurement_value", "lsl", "usl"),
                scalar_column_arguments=("value_column", "lsl_column", "usl_column"),
                list_column_arguments=(
                    "candidate_columns",
                    "categorical_columns",
                    "numeric_columns",
                ),
            ),
        ]
    )
