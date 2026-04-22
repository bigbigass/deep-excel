from fastapi.testclient import TestClient

from api.app.config import Settings, get_settings
from api.app.main import app

client = TestClient(app)


def test_healthcheck() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": get_settings().app_name}


def test_upstream_check_returns_configuration_error_without_key(monkeypatch) -> None:
    from api.app.services import upstream_check as upstream_check_service

    monkeypatch.setattr(
        upstream_check_service,
        "get_settings",
        lambda: Settings(
            model_name="gpt-5.4",
            openai_api_key=None,
            openai_base_url=None,
        ),
    )

    response = client.post("/api/v1/health/upstream-check")

    assert response.status_code == 200
    assert response.json() == {
        "configured": False,
        "reachable": False,
        "model": "gpt-5.4",
        "base_url": None,
        "latency_ms": None,
        "response_preview": None,
        "error": "Missing DEEPEXCEL_OPENAI_API_KEY",
    }


def test_upstream_check_returns_success_payload(monkeypatch) -> None:
    monkeypatch.setenv("DEEPEXCEL_MODEL_NAME", "gpt-5.4")
    monkeypatch.setenv("DEEPEXCEL_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("DEEPEXCEL_OPENAI_BASE_URL", "http://example.test/v1")
    get_settings.cache_clear()

    from api.app.routes import health as health_routes

    monkeypatch.setattr(
        health_routes.upstream_check_service,
        "run_upstream_connectivity_check",
        lambda: health_routes.upstream_check_service.UpstreamCheckResult(
            configured=True,
            reachable=True,
            model="gpt-5.4",
            base_url="http://example.test/v1",
            latency_ms=123,
            response_preview="PONG",
            error=None,
        ),
    )

    response = client.post("/api/v1/health/upstream-check")

    assert response.status_code == 200
    assert response.json() == {
        "configured": True,
        "reachable": True,
        "model": "gpt-5.4",
        "base_url": "http://example.test/v1",
        "latency_ms": 123,
        "response_preview": "PONG",
        "error": None,
    }
