"""质量结果关联因素排名工具。

本模块只计算统计关联，不输出因果结论。结果用于决定后续优先验证哪些因素，
不能直接把排名第一的字段写成已确认根因。
"""

from __future__ import annotations

from math import isfinite, sqrt

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency, pointbiserialr

from api.app.domain import EvidenceItem


def _json_scalar(value: object) -> object:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def _holm_adjust(p_values: list[float]) -> list[float]:
    """对多因素扫描的 p 值执行 Holm-Bonferroni 修正。"""
    if not p_values:
        return []
    order = sorted(range(len(p_values)), key=p_values.__getitem__)
    adjusted = [1.0] * len(p_values)
    running_max = 0.0
    total = len(p_values)
    for rank, index in enumerate(order):
        candidate = min(1.0, (total - rank) * p_values[index])
        running_max = max(running_max, candidate)
        adjusted[index] = running_max
    return adjusted


def _infer_factor_kind(
    series: pd.Series,
    *,
    column: str,
    categorical_columns: set[str],
    numeric_columns: set[str],
    max_categories: int,
) -> str:
    if column in categorical_columns:
        return "categorical"
    if column in numeric_columns:
        return "numeric"
    if not pd.api.types.is_numeric_dtype(series):
        return "categorical"

    unique_count = int(series.dropna().nunique())
    if pd.api.types.is_integer_dtype(series) and unique_count <= max_categories:
        return "categorical"
    return "numeric"


def _categorical_association(
    frame: pd.DataFrame,
    *,
    column: str,
    max_categories: int,
) -> tuple[dict[str, object] | None, str | None]:
    working = frame[[column, "is_failure"]].dropna()
    category_count = int(working[column].nunique())
    if category_count < 2:
        return None, "fewer than two categories"
    if category_count > max_categories:
        return None, f"category count {category_count} exceeds limit {max_categories}"

    contingency = pd.crosstab(working[column], working["is_failure"]).reindex(
        columns=[False, True],
        fill_value=0,
    )
    if contingency[True].sum() == 0 or contingency[False].sum() == 0:
        return None, "outcome contains only one class"

    try:
        chi_square, p_value, _, _ = chi2_contingency(contingency, correction=False)
    except ValueError as exc:
        return None, f"chi-square test unavailable: {exc}"

    denominator = len(working) * min(contingency.shape[0] - 1, contingency.shape[1] - 1)
    effect_size = sqrt(float(chi_square) / denominator) if denominator > 0 else 0.0
    rates = working.groupby(column, dropna=False)["is_failure"].agg(["count", "sum", "mean"])
    highest_value = rates["mean"].idxmax()
    lowest_value = rates["mean"].idxmin()
    highest = rates.loc[highest_value]
    lowest = rates.loc[lowest_value]

    return (
        {
            "factor": column,
            "factor_type": "categorical",
            "sample_count": len(working),
            "category_count": category_count,
            "effect_size": effect_size,
            "p_value": float(p_value),
            "highest_risk_group": _json_scalar(highest_value),
            "highest_risk_group_count": int(highest["count"]),
            "highest_risk_group_failures": int(highest["sum"]),
            "highest_risk_group_rate": float(highest["mean"]),
            "lowest_risk_group": _json_scalar(lowest_value),
            "lowest_risk_group_rate": float(lowest["mean"]),
            "rate_range": float(highest["mean"] - lowest["mean"]),
        },
        None,
    )


def _numeric_association(
    frame: pd.DataFrame,
    *,
    column: str,
) -> tuple[dict[str, object] | None, str | None]:
    working = frame[[column, "is_failure"]].copy()
    working[column] = pd.to_numeric(working[column], errors="coerce")
    working = working.dropna()
    if working[column].nunique() < 2:
        return None, "numeric factor has no variation"
    if working["is_failure"].nunique() < 2:
        return None, "outcome contains only one class"

    result = pointbiserialr(working["is_failure"].astype(int), working[column])
    correlation = float(result.statistic)
    p_value = float(result.pvalue)
    if not isfinite(correlation) or not isfinite(p_value):
        return None, "point-biserial correlation is not finite"

    failed_values = working.loc[working["is_failure"], column]
    passed_values = working.loc[~working["is_failure"], column]
    return (
        {
            "factor": column,
            "factor_type": "numeric",
            "sample_count": len(working),
            "effect_size": abs(correlation),
            "signed_correlation": correlation,
            "p_value": p_value,
            "failure_mean": float(failed_values.mean()),
            "pass_mean": float(passed_values.mean()),
            "mean_difference": float(failed_values.mean() - passed_values.mean()),
        },
        None,
    )


def rank_failure_associations(
    frame: pd.DataFrame,
    *,
    candidate_columns: list[str],
    evidence_id: str = "E-FACTOR-RANKING",
    value_column: str = "measurement_value",
    lsl_column: str = "lsl",
    usl_column: str = "usl",
    categorical_columns: list[str] | None = None,
    numeric_columns: list[str] | None = None,
    max_categories: int = 20,
    alpha: float = 0.05,
    minimum_effect_size: float = 0.10,
    source_refs: list[str] | None = None,
) -> EvidenceItem:
    """按不良结果关联强度对候选生产因素排序。"""
    if not candidate_columns:
        raise ValueError("candidate_columns must contain at least one column")
    if max_categories < 2:
        raise ValueError("max_categories must be at least 2")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between 0 and 1")
    if not 0 <= minimum_effect_size <= 1:
        raise ValueError("minimum_effect_size must be between 0 and 1")

    categorical_set = set(categorical_columns or [])
    numeric_set = set(numeric_columns or [])
    overlap = categorical_set & numeric_set
    if overlap:
        raise ValueError(f"factor columns cannot be both categorical and numeric: {sorted(overlap)}")

    required_columns = {value_column, lsl_column, usl_column, *candidate_columns}
    missing_columns = sorted(required_columns - set(frame.columns))
    if missing_columns:
        raise ValueError(f"missing required columns: {missing_columns}")

    working = frame[list(required_columns)].copy()
    working[value_column] = pd.to_numeric(working[value_column], errors="coerce")
    working[lsl_column] = pd.to_numeric(working[lsl_column], errors="coerce")
    working[usl_column] = pd.to_numeric(working[usl_column], errors="coerce")
    working = working.dropna(subset=[value_column, lsl_column, usl_column])
    working = working.loc[working[usl_column] > working[lsl_column]].copy()
    if working.empty:
        raise ValueError("no rows with valid measurements and specifications are available")

    working["is_failure"] = (
        (working[value_column] < working[lsl_column])
        | (working[value_column] > working[usl_column])
    )
    if working["is_failure"].nunique() < 2:
        return EvidenceItem(
            id=evidence_id,
            evidence_type="factor_association",
            title="质量结果关联因素排名",
            statement="当前有效数据中只有一种质量结果，无法比较不良与合格样本的关联因素。",
            metrics={
                "association_detected": False,
                "candidate_columns": candidate_columns,
                "ranked_factors": [],
                "skipped_factors": [],
            },
            sample_size=len(working),
            source_refs=source_refs or [],
            confidence="low",
            origin="deterministic_tool",
        )

    results: list[dict[str, object]] = []
    skipped: list[dict[str, str]] = []
    for column in candidate_columns:
        kind = _infer_factor_kind(
            working[column],
            column=column,
            categorical_columns=categorical_set,
            numeric_columns=numeric_set,
            max_categories=max_categories,
        )
        if kind == "categorical":
            result, reason = _categorical_association(
                working,
                column=column,
                max_categories=max_categories,
            )
        else:
            result, reason = _numeric_association(working, column=column)

        if result is None:
            skipped.append({"factor": column, "reason": reason or "association unavailable"})
            continue
        results.append(result)

    adjusted_p_values = _holm_adjust([float(item["p_value"]) for item in results])
    for item, adjusted_p_value in zip(results, adjusted_p_values):
        item["adjusted_p_value"] = adjusted_p_value
        item["association_detected"] = (
            adjusted_p_value <= alpha
            and float(item["effect_size"]) >= minimum_effect_size
        )

    results.sort(
        key=lambda item: (
            bool(item["association_detected"]),
            float(item["effect_size"]),
            -float(item["adjusted_p_value"]),
        ),
        reverse=True,
    )
    detected_results = [item for item in results if bool(item["association_detected"])]
    top = detected_results[0] if detected_results else (results[0] if results else None)

    if top is None:
        confidence = "low"
        statement = "候选字段均不具备可计算的关联条件，当前无法形成因素排名。"
    elif detected_results:
        top_effect = float(top["effect_size"])
        top_adjusted_p = float(top["adjusted_p_value"])
        if top_effect >= 0.50 and top_adjusted_p <= 0.01:
            confidence = "high"
        else:
            confidence = "medium"
        statement = (
            f"与不良结果关联度最高的因素为 {top['factor']}"
            f"（{top['factor_type']}，效应量 {top_effect:.3g}，"
            f"多重比较修正后 p 值 {top_adjusted_p:.3g}）。"
            "该结果仅表示统计关联，应通过现场检查或受控试验验证，不能直接认定为根因。"
        )
    else:
        confidence = "low"
        statement = (
            f"当前排名最高的因素为 {top['factor']}，但没有候选因素同时达到"
            "统计显著性和最小效应量要求。"
        )

    return EvidenceItem(
        id=evidence_id,
        evidence_type="factor_association",
        title="质量结果关联因素排名",
        statement=statement,
        metrics={
            "association_detected": bool(detected_results),
            "candidate_columns": candidate_columns,
            "ranked_factors": results,
            "skipped_factors": skipped,
            "alpha": alpha,
            "minimum_effect_size": minimum_effect_size,
            "multiple_testing_correction": "Holm-Bonferroni",
        },
        sample_size=len(working),
        source_refs=source_refs or [],
        confidence=confidence,
        origin="deterministic_tool",
    )
