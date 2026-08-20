import time
from pathlib import Path

from fastapi.testclient import TestClient

from api.app.main import app
from api.app.services.investigation import cases
from api.app.services.investigation.repository import InvestigationRepository


client = TestClient(app)
DEMO_DATA_PATH = Path("sample_data/investigation_demo.csv")


def _wait_for_terminal_analysis_state(case_id: str, timeout_seconds: float = 10.0) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    latest: dict[str, object] | None = None
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/investigations/{case_id}")
        assert response.status_code == 200
        latest = response.json()
        if latest["state"] in {"ready", "failed"}:
            return latest
        time.sleep(0.05)
    raise AssertionError(f"investigation did not finish: {latest}")


def test_investigation_api_creates_and_analyzes_case(monkeypatch, tmp_path: Path) -> None:
    repository = InvestigationRepository(tmp_path / "investigations")
    monkeypatch.setattr(cases, "_DEFAULT_REPOSITORY", repository)

    response = client.post(
        "/api/v1/investigations",
        data={"question": "为什么外径不良率升高？"},
        files={
            "file": (
                DEMO_DATA_PATH.name,
                DEMO_DATA_PATH.read_bytes(),
                "text/csv",
            )
        },
    )

    assert response.status_code == 202
    case_id = response.json()["case_id"]
    result = _wait_for_terminal_analysis_state(case_id)

    assert result["state"] == "ready", result.get("error")
    assert result["question"] == "为什么外径不良率升高？"
    assert result["scope"]["quality_feature"] == "outer_diameter"
    evidence_by_id = {item["id"]: item for item in result["evidence"]}
    assert evidence_by_id["E-CHANGE-POINT"]["metrics"]["detected"] is True
    assert evidence_by_id["E-GROUP-MACHINE-ID-CAVITY-ID"]["metrics"]["selected_group"] == {
        "machine_id": "M02",
        "cavity_id": 4,
    }
    assert evidence_by_id["E-FACTOR-RANKING"]["metrics"]["association_detected"] is True


def test_investigation_api_rejects_unsupported_file_type(monkeypatch, tmp_path: Path) -> None:
    repository = InvestigationRepository(tmp_path / "investigations")
    monkeypatch.setattr(cases, "_DEFAULT_REPOSITORY", repository)

    response = client.post(
        "/api/v1/investigations",
        data={"question": "分析这份数据"},
        files={"file": ("notes.txt", b"demo", "text/plain")},
    )

    assert response.status_code == 400
    assert "unsupported investigation file type" in response.json()["detail"]


def test_investigation_api_rejects_empty_question(monkeypatch, tmp_path: Path) -> None:
    repository = InvestigationRepository(tmp_path / "investigations")
    monkeypatch.setattr(cases, "_DEFAULT_REPOSITORY", repository)

    response = client.post(
        "/api/v1/investigations",
        data={"question": "   "},
        files={"file": ("demo.csv", b"measurement_value\n10.0\n", "text/csv")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "question must not be empty"


def test_investigation_api_returns_not_found_for_missing_case(monkeypatch, tmp_path: Path) -> None:
    repository = InvestigationRepository(tmp_path / "investigations")
    monkeypatch.setattr(cases, "_DEFAULT_REPOSITORY", repository)

    response = client.get("/api/v1/investigations/CASE-MISSING")

    assert response.status_code == 404


def test_investigation_api_rejects_invalid_case_id(monkeypatch, tmp_path: Path) -> None:
    repository = InvestigationRepository(tmp_path / "investigations")
    monkeypatch.setattr(cases, "_DEFAULT_REPOSITORY", repository)

    response = client.get("/api/v1/investigations/invalid")

    assert response.status_code == 400
