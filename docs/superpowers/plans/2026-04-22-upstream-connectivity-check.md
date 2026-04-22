# Upstream Connectivity Check Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local `.env` with the user-provided OpenAI-compatible endpoint config and expose an API endpoint that performs a minimal upstream model connectivity check.

**Architecture:** Keep configuration in `.env` and `Settings`, add one small service responsible for the upstream probe, and expose it through a dedicated API route under `/api/v1`. The probe should use the same `ChatOpenAI` configuration path as the agent planner and return a structured status payload without affecting the main report flow.

**Tech Stack:** FastAPI, Pydantic, LangChain `ChatOpenAI`, pytest, FastAPI `TestClient`

---

### Task 1: Local environment configuration

**Files:**
- Create: `.env`
- Modify: `README.md`

- [ ] **Step 1: Write the local environment file**

```dotenv
DEEPEXCEL_MODEL_NAME=gpt-5.4
DEEPEXCEL_OPENAI_BASE_URL=http://14.102.239.172:8080
DEEPEXCEL_OPENAI_API_KEY=<user-provided-key>
```

- [ ] **Step 2: Verify the file exists locally**

Run: `Get-Content .env`
Expected: shows the three `DEEPEXCEL_*` values above

- [ ] **Step 3: Update backend startup docs**

```powershell
$env:DEEPEXCEL_MODEL_NAME="gpt-5.4"
$env:DEEPEXCEL_OPENAI_BASE_URL="http://14.102.239.172:8080"
$env:DEEPEXCEL_OPENAI_API_KEY="your-api-key"
```

- [ ] **Step 4: Verify docs still reflect the current startup path**

Run: `Get-Content README.md`
Expected: backend section includes `DEEPEXCEL_MODEL_NAME`, `DEEPEXCEL_OPENAI_BASE_URL`, and `DEEPEXCEL_OPENAI_API_KEY`

### Task 2: Upstream connectivity probe service and route

**Files:**
- Create: `api/app/services/upstream_check.py`
- Create: `api/app/routes/health.py`
- Modify: `api/app/main.py`
- Test: `api/tests/test_health.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_healthcheck() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_upstream_check_returns_configuration_error_without_key(monkeypatch) -> None:
    monkeypatch.delenv("DEEPEXCEL_OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()

    response = client.post("/api/v1/health/upstream-check")

    assert response.status_code == 200
    assert response.json()["configured"] is False
    assert response.json()["reachable"] is False


def test_upstream_check_returns_success_payload(monkeypatch) -> None:
    monkeypatch.setenv("DEEPEXCEL_MODEL_NAME", "gpt-5.4")
    monkeypatch.setenv("DEEPEXCEL_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("DEEPEXCEL_OPENAI_BASE_URL", "http://example.test/v1")
    get_settings.cache_clear()

    monkeypatch.setattr("api.app.services.upstream_check.run_upstream_connectivity_check", fake_probe)

    response = client.post("/api/v1/health/upstream-check")

    assert response.status_code == 200
    assert response.json()["reachable"] is True
    assert response.json()["model"] == "gpt-5.4"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.\.venv311\Scripts\python -m pytest api\tests\test_health.py -q`
Expected: FAIL because `/api/v1/health/upstream-check` and the probe service do not exist yet

- [ ] **Step 3: Write the minimal probe service**

```python
class UpstreamCheckResult(BaseModel):
    configured: bool
    reachable: bool
    model: str
    base_url: str | None
    latency_ms: int | None
    response_preview: str | None
    error: str | None


def run_upstream_connectivity_check() -> UpstreamCheckResult:
    ...
```

- [ ] **Step 4: Expose the route and wire it into FastAPI**

```python
router = APIRouter(prefix="/api/v1/health", tags=["health"])


@router.post("/upstream-check")
def upstream_check() -> dict[str, object]:
    return run_upstream_connectivity_check().model_dump()
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.\.venv311\Scripts\python -m pytest api\tests\test_health.py -q`
Expected: PASS

### Task 3: Regression verification

**Files:**
- Test: `api/tests/test_agent_factory.py`
- Test: `api/tests/test_jobs_api.py`
- Test: `api/tests/test_demo_pipeline.py`

- [ ] **Step 1: Re-run the connectivity and factory tests**

Run: `.\.venv311\Scripts\python -m pytest api\tests\test_health.py api\tests\test_agent_factory.py -q`
Expected: PASS

- [ ] **Step 2: Re-run the key API flow tests**

Run: `.\.venv311\Scripts\python -m pytest api\tests\test_jobs_api.py api\tests\test_demo_pipeline.py -q`
Expected: PASS
