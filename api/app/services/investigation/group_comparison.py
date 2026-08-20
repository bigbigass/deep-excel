"""生产上下文分组不良率比较工具。"""

from __future__ import annotations

from math import isfinite

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact

from api.app.domain import EvidenceItem


def _json_scalar(value: object) -> object:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def _format_group(group_values: dict[str, object]) -> str:
    return " / ".join(f"{name}={value}" for name, value in group_values.items())


def compare_group_failure_rates(
    frame: pd.DataFrame,
    *,
    group_by: list[str],
    evidence_id: str = "E-GROUP-DIFFERENCE",
    value_column: str = "measurement_value",
    lsl_column: str = "lsl",
    usl_column: str = "usl",
    min_group_size: int = 5,
    alpha: float = 0.05,
    minimum_rate_difference: float = 0.05,
    source_refs: list[str] | None = None,
) -> EvidenceItem:
    """找出不良率最高的分组，并用其余样本作为对照。

    检验使用 2x2 Fisher 精确检验。由于最高风险组是从多个候选组中选择的，
    检测结论使用按候选组数做 Bonferroni 修正后的 p 值。所有写入证据的指标
    保持标准 JSON 可序列化。
    """
    if not group_by:
        raise ValueError("group_by must contain at least one column")
    if min_group_size < 1:
        raise ValueError("min_group_size must be at least 1")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between 0 and 1")
    if minimum_rate_difference < 0:
        raise ValueError("minimum_rate_difference must not be negative")

    required_columns = {value_column, lsl_column, usl_column, *group_by}
    missing_columns = sorted(required_columns - set(frame.columns))
    if missing_columns:
        raise ValueError(f"missing required columns: {missing_columns}")

    working = frame[sorted(required_columns)].copy()
    working[value_column] = pd.to_numeric(working[value_column], errors="coerce")
    working[lsl_column] = pd.to_numeric(working[lsl_column], errors="coerce")
    working[usl_column] = pd.to_numeric(working[usl_column], errors="coerce")
    working = working.dropna(subset=[value_column, lsl_column, usl_column, *group_by])
    working = working.loc[working[usl_column] > working[lsl_column]].copy()
    if working.empty:
        raise ValueError("no rows with valid measurements, specifications, and group values are available")

    working["is_failure"] = (
        (working[value_column] < working[lsl_column])
        | (working[value_column] > working[usl_column])
    )

    summaries: list[dict[str, object]] = []
    grouper: str | list[str] = group_by[0] if len(group_by) == 1 else group_by
    for key, group in working.groupby(grouper, sort=True, dropna=False):
        key_values = key if isinstance(key, tuple) else (key,)
        group_values = {
            column: _json_scalar(value)
            for column, value in zip(group_by, key_values)
        }
        sample_count = len(group)
        failure_count = int(group["is_failure"].sum())
        summaries.append(
            {
                "group": group_values,
                "sample_count": sample_count,
                "failure_count": failure_count,
                "failure_rate": failure_count / sample_count,
            }
        )

    eligible = [item for item in summaries if int(item["sample_count"]) >= min_group_size]
    if len(eligible) < 2:
        raise ValueError("at least two groups must meet min_group_size")

    highest = max(
        eligible,
        key=lambda item: (
            float(item["failure_rate"]),
            int(item["failure_count"]),
            int(item["sample_count"]),
        ),
    )
    selected_group = highest["group"]
    selected_mask = pd.Series(True, index=working.index)
    assert isinstance(selected_group, dict)
    for column, value in selected_group.items():
        selected_mask &= working[column] == value

    group_count = int(selected_mask.sum())
    group_failures = int(working.loc[selected_mask, "is_failure"].sum())
    rest_count = int((~selected_mask).sum())
    rest_failures = int(working.loc[~selected_mask, "is_failure"].sum())
    if rest_count == 0:
        raise ValueError("selected group has no comparison rows")

    group_rate = group_failures / group_count
    rest_rate = rest_failures / rest_count
    rate_difference = group_rate - rest_rate
    raw_risk_ratio_is_infinite = rest_rate == 0 and group_rate > 0
    if raw_risk_ratio_is_infinite:
        raw_risk_ratio: float | None = None
    elif rest_rate == 0:
        raw_risk_ratio = 1.0
    else:
        raw_risk_ratio = group_rate / rest_rate

    corrected_group_rate = (group_failures + 0.5) / (group_count + 1)
    corrected_rest_rate = (rest_failures + 0.5) / (rest_count + 1)
    corrected_risk_ratio = corrected_group_rate / corrected_rest_rate

    contingency_table = [
        [group_failures, group_count - group_failures],
        [rest_failures, rest_count - rest_failures],
    ]
    fisher_result = fisher_exact(contingency_table, alternative="greater")
    raw_odds_ratio = float(fisher_result.statistic)
    odds_ratio_is_infinite = not isfinite(raw_odds_ratio)
    odds_ratio = None if odds_ratio_is_infinite else raw_odds_ratio
    p_value = float(fisher_result.pvalue)
    comparison_count = len(eligible)
    adjusted_p_value = min(1.0, p_value * comparison_count)

    difference_detected = (
        group_rate > rest_rate
        and rate_difference >= minimum_rate_difference
        and adjusted_p_value <= alpha
    )
    if difference_detected and adjusted_p_value <= 0.01 and rate_difference >= 0.10:
        confidence = "high"
    elif difference_detected:
        confidence = "medium"
    else:
        confidence = "low"

    group_label = _format_group(selected_group)
    if difference_detected:
        statement = (
            f"不良主要集中于 {group_label}：该组 {group_failures}/{group_count} 条不良"
            f"（{group_rate:.1%}），其余样本 {rest_failures}/{rest_count} 条不良"
            f"（{rest_rate:.1%}）；连续性修正风险比为 {corrected_risk_ratio:.3g}，"
            f"组选择修正后的 p 值为 {adjusted_p_value:.3g}。"
        )
    else:
        statement = (
            f"不良率最高的分组为 {group_label}（{group_rate:.1%}），"
            f"其余样本为 {rest_rate:.1%}，但差异未同时达到显著性和实际幅度要求。"
        )

    return EvidenceItem(
        id=evidence_id,
        evidence_type="group_difference",
        title="生产上下文不良率分层比较",
        statement=statement,
        metrics={
            "difference_detected": difference_detected,
            "group_by": group_by,
            "selected_group": selected_group,
            "group_sample_count": group_count,
            "group_failure_count": group_failures,
            "group_failure_rate": group_rate,
            "rest_sample_count": rest_count,
            "rest_failure_count": rest_failures,
            "rest_failure_rate": rest_rate,
            "rate_difference": rate_difference,
            "raw_risk_ratio": raw_risk_ratio,
            "raw_risk_ratio_is_infinite": raw_risk_ratio_is_infinite,
            "corrected_risk_ratio": corrected_risk_ratio,
            "odds_ratio": odds_ratio,
            "odds_ratio_is_infinite": odds_ratio_is_infinite,
            "p_value": p_value,
            "adjusted_p_value": adjusted_p_value,
            "comparison_count": comparison_count,
            "multiple_testing_correction": "Bonferroni over eligible groups",
            "alpha": alpha,
            "minimum_rate_difference": minimum_rate_difference,
            "group_summaries": summaries,
        },
        sample_size=len(working),
        filters=selected_group,
        source_refs=source_refs or [],
        confidence=confidence,
        origin="deterministic_tool",
    )
