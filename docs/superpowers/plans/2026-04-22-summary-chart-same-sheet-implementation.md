# Summary-Sheet Chart Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make exported Excel reports place the narrative summary on the left side of the `Summary` sheet and automatically arrange 1–4 chart images on the right side of that same sheet.

**Architecture:** Keep the existing analysis pipeline and PNG chart generation intact. Move layout decisions into `template_manifest.json` via a new `chart_layout` block, then teach `render_report()` to read that configuration and place chart titles and images on the `Summary` sheet, while preserving the current `Charts` sheet behavior as a fallback when a template has no layout config.

**Tech Stack:** Python 3.11, `openpyxl`, `pytest`, existing JSON template manifests under `templates/`

---

## File Structure

- `api/app/services/excel.py` — owns Excel rendering, chart ordering, summary-sheet placement, and fallback `Charts` sheet behavior.
- `api/tests/test_excel_renderer.py` — owns renderer regression tests for text slots, same-sheet chart layout, and fallback behavior.
- `templates/template_a_overview/template_manifest.json` — demo template A slot configuration plus right-side chart layout anchors.
- `templates/template_b_detailed/template_manifest.json` — demo template B slot configuration plus right-side chart layout anchors.
- `templates/template_c_showcase/template_manifest.json` — demo template C slot configuration plus right-side chart layout anchors.
- `README.md` — documents that downloaded Excel now shows the summary and charts together on the `Summary` sheet.

---

### Task 1: Add manifest-driven same-sheet chart placement in the renderer

**Files:**
- Modify: `api/tests/test_excel_renderer.py:1-123`
- Modify: `api/app/services/excel.py:12-104`

- [ ] **Step 1: Write the failing tests**

Add `json` and `pytest` imports, then replace the current chart-sheet-specific regression with the helpers and tests below in `api/tests/test_excel_renderer.py`.

```python
import json
from pathlib import Path

import openpyxl
import pandas as pd
import pytest

from api.app.report_models import (
    ChartSpec,
    KpiCard,
    NarrativeBlock,
    ReportMeta,
    ReportSpec,
    TemplateDecision,
)
from api.app.services.analytics import compute_analysis
from api.app.services.charts import generate_chart_bundle
from api.app.services.excel import render_report


def _build_report_spec(template_id: str, chart_ids: list[str]) -> ReportSpec:
    return ReportSpec(
        report_meta=ReportMeta(
            title="Bearing Inspection SPC Report",
            report_id="RPT-002",
            generated_at="2026-04-21T10:00:00Z",
            batch_id="B-02",
            product_name="6205 Bearing",
        ),
        template_decision=TemplateDecision(
            template_id=template_id,
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
        chart_specs=[
            ChartSpec(chart_id=chart_id, chart_type=chart_id, title=chart_id.replace("_", " ").title())
            for chart_id in chart_ids
        ],
        anomalies=[{"severity": "high", "summary": "1 point exceeds spec"}],
        ai_narrative=NarrativeBlock(
            executive_summary="Process center is drifting upward.",
            quality_risk="Capability is marginal.",
            recommended_actions=["Check machine drift", "Review last setup change"],
        ),
    )


def _build_chart_paths(tmp_path: Path, chart_count: int) -> dict[str, str]:
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
    selected_chart_ids = list(chart_paths.keys())[:chart_count]
    return {chart_id: chart_paths[chart_id] for chart_id in selected_chart_ids}


def _write_template_manifest(tmp_path: Path, include_chart_layout: bool) -> Path:
    templates_root = tmp_path / "templates"
    template_dir = templates_root / "test_template"
    template_dir.mkdir(parents=True)

    manifest: dict[str, object] = {
        "template_id": "test_template",
        "workbook_name": "test_template.xlsx",
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
            "detail_start_row": 2,
        },
    }
    if include_chart_layout:
        manifest["chart_layout"] = {
            "sheet": "Summary",
            "area_title_cell": "H1",
            "area_title_text": "Charts Overview",
            "layouts": {
                "1": [
                    {"title_cell": "H2", "image_cell": "H3", "width": 640, "height": 360}
                ],
                "2": [
                    {"title_cell": "H2", "image_cell": "H3", "width": 640, "height": 170},
                    {"title_cell": "H21", "image_cell": "H22", "width": 640, "height": 170},
                ],
                "3": [
                    {"title_cell": "H2", "image_cell": "H3", "width": 300, "height": 170},
                    {"title_cell": "N2", "image_cell": "N3", "width": 300, "height": 170},
                    {"title_cell": "K21", "image_cell": "K22", "width": 420, "height": 170},
                ],
                "4": [
                    {"title_cell": "H2", "image_cell": "H3", "width": 300, "height": 170},
                    {"title_cell": "N2", "image_cell": "N3", "width": 300, "height": 170},
                    {"title_cell": "H21", "image_cell": "H22", "width": 300, "height": 170},
                    {"title_cell": "N21", "image_cell": "N22", "width": 300, "height": 170},
                ],
            },
        }

    (template_dir / "template_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    return templates_root


@pytest.mark.parametrize(
    ("chart_count", "expected_title_cells"),
    [
        (1, ["H2"]),
        (2, ["H2", "H21"]),
        (3, ["H2", "N2", "K21"]),
        (4, ["H2", "N2", "H21", "N21"]),
    ],
)
def test_render_report_places_chart_images_on_summary_sheet(
    tmp_path: Path,
    chart_count: int,
    expected_title_cells: list[str],
) -> None:
    templates_root = _write_template_manifest(tmp_path, include_chart_layout=True)
    chart_paths = _build_chart_paths(tmp_path / f"charts-{chart_count}", chart_count)
    report_file = render_report(
        report_spec=_build_report_spec("test_template", list(chart_paths.keys())),
        chart_paths=chart_paths,
        templates_root=templates_root,
        output_path=tmp_path / f"summary-layout-{chart_count}.xlsx",
    )

    workbook = openpyxl.load_workbook(report_file)
    summary_sheet = workbook["Summary"]

    assert "Charts" not in workbook.sheetnames
    assert len(getattr(summary_sheet, "_images", [])) == chart_count
    for title_cell, chart_id in zip(expected_title_cells, chart_paths):
        assert summary_sheet[title_cell].value == chart_id.replace("_", " ").title()


def test_render_report_falls_back_to_charts_sheet_without_layout(tmp_path: Path) -> None:
    templates_root = _write_template_manifest(tmp_path, include_chart_layout=False)
    chart_paths = _build_chart_paths(tmp_path / "charts-fallback", 4)
    report_file = render_report(
        report_spec=_build_report_spec("test_template", list(chart_paths.keys())),
        chart_paths=chart_paths,
        templates_root=templates_root,
        output_path=tmp_path / "fallback-layout.xlsx",
    )

    workbook = openpyxl.load_workbook(report_file)

    assert "Charts" in workbook.sheetnames
    assert len(getattr(workbook["Summary"], "_images", [])) == 0
    assert len(getattr(workbook["Charts"], "_images", [])) == len(chart_paths)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
.\.venv311\Scripts\python.exe -m pytest api/tests/test_excel_renderer.py::test_render_report_places_chart_images_on_summary_sheet api/tests/test_excel_renderer.py::test_render_report_falls_back_to_charts_sheet_without_layout -v
```

Expected:

- `test_render_report_places_chart_images_on_summary_sheet` fails with an assertion like `assert "Charts" not in workbook.sheetnames`
- `test_render_report_falls_back_to_charts_sheet_without_layout` passes or remains green
- Overall command exits non-zero because the new same-sheet behavior is not implemented yet

- [ ] **Step 3: Write the minimal implementation**

Replace the current chart embedding helpers in `api/app/services/excel.py` with the code below, then update the `render_report()` call site to pass `manifest` and `summary_sheet`.

```python
def _iter_chart_images(report_spec: ReportSpec, chart_paths: dict[str, str]) -> list[tuple[str, str]]:
    ordered_charts: list[tuple[str, str]] = []
    seen_chart_ids: set[str] = set()

    for chart_spec in report_spec.chart_specs:
        chart_path = chart_paths.get(chart_spec.chart_id)
        if chart_path is None:
            continue
        ordered_charts.append((chart_spec.title, chart_path))
        seen_chart_ids.add(chart_spec.chart_id)

    for chart_id, chart_path in chart_paths.items():
        if chart_id in seen_chart_ids:
            continue
        ordered_charts.append((chart_id.replace("_", " ").title(), chart_path))

    return ordered_charts[:4]


def _embed_chart_images_on_charts_sheet(
    workbook: openpyxl.Workbook,
    chart_images: list[tuple[str, str]],
) -> None:
    if "Charts" in workbook.sheetnames:
        workbook.remove(workbook["Charts"])

    chart_sheet = workbook.create_sheet(title="Charts")
    chart_sheet["A1"] = "Generated Charts"

    for offset, (title, chart_path) in enumerate(chart_images):
        title_row = 3 + (offset * 24)
        image_row = title_row + 1
        chart_sheet[f"A{title_row}"] = title
        chart_sheet.add_image(Image(chart_path), f"A{image_row}")


def _embed_chart_images_on_summary_sheet(
    workbook: openpyxl.Workbook,
    summary_sheet: openpyxl.worksheet.worksheet.Worksheet,
    chart_images: list[tuple[str, str]],
    chart_layout: dict[str, object],
) -> bool:
    layouts = chart_layout.get("layouts")
    if not isinstance(layouts, dict):
        return False

    placements = layouts.get(str(len(chart_images)))
    if not isinstance(placements, list) or len(placements) < len(chart_images):
        return False

    layout_sheet_name = str(chart_layout.get("sheet", summary_sheet.title))
    if layout_sheet_name not in workbook.sheetnames:
        return False

    target_sheet = workbook[layout_sheet_name]
    target_sheet[str(chart_layout.get("area_title_cell", "H1"))] = str(
        chart_layout.get("area_title_text", "Charts Overview")
    )

    for (title, chart_path), placement in zip(chart_images, placements):
        if not isinstance(placement, dict):
            return False
        image = Image(chart_path)
        image.width = int(placement["width"])
        image.height = int(placement["height"])
        target_sheet[str(placement["title_cell"])] = title
        target_sheet.add_image(image, str(placement["image_cell"]))

    if "Charts" in workbook.sheetnames:
        workbook.remove(workbook["Charts"])
    return True


def _embed_chart_images(
    workbook: openpyxl.Workbook,
    summary_sheet: openpyxl.worksheet.worksheet.Worksheet,
    report_spec: ReportSpec,
    chart_paths: dict[str, str],
    manifest: dict[str, object],
) -> None:
    chart_images = _iter_chart_images(report_spec, chart_paths)
    if not chart_images:
        return

    chart_layout = manifest.get("chart_layout")
    if isinstance(chart_layout, dict) and _embed_chart_images_on_summary_sheet(
        workbook=workbook,
        summary_sheet=summary_sheet,
        chart_images=chart_images,
        chart_layout=chart_layout,
    ):
        return

    _embed_chart_images_on_charts_sheet(workbook, chart_images)


def render_report(
    report_spec: ReportSpec,
    chart_paths: dict[str, str],
    templates_root: Path,
    output_path: Path,
) -> Path:
    template_id = report_spec.template_decision.template_id
    workbook_path = ensure_demo_template_workbook(templates_root, template_id)
    manifest = load_template_manifest(templates_root, template_id)
    workbook = openpyxl.load_workbook(workbook_path)
    summary_sheet = workbook[str(manifest["summary_sheet"])]
    detail_sheet = workbook[str(manifest["detail_sheet"])]
    slots = manifest["slots"]

    summary_sheet[str(slots["title_cell"])] = report_spec.report_meta.title
    summary_sheet[str(slots["product_cell"])] = report_spec.report_meta.product_name
    summary_sheet[str(slots["batch_cell"])] = report_spec.report_meta.batch_id
    summary_sheet[str(slots["reason_cell"])] = report_spec.template_decision.reason

    kpi_cell = summary_sheet[str(slots["kpi_start_cell"])]
    start_row = kpi_cell.row
    start_col = kpi_cell.column
    for offset, card in enumerate(report_spec.kpi_cards):
        summary_sheet.cell(row=start_row + offset, column=start_col, value=card.label)
        summary_sheet.cell(row=start_row + offset, column=start_col + 1, value=card.value)

    summary_sheet[str(slots["narrative_summary_cell"])] = report_spec.ai_narrative.executive_summary
    summary_sheet[str(slots["narrative_risk_cell"])] = report_spec.ai_narrative.quality_risk
    action_row = summary_sheet[str(slots["actions_start_cell"])].row
    action_col = summary_sheet[str(slots["actions_start_cell"])].column
    for offset, action in enumerate(report_spec.ai_narrative.recommended_actions):
        summary_sheet.cell(row=action_row + offset, column=action_col, value=f"- {action}")

    detail_start_row = int(slots["detail_start_row"])
    for row_offset, detail_row in enumerate(report_spec.detail_rows):
        detail_sheet.cell(row=detail_start_row + row_offset, column=1, value=detail_row.get("sample_id"))
        detail_sheet.cell(row=detail_start_row + row_offset, column=2, value=detail_row.get("measurement_value"))
        detail_sheet.cell(row=detail_start_row + row_offset, column=3, value=detail_row.get("status"))

    _embed_chart_images(
        workbook=workbook,
        summary_sheet=summary_sheet,
        report_spec=report_spec,
        chart_paths=chart_paths,
        manifest=manifest,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)
    return output_path
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```powershell
.\.venv311\Scripts\python.exe -m pytest api/tests/test_excel_renderer.py::test_render_report_places_chart_images_on_summary_sheet api/tests/test_excel_renderer.py::test_render_report_falls_back_to_charts_sheet_without_layout -v
```

Expected:

- Both tests pass
- `test_render_report_populates_template` still remains green when run later in Task 3

- [ ] **Step 5: Checkpoint the change**

If this directory has been turned into a Git repository before execution, run:

```bash
git add api/app/services/excel.py api/tests/test_excel_renderer.py
git commit -m "feat: support summary sheet chart layouts"
```

If there is still no `.git` directory, skip the commit and move directly to Task 2.

---

### Task 2: Configure the demo templates for left-summary / right-chart layouts

**Files:**
- Modify: `api/tests/test_excel_renderer.py:68-123`
- Modify: `templates/template_a_overview/template_manifest.json:1-17`
- Modify: `templates/template_b_detailed/template_manifest.json:1-17`
- Modify: `templates/template_c_showcase/template_manifest.json:1-17`

- [ ] **Step 1: Write the failing tests for the real demo templates**

Append the tests below to `api/tests/test_excel_renderer.py`.

```python
from api.app.services.templates import load_template_manifest


def test_demo_template_manifests_define_summary_chart_layout() -> None:
    expected_title_cells = {
        "template_a_overview": "H1",
        "template_b_detailed": "J1",
        "template_c_showcase": "J2",
    }
    for template_id, title_cell in expected_title_cells.items():
        manifest = load_template_manifest(Path("templates"), template_id)
        chart_layout = manifest["chart_layout"]
        assert chart_layout["sheet"] == "Summary"
        assert chart_layout["area_title_cell"] == title_cell
        assert set(chart_layout["layouts"].keys()) == {"1", "2", "3", "4"}


def test_render_report_places_generated_charts_on_demo_summary_sheet(tmp_path: Path) -> None:
    chart_paths = _build_chart_paths(tmp_path / "charts-demo", 4)
    report_file = render_report(
        report_spec=_build_report_spec("template_a_overview", list(chart_paths.keys())),
        chart_paths=chart_paths,
        templates_root=Path("templates"),
        output_path=tmp_path / "demo-summary-layout.xlsx",
    )

    workbook = openpyxl.load_workbook(report_file)
    summary_sheet = workbook["Summary"]

    assert "Charts" not in workbook.sheetnames
    assert len(getattr(summary_sheet, "_images", [])) == 4
    assert summary_sheet["H2"].value == "Histogram"
    assert summary_sheet["N2"].value == "Control Chart Imr"
    assert summary_sheet["H21"].value == "Trend Line"
    assert summary_sheet["N21"].value == "Spec Comparison"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
.\.venv311\Scripts\python.exe -m pytest api/tests/test_excel_renderer.py::test_demo_template_manifests_define_summary_chart_layout api/tests/test_excel_renderer.py::test_render_report_places_generated_charts_on_demo_summary_sheet -v
```

Expected:

- `test_demo_template_manifests_define_summary_chart_layout` fails with `KeyError: 'chart_layout'`
- `test_render_report_places_generated_charts_on_demo_summary_sheet` fails because the renderer still falls back to a `Charts` sheet for the current demo manifests

- [ ] **Step 3: Write the minimal template manifest changes**

Replace each demo manifest file with the JSON below.

`templates/template_a_overview/template_manifest.json`

```json
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
  },
  "chart_layout": {
    "sheet": "Summary",
    "area_title_cell": "H1",
    "area_title_text": "Charts Overview",
    "layouts": {
      "1": [
        { "title_cell": "H2", "image_cell": "H3", "width": 640, "height": 360 }
      ],
      "2": [
        { "title_cell": "H2", "image_cell": "H3", "width": 640, "height": 170 },
        { "title_cell": "H21", "image_cell": "H22", "width": 640, "height": 170 }
      ],
      "3": [
        { "title_cell": "H2", "image_cell": "H3", "width": 300, "height": 170 },
        { "title_cell": "N2", "image_cell": "N3", "width": 300, "height": 170 },
        { "title_cell": "K21", "image_cell": "K22", "width": 420, "height": 170 }
      ],
      "4": [
        { "title_cell": "H2", "image_cell": "H3", "width": 300, "height": 170 },
        { "title_cell": "N2", "image_cell": "N3", "width": 300, "height": 170 },
        { "title_cell": "H21", "image_cell": "H22", "width": 300, "height": 170 },
        { "title_cell": "N21", "image_cell": "N22", "width": 300, "height": 170 }
      ]
    }
  }
}
```

`templates/template_b_detailed/template_manifest.json`

```json
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
  },
  "chart_layout": {
    "sheet": "Summary",
    "area_title_cell": "J1",
    "area_title_text": "Charts Overview",
    "layouts": {
      "1": [
        { "title_cell": "J2", "image_cell": "J3", "width": 640, "height": 360 }
      ],
      "2": [
        { "title_cell": "J2", "image_cell": "J3", "width": 640, "height": 170 },
        { "title_cell": "J21", "image_cell": "J22", "width": 640, "height": 170 }
      ],
      "3": [
        { "title_cell": "J2", "image_cell": "J3", "width": 300, "height": 170 },
        { "title_cell": "P2", "image_cell": "P3", "width": 300, "height": 170 },
        { "title_cell": "M21", "image_cell": "M22", "width": 420, "height": 170 }
      ],
      "4": [
        { "title_cell": "J2", "image_cell": "J3", "width": 300, "height": 170 },
        { "title_cell": "P2", "image_cell": "P3", "width": 300, "height": 170 },
        { "title_cell": "J21", "image_cell": "J22", "width": 300, "height": 170 },
        { "title_cell": "P21", "image_cell": "P22", "width": 300, "height": 170 }
      ]
    }
  }
}
```

`templates/template_c_showcase/template_manifest.json`

```json
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
  },
  "chart_layout": {
    "sheet": "Summary",
    "area_title_cell": "J2",
    "area_title_text": "Charts Overview",
    "layouts": {
      "1": [
        { "title_cell": "J3", "image_cell": "J4", "width": 640, "height": 360 }
      ],
      "2": [
        { "title_cell": "J3", "image_cell": "J4", "width": 640, "height": 170 },
        { "title_cell": "J22", "image_cell": "J23", "width": 640, "height": 170 }
      ],
      "3": [
        { "title_cell": "J3", "image_cell": "J4", "width": 300, "height": 170 },
        { "title_cell": "P3", "image_cell": "P4", "width": 300, "height": 170 },
        { "title_cell": "M22", "image_cell": "M23", "width": 420, "height": 170 }
      ],
      "4": [
        { "title_cell": "J3", "image_cell": "J4", "width": 300, "height": 170 },
        { "title_cell": "P3", "image_cell": "P4", "width": 300, "height": 170 },
        { "title_cell": "J22", "image_cell": "J23", "width": 300, "height": 170 },
        { "title_cell": "P22", "image_cell": "P23", "width": 300, "height": 170 }
      ]
    }
  }
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```powershell
.\.venv311\Scripts\python.exe -m pytest api/tests/test_excel_renderer.py::test_demo_template_manifests_define_summary_chart_layout api/tests/test_excel_renderer.py::test_render_report_places_generated_charts_on_demo_summary_sheet -v
```

Expected:

- Both tests pass
- The real `template_a_overview` render now embeds four images directly on the `Summary` sheet

- [ ] **Step 5: Checkpoint the change**

If this directory has been turned into a Git repository before execution, run:

```bash
git add api/tests/test_excel_renderer.py templates/template_a_overview/template_manifest.json templates/template_b_detailed/template_manifest.json templates/template_c_showcase/template_manifest.json
git commit -m "feat: configure summary sheet chart layouts"
```

If there is still no `.git` directory, skip the commit and move directly to Task 3.

---

### Task 3: Update docs and run the end-to-end export verification

**Files:**
- Modify: `README.md:37-42`
- Test: `api/tests/test_excel_renderer.py`
- Test: `api/tests/test_charts.py`
- Test: `api/tests/test_demo_pipeline.py`
- Test: `api/tests/test_jobs_api.py`

- [ ] **Step 1: Update the README demo flow to describe the new Excel layout**

Edit the `Demo flow` section in `README.md` so step 4 reads exactly as follows.

```markdown
4. 进入报告下载页并下载 Excel，`Summary` 页左侧展示总结，右侧根据实际图数自动排版 1~4 张图表
```

- [ ] **Step 2: Re-run the focused Excel renderer tests**

Run:

```powershell
.\.venv311\Scripts\python.exe -m pytest api/tests/test_excel_renderer.py -q
```

Expected:

- All tests in `api/tests/test_excel_renderer.py` pass
- Output ends with `passed`

- [ ] **Step 3: Run the broader export regression tests**

Run:

```powershell
.\.venv311\Scripts\python.exe -m pytest api/tests/test_charts.py api/tests/test_demo_pipeline.py api/tests/test_jobs_api.py -q
```

Expected:

- All three test modules pass
- Output ends with `3 passed` or the updated passing count if test totals change slightly

- [ ] **Step 4: Verify a real exported workbook contains summary-sheet images**

Run:

```powershell
.\.venv311\Scripts\python.exe -c "from pathlib import Path; import openpyxl; from api.app.services.jobs import analyze_uploaded_file, render_job_report; sample_path = Path('sample_data/out_of_spec_batch.csv'); job_payload = analyze_uploaded_file(sample_path); render_payload = render_job_report(job_payload['job_id']); workbook = openpyxl.load_workbook(render_payload['download_path']); summary_sheet = workbook['Summary']; print('sheetnames=', workbook.sheetnames); print('summary_image_count=', len(getattr(summary_sheet, '_images', []))); print('report=', render_payload['download_path'])"
```

Expected:

- `sheetnames=` includes `Summary` and `Details`
- `summary_image_count=` is between `1` and `4`
- No `Charts` sheet appears for demo templates that define `chart_layout`

- [ ] **Step 5: Checkpoint the final docs-and-verification change**

If this directory has been turned into a Git repository before execution, run:

```bash
git add README.md
git commit -m "docs: describe summary sheet chart layout"
```

If there is still no `.git` directory, stop after recording the verification output.

---

## Self-Review

### Spec coverage

- Same-sheet summary + charts requirement — covered by Task 1 implementation and Task 2 real-template configuration.
- Left-summary / right-chart layout — covered by the `chart_layout` anchors added in Task 2.
- Automatic 1–4 chart arrangement — covered by Task 1 parametrized tests and layout selection logic.
- Fallback behavior for templates without `chart_layout` — covered by Task 1 fallback test and implementation.
- Demo template support — covered by Task 2 manifest tests and manifest updates.
- Validation on real export output — covered by Task 3 end-to-end workbook inspection.

### Placeholder scan

- No `TODO`, `TBD`, “implement later”, or “similar to above” placeholders remain.
- Every task contains exact file paths, concrete code, and exact commands.

### Type consistency

- `chart_layout` is consistently treated as a nested manifest dictionary with `sheet`, `area_title_cell`, `area_title_text`, and `layouts` keys.
- Renderer helpers consistently pass `manifest`, `summary_sheet`, `chart_paths`, and `report_spec` together.
- Tests consistently build `ReportSpec` with `chart_specs` titles derived from chart ids via `replace("_", " ").title()`.
