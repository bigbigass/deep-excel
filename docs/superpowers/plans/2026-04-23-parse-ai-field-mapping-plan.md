# Parse AI Field Mapping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Insert an LLM-backed field identification step into the Parse phase, persist Chinese reasoning on the parse task, and show that reasoning in the frontend trace so demos visibly prove AI is involved before the final narrative step.

**Architecture:** Add a dedicated field-mapping planner under `api/app/agent/` that mirrors the existing report planner fallback chain: structured output first, plain JSON second, keyword rules last. Keep Normalize, Analyze, Charts, and Render behavior unchanged; only swap Parse to call the new planner, store `reasoning` on task payloads, and let the frontend prefer server-provided parse reasoning when present.

**Tech Stack:** FastAPI, Pydantic, pandas, LangChain `ChatOpenAI`, pytest, Next.js App Router, TypeScript, Jest

---

### Task 1: Add the demo fixture and planner tests

**Files:**
- Create: `api/tests/fixtures/ambiguous_columns.csv`
- Create: `api/tests/test_field_mapping_planner.py`

- [ ] **Step 1: Create the ambiguous-column fixture used by tests and demos**

```csv
sample_code,batch_code,diameter_mm,measured_time,spec_upper,spec_lower
S-001,B-01,10.012,2026-04-23 08:00:00,10.050,9.950
S-002,B-01,10.018,2026-04-23 08:01:00,10.050,9.950
S-003,B-01,10.007,2026-04-23 08:02:00,10.050,9.950
S-004,B-01,10.021,2026-04-23 08:03:00,10.050,9.950
S-005,B-01,10.015,2026-04-23 08:04:00,10.050,9.950
```

- [ ] **Step 2: Write the failing backend tests for planner fallback, validation, and Chinese reasoning**

```python
from pathlib import Path

import pandas as pd

from api.app.agent import field_mapping_planner
from api.app.config import get_settings

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "ambiguous_columns.csv"


def load_fixture_frame() -> pd.DataFrame:
    return pd.read_csv(FIXTURE_PATH)


class FakeStructuredInvoker:
    def __init__(self, response: object) -> None:
        self.response = response

    def invoke(self, messages: object) -> object:
        return self.response


class FakeModel:
    def __init__(self, response: object) -> None:
        self.response = response

    def with_structured_output(self, schema: object) -> FakeStructuredInvoker:
        return FakeStructuredInvoker(self.response)


def test_rule_based_planner_returns_mapping_and_generic_reasoning(monkeypatch) -> None:
    monkeypatch.setenv("DEEPEXCEL_OPENAI_API_KEY", "")
    get_settings.cache_clear()

    planner = field_mapping_planner.build_field_mapping_planner()
    mapping, reasoning = planner.plan(load_fixture_frame(), "ambiguous_columns.csv")

    assert isinstance(planner, field_mapping_planner.RuleBasedFieldMappingPlanner)
    assert mapping.measurement_column == "diameter_mm"
    assert reasoning == field_mapping_planner.DEFAULT_FIELD_MAPPING_REASONING


def test_llm_planner_uses_mocked_response(monkeypatch) -> None:
    monkeypatch.setenv("DEEPEXCEL_OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()

    fake_response = field_mapping_planner.FieldMappingPlanResponse(
        sample_id_column="sample_code",
        batch_column="batch_code",
        measurement_column="diameter_mm",
        lsl_column="spec_lower",
        usl_column="spec_upper",
        target_column=None,
        timestamp_column="measured_time",
        sequence_column=None,
        reasoning="AI 已识别 diameter_mm 为测量列，spec_upper / spec_lower 为规格上下限。",
    )
    monkeypatch.setattr(field_mapping_planner, "build_agent_model", lambda **kwargs: FakeModel(fake_response))

    planner = field_mapping_planner.FieldMappingPlanner()
    mapping, reasoning = planner.plan(load_fixture_frame(), "ambiguous_columns.csv")

    assert mapping.measurement_column == "diameter_mm"
    assert mapping.lsl_column == "spec_lower"
    assert mapping.usl_column == "spec_upper"
    assert mapping.timestamp_column == "measured_time"
    assert reasoning == "AI 已识别 diameter_mm 为测量列，spec_upper / spec_lower 为规格上下限。"


def test_llm_planner_rejects_hallucinated_column(monkeypatch) -> None:
    monkeypatch.setenv("DEEPEXCEL_OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()

    fake_response = field_mapping_planner.FieldMappingPlanResponse(
        sample_id_column="sample_code",
        batch_column="batch_code",
        measurement_column="not_a_real_column",
        lsl_column="spec_lower",
        usl_column="spec_upper",
        target_column=None,
        timestamp_column="measured_time",
        sequence_column=None,
        reasoning="AI 推断了一个不存在的测量列。",
    )
    monkeypatch.setattr(field_mapping_planner, "build_agent_model", lambda **kwargs: FakeModel(fake_response))

    planner = field_mapping_planner.FieldMappingPlanner()
    mapping, reasoning = planner.plan(load_fixture_frame(), "ambiguous_columns.csv")

    assert mapping.measurement_column == "diameter_mm"
    assert reasoning == field_mapping_planner.DEFAULT_FIELD_MAPPING_REASONING


def test_llm_planner_chinese_guard(monkeypatch) -> None:
    monkeypatch.setenv("DEEPEXCEL_OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()

    fake_response = field_mapping_planner.FieldMappingPlanResponse(
        sample_id_column="sample_code",
        batch_column="batch_code",
        measurement_column="diameter_mm",
        lsl_column="spec_lower",
        usl_column="spec_upper",
        target_column=None,
        timestamp_column="measured_time",
        sequence_column=None,
        reasoning="Mapped diameter_mm as the measurement column.",
    )
    monkeypatch.setattr(field_mapping_planner, "build_agent_model", lambda **kwargs: FakeModel(fake_response))

    planner = field_mapping_planner.FieldMappingPlanner()
    mapping, reasoning = planner.plan(load_fixture_frame(), "ambiguous_columns.csv")

    assert mapping.measurement_column == "diameter_mm"
    assert reasoning == field_mapping_planner.DEFAULT_FIELD_MAPPING_REASONING
```

- [ ] **Step 3: Run the tests to verify they fail before implementation exists**

Run: `.\.venv\Scripts\python -m pytest api\tests\test_field_mapping_planner.py -q`
Expected: FAIL with `ImportError` or `AttributeError` because `api.app.agent.field_mapping_planner` and the related planner types do not exist yet

### Task 2: Implement the AI field-mapping planner and reuse factory helpers

**Files:**
- Create: `api/app/agent/field_mapping_planner.py`
- Modify: `api/app/agent/factory.py`

- [ ] **Step 1: Expose public helper aliases in the existing agent factory instead of duplicating parsing logic**

```python
def coerce_message_text(content: object) -> str:
    return _coerce_message_text(content)


def extract_json_object(raw_text: str) -> str:
    return _extract_json_object(raw_text)
```

- [ ] **Step 2: Implement the new planner module with structured-output, plain-JSON, and rule fallback**

```python
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from pydantic import BaseModel

from api.app.agent.factory import build_agent_model, coerce_message_text, extract_json_object
from api.app.config import get_settings
from api.app.schemas import FieldMapping
from api.app.services.ingestion import infer_field_mapping
from api.app.services.report_localization import choose_chinese_text

DEFAULT_FIELD_MAPPING_REASONING = "系统已按关键字规则识别字段映射。"


class FieldMappingPlanResponse(BaseModel):
    sample_id_column: str | None
    batch_column: str | None
    measurement_column: str
    lsl_column: str | None
    usl_column: str | None
    target_column: str | None
    timestamp_column: str | None
    sequence_column: str | None
    reasoning: str


@dataclass
class RuleBasedFieldMappingPlanner:
    def plan(self, frame: pd.DataFrame, file_name: str) -> tuple[FieldMapping, str]:
        return infer_field_mapping(frame), DEFAULT_FIELD_MAPPING_REASONING


class FieldMappingPlanner(RuleBasedFieldMappingPlanner):
    def __init__(self) -> None:
        self.model = build_agent_model()

    def _build_messages(self, frame: pd.DataFrame, file_name: str) -> list[dict[str, str]]:
        columns_with_dtypes = "\n".join(f"- {column}: {frame[column].dtype}" for column in frame.columns)
        head_csv = frame.head(5).to_csv(index=False)
        return [
            {
                "role": "system",
                "content": (
                    "你在为一份中文 SPC 质量报告识别数据列。只返回一个 JSON 对象，不要 markdown。"
                    "reasoning 字段必须为中文，一句话，说明每个关键列为什么被这样映射。"
                    "所有列名字段必须是给定可选列中的原样字符串，或 null。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"文件名: {file_name}\n"
                    f"列清单:\n{columns_with_dtypes}\n"
                    f"前 5 行样本:\n{head_csv}\n"
                    "请识别: sample_id_column / batch_column / measurement_column / lsl_column / usl_column / "
                    "target_column / timestamp_column / sequence_column / reasoning。"
                ),
            },
        ]

    def _plan_from_plain_json_model(self, frame: pd.DataFrame, file_name: str) -> FieldMappingPlanResponse:
        response = self.model.invoke(self._build_messages(frame, file_name))
        raw_text = coerce_message_text(getattr(response, "content", response))
        json_text = extract_json_object(raw_text)
        return FieldMappingPlanResponse.model_validate_json(json_text)

    def _sanitize_column(self, columns: set[str], value: str | None) -> str | None:
        if value is None:
            return None
        return value if value in columns else None

    def _sanitize_response(self, frame: pd.DataFrame, response: FieldMappingPlanResponse) -> tuple[FieldMapping, str]:
        columns = {str(column) for column in frame.columns}
        measurement_column = self._sanitize_column(columns, response.measurement_column)
        if measurement_column is None or not pd.api.types.is_numeric_dtype(frame[measurement_column]):
            return super().plan(frame, "")

        mapping = FieldMapping(
            sample_id_column=self._sanitize_column(columns, response.sample_id_column),
            batch_column=self._sanitize_column(columns, response.batch_column),
            measurement_column=measurement_column,
            lsl_column=self._sanitize_column(columns, response.lsl_column),
            usl_column=self._sanitize_column(columns, response.usl_column),
            target_column=self._sanitize_column(columns, response.target_column),
            timestamp_column=self._sanitize_column(columns, response.timestamp_column),
            sequence_column=self._sanitize_column(columns, response.sequence_column),
        )
        reasoning = choose_chinese_text(response.reasoning, fallback=DEFAULT_FIELD_MAPPING_REASONING)
        return mapping, reasoning

    def plan(self, frame: pd.DataFrame, file_name: str) -> tuple[FieldMapping, str]:
        try:
            structured_model = self.model.with_structured_output(FieldMappingPlanResponse)
            response = structured_model.invoke(self._build_messages(frame, file_name))
            structured = FieldMappingPlanResponse.model_validate(response)
        except Exception:
            try:
                structured = self._plan_from_plain_json_model(frame, file_name)
            except Exception:
                return super().plan(frame, file_name)
        return self._sanitize_response(frame, structured)


def build_field_mapping_planner() -> RuleBasedFieldMappingPlanner:
    settings = get_settings()
    if not settings.openai_api_key:
        return RuleBasedFieldMappingPlanner()
    return FieldMappingPlanner()
```

- [ ] **Step 3: Run the new planner tests and the existing factory tests**

Run: `.\.venv\Scripts\python -m pytest api\tests\test_field_mapping_planner.py api\tests\test_agent_factory.py -q`
Expected: PASS

### Task 3: Persist parse reasoning on job tasks without changing downstream analysis behavior

**Files:**
- Modify: `api/app/schemas.py`
- Modify: `api/app/services/jobs.py`
- Create: `api/tests/test_jobs.py`

- [ ] **Step 1: Write the failing job-persistence test for parse reasoning**

```python
from pathlib import Path

from api.app.config import get_settings
from api.app.services import jobs
from api.app.services.ingestion import infer_field_mapping

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "ambiguous_columns.csv"


class FakeFieldMappingPlanner:
    def plan(self, frame, file_name):
        return (
            infer_field_mapping(frame),
            "AI 已识别 diameter_mm 为测量列，spec_upper / spec_lower 为规格上下限。",
        )


def test_run_job_analysis_persists_parse_reasoning(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DEEPEXCEL_OUTPUTS_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("DEEPEXCEL_OPENAI_API_KEY", "")
    get_settings.cache_clear()

    monkeypatch.setattr(jobs, "build_field_mapping_planner", lambda: FakeFieldMappingPlanner())
    monkeypatch.setattr(jobs, "generate_chart_bundle", lambda *args, **kwargs: {})

    jobs._create_job_record("JOB-TRACE01", FIXTURE_PATH)
    jobs.run_job_analysis("JOB-TRACE01", FIXTURE_PATH)

    payload = jobs.load_job("JOB-TRACE01")
    parse_task = next(task for task in payload["tasks"] if task["id"] == "parse")

    assert parse_task["status"] == "completed"
    assert parse_task["reasoning"] == "AI 已识别 diameter_mm 为测量列，spec_upper / spec_lower 为规格上下限。"
    assert any("\u4e00" <= char <= "\u9fff" for char in parse_task["reasoning"])
```

- [ ] **Step 2: Run the new job test to verify it fails before wiring the parse planner into jobs**

Run: `.\.venv\Scripts\python -m pytest api\tests\test_jobs.py -q`
Expected: FAIL because task payloads do not yet carry `reasoning` and Parse still calls `infer_field_mapping()` directly

- [ ] **Step 3: Add an explicit backend task schema and a reasoning-aware task status updater**

```python
from typing import Literal

from pydantic import BaseModel


class JobTask(BaseModel):
    id: str
    label: str
    status: Literal["pending", "running", "completed", "failed"]
    error: str | None = None
    reasoning: str | None = None
```

```python
from api.app.schemas import JobTask
from api.app.agent.field_mapping_planner import build_field_mapping_planner

_REASONING_UNSET = object()


def _build_empty_tasks() -> list[dict[str, object]]:
    return [
        JobTask(id=task_id, label=label, status="pending", error=None, reasoning=None).model_dump()
        for task_id, label in TASK_DEFINITIONS
    ]


def _set_task_status(
    payload: dict[str, object],
    task_id: str,
    status: str,
    error: str | None = None,
    reasoning: object = _REASONING_UNSET,
) -> None:
    tasks = payload["tasks"]
    assert isinstance(tasks, list)
    for task in tasks:
        if task["id"] == task_id:
            task["status"] = status
            task["error"] = error
            if reasoning is not _REASONING_UNSET:
                task["reasoning"] = reasoning
            return
    raise KeyError(f"Unknown task id: {task_id}")
```

- [ ] **Step 4: Replace the direct `infer_field_mapping()` call in Parse with a shared planner-backed helper**

```python
def _parse_uploaded_measurements(upload_path: Path) -> tuple[pd.DataFrame, str]:
    raw = load_source_dataframe(upload_path)
    planner = build_field_mapping_planner()
    mapping, reasoning = planner.plan(raw, upload_path.name)
    normalized = normalize_measurements(raw, mapping)
    return normalized, reasoning


def _build_job_payload(job_id: str, upload_path: Path) -> dict[str, object]:
    settings = get_settings()
    normalized, parse_reasoning = _parse_uploaded_measurements(upload_path)
    analysis = compute_analysis(normalized)
    chart_dir = Path(settings.outputs_dir) / "charts" / job_id
    chart_paths = generate_chart_bundle(normalized, analysis, chart_dir)
    planner = build_report_planner()
    report_spec = planner.plan(job_id=job_id, analysis=analysis)
    report_spec.dataset_summary["sample_count"] = len(normalized)
    report_spec.detail_rows = (
        normalized[["sample_id", "measurement_value", "lsl", "usl"]]
        .assign(
            status=lambda frame: [
                _resolve_detail_status(
                    measurement_value=float(row.measurement_value),
                    lsl=row.lsl,
                    usl=row.usl,
                )
                for row in frame.itertuples(index=False)
            ]
        )
        .drop(columns=["lsl", "usl"])
        .to_dict(orient="records")
    )
    return {
        "job_id": job_id,
        "template_id": report_spec.template_decision.template_id,
        "chart_paths": chart_paths,
        "report_spec": report_spec.model_dump(),
        "parse_reasoning": parse_reasoning,
    }
```

```python
def analyze_uploaded_file(upload_path: Path) -> dict[str, object]:
    job_id = f"JOB-{uuid4().hex[:8]}"
    job_payload = _build_job_payload(job_id, upload_path)
    payload = {
        "job_id": job_id,
        "state": "analysis_completed",
        "error": None,
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
        "source_file_name": upload_path.name,
        "template_id": job_payload["template_id"],
        "chart_paths": job_payload["chart_paths"],
        "report_spec": job_payload["report_spec"],
        "report_id": None,
        "download_path": None,
        "tasks": _build_empty_tasks(),
    }
    _set_task_status(payload, "upload", "completed")
    _set_task_status(payload, "parse", "completed", reasoning=job_payload["parse_reasoning"])
    for task_id in ["analyze", "charts", "ai"]:
        _set_task_status(payload, task_id, "completed")
    save_json(_job_payload_path(job_id), payload)
    return job_payload
```

```python
def run_job_analysis(job_id: str, upload_path: Path) -> None:
    try:
        _update_job(job_id, lambda payload: payload.update({"state": "running", "error": None}))

        _update_job(job_id, lambda payload: _set_task_status(payload, "parse", "running"))
        settings = get_settings()
        normalized, parse_reasoning = _parse_uploaded_measurements(upload_path)
        _update_job(
            job_id,
            lambda payload: _set_task_status(payload, "parse", "completed", reasoning=parse_reasoning),
        )

        _update_job(job_id, lambda payload: _set_task_status(payload, "analyze", "running"))
        analysis = compute_analysis(normalized)
        _update_job(job_id, lambda payload: _set_task_status(payload, "analyze", "completed"))

        _update_job(job_id, lambda payload: _set_task_status(payload, "charts", "running"))
        chart_dir = Path(settings.outputs_dir) / "charts" / job_id
        chart_paths = generate_chart_bundle(normalized, analysis, chart_dir)
        _update_job(job_id, lambda payload: _set_task_status(payload, "charts", "completed"))

        _update_job(job_id, lambda payload: _set_task_status(payload, "ai", "running"))
        planner = build_report_planner()
        report_spec = planner.plan(job_id=job_id, analysis=analysis)
        report_spec.dataset_summary["sample_count"] = len(normalized)
        report_spec.detail_rows = (
            normalized[["sample_id", "measurement_value", "lsl", "usl"]]
            .assign(
                status=lambda frame: [
                    _resolve_detail_status(
                        measurement_value=float(row.measurement_value),
                        lsl=row.lsl,
                        usl=row.usl,
                    )
                    for row in frame.itertuples(index=False)
                ]
            )
            .drop(columns=["lsl", "usl"])
            .to_dict(orient="records")
        )

        _update_job(
            job_id,
            lambda payload: (
                _set_task_status(payload, "ai", "completed"),
                payload.update(
                    {
                        "state": "analysis_completed",
                        "template_id": report_spec.template_decision.template_id,
                        "chart_paths": chart_paths,
                        "report_spec": report_spec.model_dump(),
                    }
                ),
            ),
        )
    except Exception as exc:
        pending_task = "parse"
        payload = load_job(job_id)
        tasks = payload["tasks"]
        assert isinstance(tasks, list)
        for task in tasks:
            if task["status"] == "running":
                pending_task = str(task["id"])
                break
        _mark_job_failed(job_id, pending_task, exc)
```

- [ ] **Step 5: Run the focused backend regression tests**

Run: `.\.venv\Scripts\python -m pytest api\tests\test_field_mapping_planner.py api\tests\test_jobs.py api\tests\test_demo_pipeline.py api\tests\test_jobs_api.py -q`
Expected: PASS

### Task 4: Surface parse reasoning in the frontend trace and keep type definitions compatible with old jobs

**Files:**
- Modify: `web/lib/api.ts`
- Modify: `web/components/reasoning-trace-card.tsx`
- Modify: `web/tests/reasoning-trace-card.test.tsx`

- [ ] **Step 1: Write the failing frontend test that prefers parse reasoning from the backend task payload**

```tsx
test("reasoning trace card prefers backend parse reasoning when present", () => {
  render(
    <ReasoningTraceCard
      job={createJob({
        tasks: [
          { id: "upload", label: "上传文件", status: "completed", error: null, reasoning: null },
          {
            id: "parse",
            label: "读取数据",
            status: "completed",
            error: null,
            reasoning: "AI 已识别 diameter_mm 为测量列，spec_upper / spec_lower 为规格上下限。"
          },
          { id: "analyze", label: "识别异常", status: "pending", error: null, reasoning: null },
          { id: "charts", label: "整理图表", status: "pending", error: null, reasoning: null },
          { id: "ai", label: "形成判断", status: "pending", error: null, reasoning: null },
          { id: "render", label: "生成报告", status: "pending", error: null, reasoning: null }
        ]
      })}
    />
  );

  expect(screen.getByTestId("reasoning-step-parse")).toHaveTextContent(
    "AI 已识别 diameter_mm 为测量列"
  );
});
```

- [ ] **Step 2: Run the frontend test to verify it fails before the component is wired to `task.reasoning`**

Run: `cd web; npm test -- reasoning-trace-card.test.tsx --runInBand`
Expected: FAIL because the parse step still renders only the old sample-count or loading copy

- [ ] **Step 3: Extend the client task type and switch the parse trace detail to prefer backend reasoning**

```ts
export type JobTaskItem = {
  id: string;
  label: string;
  status: JobTaskStatus;
  error: string | null;
  reasoning?: string | null;
};
```

```tsx
function buildSteps(job: JobPayload | null): TraceStep[] {
  const reportSpec = job?.report_spec;
  const parseTask = job?.tasks.find((task) => task.id === "parse");
  const sampleCount = reportSpec?.dataset_summary.sample_count ?? 0;
  const anomalyCount = reportSpec?.anomalies.length ?? 0;
  const cpk = getKpiValue(job, "Cpk") ?? "待计算";
  const passRate =
    reportSpec?.dataset_summary.overall_pass_rate === undefined
      ? null
      : `${(reportSpec.dataset_summary.overall_pass_rate * 100).toFixed(1)}%`;
  const chartTitles = reportSpec?.chart_specs.map((item) => item.title).join("、") ?? "";

  return [
    {
      id: "parse",
      title: "读取数据",
      detail: parseTask?.reasoning
        ? parseTask.reasoning
        : sampleCount > 0
          ? `已读取 ${sampleCount} 条检测记录，完成关键字段识别与标准化。`
          : "正在读取上传文件并识别测量值、规格限和批次字段。",
      status: getTaskStatus(job, "parse")
    },
    {
      id: "analyze",
      title: "识别异常",
      detail:
        reportSpec && passRate
          ? `当前合格率 ${passRate}，Cpk ${cpk}，识别到 ${anomalyCount} 个异常信号。`
          : "正在计算波动、过程能力和异常点。",
      status: getTaskStatus(job, "analyze")
    },
```

- [ ] **Step 4: Run the focused UI test and then the full frontend checks**

Run: `cd web; npm test -- reasoning-trace-card.test.tsx --runInBand`
Expected: PASS

Run: `cd web; npm test`
Expected: PASS

### Task 5: Full regression and manual demo verification

**Files:**
- Test: `api/tests/test_field_mapping_planner.py`
- Test: `api/tests/test_jobs.py`
- Test: `api/tests/test_agent_factory.py`
- Test: `api/tests/test_demo_pipeline.py`
- Test: `api/tests/test_jobs_api.py`
- Test: `web/tests/reasoning-trace-card.test.tsx`

- [ ] **Step 1: Run the full backend suite**

Run: `.\.venv\Scripts\python -m pytest api\tests -v`
Expected: PASS

- [ ] **Step 2: Run frontend unit tests and production build**

Run: `cd web; npm test`
Expected: PASS

Run: `cd web; npm run build`
Expected: PASS

- [ ] **Step 3: Perform the manual demo verification with and without the API key**

Run: `powershell -ExecutionPolicy Bypass -File .\scripts\start-local.ps1`
Expected: backend and frontend start and write logs under `outputs/dev/`

Run: `Invoke-WebRequest -Method Post http://127.0.0.1:8000/api/v1/health/upstream-check | Select-Object -ExpandProperty Content`
Expected: upstream check returns `configured: true` and `reachable: true` before the AI-backed demo pass

Manual check:
1. Upload `api/tests/fixtures/ambiguous_columns.csv`.
2. Open `/analysis/{jobId}` and confirm the Parse step becomes `completed`.
3. Confirm the trace card shows a Chinese parse explanation such as `AI 已识别 diameter_mm 为测量列，spec_upper / spec_lower 为规格上下限。`.
4. Trigger render and confirm the downloaded `.xlsx` still opens correctly.
5. Clear `DEEPEXCEL_OPENAI_API_KEY` and repeat once; Parse should still show `系统已按关键字规则识别字段映射。` instead of going blank.

## Self-Review

- Scope coverage: This plan only changes Parse field recognition, task reasoning plumbing, and the parse trace UI; it leaves Normalize, Analyze, Charts, and report rendering logic untouched except for carrying the new optional `reasoning` field.
- File fit: Because there is no existing `api/tests/test_jobs.py`, this plan creates it instead of editing a non-existent file while keeping the requested `test_field_mapping_planner.py` separate and focused.
- Backward compatibility: Old job JSON payloads remain readable because `reasoning` is optional on the frontend and `_build_empty_tasks()` initializes it for new jobs only.
