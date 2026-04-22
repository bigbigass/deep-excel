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
    assert analysis["out_of_spec_count"] == 1
    assert analysis["recommended_charts"] == [
        "histogram",
        "control_chart_imr",
        "trend_line",
        "spec_comparison",
    ]
