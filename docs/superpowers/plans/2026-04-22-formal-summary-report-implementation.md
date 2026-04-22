# Formal SPC Summary Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the exported Excel `Summary` sheet into a formal industrial SPC cover page that keeps KPI-first summary content on the left and 1-4 charts on the right.

**Architecture:** Keep the current data-writing and same-sheet chart embedding flow in `api/app/services/excel.py`, add a manifest-driven styling helper in `api/app/services/excel_styles.py`, and extend template manifests with a `formal_layout` block that defines title band, metadata labels, section bands, and chart framing. The renderer writes values first, embeds chart images second, then applies formal styling only when `formal_layout` exists so templates without the new metadata still render successfully.

**Tech Stack:** Python, `openpyxl`, `pytest`, JSON template manifests

---

### Task 1: Add failing tests for formal summary styling and fallback

**Files:**
- Modify: `api/tests/test_excel_renderer.py:71`
- Test: `api/tests/test_excel_renderer.py`

- [ ] **Step 1: Extend the synthetic manifest helper to emit `formal_layout`**

```python
def _write_template_manifest(
    tmp_path: Path,
    include_chart_layout: bool,
    include_formal_layout: bool = False,
) -> Path:
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
            "product_cell": "B3",
            "batch_cell": "B4",
            "reason_cell": "B5",
            "kpi_start_cell": "A8",
            "narrative_summary_cell": "A15",
            "narrative_risk_cell": "A21",
            "actions_start_cell": "A26",
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
    if include_formal_layout:
        manifest["formal_layout"] = {
            "column_widths": {
                "A": 16,
                "B": 18,
                "C": 14,
                "D": 2.5,
                "H": 18,
                "I": 18,
                "J": 18,
                "K": 18,
                "L": 18,
                "M": 18,
                "N": 18,
                "O": 18,
                "P": 18,
                "Q": 18
            },
            "title_band": {"range": "A1:D1"},
            "metadata_rows": [
                {"label_cell": "A3", "value_cell": "B3", "label": "Product"},
                {"label_cell": "A4", "value_cell": "B4", "label": "Batch"},
                {"label_cell": "A5", "value_cell": "B5", "label": "Basis"}
            ],
            "sections": {
                "kpi": {
                    "header_cell": "A7",
                    "header_text": "Key Metrics",
                    "body_range": "A8:B12",
                    "kind": "kpi"
                },
                "summary": {
                    "header_cell": "A14",
                    "header_text": "Conclusion",
                    "body_range": "A15:D18",
                    "kind": "text"
                },
                "risk": {
                    "header_cell": "A20",
                    "header_text": "Risk",
                    "body_range": "A21:D23",
                    "kind": "text"
                },
                "actions": {
                    "header_cell": "A25",
                    "header_text": "Actions",
                    "body_range": "A26:D29",
                    "kind": "actions"
                }
            },
            "chart_board": {
                "title_cell": "H1",
                "title_text": "SPC Chart Overview",
                "frames": {
                    "1": ["H2:Q20"],
                    "2": ["H2:Q19", "H21:Q38"],
                    "3": ["H2:M19", "N2:Q19", "K21:P38"],
                    "4": ["H2:M19", "N2:Q19", "H21:M38", "N21:Q38"]
                }
            }
        }

    (template_dir / "template_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    return templates_root
```

- [ ] **Step 2: Add a failing test that locks the formal report styling contract**

```python
def test_render_report_applies_formal_summary_style_on_summary_sheet(tmp_path: Path) -> None:
    templates_root = _write_template_manifest(
        tmp_path,
        include_chart_layout=True,
        include_formal_layout=True,
    )
    chart_paths = _build_chart_paths(tmp_path / "charts-formal", 4)
    report_file = render_report(
        report_spec=_build_report_spec("test_template", list(chart_paths.keys())),
        chart_paths=chart_paths,
        templates_root=templates_root,
        output_path=tmp_path / "formal-summary.xlsx",
    )

    workbook = openpyxl.load_workbook(report_file)
    summary_sheet = workbook["Summary"]
    merged_ranges = {str(cell_range) for cell_range in summary_sheet.merged_cells.ranges}

    assert "A1:D1" in merged_ranges
    assert summary_sheet["A1"].fill.fgColor.rgb == "FF1F2937"
    assert summary_sheet["A1"].font.bold is True
    assert summary_sheet["A3"].value == "Product"
    assert summary_sheet["B3"].value == "6205 Bearing"
    assert summary_sheet["A7"].value == "Key Metrics"
    assert summary_sheet["A8"].border.left.style == "thin"
    assert summary_sheet["B8"].font.bold is True
    assert summary_sheet["A14"].value == "Conclusion"
    assert summary_sheet["A15"].value == "Process center is drifting upward."
    assert summary_sheet["A20"].value == "Risk"
    assert summary_sheet["A21"].value == "Capability is marginal."
    assert summary_sheet["A25"].value == "Actions"
    assert summary_sheet["A26"].value == "- Check machine drift"
    assert summary_sheet["H1"].value == "SPC Chart Overview"
    assert summary_sheet["H2"].font.bold is True
    assert summary_sheet["H2"].border.top.style == "thin"
```

- [ ] **Step 3: Add a failing fallback test for templates without `formal_layout`**

```python
def test_render_report_keeps_plain_summary_when_formal_layout_is_missing(tmp_path: Path) -> None:
    templates_root = _write_template_manifest(
        tmp_path,
        include_chart_layout=True,
        include_formal_layout=False,
    )
    chart_paths = _build_chart_paths(tmp_path / "charts-no-formal", 2)
    report_file = render_report(
        report_spec=_build_report_spec("test_template", list(chart_paths.keys())),
        chart_paths=chart_paths,
        templates_root=templates_root,
        output_path=tmp_path / "plain-summary.xlsx",
    )

    workbook = openpyxl.load_workbook(report_file)
    summary_sheet = workbook["Summary"]

    assert "A1:D1" not in {str(cell_range) for cell_range in summary_sheet.merged_cells.ranges}
    assert summary_sheet["A1"].fill.patternType is None
    assert summary_sheet["A8"].value == "Mean"
    assert summary_sheet["H1"].value == "Charts Overview"
    assert summary_sheet["H1"].fill.patternType is None
```

- [ ] **Step 4: Run the focused renderer tests and confirm they fail for the new assertions**

Run: `./.venv311/Scripts/python.exe -m pytest api/tests/test_excel_renderer.py -q`
Expected: FAIL with the new formal-layout assertions because `render_report()` does not style merged title bands, section headers, metadata labels, or chart frames yet.

- [ ] **Step 5: Skip the Git commit in this workspace**

Run: `if (Test-Path .git) { git add api/tests/test_excel_renderer.py; git commit -m "test: cover formal summary report styling" } else { "SKIP: no git repo in current workspace" }`
Expected: `SKIP: no git repo in current workspace`
### Task 2: Implement the manifest-driven styling helper and renderer integration

**Files:**
- Create: `api/app/services/excel_styles.py`
- Modify: `api/app/services/excel.py:109`
- Test: `api/tests/test_excel_renderer.py`

- [ ] **Step 1: Create `api/app/services/excel_styles.py` with explicit summary-sheet styling helpers**

```python
from __future__ import annotations

from collections.abc import Mapping

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils.cell import range_boundaries
from openpyxl.worksheet.worksheet import Worksheet

THIN_SIDE = Side(style="thin", color="FFCBD5E1")
BLOCK_BORDER = Border(left=THIN_SIDE, right=THIN_SIDE, top=THIN_SIDE, bottom=THIN_SIDE)
TITLE_FILL = PatternFill("solid", fgColor="FF1F2937")
SECTION_FILL = PatternFill("solid", fgColor="FF334155")
LABEL_FILL = PatternFill("solid", fgColor="FFF8FAFC")
CHART_TITLE_FILL = PatternFill("solid", fgColor="FFE2E8F0")


def apply_formal_summary_style(summary_sheet: Worksheet, manifest: dict[str, object]) -> None:
    formal_layout = manifest.get("formal_layout")
    if not isinstance(formal_layout, Mapping):
        return

    _apply_column_widths(summary_sheet, formal_layout.get("column_widths", {}))
    _style_title_band(summary_sheet, formal_layout.get("title_band", {}))
    _style_metadata_rows(summary_sheet, formal_layout.get("metadata_rows", []))

    sections = formal_layout.get("sections", {})
    if isinstance(sections, Mapping):
        for section in sections.values():
            _style_section(summary_sheet, section)

    _style_chart_board(summary_sheet, manifest, formal_layout.get("chart_board", {}))


def _apply_column_widths(summary_sheet: Worksheet, column_widths: object) -> None:
    if not isinstance(column_widths, Mapping):
        return
    for column_letter, width in column_widths.items():
        summary_sheet.column_dimensions[str(column_letter)].width = float(width)


def _style_title_band(summary_sheet: Worksheet, title_band: object) -> None:
    if not isinstance(title_band, Mapping):
        return
    cell_range = str(title_band["range"])
    summary_sheet.merge_cells(cell_range)
    anchor = summary_sheet[cell_range.split(":")[0]]
    anchor.fill = TITLE_FILL
    anchor.font = Font(size=16, bold=True, color="FFFFFFFF")
    anchor.alignment = Alignment(horizontal="left", vertical="center")
    _apply_border_to_range(summary_sheet, cell_range)


def _style_metadata_rows(summary_sheet: Worksheet, metadata_rows: object) -> None:
    if not isinstance(metadata_rows, list):
        return
    for row in metadata_rows:
        if not isinstance(row, Mapping):
            continue
        label_cell = summary_sheet[str(row["label_cell"])]
        value_cell = summary_sheet[str(row["value_cell"])]
        label_cell.value = str(row["label"])
        label_cell.font = Font(bold=True, color="FF0F172A")
        label_cell.fill = LABEL_FILL
        value_cell.border = BLOCK_BORDER
        label_cell.border = BLOCK_BORDER
        label_cell.alignment = Alignment(horizontal="left", vertical="center")
        value_cell.alignment = Alignment(horizontal="left", vertical="center")


def _style_section(summary_sheet: Worksheet, section: object) -> None:
    if not isinstance(section, Mapping):
        return

    header = summary_sheet[str(section["header_cell"])]
    header.value = str(section["header_text"])
    header.fill = SECTION_FILL
    header.font = Font(bold=True, color="FFFFFFFF")
    header.alignment = Alignment(horizontal="left", vertical="center")
    header.border = BLOCK_BORDER

    body_range = str(section["body_range"])
    _apply_border_to_range(summary_sheet, body_range)

    if str(section.get("kind")) == "kpi":
        min_col, min_row, max_col, max_row = range_boundaries(body_range)
        for row_index in range(min_row, max_row + 1):
            summary_sheet.cell(row=row_index, column=min_col).fill = LABEL_FILL
            summary_sheet.cell(row=row_index, column=min_col).alignment = Alignment(horizontal="left", vertical="center")
            summary_sheet.cell(row=row_index, column=max_col).font = Font(bold=True, color="FF0F172A")
            summary_sheet.cell(row=row_index, column=max_col).alignment = Alignment(horizontal="right", vertical="center")
    else:
        min_col, min_row, _, _ = range_boundaries(body_range)
        summary_sheet.cell(row=min_row, column=min_col).alignment = Alignment(wrap_text=True, vertical="top")


def _style_chart_board(summary_sheet: Worksheet, manifest: dict[str, object], chart_board: object) -> None:
    if not isinstance(chart_board, Mapping):
        return

    title_cell = str(chart_board.get("title_cell", "H1"))
    title = summary_sheet[title_cell]
    title.value = str(chart_board.get("title_text", title.value or "SPC Chart Overview"))
    title.fill = SECTION_FILL
    title.font = Font(size=12, bold=True, color="FFFFFFFF")
    title.alignment = Alignment(horizontal="center", vertical="center")
    title.border = BLOCK_BORDER

    chart_layout = manifest.get("chart_layout")
    chart_count = len(getattr(summary_sheet, "_images", []))
    if isinstance(chart_layout, Mapping):
        layouts = chart_layout.get("layouts", {})
        placements = layouts.get(str(chart_count), []) if isinstance(layouts, Mapping) else []
        for placement in placements:
            if not isinstance(placement, Mapping):
                continue
            chart_title = summary_sheet[str(placement["title_cell"])]
            chart_title.font = Font(bold=True, color="FF0F172A")
            chart_title.fill = CHART_TITLE_FILL
            chart_title.alignment = Alignment(horizontal="left", vertical="center")
            chart_title.border = BLOCK_BORDER

    frames = chart_board.get("frames", {})
    frame_ranges = frames.get(str(chart_count), []) if isinstance(frames, Mapping) else []
    for cell_range in frame_ranges:
        _apply_border_to_range(summary_sheet, str(cell_range))


def _apply_border_to_range(summary_sheet: Worksheet, cell_range: str) -> None:
    min_col, min_row, max_col, max_row = range_boundaries(cell_range)
    for row_index in range(min_row, max_row + 1):
        for column_index in range(min_col, max_col + 1):
            summary_sheet.cell(row=row_index, column=column_index).border = BLOCK_BORDER
```

- [ ] **Step 2: Import and call the styling helper from the renderer after chart embedding**

```python
from api.app.services.excel_styles import apply_formal_summary_style
from api.app.services.templates import ensure_demo_template_workbook, load_template_manifest


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
    apply_formal_summary_style(summary_sheet=summary_sheet, manifest=manifest)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)
    return output_path
```

- [ ] **Step 3: Style the chart board using the existing `chart_layout` title cells and the new `formal_layout.chart_board.frames`**

```python
def _style_chart_board(summary_sheet: Worksheet, manifest: dict[str, object], chart_board: object) -> None:
    if not isinstance(chart_board, Mapping):
        return

    title_cell = str(chart_board.get("title_cell", "H1"))
    title = summary_sheet[title_cell]
    title.value = str(chart_board.get("title_text", title.value or "SPC Chart Overview"))
    title.fill = SECTION_FILL
    title.font = Font(size=12, bold=True, color="FFFFFFFF")
    title.alignment = Alignment(horizontal="center", vertical="center")
    title.border = BLOCK_BORDER

    chart_layout = manifest.get("chart_layout")
    chart_count = len(getattr(summary_sheet, "_images", []))
    if isinstance(chart_layout, Mapping):
        layouts = chart_layout.get("layouts", {})
        placements = layouts.get(str(chart_count), []) if isinstance(layouts, Mapping) else []
        for placement in placements:
            if not isinstance(placement, Mapping):
                continue
            chart_title = summary_sheet[str(placement["title_cell"])]
            chart_title.font = Font(size=10, bold=True, color="FF0F172A")
            chart_title.fill = CHART_TITLE_FILL
            chart_title.alignment = Alignment(horizontal="left", vertical="center")
            chart_title.border = BLOCK_BORDER

    frames = chart_board.get("frames", {})
    frame_ranges = frames.get(str(chart_count), []) if isinstance(frames, Mapping) else []
    for frame_range in frame_ranges:
        _apply_border_to_range(summary_sheet, str(frame_range))
```

- [ ] **Step 4: Run the focused renderer tests and confirm the new style assertions pass**

Run: `./.venv311/Scripts/python.exe -m pytest api/tests/test_excel_renderer.py -q`
Expected: PASS with `10 passed` after the two new formal-layout tests are green.

- [ ] **Step 5: Skip the Git commit in this workspace**

Run: `if (Test-Path .git) { git add api/app/services/excel.py api/app/services/excel_styles.py api/tests/test_excel_renderer.py; git commit -m "feat: add formal summary sheet styling" } else { "SKIP: no git repo in current workspace" }`
Expected: `SKIP: no git repo in current workspace`

### Task 3: Update demo manifests, README, and run full verification

**Files:**
- Modify: `api/tests/test_excel_renderer.py:227`
- Modify: `templates/template_a_overview/template_manifest.json`
- Modify: `templates/template_b_detailed/template_manifest.json`
- Modify: `templates/template_c_showcase/template_manifest.json`
- Modify: `README.md`
- Test: `api/tests/test_excel_renderer.py`
- Test: `api/tests/test_charts.py`
- Test: `api/tests/test_demo_pipeline.py`
- Test: `api/tests/test_jobs_api.py`

- [ ] **Step 1: Add a manifest contract test for the three shipped templates**

```python
def test_demo_template_manifests_define_formal_summary_layout() -> None:
    expected_layout = {
        "template_a_overview": {
            "title_cell": "A1",
            "kpi_start_cell": "A8",
            "chart_title_cell": "H1",
        },
        "template_b_detailed": {
            "title_cell": "A1",
            "kpi_start_cell": "A8",
            "chart_title_cell": "J1",
        },
        "template_c_showcase": {
            "title_cell": "B2",
            "kpi_start_cell": "B9",
            "chart_title_cell": "J2",
        },
    }
    for template_id, expected in expected_layout.items():
        manifest = load_template_manifest(Path("templates"), template_id)
        formal_layout = manifest["formal_layout"]
        assert manifest["slots"]["title_cell"] == expected["title_cell"]
        assert manifest["slots"]["kpi_start_cell"] == expected["kpi_start_cell"]
        assert formal_layout["sections"]["kpi"]["header_text"] == "Key Metrics"
        assert formal_layout["chart_board"]["title_cell"] == expected["chart_title_cell"]
        assert set(formal_layout["chart_board"]["frames"].keys()) == {"1", "2", "3", "4"}
```

- [ ] **Step 2: Update the three shipped template manifests with formal-report slots and `formal_layout` metadata**

```json
// templates/template_a_overview/template_manifest.json
{
  "slots": {
    "title_cell": "A1",
    "product_cell": "B3",
    "batch_cell": "B4",
    "reason_cell": "B5",
    "kpi_start_cell": "A8",
    "narrative_summary_cell": "A15",
    "narrative_risk_cell": "A21",
    "actions_start_cell": "A26",
    "detail_start_row": 2
  },
  "chart_layout": {
    "sheet": "Summary",
    "area_title_cell": "H1",
    "area_title_text": "SPC Chart Overview"
  },
  "formal_layout": {
    "column_widths": {"A": 16, "B": 18, "C": 14, "D": 2.5, "H": 18, "I": 18, "J": 18, "K": 18, "L": 18, "M": 18, "N": 18, "O": 18, "P": 18, "Q": 18},
    "title_band": {"range": "A1:D1"},
    "metadata_rows": [
      {"label_cell": "A3", "value_cell": "B3", "label": "Product"},
      {"label_cell": "A4", "value_cell": "B4", "label": "Batch"},
      {"label_cell": "A5", "value_cell": "B5", "label": "Basis"}
    ],
    "sections": {
      "kpi": {"header_cell": "A7", "header_text": "Key Metrics", "body_range": "A8:B12", "kind": "kpi"},
      "summary": {"header_cell": "A14", "header_text": "Conclusion", "body_range": "A15:D18", "kind": "text"},
      "risk": {"header_cell": "A20", "header_text": "Risk", "body_range": "A21:D23", "kind": "text"},
      "actions": {"header_cell": "A25", "header_text": "Actions", "body_range": "A26:D29", "kind": "actions"}
    },
    "chart_board": {
      "title_cell": "H1",
      "title_text": "SPC Chart Overview",
      "frames": {"1": ["H2:Q20"], "2": ["H2:Q19", "H21:Q38"], "3": ["H2:M19", "N2:Q19", "K21:P38"], "4": ["H2:M19", "N2:Q19", "H21:M38", "N21:Q38"]}
    }
  }
}

// templates/template_b_detailed/template_manifest.json
{
  "slots": {
    "title_cell": "A1",
    "product_cell": "B3",
    "batch_cell": "B4",
    "reason_cell": "B5",
    "kpi_start_cell": "A8",
    "narrative_summary_cell": "A15",
    "narrative_risk_cell": "A21",
    "actions_start_cell": "A26",
    "detail_start_row": 2
  },
  "chart_layout": {
    "sheet": "Summary",
    "area_title_cell": "J1",
    "area_title_text": "SPC Chart Overview"
  },
  "formal_layout": {
    "column_widths": {"A": 16, "B": 18, "C": 14, "D": 2.5, "J": 18, "K": 18, "L": 18, "M": 18, "N": 18, "O": 18, "P": 18, "Q": 18},
    "title_band": {"range": "A1:D1"},
    "metadata_rows": [
      {"label_cell": "A3", "value_cell": "B3", "label": "Product"},
      {"label_cell": "A4", "value_cell": "B4", "label": "Batch"},
      {"label_cell": "A5", "value_cell": "B5", "label": "Basis"}
    ],
    "sections": {
      "kpi": {"header_cell": "A7", "header_text": "Key Metrics", "body_range": "A8:B12", "kind": "kpi"},
      "summary": {"header_cell": "A14", "header_text": "Conclusion", "body_range": "A15:D18", "kind": "text"},
      "risk": {"header_cell": "A20", "header_text": "Risk", "body_range": "A21:D23", "kind": "text"},
      "actions": {"header_cell": "A25", "header_text": "Actions", "body_range": "A26:D29", "kind": "actions"}
    },
    "chart_board": {
      "title_cell": "J1",
      "title_text": "SPC Chart Overview",
      "frames": {"1": ["J2:Q20"], "2": ["J2:Q19", "J21:Q38"], "3": ["J2:M19", "P2:Q19", "M21:Q38"], "4": ["J2:M19", "P2:Q19", "J21:M38", "P21:Q38"]}
    }
  }
}

// templates/template_c_showcase/template_manifest.json
{
  "slots": {
    "title_cell": "B2",
    "product_cell": "C4",
    "batch_cell": "C5",
    "reason_cell": "C6",
    "kpi_start_cell": "B9",
    "narrative_summary_cell": "B16",
    "narrative_risk_cell": "B22",
    "actions_start_cell": "B27",
    "detail_start_row": 2
  },
  "chart_layout": {
    "sheet": "Summary",
    "area_title_cell": "J2",
    "area_title_text": "SPC Chart Overview"
  },
  "formal_layout": {
    "column_widths": {"B": 16, "C": 18, "D": 14, "E": 2.5, "J": 18, "K": 18, "L": 18, "M": 18, "N": 18, "O": 18, "P": 18, "Q": 18},
    "title_band": {"range": "B2:E2"},
    "metadata_rows": [
      {"label_cell": "B4", "value_cell": "C4", "label": "Product"},
      {"label_cell": "B5", "value_cell": "C5", "label": "Batch"},
      {"label_cell": "B6", "value_cell": "C6", "label": "Basis"}
    ],
    "sections": {
      "kpi": {"header_cell": "B8", "header_text": "Key Metrics", "body_range": "B9:C13", "kind": "kpi"},
      "summary": {"header_cell": "B15", "header_text": "Conclusion", "body_range": "B16:E19", "kind": "text"},
      "risk": {"header_cell": "B21", "header_text": "Risk", "body_range": "B22:E24", "kind": "text"},
      "actions": {"header_cell": "B26", "header_text": "Actions", "body_range": "B27:E30", "kind": "actions"}
    },
    "chart_board": {
      "title_cell": "J2",
      "title_text": "SPC Chart Overview",
      "frames": {"1": ["J3:Q21"], "2": ["J3:Q20", "J22:Q39"], "3": ["J3:M20", "P3:Q20", "M22:Q39"], "4": ["J3:M20", "P3:Q20", "J22:M39", "P22:Q39"]}
    }
  }
}
```

- [ ] **Step 3: Document the formal report layout in `README.md`**

```markdown
- `Summary` sheet now uses a formal report layout: concise title band, left-side `KPI -> Conclusion -> Risk -> Actions`, and right-side auto-arranged `1~4` charts.
```

- [ ] **Step 4: Run the regression suite and inspect one real workbook export**

Run: `./.venv311/Scripts/python.exe -m pytest api/tests/test_excel_renderer.py -q`
Expected: PASS with `11 passed`

Run: `./.venv311/Scripts/python.exe -m pytest api/tests/test_charts.py api/tests/test_demo_pipeline.py api/tests/test_jobs_api.py -q`
Expected: PASS with `3 passed`

Run: `./.venv311/Scripts/python.exe -c "from pathlib import Path; import openpyxl; from api.app.services.excel import render_report; from api.tests.test_excel_renderer import _build_chart_paths, _build_report_spec; tmp_path = Path('outputs/dev/formal-summary-check'); tmp_path.mkdir(parents=True, exist_ok=True); chart_paths = _build_chart_paths(tmp_path / 'charts', 4); report_file = render_report(report_spec=_build_report_spec('template_a_overview', list(chart_paths.keys())), chart_paths=chart_paths, templates_root=Path('templates'), output_path=tmp_path / 'formal-summary-report.xlsx'); workbook = openpyxl.load_workbook(report_file); summary_sheet = workbook['Summary']; print(workbook.sheetnames); print(len(getattr(summary_sheet, '_images', []))); print(summary_sheet['A7'].value); print(summary_sheet['A14'].value); print(summary_sheet['H1'].value)"`

Expected:
- `['Summary', 'Details']`
- `4`
- `Key Metrics`
- `Conclusion`
- `SPC Chart Overview`

- [ ] **Step 5: Skip the Git commit in this workspace**

Run: `if (Test-Path .git) { git add api/tests/test_excel_renderer.py templates/template_a_overview/template_manifest.json templates/template_b_detailed/template_manifest.json templates/template_c_showcase/template_manifest.json README.md; git commit -m "feat: style summary sheet as formal report" } else { "SKIP: no git repo in current workspace" }`
Expected: `SKIP: no git repo in current workspace`
