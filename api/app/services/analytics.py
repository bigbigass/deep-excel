from __future__ import annotations

from statistics import mean, pstdev

import pandas as pd


def _build_individual_control_limits(values: list[float], series_mean: float) -> tuple[float | None, float | None]:
    moving_ranges = [abs(current - previous) for previous, current in zip(values, values[1:])]
    moving_range_mean = mean(moving_ranges) if moving_ranges else 0.0
    sigma_estimate = moving_range_mean / 1.128 if moving_range_mean else 0.0

    if sigma_estimate == 0.0:
        return None, None

    return series_mean + (3 * sigma_estimate), series_mean - (3 * sigma_estimate)


def compute_analysis(normalized: pd.DataFrame) -> dict[str, object]:
    values = normalized["measurement_value"].astype(float).tolist()
    series_mean = mean(values)
    std_dev = pstdev(values) if len(values) > 1 else 0.0
    min_value = min(values)
    max_value = max(values)

    usl = float(normalized["usl"].dropna().iloc[0]) if normalized["usl"].notna().any() else None
    lsl = float(normalized["lsl"].dropna().iloc[0]) if normalized["lsl"].notna().any() else None

    out_of_spec_count = 0
    if usl is not None and lsl is not None:
        out_of_spec_count = int(
            ((normalized["measurement_value"] > usl) | (normalized["measurement_value"] < lsl)).sum()
        )

    pass_rate = 1.0 - (out_of_spec_count / len(values))

    cp = None
    cpk = None
    if usl is not None and lsl is not None and std_dev > 0:
        cp = (usl - lsl) / (6 * std_dev)
        cpk = min(
            (usl - series_mean) / (3 * std_dev),
            (series_mean - lsl) / (3 * std_dev),
        )

    ucl, lcl = _build_individual_control_limits(values, series_mean)

    anomalies: list[dict[str, object]] = []
    if out_of_spec_count:
        anomalies.append(
            {
                "type": "out_of_spec",
                "severity": "high",
                "summary": f"{out_of_spec_count} points exceed the specification limits",
            }
        )
    if ucl is not None and any(value > ucl or value < lcl for value in values):
        anomalies.append(
            {
                "type": "control_limit",
                "severity": "medium",
                "summary": "One or more points exceed the calculated control limits",
            }
        )

    recommended_charts = [
        "histogram",
        "control_chart_imr",
        "trend_line",
    ]
    if usl is not None and lsl is not None:
        recommended_charts.append("spec_comparison")

    return {
        "mean": series_mean,
        "std_dev": std_dev,
        "min_value": min_value,
        "max_value": max_value,
        "pass_rate": pass_rate,
        "cp": cp,
        "cpk": cpk,
        "ucl": ucl,
        "lcl": lcl,
        "out_of_spec_count": out_of_spec_count,
        "anomalies": anomalies,
        "recommended_charts": recommended_charts,
    }
