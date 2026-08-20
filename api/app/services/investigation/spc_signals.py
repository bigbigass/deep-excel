"""确定性 SPC 规则信号检测。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from api.app.domain import EvidenceItem


def _json_scalar(value: object) -> object:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def _prepare_series(
    frame: pd.DataFrame,
    *,
    value_column: str,
    order_column: str,
) -> tuple[pd.DataFrame, str]:
    if value_column not in frame.columns:
        raise ValueError(f"{value_column} column is required")

    working = pd.DataFrame(
        {
            "value": pd.to_numeric(frame[value_column], errors="coerce"),
            "source_index": frame.index,
        }
    )
    if "sample_id" in frame.columns:
        working["sample_id"] = frame["sample_id"]
    else:
        working["sample_id"] = None

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
    working["position"] = range(1, len(working) + 1)
    return working, resolved_order_column


def _point_payload(row: pd.Series) -> dict[str, object]:
    sample_id = row.get("sample_id")
    return {
        "position": int(row["position"]),
        "source_index": _json_scalar(row["source_index"]),
        "sample_id": None if pd.isna(sample_id) else str(sample_id),
        "order": _json_scalar(row["order"]),
        "value": float(row["value"]),
    }


def _find_same_side_runs(values: np.ndarray, centerline: float, minimum_length: int = 8) -> list[tuple[int, int, str]]:
    signs = np.sign(values - centerline)
    runs: list[tuple[int, int, str]] = []
    start = 0
    while start < len(signs):
        sign = signs[start]
        if sign == 0:
            start += 1
            continue
        end = start + 1
        while end < len(signs) and signs[end] == sign:
            end += 1
        if end - start >= minimum_length:
            runs.append((start, end - 1, "above" if sign > 0 else "below"))
        start = end
    return runs


def _find_monotonic_runs(values: np.ndarray, minimum_points: int = 6) -> list[tuple[int, int, str]]:
    if len(values) < minimum_points:
        return []
    directions = np.sign(np.diff(values))
    runs: list[tuple[int, int, str]] = []
    start = 0
    required_differences = minimum_points - 1
    while start < len(directions):
        direction = directions[start]
        if direction == 0:
            start += 1
            continue
        end = start + 1
        while end < len(directions) and directions[end] == direction:
            end += 1
        if end - start >= required_differences:
            runs.append((start, end, "increasing" if direction > 0 else "decreasing"))
        start = end
    return runs


def detect_spc_signals(
    frame: pd.DataFrame,
    *,
    value_column: str = "measurement_value",
    order_column: str = "measured_at",
    evidence_id: str = "E-SPC-SIGNALS",
    same_side_run_length: int = 8,
    trend_point_count: int = 6,
    source_refs: list[str] | None = None,
) -> EvidenceItem:
    """检测控制限越界、连续同侧和连续单调趋势三类可解释信号。"""
    if same_side_run_length < 2:
        raise ValueError("same_side_run_length must be at least 2")
    if trend_point_count < 3:
        raise ValueError("trend_point_count must be at least 3")

    working, resolved_order_column = _prepare_series(
        frame,
        value_column=value_column,
        order_column=order_column,
    )
    values = working["value"].to_numpy(dtype=float)
    centerline = float(np.mean(values))
    moving_ranges = np.abs(np.diff(values))
    moving_range_mean = float(np.mean(moving_ranges)) if len(moving_ranges) else 0.0
    sigma_estimate = moving_range_mean / 1.128 if moving_range_mean > 0 else 0.0
    ucl = centerline + 3 * sigma_estimate if sigma_estimate > 0 else None
    lcl = centerline - 3 * sigma_estimate if sigma_estimate > 0 else None

    signals: list[dict[str, object]] = []
    if ucl is not None and lcl is not None:
        outside_mask = (working["value"] > ucl) | (working["value"] < lcl)
        outside_points = [_point_payload(row) for _, row in working.loc[outside_mask].iterrows()]
        if outside_points:
            signals.append(
                {
                    "rule": "beyond_3_sigma",
                    "severity": "high",
                    "summary": f"{len(outside_points)} 个点超出 I-MR 三西格玛控制限",
                    "points": outside_points,
                }
            )

    for start, end, side in _find_same_side_runs(values, centerline, same_side_run_length):
        signals.append(
            {
                "rule": "same_side_run",
                "severity": "medium",
                "summary": (
                    f"连续 {end - start + 1} 个点位于均值"
                    f"{'上方' if side == 'above' else '下方'}"
                ),
                "side": side,
                "start": _point_payload(working.iloc[start]),
                "end": _point_payload(working.iloc[end]),
                "point_count": end - start + 1,
            }
        )

    for start, end, direction in _find_monotonic_runs(values, trend_point_count):
        signals.append(
            {
                "rule": "monotonic_trend",
                "severity": "medium",
                "summary": (
                    f"连续 {end - start + 1} 个点"
                    f"{'上升' if direction == 'increasing' else '下降'}"
                ),
                "direction": direction,
                "start": _point_payload(working.iloc[start]),
                "end": _point_payload(working.iloc[end]),
                "point_count": end - start + 1,
            }
        )

    beyond_count = sum(
        len(signal.get("points", []))
        for signal in signals
        if signal["rule"] == "beyond_3_sigma"
    )
    if beyond_count:
        confidence = "high"
    elif signals:
        confidence = "medium"
    else:
        confidence = "low"

    if signals:
        rule_counts: dict[str, int] = {}
        for signal in signals:
            rule = str(signal["rule"])
            rule_counts[rule] = rule_counts.get(rule, 0) + 1
        rule_text = "、".join(f"{rule} {count} 项" for rule, count in rule_counts.items())
        statement = f"检测到 {len(signals)} 项 SPC 规则信号：{rule_text}。"
    else:
        statement = "当前数据未触发控制限越界、连续同侧或连续趋势规则。"

    return EvidenceItem(
        id=evidence_id,
        evidence_type="spc_signal",
        title="SPC 过程信号检查",
        statement=statement,
        metrics={
            "signal_detected": bool(signals),
            "signal_count": len(signals),
            "beyond_control_limit_point_count": beyond_count,
            "centerline": centerline,
            "moving_range_mean": moving_range_mean,
            "sigma_estimate": sigma_estimate,
            "ucl": ucl,
            "lcl": lcl,
            "order_column": resolved_order_column,
            "same_side_run_length": same_side_run_length,
            "trend_point_count": trend_point_count,
            "signals": signals,
        },
        sample_size=len(working),
        source_refs=source_refs or [],
        confidence=confidence,
        origin="deterministic_tool",
    )
