from pathlib import Path

import pandas as pd

from api.app.services.investigation import compare_group_failure_rates


DEMO_DATA_PATH = Path("sample_data/investigation_demo.csv")


def test_selected_group_p_value_is_adjusted_for_group_scan() -> None:
    frame = pd.read_csv(DEMO_DATA_PATH)

    evidence = compare_group_failure_rates(
        frame,
        group_by=["machine_id", "cavity_id"],
    )

    assert evidence.metrics["comparison_count"] == 8
    assert evidence.metrics["multiple_testing_correction"] == "Bonferroni over eligible groups"
    assert evidence.metrics["adjusted_p_value"] == min(
        1.0,
        evidence.metrics["p_value"] * evidence.metrics["comparison_count"],
    )
    assert evidence.metrics["adjusted_p_value"] < 0.01
    assert evidence.metrics["difference_detected"] is True
