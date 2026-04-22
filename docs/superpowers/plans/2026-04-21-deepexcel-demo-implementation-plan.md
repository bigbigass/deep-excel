# DeepExcel Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local MVP demo that ingests `xlsx/csv` inspection data, computes SPC metrics, uses Deep Agents to generate bounded report content, previews results in a web app, and exports a templated Excel report.

**Architecture:** The system uses a `Next.js` front end for upload, preview, and download, and a `FastAPI` back end for ingestion, SPC analytics, chart generation, agent orchestration, and Excel rendering. Deterministic Python modules own parsing, statistics, charts, and workbook output, while `deepagents` is only used for bounded planning, template selection, and quality narrative generation through a strict `report_spec` contract.

**Tech Stack:** `Next.js`, `React`, `Tailwind CSS`, `FastAPI`, `deepagents`, `langchain`, `langchain-openai`, `langsmith`, `pandas`, `numpy`, `scipy`, `matplotlib`, `openpyxl`, `pytest`, `Jest`

---

## Scope Check

This spec is broad but still describes one cohesive MVP: a single end-to-end demo pipeline from upload to Excel export. It should stay as one implementation plan because each subsystem exists only to support that one happy path.

## File Map

- `api/requirements-dev.txt` — Python runtime and test dependencies.
- `api/app/config.py` — environment-backed application settings.
- `api/app/main.py` — FastAPI app creation, health route, router mounting, static output mounting.
- `api/app/schemas.py` — normalized dataset models and schema inference models.
- `api/app/report_models.py` — `report_spec` models and render-facing structures.
- `api/app/storage.py` — local JSON and artifact persistence for jobs and reports.
- `api/app/services/ingestion.py` — file loading, field inference, normalization.
- `api/app/services/analytics.py` — deterministic SPC and anomaly rules.
- `api/app/services/charts.py` — PNG chart generation.
- `api/app/services/templates.py` — template manifest loading and workbook bootstrap.
- `api/app/services/excel.py` — workbook population and report export.
- `api/app/services/jobs.py` — orchestration service tying together ingestion, analytics, agent output, and rendering.
- `api/app/agent/tools.py` — tool definitions exposed to the report agent.
- `api/app/agent/subagents.py` — bounded Deep Agents subagent definitions.
- `api/app/agent/factory.py` — main agent factory with rule-based fallback.
- `api/app/routes/jobs.py` — analysis and report API endpoints.
- `api/tests/` — backend tests.
- `templates/` — manifests and generated template workbooks.
- `sample_data/` — demo-ready synthetic inspection datasets.
- `web/` — Next.js application.
- `README.md` — local setup, demo flow, and operator instructions.
### Task 1: Scaffold the Python API service

**Files:**
- Create: `api/requirements-dev.txt`
- Create: `api/__init__.py`
- Create: `api/app/__init__.py`
- Create: `api/app/config.py`
- Create: `api/app/main.py`
- Create: `api/tests/test_health.py`
- Create: `.gitignore`

- [ ] **Step 1: Write the failing test**

```text
# api/requirements-dev.txt
fastapi==0.115.12
uvicorn==0.34.0
pydantic-settings==2.8.1
pandas==2.2.3
numpy==2.2.4
scipy==1.15.2
matplotlib==3.10.1
openpyxl==3.1.5
python-multipart==0.0.20
deepagents
langchain>=1.0,<2.0
langchain-core>=1.0,<2.0
langsmith>=0.3.0
langchain-openai>=0.3.0
pytest==8.3.5
httpx==0.28.1
```

```python
# api/tests/test_health.py
from fastapi.testclient import TestClient

from api.app.main import app

client = TestClient(app)


def test_healthcheck() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "deepexcel-api"}
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r api/requirements-dev.txt
.\.venv\Scripts\python -m pytest api/tests/test_health.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'api.app'`.

- [ ] **Step 3: Write minimal implementation**

```text
# .gitignore
.venv/
__pycache__/
.pytest_cache/
outputs/
web/node_modules/
web/.next/
```

```python
# api/__init__.py
"""Top-level package for the DeepExcel API."""
```

```python
# api/app/__init__.py
"""Application package for the DeepExcel API."""
```

```python
# api/app/config.py
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "deepexcel-api"
    app_env: str = "local"
    outputs_dir: str = "outputs"
    model_name: str = "gpt-4.1-mini"
    openai_api_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="DEEPEXCEL_",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
```

```python
# api/app/main.py
from fastapi import FastAPI

from api.app.config import get_settings

app = FastAPI(title="DeepExcel API", version="0.1.0")


@app.get("/health")
def healthcheck() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ok", "app": settings.app_name}
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
.\.venv\Scripts\python -m pytest api/tests/test_health.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git init
git add .gitignore api/requirements-dev.txt api/__init__.py api/app/__init__.py api/app/config.py api/app/main.py api/tests/test_health.py
git commit -m "chore: scaffold deepexcel api"
```
### Task 2: Implement ingestion, schema inference, and normalization

**Files:**
- Create: `api/app/schemas.py`
- Create: `api/app/services/__init__.py`
- Create: `api/app/services/ingestion.py`
- Create: `api/tests/test_ingestion.py`

- [ ] **Step 1: Write the failing test**

```python
# api/tests/test_ingestion.py
from pathlib import Path

from api.app.services.ingestion import (
    infer_field_mapping,
    load_source_dataframe,
    normalize_measurements,
)


CSV_TEXT = """sample_id,batch_id,measured_at,value,lsl,usl
A-001,B-01,2026-04-21 08:00:00,10.010,9.950,10.050
A-002,B-01,2026-04-21 08:01:00,10.025,9.950,10.050
A-003,B-01,2026-04-21 08:02:00,10.060,9.950,10.050
"""


def test_infer_and_normalize_measurement_file(tmp_path: Path) -> None:
    source_path = tmp_path / "simple_measurements.csv"
    source_path.write_text(CSV_TEXT, encoding="utf-8")

    raw_frame = load_source_dataframe(source_path)
    mapping = infer_field_mapping(raw_frame)
    normalized = normalize_measurements(raw_frame, mapping)

    assert mapping.measurement_column == "value"
    assert mapping.lsl_column == "lsl"
    assert mapping.usl_column == "usl"
    assert mapping.batch_column == "batch_id"
    assert normalized.loc[0, "measurement_value"] == 10.01
    assert normalized.loc[1, "sequence_index"] == 2
    assert normalized.loc[2, "batch_id"] == "B-01"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python -m pytest api/tests/test_ingestion.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'api.app.services.ingestion'`.

- [ ] **Step 3: Write minimal implementation**

```python
# api/app/schemas.py
from pydantic import BaseModel


class FieldMapping(BaseModel):
    sample_id_column: str | None = None
    batch_column: str | None = None
    measurement_column: str
    lsl_column: str | None = None
    usl_column: str | None = None
    target_column: str | None = None
    timestamp_column: str | None = None
    sequence_column: str | None = None


class DatasetProfile(BaseModel):
    row_count: int
    has_spec_limits: bool
    has_timestamp: bool
    has_sequence: bool
```

```python
# api/app/services/__init__.py
"""Service package for ingestion, analytics, rendering, and orchestration."""
```

```python
# api/app/services/ingestion.py
from pathlib import Path

import pandas as pd

from api.app.schemas import DatasetProfile, FieldMapping

CANONICAL_COLUMNS = [
    "sample_id",
    "batch_id",
    "part_number",
    "inspection_item",
    "measurement_value",
    "target_value",
    "usl",
    "lsl",
    "unit",
    "measured_at",
    "sequence_index",
    "operator_name",
    "device_name",
]


def load_source_dataframe(file_path: Path) -> pd.DataFrame:
    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(file_path)
    if suffix in {".xlsx", ".xlsm"}:
        return pd.read_excel(file_path)
    raise ValueError(f"Unsupported file type: {suffix}")


def infer_field_mapping(frame: pd.DataFrame) -> FieldMapping:
    lowered = {column.lower(): column for column in frame.columns}

    measurement_column = lowered.get("value") or lowered.get("measurement") or lowered.get("measurement_value")
    if measurement_column is None:
        numeric_candidates = frame.select_dtypes(include="number").columns.tolist()
        if not numeric_candidates:
            raise ValueError("No numeric measurement column found")
        measurement_column = numeric_candidates[0]

    return FieldMapping(
        sample_id_column=lowered.get("sample_id") or lowered.get("sample"),
        batch_column=lowered.get("batch_id") or lowered.get("batch"),
        measurement_column=measurement_column,
        lsl_column=lowered.get("lsl") or lowered.get("lower_spec_limit"),
        usl_column=lowered.get("usl") or lowered.get("upper_spec_limit"),
        target_column=lowered.get("target") or lowered.get("target_value"),
        timestamp_column=lowered.get("measured_at") or lowered.get("timestamp") or lowered.get("time"),
        sequence_column=lowered.get("sequence_index") or lowered.get("sequence") or lowered.get("index"),
    )


def normalize_measurements(frame: pd.DataFrame, mapping: FieldMapping) -> pd.DataFrame:
    normalized = pd.DataFrame(columns=CANONICAL_COLUMNS)
    normalized["sample_id"] = frame[mapping.sample_id_column] if mapping.sample_id_column else frame.index.astype(str)
    normalized["batch_id"] = frame[mapping.batch_column] if mapping.batch_column else "DEMO-BATCH"
    normalized["part_number"] = "6205"
    normalized["inspection_item"] = "Outer Diameter"
    normalized["measurement_value"] = frame[mapping.measurement_column].astype(float)
    normalized["target_value"] = frame[mapping.target_column].astype(float) if mapping.target_column else None
    normalized["usl"] = frame[mapping.usl_column].astype(float) if mapping.usl_column else None
    normalized["lsl"] = frame[mapping.lsl_column].astype(float) if mapping.lsl_column else None
    normalized["unit"] = "mm"
    normalized["measured_at"] = pd.to_datetime(frame[mapping.timestamp_column]) if mapping.timestamp_column else pd.NaT

    if mapping.sequence_column:
        normalized["sequence_index"] = frame[mapping.sequence_column].astype(int)
    else:
        normalized["sequence_index"] = range(1, len(frame) + 1)

    normalized["operator_name"] = "demo-operator"
    normalized["device_name"] = "demo-gauge"
    return normalized


def build_dataset_profile(normalized: pd.DataFrame) -> DatasetProfile:
    has_spec_limits = normalized["usl"].notna().all() and normalized["lsl"].notna().all()
    has_timestamp = normalized["measured_at"].notna().any()
    has_sequence = normalized["sequence_index"].notna().any()
    return DatasetProfile(
        row_count=len(normalized),
        has_spec_limits=bool(has_spec_limits),
        has_timestamp=bool(has_timestamp),
        has_sequence=bool(has_sequence),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
.\.venv\Scripts\python -m pytest api/tests/test_ingestion.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/app/schemas.py api/app/services/__init__.py api/app/services/ingestion.py api/tests/test_ingestion.py
git commit -m "feat: add dataset ingestion and normalization"
```
### Task 3: Implement SPC analytics, anomaly rules, and chart generation

**Files:**
- Create: `api/app/services/analytics.py`
- Create: `api/app/services/charts.py`
- Create: `api/tests/test_analytics.py`
- Create: `api/tests/test_charts.py`

- [ ] **Step 1: Write the failing test**

```python
# api/tests/test_analytics.py
import pandas as pd

from api.app.services.analytics import compute_analysis


def test_compute_analysis_returns_spc_metrics() -> None:
    normalized = pd.DataFrame(
        {
            "measurement_value": [10.01, 10.02, 10.03, 10.00, 10.06, 10.01],
            "usl": [10.05] * 6,
            "lsl": [9.95] * 6,
            "sequence_index": [1, 2, 3, 4, 5, 6],
        }
    )

    analysis = compute_analysis(normalized)

    assert round(analysis["mean"], 3) == 10.022
    assert analysis["max_value"] == 10.06
    assert analysis["out_of_spec_count"] == 1
    assert analysis["recommended_charts"] == [
        "histogram",
        "control_chart_imr",
        "trend_line",
        "spec_comparison",
    ]
```

```python
# api/tests/test_charts.py
from pathlib import Path

import pandas as pd

from api.app.services.analytics import compute_analysis
from api.app.services.charts import generate_chart_bundle



def test_generate_chart_bundle_writes_png_files(tmp_path: Path) -> None:
    normalized = pd.DataFrame(
        {
            "measurement_value": [10.01, 10.02, 10.03, 10.00, 10.06, 10.01],
            "usl": [10.05] * 6,
            "lsl": [9.95] * 6,
            "sequence_index": [1, 2, 3, 4, 5, 6],
        }
    )
    analysis = compute_analysis(normalized)

    chart_paths = generate_chart_bundle(normalized, analysis, tmp_path)

    assert set(chart_paths.keys()) == {
        "histogram",
        "control_chart_imr",
        "trend_line",
        "spec_comparison",
    }
    assert all(Path(path).exists() for path in chart_paths.values())
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python -m pytest api/tests/test_analytics.py api/tests/test_charts.py -v
```

Expected: FAIL with `ModuleNotFoundError` for the analytics and chart services.

- [ ] **Step 3: Write minimal implementation**

```python
# api/app/services/analytics.py
from __future__ import annotations

import math
from statistics import mean, pstdev

import pandas as pd



def compute_analysis(normalized: pd.DataFrame) -> dict[str, object]:
    values = normalized["measurement_value"].astype(float).tolist()
    series_mean = mean(values)
    std_dev = pstdev(values) if len(values) > 1 else 0.0
    max_value = max(values)
    min_value = min(values)

    usl = float(normalized["usl"].dropna().iloc[0]) if normalized["usl"].notna().any() else None
    lsl = float(normalized["lsl"].dropna().iloc[0]) if normalized["lsl"].notna().any() else None

    out_of_spec_count = 0
    if usl is not None and lsl is not None:
        out_of_spec_count = int(((normalized["measurement_value"] > usl) | (normalized["measurement_value"] < lsl)).sum())

    pass_rate = 1.0 - (out_of_spec_count / len(values))
    cp = None
    cpk = None
    if usl is not None and lsl is not None and std_dev > 0:
        cp = (usl - lsl) / (6 * std_dev)
        cpk = min((usl - series_mean) / (3 * std_dev), (series_mean - lsl) / (3 * std_dev))

    moving_ranges = [abs(values[index] - values[index - 1]) for index in range(1, len(values))]
    mr_mean = mean(moving_ranges) if moving_ranges else 0.0
    sigma_estimate = mr_mean / 1.128 if mr_mean else 0.0
    ucl = series_mean + 3 * sigma_estimate if sigma_estimate else None
    lcl = series_mean - 3 * sigma_estimate if sigma_estimate else None

    anomalies: list[dict[str, object]] = []
    if out_of_spec_count:
        anomalies.append(
            {
                "type": "out_of_spec",
                "severity": "high",
                "summary": f"{out_of_spec_count} points exceed the specification limits",
            }
        )
    if ucl is not None and any(value > ucl or value < lcl for value in values):
        anomalies.append(
            {
                "type": "control_limit",
                "severity": "medium",
                "summary": "One or more points exceed the calculated control limits",
            }
        )

    recommended_charts = ["histogram", "control_chart_imr", "trend_line"]
    if usl is not None and lsl is not None:
        recommended_charts.append("spec_comparison")

    return {
        "mean": series_mean,
        "std_dev": std_dev,
        "min_value": min_value,
        "max_value": max_value,
        "pass_rate": pass_rate,
        "cp": cp,
        "cpk": cpk,
        "ucl": ucl,
        "lcl": lcl,
        "out_of_spec_count": out_of_spec_count,
        "anomalies": anomalies,
        "recommended_charts": recommended_charts,
    }
```

```python
# api/app/services/charts.py
from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

matplotlib.use("Agg")



def generate_chart_bundle(normalized: pd.DataFrame, analysis: dict[str, object], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    values = normalized["measurement_value"].astype(float)
    sequence = normalized["sequence_index"].astype(int)
    chart_paths: dict[str, str] = {}

    histogram_path = output_dir / "histogram.png"
    plt.figure(figsize=(6, 4))
    plt.hist(values, bins=8, color="#2563eb", edgecolor="white")
    plt.title("Measurement Distribution")
    plt.xlabel("Value")
    plt.ylabel("Frequency")
    plt.tight_layout()
    plt.savefig(histogram_path)
    plt.close()
    chart_paths["histogram"] = str(histogram_path)

    imr_path = output_dir / "control_chart_imr.png"
    plt.figure(figsize=(7, 4))
    plt.plot(sequence, values, marker="o", color="#0f766e")
    if analysis["ucl"] is not None:
        plt.axhline(analysis["ucl"], color="#dc2626", linestyle="--", label="UCL")
        plt.axhline(analysis["lcl"], color="#dc2626", linestyle="--", label="LCL")
    plt.axhline(analysis["mean"], color="#1d4ed8", linestyle="-", label="Mean")
    plt.title("I-MR Control Chart (Individuals)")
    plt.xlabel("Sequence")
    plt.ylabel("Measurement")
    plt.legend()
    plt.tight_layout()
    plt.savefig(imr_path)
    plt.close()
    chart_paths["control_chart_imr"] = str(imr_path)

    trend_path = output_dir / "trend_line.png"
    plt.figure(figsize=(7, 4))
    plt.plot(sequence, values, marker="o", color="#7c3aed")
    plt.title("Measurement Trend")
    plt.xlabel("Sequence")
    plt.ylabel("Measurement")
    plt.tight_layout()
    plt.savefig(trend_path)
    plt.close()
    chart_paths["trend_line"] = str(trend_path)

    if "spec_comparison" in analysis["recommended_charts"]:
        spec_path = output_dir / "spec_comparison.png"
        plt.figure(figsize=(7, 4))
        plt.plot(sequence, values, marker="o", color="#111827", label="Measurement")
        plt.axhline(float(normalized["usl"].iloc[0]), color="#dc2626", linestyle="--", label="USL")
        plt.axhline(float(normalized["lsl"].iloc[0]), color="#059669", linestyle="--", label="LSL")
        plt.title("Measurement vs Specification")
        plt.xlabel("Sequence")
        plt.ylabel("Measurement")
        plt.legend()
        plt.tight_layout()
        plt.savefig(spec_path)
        plt.close()
        chart_paths["spec_comparison"] = str(spec_path)

    return chart_paths
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
.\.venv\Scripts\python -m pytest api/tests/test_analytics.py api/tests/test_charts.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/app/services/analytics.py api/app/services/charts.py api/tests/test_analytics.py api/tests/test_charts.py
git commit -m "feat: add spc metrics and chart generation"
```
### Task 4: Implement the template system and Excel renderer

**Files:**
- Create: `api/app/report_models.py`
- Create: `api/app/services/templates.py`
- Create: `api/app/services/excel.py`
- Create: `templates/template_a_overview/template_manifest.json`
- Create: `templates/template_b_detailed/template_manifest.json`
- Create: `templates/template_c_showcase/template_manifest.json`
- Create: `api/tests/test_excel_renderer.py`

- [ ] **Step 1: Write the failing test**

```python
# api/tests/test_excel_renderer.py
from pathlib import Path

import openpyxl

from api.app.report_models import (
    ChartSpec,
    KpiCard,
    NarrativeBlock,
    ReportMeta,
    ReportSpec,
    TemplateDecision,
)
from api.app.services.excel import render_report



def test_render_report_populates_template(tmp_path: Path) -> None:
    output_path = tmp_path / "demo_report.xlsx"
    report_spec = ReportSpec(
        report_meta=ReportMeta(
            title="Bearing Inspection SPC Report",
            report_id="RPT-001",
            generated_at="2026-04-21T10:00:00Z",
            batch_id="B-01",
            product_name="6205 Bearing",
        ),
        template_decision=TemplateDecision(
            template_id="template_a_overview",
            reason="Summary-first layout fits this batch",
        ),
        dataset_summary={"sample_count": 6, "overall_pass_rate": 0.8333},
        kpi_cards=[
            KpiCard(label="Mean", value="10.022"),
            KpiCard(label="Cpk", value="0.91"),
        ],
        detail_rows=[
            {"sample_id": "A-001", "measurement_value": 10.01, "status": "PASS"},
            {"sample_id": "A-002", "measurement_value": 10.06, "status": "FAIL"},
        ],
        chart_specs=[ChartSpec(chart_id="histogram", chart_type="histogram", title="Distribution")],
        anomalies=[{"severity": "high", "summary": "1 point exceeds spec"}],
        ai_narrative=NarrativeBlock(
            executive_summary="Process center is drifting upward.",
            quality_risk="Capability is marginal.",
            recommended_actions=["Check machine drift", "Review last setup change"],
        ),
    )

    report_file = render_report(
        report_spec=report_spec,
        chart_paths={},
        templates_root=Path("templates"),
        output_path=output_path,
    )

    workbook = openpyxl.load_workbook(report_file)
    summary_sheet = workbook["Summary"]

    assert report_file.exists()
    assert summary_sheet["A1"].value == "Bearing Inspection SPC Report"
    assert summary_sheet["A4"].value == "B-01"
    assert summary_sheet["A8"].value == "Mean"
    assert summary_sheet["A14"].value == "Process center is drifting upward."
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python -m pytest api/tests/test_excel_renderer.py -v
```

Expected: FAIL with `ModuleNotFoundError` for the report model or renderer modules.

- [ ] **Step 3: Write minimal implementation**

```python
# api/app/report_models.py
from pydantic import BaseModel


class ReportMeta(BaseModel):
    title: str
    report_id: str
    generated_at: str
    batch_id: str
    product_name: str


class TemplateDecision(BaseModel):
    template_id: str
    reason: str


class KpiCard(BaseModel):
    label: str
    value: str


class ChartSpec(BaseModel):
    chart_id: str
    chart_type: str
    title: str


class NarrativeBlock(BaseModel):
    executive_summary: str
    quality_risk: str
    recommended_actions: list[str]


class ReportSpec(BaseModel):
    report_meta: ReportMeta
    template_decision: TemplateDecision
    dataset_summary: dict[str, object]
    kpi_cards: list[KpiCard]
    detail_rows: list[dict[str, object]]
    chart_specs: list[ChartSpec]
    anomalies: list[dict[str, object]]
    ai_narrative: NarrativeBlock
```

```json
// templates/template_a_overview/template_manifest.json
{
  "template_id": "template_a_overview",
  "workbook_name": "template_a_overview.xlsx",
  "summary_sheet": "Summary",
  "detail_sheet": "Details",
  "slots": {
    "title_cell": "A1",
    "product_cell": "A3",
    "batch_cell": "A4",
    "reason_cell": "A6",
    "kpi_start_cell": "A8",
    "narrative_summary_cell": "A14",
    "narrative_risk_cell": "A15",
    "actions_start_cell": "A17",
    "detail_start_row": 2
  }
}
```

```json
// templates/template_b_detailed/template_manifest.json
{
  "template_id": "template_b_detailed",
  "workbook_name": "template_b_detailed.xlsx",
  "summary_sheet": "Summary",
  "detail_sheet": "Details",
  "slots": {
    "title_cell": "A1",
    "product_cell": "A3",
    "batch_cell": "A4",
    "reason_cell": "A6",
    "kpi_start_cell": "D8",
    "narrative_summary_cell": "A14",
    "narrative_risk_cell": "A15",
    "actions_start_cell": "A17",
    "detail_start_row": 2
  }
}
```

```json
// templates/template_c_showcase/template_manifest.json
{
  "template_id": "template_c_showcase",
  "workbook_name": "template_c_showcase.xlsx",
  "summary_sheet": "Summary",
  "detail_sheet": "Details",
  "slots": {
    "title_cell": "B2",
    "product_cell": "B4",
    "batch_cell": "B5",
    "reason_cell": "B7",
    "kpi_start_cell": "B9",
    "narrative_summary_cell": "B15",
    "narrative_risk_cell": "B16",
    "actions_start_cell": "B18",
    "detail_start_row": 2
  }
}
```

```python
# api/app/services/templates.py
from __future__ import annotations

import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font



def load_template_manifest(templates_root: Path, template_id: str) -> dict[str, object]:
    manifest_path = templates_root / template_id / "template_manifest.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))



def ensure_demo_template_workbook(templates_root: Path, template_id: str) -> Path:
    manifest = load_template_manifest(templates_root, template_id)
    workbook_path = templates_root / template_id / manifest["workbook_name"]
    workbook_path.parent.mkdir(parents=True, exist_ok=True)
    if workbook_path.exists():
        return workbook_path

    workbook = Workbook()
    summary = workbook.active
    summary.title = manifest["summary_sheet"]
    details = workbook.create_sheet(manifest["detail_sheet"])

    summary["A1"] = "Template placeholder"
    summary["A1"].font = Font(size=18, bold=True)
    details["A1"] = "sample_id"
    details["B1"] = "measurement_value"
    details["C1"] = "status"

    workbook.save(workbook_path)
    return workbook_path
```

```python
# api/app/services/excel.py
from __future__ import annotations

from pathlib import Path

import openpyxl

from api.app.report_models import ReportSpec
from api.app.services.templates import ensure_demo_template_workbook, load_template_manifest



def render_report(report_spec: ReportSpec, chart_paths: dict[str, str], templates_root: Path, output_path: Path) -> Path:
    template_id = report_spec.template_decision.template_id
    workbook_path = ensure_demo_template_workbook(templates_root, template_id)
    manifest = load_template_manifest(templates_root, template_id)
    workbook = openpyxl.load_workbook(workbook_path)
    summary_sheet = workbook[manifest["summary_sheet"]]
    detail_sheet = workbook[manifest["detail_sheet"]]
    slots = manifest["slots"]

    summary_sheet[slots["title_cell"]] = report_spec.report_meta.title
    summary_sheet[slots["product_cell"]] = report_spec.report_meta.product_name
    summary_sheet[slots["batch_cell"]] = report_spec.report_meta.batch_id
    summary_sheet[slots["reason_cell"]] = report_spec.template_decision.reason

    kpi_cell = summary_sheet[slots["kpi_start_cell"]]
    start_row = kpi_cell.row
    start_col = kpi_cell.column
    for offset, card in enumerate(report_spec.kpi_cards):
        summary_sheet.cell(row=start_row + offset, column=start_col, value=card.label)
        summary_sheet.cell(row=start_row + offset, column=start_col + 1, value=card.value)

    summary_sheet[slots["narrative_summary_cell"]] = report_spec.ai_narrative.executive_summary
    summary_sheet[slots["narrative_risk_cell"]] = report_spec.ai_narrative.quality_risk
    action_row = summary_sheet[slots["actions_start_cell"]].row
    action_col = summary_sheet[slots["actions_start_cell"]].column
    for offset, action in enumerate(report_spec.ai_narrative.recommended_actions):
        summary_sheet.cell(row=action_row + offset, column=action_col, value=f"- {action}")

    detail_start_row = int(slots["detail_start_row"])
    for row_offset, detail_row in enumerate(report_spec.detail_rows):
        detail_sheet.cell(row=detail_start_row + row_offset, column=1, value=detail_row.get("sample_id"))
        detail_sheet.cell(row=detail_start_row + row_offset, column=2, value=detail_row.get("measurement_value"))
        detail_sheet.cell(row=detail_start_row + row_offset, column=3, value=detail_row.get("status"))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)
    return output_path
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
.\.venv\Scripts\python -m pytest api/tests/test_excel_renderer.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/app/report_models.py api/app/services/templates.py api/app/services/excel.py templates/template_a_overview/template_manifest.json templates/template_b_detailed/template_manifest.json templates/template_c_showcase/template_manifest.json api/tests/test_excel_renderer.py
git commit -m "feat: add report spec and excel rendering"
```
### Task 5: Implement Deep Agents planning and report API routes

**Files:**
- Create: `api/app/storage.py`
- Create: `api/app/agent/tools.py`
- Create: `api/app/agent/subagents.py`
- Create: `api/app/agent/factory.py`
- Create: `api/app/services/jobs.py`
- Create: `api/app/routes/jobs.py`
- Modify: `api/app/main.py`
- Create: `api/tests/test_jobs_api.py`

- [ ] **Step 1: Write the failing test**

```python
# api/tests/test_jobs_api.py
from io import BytesIO

from fastapi.testclient import TestClient

from api.app.main import app

client = TestClient(app)

CSV_BYTES = b"sample_id,batch_id,measured_at,value,lsl,usl\nA-001,B-01,2026-04-21 08:00:00,10.010,9.950,10.050\nA-002,B-01,2026-04-21 08:01:00,10.025,9.950,10.050\nA-003,B-01,2026-04-21 08:02:00,10.060,9.950,10.050\n"


def test_create_job_and_render_report() -> None:
    create_response = client.post(
        "/api/v1/jobs",
        files={"file": ("demo.csv", BytesIO(CSV_BYTES), "text/csv")},
    )

    assert create_response.status_code == 200
    create_payload = create_response.json()
    assert create_payload["template_id"] in {
        "template_a_overview",
        "template_b_detailed",
        "template_c_showcase",
    }

    render_response = client.post(f"/api/v1/jobs/{create_payload['job_id']}/render")
    assert render_response.status_code == 200
    assert render_response.json()["download_path"].endswith(".xlsx")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python -m pytest api/tests/test_jobs_api.py -v
```

Expected: FAIL with `404 Not Found` for `/api/v1/jobs`.

- [ ] **Step 3: Write minimal implementation**

```python
# api/app/storage.py
from __future__ import annotations

import json
from pathlib import Path



def save_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")



def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))
```

```python
# api/app/agent/tools.py
from langchain_core.tools import tool


@tool
def choose_template(has_failures: bool) -> str:
    """Choose a report template ID from bounded demo templates."""
    if has_failures:
        return "template_a_overview"
    return "template_c_showcase"


@tool
def summarize_quality(mean_value: float, cpk: float | None, out_of_spec_count: int) -> str:
    """Return a concise quality summary for the report narrative."""
    if out_of_spec_count:
        return f"{out_of_spec_count} points exceed specification and the process needs review."
    if cpk is not None and cpk < 1.0:
        return "Process capability is marginal because Cpk is below the target threshold."
    return "The process is currently stable with no out-of-spec points detected."
```

```python
# api/app/agent/subagents.py
DATA_UNDERSTANDING_SUBAGENT = {
    "name": "data-understanding",
    "description": "Interpret schema and confirm which columns matter for quality analysis.",
    "system_prompt": "Work only with provided metrics and return concise schema insight.",
    "tools": [],
}

QUALITY_ANALYST_SUBAGENT = {
    "name": "quality-analyst",
    "description": "Explain SPC results in quality engineering language.",
    "system_prompt": "Produce concise quality-engineering narrative and recommendations.",
    "tools": [],
}
```

```python
# api/app/agent/factory.py
from __future__ import annotations

from dataclasses import asdict, dataclass

from deepagents import create_deep_agent

from api.app.config import get_settings
from api.app.report_models import ChartSpec, KpiCard, NarrativeBlock, ReportMeta, ReportSpec, TemplateDecision
from api.app.agent.subagents import DATA_UNDERSTANDING_SUBAGENT, QUALITY_ANALYST_SUBAGENT
from api.app.agent.tools import choose_template, summarize_quality


@dataclass
class RuleBasedReportPlanner:
    def plan(self, *, job_id: str, analysis: dict[str, object]) -> ReportSpec:
        template_id = choose_template.invoke({"has_failures": bool(analysis["out_of_spec_count"])})
        summary = summarize_quality.invoke(
            {
                "mean_value": float(analysis["mean"]),
                "cpk": analysis["cpk"],
                "out_of_spec_count": int(analysis["out_of_spec_count"]),
            }
        )
        actions = ["Check tool wear or setup drift", "Review the last machine adjustment"]
        if not analysis["out_of_spec_count"]:
            actions = ["Continue monitoring the next batch", "Keep current inspection frequency"]
        return ReportSpec(
            report_meta=ReportMeta(
                title="Bearing Inspection SPC Report",
                report_id=job_id,
                generated_at="2026-04-21T10:00:00Z",
                batch_id="DEMO-BATCH",
                product_name="6205 Bearing",
            ),
            template_decision=TemplateDecision(template_id=template_id, reason="Auto-selected from bounded demo templates"),
            dataset_summary={
                "sample_count": 0,
                "overall_pass_rate": analysis["pass_rate"],
            },
            kpi_cards=[
                KpiCard(label="Mean", value=f"{analysis['mean']:.3f}"),
                KpiCard(label="Std Dev", value=f"{analysis['std_dev']:.3f}"),
                KpiCard(label="Pass Rate", value=f"{analysis['pass_rate'] * 100:.1f}%"),
                KpiCard(label="Cpk", value="n/a" if analysis["cpk"] is None else f"{analysis['cpk']:.2f}"),
            ],
            detail_rows=[],
            chart_specs=[ChartSpec(chart_id=name, chart_type=name, title=name.replace("_", " ").title()) for name in analysis["recommended_charts"]],
            anomalies=analysis["anomalies"],
            ai_narrative=NarrativeBlock(
                executive_summary=summary,
                quality_risk="Capability review required" if analysis["out_of_spec_count"] else "No immediate quality block found",
                recommended_actions=actions,
            ),
        )


class DeepAgentPlanner(RuleBasedReportPlanner):
    def __init__(self) -> None:
        settings = get_settings()
        self.agent = create_deep_agent(
            name="report-orchestrator",
            model=settings.model_name,
            tools=[choose_template, summarize_quality],
            system_prompt="Choose one demo template, summarize SPC risk, and stay within the provided tools.",
            subagents=[DATA_UNDERSTANDING_SUBAGENT, QUALITY_ANALYST_SUBAGENT],
        )



def build_report_planner() -> RuleBasedReportPlanner:
    settings = get_settings()
    if not settings.openai_api_key:
        return RuleBasedReportPlanner()
    return DeepAgentPlanner()
```

```python
# api/app/services/jobs.py
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from api.app.agent.factory import build_report_planner
from api.app.config import get_settings
from api.app.services.analytics import compute_analysis
from api.app.services.charts import generate_chart_bundle
from api.app.services.excel import render_report
from api.app.services.ingestion import infer_field_mapping, load_source_dataframe, normalize_measurements
from api.app.storage import load_json, save_json



def analyze_uploaded_file(upload_path: Path) -> dict[str, object]:
    settings = get_settings()
    job_id = f"JOB-{uuid4().hex[:8]}"
    raw = load_source_dataframe(upload_path)
    mapping = infer_field_mapping(raw)
    normalized = normalize_measurements(raw, mapping)
    analysis = compute_analysis(normalized)
    chart_dir = Path(settings.outputs_dir) / "charts" / job_id
    chart_paths = generate_chart_bundle(normalized, analysis, chart_dir)
    planner = build_report_planner()
    report_spec = planner.plan(job_id=job_id, analysis=analysis)
    report_spec.dataset_summary["sample_count"] = len(normalized)
    report_spec.detail_rows = normalized[["sample_id", "measurement_value"]].assign(status=lambda frame: ["FAIL" if value > 10.05 or value < 9.95 else "PASS" for value in frame["measurement_value"]]).to_dict(orient="records")

    job_payload = {
        "job_id": job_id,
        "template_id": report_spec.template_decision.template_id,
        "chart_paths": chart_paths,
        "report_spec": report_spec.model_dump(),
    }
    save_json(Path(settings.outputs_dir) / "jobs" / f"{job_id}.json", job_payload)
    return job_payload



def load_job(job_id: str) -> dict[str, object]:
    settings = get_settings()
    return load_json(Path(settings.outputs_dir) / "jobs" / f"{job_id}.json")



def render_job_report(job_id: str) -> dict[str, object]:
    settings = get_settings()
    job_payload = load_job(job_id)
    report_id = f"RPT-{job_id.split('-')[-1]}"
    report_path = Path(settings.outputs_dir) / "reports" / f"{report_id}.xlsx"
    render_report(
        report_spec=ReportSpec.model_validate(job_payload["report_spec"]),
        chart_paths=job_payload["chart_paths"],
        templates_root=Path("templates"),
        output_path=report_path,
    )
    return {"report_id": report_id, "download_path": str(report_path)}
```

```python
# api/app/routes/jobs.py
from pathlib import Path

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse

from api.app.services.jobs import analyze_uploaded_file, load_job, render_job_report

router = APIRouter(prefix="/api/v1", tags=["jobs"])


@router.post("/jobs")
async def create_job(file: UploadFile = File(...)) -> dict[str, object]:
    upload_dir = Path("outputs") / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_path = upload_dir / file.filename
    upload_path.write_bytes(await file.read())
    return analyze_uploaded_file(upload_path)


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, object]:
    return load_job(job_id)


@router.post("/jobs/{job_id}/render")
def render_job(job_id: str) -> dict[str, object]:
    return render_job_report(job_id)


@router.get("/reports/{report_file_name}")
def download_report(report_file_name: str) -> FileResponse:
    report_path = Path("outputs") / "reports" / report_file_name
    return FileResponse(report_path)
```

```python
# api/app/main.py
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.app.config import get_settings
from api.app.routes.jobs import router as jobs_router

app = FastAPI(title="DeepExcel API", version="0.1.0")


@app.get("/health")
def healthcheck() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ok", "app": settings.app_name}


app.include_router(jobs_router)
Path("outputs").mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
.\.venv\Scripts\python -m pytest api/tests/test_jobs_api.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/app/storage.py api/app/agent/tools.py api/app/agent/subagents.py api/app/agent/factory.py api/app/services/jobs.py api/app/routes/jobs.py api/app/main.py api/tests/test_jobs_api.py
git commit -m "feat: add bounded report planning api"
```
### Task 6: Build the web upload, analysis, and download flow

**Files:**
- Create: `web/package.json`
- Create: `web/tsconfig.json`
- Create: `web/next.config.mjs`
- Create: `web/jest.config.mjs`
- Create: `web/jest.setup.ts`
- Create: `web/app/globals.css`
- Create: `web/app/layout.tsx`
- Create: `web/app/page.tsx`
- Create: `web/app/analysis/[jobId]/page.tsx`
- Create: `web/app/report/[reportId]/page.tsx`
- Create: `web/components/upload-form.tsx`
- Create: `web/components/kpi-grid.tsx`
- Create: `web/components/chart-list.tsx`
- Create: `web/lib/api.ts`
- Create: `web/tests/upload-form.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// web/tests/upload-form.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { UploadForm } from "../components/upload-form";


test("upload form passes the selected file to the submit handler", async () => {
  const user = userEvent.setup();
  const file = new File(["demo"], "demo.csv", { type: "text/csv" });
  const handleSubmit = jest.fn().mockResolvedValue(undefined);

  render(<UploadForm onSubmit={handleSubmit} />);

  await user.upload(screen.getByLabelText("检测数据文件"), file);
  await user.click(screen.getByRole("button", { name: "开始分析" }));

  expect(handleSubmit).toHaveBeenCalledWith(file);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd web
npm install
npm test -- upload-form.test.tsx
```

Expected: FAIL because the web app and test configuration do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```json
// web/package.json
{
  "name": "deepexcel-web",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "test": "jest"
  },
  "dependencies": {
    "next": "15.2.2",
    "react": "19.0.0",
    "react-dom": "19.0.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "6.6.3",
    "@testing-library/react": "16.2.0",
    "@testing-library/user-event": "14.6.1",
    "@types/jest": "29.5.14",
    "@types/node": "22.13.10",
    "@types/react": "19.0.10",
    "@types/react-dom": "19.0.4",
    "jest": "29.7.0",
    "jest-environment-jsdom": "29.7.0",
    "typescript": "5.8.2"
  }
}
```

```json
// web/tsconfig.json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "es2022"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./*"]
    }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx"],
  "exclude": ["node_modules"]
}
```

```javascript
// web/next.config.mjs
const nextConfig = {};
export default nextConfig;
```

```javascript
// web/jest.config.mjs
export default {
  testEnvironment: "jsdom",
  setupFilesAfterEnv: ["<rootDir>/jest.setup.ts"],
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/$1"
  }
};
```

```ts
// web/jest.setup.ts
import "@testing-library/jest-dom";
```

```tsx
// web/components/upload-form.tsx
"use client";

import { useState } from "react";

export function UploadForm({ onSubmit }: { onSubmit: (file: File) => Promise<void> }) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  return (
    <form
      className="space-y-4 rounded border p-6"
      onSubmit={async (event) => {
        event.preventDefault();
        if (selectedFile) {
          await onSubmit(selectedFile);
        }
      }}
    >
      <label className="block text-sm font-medium" htmlFor="inspection-file">
        检测数据文件
      </label>
      <input
        id="inspection-file"
        name="inspection-file"
        type="file"
        accept=".csv,.xlsx"
        onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
      />
      <button className="rounded bg-blue-600 px-4 py-2 text-white" type="submit">
        开始分析
      </button>
    </form>
  );
}
```

```tsx
// web/components/kpi-grid.tsx
export function KpiGrid({ items }: { items: Array<{ label: string; value: string }> }) {
  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
      {items.map((item) => (
        <div key={item.label} className="rounded border p-4">
          <div className="text-sm text-slate-500">{item.label}</div>
          <div className="mt-1 text-xl font-semibold">{item.value}</div>
        </div>
      ))}
    </div>
  );
}
```

```tsx
// web/components/chart-list.tsx
export function ChartList({ charts }: { charts: Array<{ key: string; url: string }> }) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {charts.map((chart) => (
        <div key={chart.key} className="rounded border p-4">
          <div className="mb-2 text-sm font-medium">{chart.key}</div>
          <img alt={chart.key} src={chart.url} />
        </div>
      ))}
    </div>
  );
}
```

```ts
// web/lib/api.ts
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function createJob(file: File): Promise<{ job_id: string }> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE_URL}/api/v1/jobs`, { method: "POST", body: formData });
  return response.json();
}

export async function getJob(jobId: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/api/v1/jobs/${jobId}`, { cache: "no-store" });
  return response.json();
}

export async function renderJob(jobId: string): Promise<{ report_id: string; download_path: string }> {
  const response = await fetch(`${API_BASE_URL}/api/v1/jobs/${jobId}/render`, { method: "POST" });
  return response.json();
}
```

```tsx
// web/app/layout.tsx
import "./globals.css";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="bg-slate-50 text-slate-900">{children}</body>
    </html>
  );
}
```

```tsx
// web/app/page.tsx
"use client";

import { useRouter } from "next/navigation";

import { UploadForm } from "@/components/upload-form";
import { createJob } from "@/lib/api";

export default function HomePage() {
  const router = useRouter();

  return (
    <main className="mx-auto max-w-5xl p-8">
      <h1 className="mb-2 text-3xl font-bold">DeepExcel SPC Demo</h1>
      <p className="mb-6 text-slate-600">上传检测数据，自动生成带 SPC 图表和 AI 结论的 Excel 报告。</p>
      <UploadForm
        onSubmit={async (file) => {
          const payload = await createJob(file);
          router.push(`/analysis/${payload.job_id}`);
        }}
      />
    </main>
  );
}
```

```tsx
// web/app/analysis/[jobId]/page.tsx
import Link from "next/link";

import { ChartList } from "@/components/chart-list";
import { KpiGrid } from "@/components/kpi-grid";
import { getJob, renderJob } from "@/lib/api";

export default async function AnalysisPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await params;
  const job = await getJob(jobId);
  const kpis = job.report_spec.kpi_cards;
  const charts = Object.entries(job.chart_paths).map(([key, url]) => ({ key, url: `${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000"}/${url}` }));
  const report = await renderJob(jobId);

  return (
    <main className="mx-auto max-w-6xl space-y-6 p-8">
      <h1 className="text-2xl font-bold">分析结果</h1>
      <div className="rounded border bg-white p-4">
        <div>模板推荐：{job.template_id}</div>
        <div>摘要：{job.report_spec.ai_narrative.executive_summary}</div>
      </div>
      <KpiGrid items={kpis} />
      <ChartList charts={charts} />
      <Link className="inline-block rounded bg-slate-900 px-4 py-2 text-white" href={`/report/${report.report_id}?file=${encodeURIComponent(report.download_path.split("/").pop())}`}>
        查看报告下载页
      </Link>
    </main>
  );
}
```

```tsx
// web/app/report/[reportId]/page.tsx
export default async function ReportPage({ params, searchParams }: { params: Promise<{ reportId: string }>; searchParams: Promise<{ file?: string }> }) {
  const { reportId } = await params;
  const { file } = await searchParams;
  const downloadUrl = `${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000"}/api/v1/reports/${file}`;

  return (
    <main className="mx-auto max-w-4xl space-y-4 p-8">
      <h1 className="text-2xl font-bold">报告已生成</h1>
      <div>报告编号：{reportId}</div>
      <a className="inline-block rounded bg-blue-600 px-4 py-2 text-white" href={downloadUrl}>
        下载 Excel 报告
      </a>
    </main>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
cd web
npm test -- upload-form.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/package.json web/tsconfig.json web/next.config.mjs web/jest.config.mjs web/jest.setup.ts web/app/layout.tsx web/app/page.tsx web/app/analysis/[jobId]/page.tsx web/app/report/[reportId]/page.tsx web/components/upload-form.tsx web/components/kpi-grid.tsx web/components/chart-list.tsx web/lib/api.ts web/tests/upload-form.test.tsx
git commit -m "feat: add web upload and report flow"
```
### Task 7: Add demo datasets, end-to-end smoke coverage, and runbook docs

**Files:**
- Create: `sample_data/normal_batch.csv`
- Create: `sample_data/shifted_mean_batch.csv`
- Create: `sample_data/out_of_spec_batch.csv`
- Create: `sample_data/high_variation_batch.csv`
- Create: `api/tests/test_demo_pipeline.py`
- Create: `README.md`

- [ ] **Step 1: Write the failing test**

```python
# api/tests/test_demo_pipeline.py
from pathlib import Path

from api.app.services.jobs import analyze_uploaded_file, render_job_report



def test_demo_pipeline_from_sample_data() -> None:
    sample_path = Path("sample_data/out_of_spec_batch.csv")

    job_payload = analyze_uploaded_file(sample_path)
    render_payload = render_job_report(job_payload["job_id"])

    assert job_payload["template_id"] == "template_a_overview"
    assert Path(render_payload["download_path"]).exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python -m pytest api/tests/test_demo_pipeline.py -v
```

Expected: FAIL because the sample data files do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```csv
# sample_data/normal_batch.csv
sample_id,batch_id,measured_at,value,lsl,usl
N-001,NORMAL,2026-04-21 08:00:00,10.002,9.950,10.050
N-002,NORMAL,2026-04-21 08:01:00,10.008,9.950,10.050
N-003,NORMAL,2026-04-21 08:02:00,10.011,9.950,10.050
N-004,NORMAL,2026-04-21 08:03:00,10.006,9.950,10.050
N-005,NORMAL,2026-04-21 08:04:00,10.003,9.950,10.050
```

```csv
# sample_data/shifted_mean_batch.csv
sample_id,batch_id,measured_at,value,lsl,usl
S-001,SHIFTED,2026-04-21 09:00:00,10.030,9.950,10.050
S-002,SHIFTED,2026-04-21 09:01:00,10.034,9.950,10.050
S-003,SHIFTED,2026-04-21 09:02:00,10.038,9.950,10.050
S-004,SHIFTED,2026-04-21 09:03:00,10.041,9.950,10.050
S-005,SHIFTED,2026-04-21 09:04:00,10.044,9.950,10.050
```

```csv
# sample_data/out_of_spec_batch.csv
sample_id,batch_id,measured_at,value,lsl,usl
O-001,OUTSPEC,2026-04-21 10:00:00,10.010,9.950,10.050
O-002,OUTSPEC,2026-04-21 10:01:00,10.025,9.950,10.050
O-003,OUTSPEC,2026-04-21 10:02:00,10.061,9.950,10.050
O-004,OUTSPEC,2026-04-21 10:03:00,10.018,9.950,10.050
O-005,OUTSPEC,2026-04-21 10:04:00,10.052,9.950,10.050
```

```csv
# sample_data/high_variation_batch.csv
sample_id,batch_id,measured_at,value,lsl,usl
V-001,VARIATION,2026-04-21 11:00:00,10.001,9.950,10.050
V-002,VARIATION,2026-04-21 11:01:00,9.982,9.950,10.050
V-003,VARIATION,2026-04-21 11:02:00,10.036,9.950,10.050
V-004,VARIATION,2026-04-21 11:03:00,9.971,9.950,10.050
V-005,VARIATION,2026-04-21 11:04:00,10.047,9.950,10.050
```

```markdown
# README.md

## DeepExcel Demo

本项目是一个本地运行的质检报告 Demo：上传 `csv/xlsx` 检测数据，自动完成字段识别、SPC 分析、图表生成、AI 结论生成，并导出带模板的 Excel 报告。

## Back end

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r api/requirements-dev.txt
.\.venv\Scripts\uvicorn api.app.main:app --reload --port 8000
```

## Front end

```powershell
cd web
npm install
$env:NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8000"
npm run dev
```

## Demo flow

1. 打开 `http://127.0.0.1:3000`
2. 上传 `sample_data/out_of_spec_batch.csv`
3. 查看分析页中的 KPI、图表和 AI 摘要
4. 进入报告下载页并下载 Excel

## Test commands

```powershell
.\.venv\Scripts\python -m pytest api/tests -v
cd web
npm test
```
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
.\.venv\Scripts\python -m pytest api/tests/test_demo_pipeline.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sample_data/normal_batch.csv sample_data/shifted_mean_batch.csv sample_data/out_of_spec_batch.csv sample_data/high_variation_batch.csv api/tests/test_demo_pipeline.py README.md
git commit -m "feat: add demo datasets and runbook"
```


