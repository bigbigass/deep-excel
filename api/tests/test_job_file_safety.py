from io import BytesIO
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from api.app.main import app
from api.app.routes import jobs as job_routes


client = TestClient(app)


def test_same_named_uploads_are_written_to_isolated_directories(monkeypatch, tmp_path: Path) -> None:
    captured_paths: list[Path] = []

    def fake_enqueue_job_analysis(upload_path: Path) -> dict[str, str]:
        captured_paths.append(upload_path)
        return {"job_id": f"JOB-{len(captured_paths)}"}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(job_routes, "enqueue_job_analysis", fake_enqueue_job_analysis)

    first_response = client.post(
        "/api/v1/jobs",
        files={"file": ("demo.csv", BytesIO(b"first"), "text/csv")},
    )
    second_response = client.post(
        "/api/v1/jobs",
        files={"file": ("demo.csv", BytesIO(b"second"), "text/csv")},
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert len(captured_paths) == 2
    assert captured_paths[0].name == "demo.csv"
    assert captured_paths[1].name == "demo.csv"
    assert captured_paths[0].parent != captured_paths[1].parent
    assert captured_paths[0].read_bytes() == b"first"
    assert captured_paths[1].read_bytes() == b"second"


@pytest.mark.parametrize(
    "file_name",
    [
        "report.txt",
        "../secret.xlsx",
        "nested/report.xlsx",
        "..\\secret.xlsx",
    ],
)
def test_report_path_rejects_unsafe_or_non_excel_names(file_name: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        job_routes._resolve_report_path(file_name)

    assert exc_info.value.status_code == 400


def test_report_path_returns_not_found_for_missing_report(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(HTTPException) as exc_info:
        job_routes._resolve_report_path("RPT-missing.xlsx")

    assert exc_info.value.status_code == 404


def test_report_path_accepts_existing_report(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    report_path = tmp_path / "outputs" / "reports" / "RPT-valid.xlsx"
    report_path.parent.mkdir(parents=True)
    report_path.write_bytes(b"xlsx-placeholder")

    resolved = job_routes._resolve_report_path("RPT-valid.xlsx")

    assert resolved == report_path.resolve()
