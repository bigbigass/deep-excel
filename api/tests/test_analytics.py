import pandas as pd

from api.app.services.analytics import compute_analysis


def test_compute_analysis_returns_spc_metrics() -> None:
    normalized = pd.DataFrame(
        {
            "measurement_value": [10.01, 10.02, 10.03, 10.00, 10.06, 10.01],
            "usl": [10.05] * 6,
            "lsl": [9.95] * 6,
            "sequence_index": [1, 2, 3, 4, 5, 6],
        }
    )

    analysis = compute_analysis(normalized)

    assert round(analysis["mean"], 3) == 10.022
    assert analysis["max_value"] == 10.06
    assert analysis["has_spec_limits"] is True
    assert analysis["out_of_spec_count"] == 1
    assert analysis["pass_rate"] == 5 / 6
    assert analysis["recommended_charts"] == [
        "histogram",
        "control_chart_imr",
        "trend_line",
        "spec_comparison",
    ]


def test_compute_analysis_marks_pass_rate_unavailable_without_spec_limits() -> None:
    normalized = pd.DataFrame(
        {
            "measurement_value": [10.01, 10.02, 10.03],
            "usl": [None, None, None],
            "lsl": [None, None, None],
            "sequence_index": [1, 2, 3],
        }
    )

    analysis = compute_analysis(normalized)

    assert analysis["has_spec_limits"] is False
    assert analysis["out_of_spec_count"] == 0
    assert analysis["pass_rate"] is None
    assert analysis["cp"] is None
    assert analysis["cpk"] is None
    assert "spec_comparison" not in analysis["recommended_charts"]
