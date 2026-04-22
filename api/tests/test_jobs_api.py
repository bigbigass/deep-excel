from io import BytesIO
from time import monotonic, sleep

from fastapi.testclient import TestClient

from api.app.main import app

client = TestClient(app)

CSV_BYTES = (
    b"sample_id,batch_id,measured_at,value,lsl,usl\n"
    b"A-001,B-01,2026-04-21 08:00:00,10.010,9.950,10.050\n"
    b"A-002,B-01,2026-04-21 08:01:00,10.025,9.950,10.050\n"
    b"A-003,B-01,2026-04-21 08:02:00,10.060,9.950,10.050\n"
)


def wait_for_job(job_id: str, expected_state: str, timeout: float = 30.0) -> dict[str, object]:
    deadline = monotonic() + timeout
    latest_payload: dict[str, object] | None = None

    while monotonic() < deadline:
        response = client.get(f"/api/v1/jobs/{job_id}")
        assert response.status_code == 200
        latest_payload = response.json()
        if latest_payload["state"] == expected_state:
            return latest_payload
        sleep(0.05)

    raise AssertionError(f"job did not reach {expected_state}: {latest_payload}")


def test_create_job_and_render_report() -> None:
    create_response = client.post(
        "/api/v1/jobs",
        files={"file": ("demo.csv", BytesIO(CSV_BYTES), "text/csv")},
    )

    assert create_response.status_code == 202
    create_payload = create_response.json()
    assert create_payload["job_id"].startswith("JOB-")

    analysis_payload = wait_for_job(create_payload["job_id"], "analysis_completed")
    assert analysis_payload["template_id"] in {
        "template_a_overview",
        "template_b_detailed",
        "template_c_showcase",
    }
    assert [task["id"] for task in analysis_payload["tasks"]] == [
        "upload",
        "parse",
        "analyze",
        "charts",
        "ai",
        "render",
    ]
    assert analysis_payload["tasks"][0]["status"] == "completed"
    assert analysis_payload["tasks"][4]["status"] == "completed"
    assert analysis_payload["tasks"][5]["status"] == "pending"

    render_response = client.post(f"/api/v1/jobs/{create_payload['job_id']}/render")
    assert render_response.status_code == 202

    completed_payload = wait_for_job(create_payload["job_id"], "completed")
    assert completed_payload["download_path"].endswith(".xlsx")
    assert completed_payload["tasks"][5]["status"] == "completed"
