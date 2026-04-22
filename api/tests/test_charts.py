from pathlib import Path

import pandas as pd

from api.app.services.analytics import compute_analysis
from api.app.services.charts import generate_chart_bundle


def test_generate_chart_bundle_writes_png_files(tmp_path: Path) -> None:
    normalized = pd.DataFrame(
        {
            "measurement_value": [10.01, 10.02, 10.03, 10.00, 10.06, 10.01],
            "usl": [10.05] * 6,
            "lsl": [9.95] * 6,
            "sequence_index": [1, 2, 3, 4, 5, 6],
        }
    )
    analysis = compute_analysis(normalized)

    chart_paths = generate_chart_bundle(normalized, analysis, tmp_path)

    assert set(chart_paths.keys()) == {
        "histogram",
        "control_chart_imr",
        "trend_line",
        "spec_comparison",
    }
    assert all(Path(path).exists() for path in chart_paths.values())
