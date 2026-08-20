import json
from pathlib import Path

import pandas as pd
import pytest

from api.app.services.investigation import run_baseline_investigation


DEMO_DATA_PATH = Path("sample_data/investigation_demo.csv")


def _load_demo_data() -> pd.DataFrame:
    return pd.read_csv(DEMO_DATA_PATH, parse_dates=["measured_at"])


def test_baseline_investigation_builds_evidence_case_without_ai() -> None:
    case = run_baseline_investigation(
        _load_demo_data(),
        question="为什么外径不良率升高？",
        case_id="CASE-DEMO",
        source_refs=[str(DEMO_DATA_PATH)],
    )

    assert case.state == "ready"
    assert case.scope.quality_feature == "outer_diameter"
    assert case.hypotheses == []
    assert case.actions == []
    assert case.missing_data == []

    evidence_by_id = {item.id: item for item in case.evidence}
    assert set(evidence_by_id) == {
        "E-DATA-QUALITY",
        "E-SPC-SIGNALS",
        "E-CHANGE-POINT",
        "E-GROUP-MACHINE-ID-CAVITY-ID",
        "E-GROUP-MATERIAL-LOT",
        "E-FACTOR-RANKING",
    }
    assert evidence_by_id["E-CHANGE-POINT"].metrics["detected"] is True
    assert evidence_by_id["E-GROUP-MACHINE-ID-CAVITY-ID"].metrics["selected_group"] == {
        "machine_id": "M02",
        "cavity_id": 4,
    }
    assert evidence_by_id["E-GROUP-MATERIAL-LOT"].metrics["difference_detected"] is False
    assert evidence_by_id["E-FACTOR-RANKING"].metrics["association_detected"] is True

    json.dumps(case.model_dump(mode="json"), allow_nan=False)


def test_baseline_investigation_keeps_partial_value_without_specifications() -> None:
    frame = _load_demo_data().drop(columns=["usl", "lsl"])

    case = run_baseline_investigation(
        frame,
        question="过程从什么时候开始变化？",
        case_id="CASE-NO-SPEC",
    )

    evidence_ids = {item.id for item in case.evidence}
    assert case.state == "ready"
    assert evidence_ids == {
        "E-DATA-QUALITY",
        "E-SPC-SIGNALS",
        "E-CHANGE-POINT",
    }
    assert any("规格限" in item for item in case.missing_data)
    assert next(
        item for item in case.evidence if item.id == "E-CHANGE-POINT"
    ).metrics["detected"] is True


def test_baseline_investigation_records_optional_tool_failure_instead_of_failing_case() -> None:
    frame = _load_demo_data().head(10)

    case = run_baseline_investigation(
        frame,
        question="这批数据能否调查？",
        case_id="CASE-SHORT",
    )

    assert case.state == "ready"
    assert any("变化点检查未执行" in item for item in case.missing_data)
    assert any(item.id == "E-DATA-QUALITY" for item in case.evidence)


def test_baseline_investigation_rejects_empty_question() -> None:
    with pytest.raises(ValueError, match="question must not be empty"):
        run_baseline_investigation(_load_demo_data(), question="   ")
