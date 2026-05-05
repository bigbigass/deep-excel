"""SPC 基础统计分析服务。

输入要求是已经标准化过的测量表，至少包含 `measurement_value`，
如果存在 `usl/lsl` 列则会额外计算能力指数和超规数量。

这个模块只做“可重复、可解释”的确定性统计，不掺杂 AI 推理。
AI 叙述阶段会消费这里的结果，但不会反过来影响这里的计算。
"""

from __future__ import annotations

from statistics import mean, pstdev

import pandas as pd


def _build_individual_control_limits(values: list[float], series_mean: float) -> tuple[float | None, float | None]:
    """基于移动极差估算 I-MR 控制图上下控制限。

    如果样本太少或波动为 0，会返回 `(None, None)`，
    调用方据此判断是否跳过控制限相关的异常检测和图表标线。
    """
    moving_ranges = [abs(current - previous) for previous, current in zip(values, values[1:])]
    moving_range_mean = mean(moving_ranges) if moving_ranges else 0.0
    # 1.128 是单值移动极差估算 sigma 的常见常数。
    sigma_estimate = moving_range_mean / 1.128 if moving_range_mean else 0.0

    if sigma_estimate == 0.0:
        return None, None

    return series_mean + (3 * sigma_estimate), series_mean - (3 * sigma_estimate)


def compute_analysis(normalized: pd.DataFrame) -> dict[str, object]:
    """从标准化测量数据中计算报表所需的统计指标和异常摘要。

    返回的是一个面向上层消费的通用分析字典，里面既有原始统计量，
    也有前端和报表可以直接使用的异常摘要和推荐图表列表。
    """
    values = normalized["measurement_value"].astype(float).tolist()
    series_mean = mean(values)
    std_dev = pstdev(values) if len(values) > 1 else 0.0
    min_value = min(values)
    max_value = max(values)

    usl = float(normalized["usl"].dropna().iloc[0]) if normalized["usl"].notna().any() else None
    lsl = float(normalized["lsl"].dropna().iloc[0]) if normalized["lsl"].notna().any() else None

    out_of_spec_count = 0
    if usl is not None and lsl is not None:
        # 只有规格上下限都存在时，超规判断才有业务意义。
        out_of_spec_count = int(
            ((normalized["measurement_value"] > usl) | (normalized["measurement_value"] < lsl)).sum()
        )

    # pass_rate 的定义是“在规格内的样本占比”，如果没有规格限则默认视为未发现超规。
    pass_rate = 1.0 - (out_of_spec_count / len(values))

    cp = None
    cpk = None
    if usl is not None and lsl is not None and std_dev > 0:
        # Cp 衡量潜在过程能力，Cpk 进一步考虑均值偏移。
        cp = (usl - lsl) / (6 * std_dev)
        cpk = min(
            (usl - series_mean) / (3 * std_dev),
            (series_mean - lsl) / (3 * std_dev),
        )

    ucl, lcl = _build_individual_control_limits(values, series_mean)

    anomalies: list[dict[str, object]] = []
    if out_of_spec_count:
        # 超规属于强业务信号，优先级最高。
        anomalies.append(
            {
                "type": "out_of_spec",
                "severity": "high",
                "summary": f"{out_of_spec_count} points exceed the specification limits",
            }
        )
    if ucl is not None and any(value > ucl or value < lcl for value in values):
        # 控制限异常强调“过程波动异常”，和规格超限不是一回事。
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
    # 只有存在规格上下限时，规格对比图才有展示意义。
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
