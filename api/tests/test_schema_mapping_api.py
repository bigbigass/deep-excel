from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from api.app.main import app
from api.app.services.investigation import cases
from api.app.services.investigation.repository import InvestigationRepository


client = TestClient(app)
DEMO_DATA_PATH = Path("sample_data/investigation_demo.csv")

_COLUMN_RENAMES = {
    "sample_id": "样本编号",
    "measured_at": "检测时间",
    "quality_feature": "检测项目",
    "measurement_value": "外径实测值",
    "target": "目标值",
    "usl": "规格上限",
    "lsl": "规格下限",
    "machine_id": "设备号",
    "cavity_id": "模穴",
    "shift": "班次",
    "material_lot": "物料批次",
    "tool_id": "刀具编号",
    "tool_cycles": "刀具寿命",
}


def _noncanonical_csv_bytes() -> bytes:
    frame = pd.read_csv(DEMO_DATA_PATH)
    return frame.rename(columns=_COLUMN_RENAMES).to_csv(index=False).encode("utf-8-sig")


def _create_mapping_required_case(repository: InvestigationRepository) -> str:
    payload = cases.create_investigation(
        question="为什么外径不良率升高？",
        file_name="客户外径记录.csv",
        content=_noncanonical_csv_bytes(),
        repository=repository,
        start_background=False,
    )
    case_id = payload["case_id"]
    initial = repository.load(case_id)
    source_path = repository.resolve_source_ref(case_id, initial.source_refs[0])
    result = cases.run_investigation(case_id, source_path, repository=repository)
    assert result.state == "mapping_required", result.error
    return case_id


def _confirmation_payload(mapping_payload: dict[str, object]) -> dict[str, object]:
    mappings = mapping_payload["mappings"]
    assert isinstance(mappings, list)
    return {
        "actor_id": "quality-engineer-01",
        "mappings": [
            {
                "source_column": item["source_column"],
                "role": item["role"],
            }
            for item in mappings
        ],
    }


def test_mapping_api_returns_pending_semantic_suggestions(monkeypatch, tmp_path: Path) -> None:
    repository = InvestigationRepository(tmp_path / "investigations")
    monkeypatch.setattr(cases, "_DEFAULT_REPOSITORY", repository)
    case_id = _create_mapping_required_case(repository)

    response = client.get(f"/api/v1/investigations/{case_id}/mapping")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "pending"
    assert payload["generated_by"] == "deterministic"
    by_role = {
        item["role"]: item
        for item in payload["mappings"]
        if item["role"] != "ignore"
    }
    assert by_role["measurement_value"]["source_column"] == "外径实测值"
    assert by_role["machine_id"]["source_column"] == "设备号"
    assert by_role["cavity_id"]["source_column"] == "模穴"
    assert by_role["measurement_value"]["origin"] == "rule"


def test_mapping_confirmation_api_runs_baseline_and_persists_human_record(
    monkeypatch,
    tmp_path: Path,
) -> None:
    repository = InvestigationRepository(tmp_path / "investigations")
    monkeypatch.setattr(cases, "_DEFAULT_REPOSITORY", repository)
    case_id = _create_mapping_required_case(repository)
    mapping_response = client.get(f"/api/v1/investigations/{case_id}/mapping")
    assert mapping_response.status_code == 200

    confirm_response = client.post(
        f"/api/v1/investigations/{case_id}/mapping/confirm",
        json=_confirmation_payload(mapping_response.json()),
    )

    assert confirm_response.status_code == 200, confirm_response.text
    case_payload = confirm_response.json()
    assert case_payload["state"] == "ready"
    assert len(case_payload["evidence"]) >= 5
    assert any(
        item["id"] == "E-GROUP-MACHINE-ID-CAVITY-ID"
        for item in case_payload["evidence"]
    )

    persisted_mapping_response = client.get(
        f"/api/v1/investigations/{case_id}/mapping"
    )
    assert persisted_mapping_response.status_code == 200
    persisted_mapping = persisted_mapping_response.json()
    assert persisted_mapping["status"] == "confirmed"
    assert persisted_mapping["generated_by"] == "human"
    assert persisted_mapping["confirmed_by"] == "quality-engineer-01"
    assert persisted_mapping["confirmed_at"] is not None
    assert persisted_mapping["revision"] == 2


def test_mapping_confirmation_api_rejects_missing_measurement_role_without_mutation(
    monkeypatch,
    tmp_path: Path,
) -> None:
    repository = InvestigationRepository(tmp_path / "investigations")
    monkeypatch.setattr(cases, "_DEFAULT_REPOSITORY", repository)
    case_id = _create_mapping_required_case(repository)
    mapping_response = client.get(f"/api/v1/investigations/{case_id}/mapping")
    assert mapping_response.status_code == 200
    original_mapping = mapping_response.json()
    confirmation = _confirmation_payload(original_mapping)
    for item in confirmation["mappings"]:
        if item["role"] == "measurement_value":
            item["role"] = "ignore"

    response = client.post(
        f"/api/v1/investigations/{case_id}/mapping/confirm",
        json=confirmation,
    )

    assert response.status_code == 409
    assert "measurement_value must be assigned" in response.json()["detail"]
    case_response = client.get(f"/api/v1/investigations/{case_id}")
    assert case_response.status_code == 200
    assert case_response.json()["state"] == "mapping_required"
    mapping_after = client.get(f"/api/v1/investigations/{case_id}/mapping")
    assert mapping_after.status_code == 200
    assert mapping_after.json() == original_mapping


def test_mapping_api_returns_not_found_for_unknown_case(monkeypatch, tmp_path: Path) -> None:
    repository = InvestigationRepository(tmp_path / "investigations")
    monkeypatch.setattr(cases, "_DEFAULT_REPOSITORY", repository)

    response = client.get("/api/v1/investigations/CASE-NOT-FOUND/mapping")

    assert response.status_code == 404
