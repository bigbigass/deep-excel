from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["font.sans-serif"] = [
    "Microsoft YaHei",
    "SimHei",
    "Noto Sans CJK SC",
    "Arial Unicode MS",
    "DejaVu Sans",
]
matplotlib.rcParams["axes.unicode_minus"] = False

import matplotlib.pyplot as plt
import pandas as pd

from api.app.services.report_localization import chart_title


def _save_histogram(values: pd.Series, output_path: Path) -> None:
    figure, axis = plt.subplots(figsize=(6, 4))
    axis.hist(values, bins=8, color="#2563eb", edgecolor="white")
    axis.set_title(chart_title("histogram"))
    axis.set_xlabel("测量值")
    axis.set_ylabel("频数")
    figure.tight_layout()
    figure.savefig(output_path)
    plt.close(figure)


def _save_control_chart(
    sequence: pd.Series,
    values: pd.Series,
    analysis: dict[str, object],
    output_path: Path,
) -> None:
    figure, axis = plt.subplots(figsize=(7, 4))
    axis.plot(sequence, values, marker="o", color="#0f766e")
    axis.axhline(analysis["mean"], color="#1d4ed8", linestyle="-", label="均值")

    if analysis["ucl"] is not None:
        axis.axhline(analysis["ucl"], color="#dc2626", linestyle="--", label="上控制限")
        axis.axhline(analysis["lcl"], color="#dc2626", linestyle="--", label="下控制限")

    axis.set_title(chart_title("control_chart_imr"))
    axis.set_xlabel("序号")
    axis.set_ylabel("测量值")
    axis.legend()
    figure.tight_layout()
    figure.savefig(output_path)
    plt.close(figure)


def _save_trend_line(sequence: pd.Series, values: pd.Series, output_path: Path) -> None:
    figure, axis = plt.subplots(figsize=(7, 4))
    axis.plot(sequence, values, marker="o", color="#7c3aed")
    axis.set_title(chart_title("trend_line"))
    axis.set_xlabel("序号")
    axis.set_ylabel("测量值")
    figure.tight_layout()
    figure.savefig(output_path)
    plt.close(figure)


def _save_spec_comparison(
    sequence: pd.Series,
    values: pd.Series,
    normalized: pd.DataFrame,
    output_path: Path,
) -> None:
    figure, axis = plt.subplots(figsize=(7, 4))
    axis.plot(sequence, values, marker="o", color="#111827", label="测量值")
    axis.axhline(float(normalized["usl"].iloc[0]), color="#dc2626", linestyle="--", label="上规格限")
    axis.axhline(float(normalized["lsl"].iloc[0]), color="#059669", linestyle="--", label="下规格限")
    axis.set_title(chart_title("spec_comparison"))
    axis.set_xlabel("序号")
    axis.set_ylabel("测量值")
    axis.legend()
    figure.tight_layout()
    figure.savefig(output_path)
    plt.close(figure)


def generate_chart_bundle(
    normalized: pd.DataFrame,
    analysis: dict[str, object],
    output_dir: Path,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)

    values = normalized["measurement_value"].astype(float)
    sequence = normalized["sequence_index"].astype(int)

    chart_paths: dict[str, str] = {}

    histogram_path = output_dir / "histogram.png"
    _save_histogram(values, histogram_path)
    chart_paths["histogram"] = str(histogram_path)

    control_chart_path = output_dir / "control_chart_imr.png"
    _save_control_chart(sequence, values, analysis, control_chart_path)
    chart_paths["control_chart_imr"] = str(control_chart_path)

    trend_line_path = output_dir / "trend_line.png"
    _save_trend_line(sequence, values, trend_line_path)
    chart_paths["trend_line"] = str(trend_line_path)

    if "spec_comparison" in analysis["recommended_charts"]:
        spec_comparison_path = output_dir / "spec_comparison.png"
        _save_spec_comparison(sequence, values, normalized, spec_comparison_path)
        chart_paths["spec_comparison"] = str(spec_comparison_path)

    return chart_paths
