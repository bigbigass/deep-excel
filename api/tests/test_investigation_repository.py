import json
from pathlib import Path

import pytest

from api.app.domain import InvestigationCase
from api.app.services.investigation.cases import (
    create_investigation,
    run_investigation,
)
from api.app.services.investigation.repository import InvestigationRepository


DEMO_DATA_PATH = Path("sample_data/investigation_demo.csv")


def test_repository_round_trips_case_with_strict_json(tmp_path: Path) -> None:
    repository = InvestigationRepository(tmp_path / "investigations")
    case = InvestigationCase(
        case_id="CASE-ROUNDTRIP",
        question="为什么外径不良率升高？",
        state="created",
        source_refs=["uploads/demo.csv"],
    )

    case_path = repository.save(case)
    loaded = repository.load(case.case_id)

    assert loaded == case
    payload = json.loads(case_path.read_text(encoding="utf-8"))
    assert payload["case_id"] == "CASE-ROUNDTRIP"
    assert not list(case_path.parent.glob(".case-*.tmp"))


def test_repository_isolates_and_sanitizes_upload_path(tmp_path: Path) -> None:
    repository = InvestigationRepository(tmp_path / "investigations")

    upload_path = repository.save_upload(
        "CASE-UPLOAD",
        "../demo.csv",
        b"measurement_value\n10.0\n",
    )

    assert upload_path.name == "demo.csv"
    assert upload_path.parent.name == "uploads"
    assert upload_path.parent.parent.name == "CASE-UPLOAD"
    assert upload_path.read_bytes() == b"measurement_value\n10.0\n"


@pytest.mark.parametrize("case_id", ["../CASE-1", "CASE/1", "invalid", ""])
def test_repository_rejects_invalid_case_ids(tmp_path: Path, case_id: str) -> None:
    repository = InvestigationRepository(tmp_path / "investigations")

    with pytest.raises(ValueError, match="invalid investigation case id"):
        repository.case_dir(case_id)


def test_repository_rejects_unsupported_investigation_file_type(tmp_path: Path) -> None:
    repository = InvestigationRepository(tmp_path / "investigations")

    with pytest.raises(ValueError, match="unsupported investigation file type"):
        repository.save_upload("CASE-UPLOAD", "notes.txt", b"demo")


def test_case_service_runs_baseline_and_persists_ready_case(tmp_path: Path) -> None:
    repository = InvestigationRepository(tmp_path / "investigations")
    created = create_investigation(
        question="为什么外径不良率升高？",
        file_name=DEMO_DATA_PATH.name,
        content=DEMO_DATA_PATH.read_bytes(),
        repository=repository,
        start_background=False,
    )
    initial = repository.load(created["case_id"])
    upload_path = Path(initial.source_refs[0])

    result = run_investigation(
        initial.case_id,
        upload_path,
        repository=repository,
    )
    persisted = repository.load(initial.case_id)

    assert result.state == "ready"
    assert persisted == result
    assert persisted.created_at == initial.created_at
    assert persisted.scope.quality_feature == "outer_diameter"
    assert persisted.scope.start_at is not None
    assert persisted.scope.end_at is not None
    assert persisted.source_refs == [str(upload_path)]
    assert {item.id for item in persisted.evidence} >= {
        "E-DATA-QUALITY",
        "E-SPC-SIGNALS",
        "E-CHANGE-POINT",
        "E-GROUP-MACHINE-ID-CAVITY-ID",
        "E-FACTOR-RANKING",
    }


def test_case_service_persists_failure_state_for_invalid_source(tmp_path: Path) -> None:
    repository = InvestigationRepository(tmp_path / "investigations")
    created = create_investigation(
        question="这份文件是否可分析？",
        file_name="broken.csv",
        content=b"\xff\xfe\x00",
        repository=repository,
        start_background=False,
    )
    initial = repository.load(created["case_id"])

    result = run_investigation(
        initial.case_id,
        Path(initial.source_refs[0]),
        repository=repository,
    )

    assert result.state == "failed"
    assert result.error
    assert repository.load(initial.case_id).state == "failed"


def test_case_service_rejects_empty_question_before_creating_case(tmp_path: Path) -> None:
    repository = InvestigationRepository(tmp_path / "investigations")

    with pytest.raises(ValueError, match="question must not be empty"):
        create_investigation(
            question="  ",
            file_name="demo.csv",
            content=b"measurement_value\n10.0\n",
            repository=repository,
            start_background=False,
        )

    assert not repository.root.exists()
