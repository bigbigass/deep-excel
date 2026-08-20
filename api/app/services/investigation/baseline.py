"""无需 AI 的基线质量调查编排。"""

from __future__ import annotations

from uuid import uuid4

import pandas as pd

from api.app.domain import EvidenceItem, InvestigationCase, InvestigationScope
from api.app.services.investigation.change_points import detect_mean_change_point
from api.app.services.investigation.factor_ranking import rank_failure_associations
from api.app.services.investigation.group_comparison import compare_group_failure_rates
from api.app.services.investigation.profiling import profile_dataset
from api.app.services.investigation.spc_signals import detect_spc_signals

DEFAULT_FACTOR_COLUMNS = [
    "machine_id",
    "cavity_id",
    "shift",
    "material_lot",
    "tool_id",
    "tool_cycles",
]
DEFAULT_GROUPINGS = [
    ["machine_id", "cavity_id"],
    ["material_lot"],
]


def _resolve_quality_feature(frame: pd.DataFrame) -> str | None:
    if "quality_feature" not in frame.columns:
        return None
    values = frame["quality_feature"].dropna().astype(str).unique().tolist()
    return values[0] if len(values) == 1 else None


def _group_evidence_id(group_by: list[str]) -> str:
    suffix = "-".join(column.replace("_", "-").upper() for column in group_by)
    return f"E-GROUP-{suffix}"


def run_baseline_investigation(
    frame: pd.DataFrame,
    *,
    question: str,
    case_id: str | None = None,
    source_refs: list[str] | None = None,
    groupings: list[list[str]] | None = None,
    candidate_factors: list[str] | None = None,
) -> InvestigationCase:
    """执行确定性调查工具，返回可持久化的调查案件。

    该函数不调用模型、不生成候选根因，只收集事实和统计关联证据。后续 AI
    只能在这些证据上制定调查计划或提出待验证假设。
    """
    normalized_question = question.strip()
    if not normalized_question:
        raise ValueError("question must not be empty")

    resolved_case_id = case_id or f"CASE-{uuid4().hex[:8]}"
    resolved_source_refs = source_refs or []
    evidence: list[EvidenceItem] = []
    missing_data: list[str] = []

    evidence.append(
        profile_dataset(
            frame,
            evidence_id="E-DATA-QUALITY",
            source_refs=resolved_source_refs,
        )
    )

    try:
        evidence.append(
            detect_spc_signals(
                frame,
                evidence_id="E-SPC-SIGNALS",
                source_refs=resolved_source_refs,
            )
        )
    except ValueError as exc:
        missing_data.append(f"SPC 信号检查未执行：{exc}")

    try:
        evidence.append(
            detect_mean_change_point(
                frame,
                evidence_id="E-CHANGE-POINT",
                source_refs=resolved_source_refs,
            )
        )
    except ValueError as exc:
        missing_data.append(f"变化点检查未执行：{exc}")

    has_valid_specification_columns = {"measurement_value", "lsl", "usl"}.issubset(frame.columns)
    if has_valid_specification_columns:
        resolved_groupings = groupings if groupings is not None else DEFAULT_GROUPINGS
        usable_groupings = [
            grouping
            for grouping in resolved_groupings
            if grouping and set(grouping).issubset(frame.columns)
        ]
        if not usable_groupings:
            missing_data.append("缺少可用于不良率分层比较的生产上下文字段")
        for grouping in usable_groupings:
            try:
                evidence.append(
                    compare_group_failure_rates(
                        frame,
                        group_by=grouping,
                        evidence_id=_group_evidence_id(grouping),
                        source_refs=resolved_source_refs,
                    )
                )
            except ValueError as exc:
                missing_data.append(f"分组比较 {'/'.join(grouping)} 未执行：{exc}")

        resolved_factors = candidate_factors if candidate_factors is not None else DEFAULT_FACTOR_COLUMNS
        usable_factors = [column for column in resolved_factors if column in frame.columns]
        if usable_factors:
            try:
                evidence.append(
                    rank_failure_associations(
                        frame,
                        candidate_columns=usable_factors,
                        evidence_id="E-FACTOR-RANKING",
                        source_refs=resolved_source_refs,
                    )
                )
            except ValueError as exc:
                missing_data.append(f"因素关联排名未执行：{exc}")
        else:
            missing_data.append("缺少可用于因素关联排名的生产上下文字段")
    else:
        missing_data.append("缺少测量值或规格限，无法进行不良率分层和因素关联排名")

    scope = InvestigationScope(quality_feature=_resolve_quality_feature(frame))
    return InvestigationCase(
        case_id=resolved_case_id,
        question=normalized_question,
        scope=scope,
        state="ready",
        evidence=evidence,
        hypotheses=[],
        actions=[],
        missing_data=missing_data,
    )
