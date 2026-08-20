from pathlib import Path

import pandas as pd

from api.app.domain.mapping import (
    MappingAssignment,
    SchemaMappingConfirmation,
)
from api.app.services.investigation import cases
from api.app.services.investigation.repository import InvestigationRepository


DEMO_DATA_PATH = Path("sample_data/investigation_demo.csv")

# 两个设备/型腔组合各 8 条，满足默认 min_group_size=5；两个材料批次
# 都各含 4 条正常和 4 条超规，避免把材料批次误判为主要因素。
NONCANONICAL_CSV = """样本编号,检测时间,外径实测值,规格上限,规格下限,设备号,模穴,班次,物料批次,刀具编号,刀具寿命
S-001,2026-08-13 08:00,20.000,20.040,19.960,M01,1,白班,LOT-A,T-01,100
S-002,2026-08-13 08:05,20.045,20.040,19.960,M02,4,白班,LOT-A,T-04,9001
S-003,2026-08-13 08:10,20.002,20.040,19.960,M01,1,白班,LOT-B,T-01,101
S-004,2026-08-13 08:15,20.046,20.040,19.960,M02,4,白班,LOT-B,T-04,9002
S-005,2026-08-13 08:20,20.001,20.040,19.960,M01,1,白班,LOT-A,T-01,102
S-006,2026-08-13 08:25,20.047,20.040,19.960,M02,4,白班,LOT-A,T-04,9003
S-007,2026-08-13 08:30,20.003,20.040,19.960,M01,1,白班,LOT-B,T-01,103
S-008,2026-08-13 08:35,20.048,20.040,19.960,M02,4,白班,LOT-B,T-04,9004
S-009,2026-08-13 08:40,20.000,20.040,19.960,M01,1,夜班,LOT-A,T-01,104
S-010,2026-08-13 08:45,20.045,20.040,19.960,M02,4,夜班,LOT-A,T-04,9005
S-011,2026-08-13 08:50,20.002,20.040,19.960,M01,1,夜班,LOT-B,T-01,105
S-012,2026-08-13 08:55,20.046,20.040,19.960,M02,4,夜班,LOT-B,T-04,9006
S-013,2026-08-13 09:00,20.001,20.040,19.960,M01,1,夜班,LOT-A,T-01,106
S-014,2026-08-13 09:05,20.047,20.040,19.960,M02,4,夜班,LOT-A,T-04,9007
S-015,2026-08-13 09:10,20.003,20.040,19.960,M01,1,夜班,LOT-B,T-01,107
S-016,2026-08-13 09:15,20.048,20.040,19.960,M02,4,夜班,LOT-B,T-04,9008
"""


def _create_case(
    repository: InvestigationRepository,
    *,
    file_name: str,
    content: bytes,
) -> tuple[str, Path]:
    payload = cases.create_investigation(
        question="为什么外径不良率升高？",
        file_name=file_name,
        content=content,
        repository=repository,
        start_background=False,
    )
    case_id = payload["case_id"]
    initial = repository.load(case_id)
    source_path = repository.resolve_source_ref(case_id, initial.source_refs[0])
    return case_id, source_path


def test_canonical_upload_runs_without_manual_mapping(tmp_path: Path) -> None:
    repository = InvestigationRepository(tmp_path / "investigations")
    case_id, source_path = _create_case(
        repository,
        file_name=DEMO_DATA_PATH.name,
        content=DEMO_DATA_PATH.read_bytes(),
    )

    completed = cases.run_investigation(case_id, source_path, repository=repository)
    mapping = repository.load_mapping(case_id)

    assert completed.state == "ready", completed.error
    assert mapping.status == "confirmed"
    assert mapping.generated_by == "canonical"
    assert mapping.confirmed_by == "system:canonical-schema"
    assert len(completed.evidence) >= 5


def test_noncanonical_upload_stops_for_mapping_confirmation(tmp_path: Path) -> None:
    repository = InvestigationRepository(tmp_path / "investigations")
    case_id, source_path = _create_case(
        repository,
        file_name="客户外径记录.csv",
        content=NONCANONICAL_CSV.encode("utf-8-sig"),
    )

    mapping_required = cases.run_investigation(
        case_id,
        source_path,
        repository=repository,
    )
    mapping = cases.load_investigation_mapping(case_id, repository=repository)

    assert mapping_required.state == "mapping_required"
    assert mapping_required.evidence == []
    assert mapping.status == "pending"
    assert mapping.mapping_for_role("measurement_value").source_column == "外径实测值"
    assert mapping.mapping_for_role("machine_id").source_column == "设备号"
    assert any("人工确认" in item for item in mapping_required.missing_data)


def test_confirmed_noncanonical_mapping_runs_baseline_investigation(tmp_path: Path) -> None:
    repository = InvestigationRepository(tmp_path / "investigations")
    case_id, source_path = _create_case(
        repository,
        file_name="客户外径记录.csv",
        content=NONCANONICAL_CSV.encode("utf-8-sig"),
    )
    mapping_required = cases.run_investigation(
        case_id,
        source_path,
        repository=repository,
    )
    assert mapping_required.state == "mapping_required"
    proposal = repository.load_mapping(case_id)

    completed = cases.confirm_investigation_mapping(
        case_id,
        SchemaMappingConfirmation(
            actor_id="quality-engineer-01",
            mappings=[
                MappingAssignment(source_column=item.source_column, role=item.role)
                for item in proposal.mappings
            ],
        ),
        repository=repository,
    )
    confirmed = repository.load_mapping(case_id)

    assert completed.state == "ready", completed.error
    assert confirmed.status == "confirmed"
    assert confirmed.confirmed_by == "quality-engineer-01"
    assert completed.scope.start_at is not None
    assert completed.scope.end_at is not None
    assert len(completed.evidence) >= 5
    group_evidence = next(
        item
        for item in completed.evidence
        if item.id == "E-GROUP-MACHINE-ID-CAVITY-ID"
    )
    assert group_evidence.metrics["selected_group"] == {
        "machine_id": "M02",
        "cavity_id": 4,
    }
    material_evidence = next(
        item
        for item in completed.evidence
        if item.id == "E-GROUP-MATERIAL-LOT"
    )
    assert material_evidence.metrics["difference_detected"] is False


def test_invalid_manual_mapping_does_not_replace_pending_proposal(tmp_path: Path) -> None:
    repository = InvestigationRepository(tmp_path / "investigations")
    invalid_csv = "编号,结果\nS-1,20.01\nS-2,bad-value\n"
    case_id, source_path = _create_case(
        repository,
        file_name="invalid.csv",
        content=invalid_csv.encode("utf-8"),
    )
    state = cases.run_investigation(case_id, source_path, repository=repository)
    assert state.state == "mapping_required"
    proposal = repository.load_mapping(case_id)

    try:
        cases.confirm_investigation_mapping(
            case_id,
            SchemaMappingConfirmation(
                actor_id="quality-engineer-01",
                mappings=[
                    MappingAssignment(source_column="编号", role="sample_id"),
                    MappingAssignment(source_column="结果", role="measurement_value"),
                ],
            ),
            repository=repository,
        )
    except ValueError as exc:
        assert "non-numeric values" in str(exc)
    else:
        raise AssertionError("invalid measurement values must reject the mapping")

    persisted_case = repository.load(case_id)
    persisted_mapping = repository.load_mapping(case_id)
    assert persisted_case.state == "mapping_required"
    assert persisted_mapping == proposal
    assert persisted_mapping.status == "pending"


def test_ai_investigation_uses_confirmed_noncanonical_mapping(tmp_path: Path, monkeypatch) -> None:
    repository = InvestigationRepository(tmp_path / "investigations")
    case_id, source_path = _create_case(
        repository,
        file_name="客户外径记录.csv",
        content=NONCANONICAL_CSV.encode("utf-8-sig"),
    )
    cases.run_investigation(case_id, source_path, repository=repository)
    proposal = repository.load_mapping(case_id)
    completed = cases.confirm_investigation_mapping(
        case_id,
        SchemaMappingConfirmation(
            actor_id="quality-engineer-01",
            mappings=[
                MappingAssignment(source_column=item.source_column, role=item.role)
                for item in proposal.mappings
            ],
        ),
        repository=repository,
    )
    assert completed.state == "ready"

    captured: dict[str, object] = {}

    def fake_run(case, frame: pd.DataFrame, **kwargs):
        captured["columns"] = list(frame.columns)
        captured["measurement_values"] = frame["measurement_value"].tolist()
        raise RuntimeError("stop after normalized frame capture")

    monkeypatch.setattr(cases, "run_evidence_grounded_ai", fake_run)

    try:
        cases.run_ai_investigation(case_id, repository=repository)
    except RuntimeError as exc:
        assert "normalized frame capture" in str(exc)
    else:
        raise AssertionError("fake AI pipeline should stop the test")

    assert "measurement_value" in captured["columns"]
    assert captured["measurement_values"][:2] == [20.0, 20.045]
