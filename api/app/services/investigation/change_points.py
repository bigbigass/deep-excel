"""可解释的过程均值变化点检测工具。"""

from __future__ import annotations

from math import isfinite

import numpy as np
import pandas as pd
from scipy.stats import ttest_ind

from api.app.domain import EvidenceItem


def _prepare_ordered_series(
    frame: pd.DataFrame,
    *,
    value_column: str,
    order_column: str,
) -> tuple[pd.DataFrame, str]:
    if value_column not in frame.columns:
        raise ValueError(f"{value_column} column is required")

    working = pd.DataFrame({"value": pd.to_numeric(frame[value_column], errors="coerce")})
    resolved_order_column = order_column

    if order_column in frame.columns:
        source_order = frame[order_column]
        if pd.api.types.is_numeric_dtype(source_order):
            working["order"] = pd.to_numeric(source_order, errors="coerce")
        else:
            working["order"] = pd.to_datetime(source_order, errors="coerce")
    elif "sequence_index" in frame.columns:
        resolved_order_column = "sequence_index"
        working["order"] = pd.to_numeric(frame["sequence_index"], errors="coerce")
    else:
        resolved_order_column = "row_order"
        working["order"] = range(1, len(frame) + 1)

    working = working.dropna(subset=["value", "order"]).sort_values("order", kind="mergesort").reset_index(drop=True)
    if working.empty:
        raise ValueError("no valid ordered measurement rows are available")
    return working, resolved_order_column


def _pooled_standard_deviation(before: np.ndarray, after: np.ndarray) -> float:
    degrees_of_freedom = len(before) + len(after) - 2
    if degrees_of_freedom <= 0:
        return 0.0
    pooled_variance = (
        ((len(before) - 1) * float(np.var(before, ddof=1)))
        + ((len(after) - 1) * float(np.var(after, ddof=1)))
    ) / degrees_of_freedom
    return float(np.sqrt(max(0.0, pooled_variance)))


def _serialize_order_value(value: object) -> object:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    return value


def detect_mean_change_point(
    frame: pd.DataFrame,
    *,
    value_column: str = "measurement_value",
    order_column: str = "measured_at",
    evidence_id: str = "E-CHANGE-POINT",
    min_segment_size: int = 12,
    alpha: float = 0.01,
    min_absolute_shift: float | None = None,
    source_refs: list[str] | None = None,
) -> EvidenceItem:
    """扫描所有合法切分点，寻找最显著且具实际幅度的均值变化。

    每个切分点使用 Welch t 检验比较前后两段，并对扫描次数做 Bonferroni
    修正。该方法不是黑盒预测模型，所有均值、样本数、效应量和显著性都可追溯。
    """
    if min_segment_size < 2:
        raise ValueError("min_segment_size must be at least 2")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between 0 and 1")

    working, resolved_order_column = _prepare_ordered_series(
        frame,
        value_column=value_column,
        order_column=order_column,
    )
    values = working["value"].to_numpy(dtype=float)
    row_count = len(values)
    if row_count < min_segment_size * 2:
        raise ValueError(
            f"at least {min_segment_size * 2} valid rows are required for change point detection"
        )

    overall_std = float(np.std(values, ddof=1)) if row_count > 1 else 0.0
    practical_shift = (
        float(min_absolute_shift)
        if min_absolute_shift is not None
        else max(overall_std * 0.25, np.finfo(float).eps)
    )
    if practical_shift < 0:
        raise ValueError("min_absolute_shift must not be negative")

    candidates: list[dict[str, object]] = []
    for split_index in range(min_segment_size, row_count - min_segment_size + 1):
        before = values[:split_index]
        after = values[split_index:]
        test_result = ttest_ind(before, after, equal_var=False, nan_policy="omit")
        statistic = float(test_result.statistic)
        p_value = float(test_result.pvalue)
        if not isfinite(statistic) or not isfinite(p_value):
            continue

        before_mean = float(np.mean(before))
        after_mean = float(np.mean(after))
        delta = after_mean - before_mean
        pooled_std = _pooled_standard_deviation(before, after)
        effect_size = delta / pooled_std if pooled_std > 0 else None
        candidates.append(
            {
                "split_index": split_index,
                "change_at": _serialize_order_value(working.loc[split_index, "order"]),
                "before_count": len(before),
                "after_count": len(after),
                "before_mean": before_mean,
                "after_mean": after_mean,
                "delta": delta,
                "t_statistic": statistic,
                "p_value": p_value,
                "effect_size": effect_size,
            }
        )

    if not candidates:
        return EvidenceItem(
            id=evidence_id,
            evidence_type="change_point",
            title="过程均值变化点检查",
            statement="有效数据的波动不足以形成可检验的均值变化点。",
            metrics={
                "detected": False,
                "row_count": row_count,
                "order_column": resolved_order_column,
                "candidate_count": 0,
                "min_absolute_shift": practical_shift,
            },
            sample_size=row_count,
            source_refs=source_refs or [],
            confidence="medium",
            origin="deterministic_tool",
        )

    best = max(candidates, key=lambda item: abs(float(item["t_statistic"])))
    adjusted_p_value = min(1.0, float(best["p_value"]) * len(candidates))
    detected = adjusted_p_value <= alpha and abs(float(best["delta"])) >= practical_shift
    effect_size = best["effect_size"]

    if detected and effect_size is not None and abs(float(effect_size)) >= 0.8:
        confidence = "high"
    elif detected:
        confidence = "medium"
    else:
        confidence = "low"

    change_at = best["change_at"]
    before_mean = float(best["before_mean"])
    after_mean = float(best["after_mean"])
    delta = float(best["delta"])
    if detected:
        statement = (
            f"在 {change_at} 附近检测到过程均值变化："
            f"前段均值 {before_mean:.6g}，后段均值 {after_mean:.6g}，"
            f"变化量 {delta:+.6g}；扫描修正后的 p 值为 {adjusted_p_value:.3g}。"
        )
    else:
        statement = (
            f"最强候选变化点位于 {change_at}，前后均值变化 {delta:+.6g}，"
            "但未同时达到统计显著性和实际变化幅度要求。"
        )

    metrics = dict(best)
    metrics.update(
        {
            "detected": detected,
            "row_count": row_count,
            "order_column": resolved_order_column,
            "candidate_count": len(candidates),
            "adjusted_p_value": adjusted_p_value,
            "alpha": alpha,
            "min_absolute_shift": practical_shift,
        }
    )
    return EvidenceItem(
        id=evidence_id,
        evidence_type="change_point",
        title="过程均值变化点检查",
        statement=statement,
        metrics=metrics,
        sample_size=row_count,
        source_refs=source_refs or [],
        confidence=confidence,
        origin="deterministic_tool",
    )
