# Summary Chart Density Tuning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the `Summary` sheet chart board denser for 3-chart and 4-chart exports by enlarging charts and tightening spacing, while keeping the current left-right report balance unchanged.

**Architecture:** Keep the renderer logic unchanged and implement this refinement as a manifest-driven layout update. Add failing tests that lock the new 3-chart and 4-chart anchor cells, image sizes, and frame ranges, then update the three shipped template manifests so `chart_layout.layouts["3"]`, `chart_layout.layouts["4"]`, and matching `formal_layout.chart_board.frames` reflect the approved medium-tight density design.

**Tech Stack:** Python, `pytest`, JSON template manifests, `openpyxl`

---

### Task 1: Add failing tests for denser 3-chart and 4-chart layouts

**Files:**
- Modify: `api/tests/test_excel_renderer.py:369`
- Test: `api/tests/test_excel_renderer.py`

- [ ] **Step 1: Add a manifest contract test for the new 3-chart and 4-chart layout metadata**

```python
def test_demo_template_manifests_define_denser_three_and_four_chart_layouts() -> None:
    expected_layouts = {
        "template_a_overview": {
            "3": [
                {"title_cell": "H2", "image_cell": "H3", "width": 330, "height": 185},
                {"title_cell": "N2", "image_cell": "N3", "width": 330, "height": 185},
                {"title_cell": "K18", "image_cell": "K19", "width": 460, "height": 185},
            ],
            "4": [
                {"title_cell": "H2", "image_cell": "H3", "width": 330, "height": 185},
                {"title_cell": "N2", "image_cell": "N3", "width": 330, "height": 185},
                {"title_cell": "H18", "image_cell": "H19", "width": 330, "height": 185},
                {"title_cell": "N18", "image_cell": "N19", "width": 330, "height": 185},
            ],
            "frames": {
                "3": ["H2:M20", "N2:Q20", "K18:P35"],
                "4": ["H2:M20", "N2:Q20", "H18:M35", "N18:Q35"],
            },
        },
        "template_b_detailed": {
            "3": [
                {"title_cell": "J2", "image_cell": "J3", "width": 330, "height": 185},
                {"title_cell": "P2", "image_cell": "P3", "width": 330, "height": 185},
                {"title_cell": "M18", "image_cell": "M19", "width": 460, "height": 185},
            ],
            "4": [
                {"title_cell": "J2", "image_cell": "J3", "width": 330, "height": 185},
                {"title_cell": "P2", "image_cell": "P3", "width": 330, "height": 185},
                {"title_cell": "J18", "image_cell": "J19", "width": 330, "height": 185},
                {"title_cell": "P18", "image_cell": "P19", "width": 330, "height": 185},
            ],
            "frames": {
                "3": ["J2:M20", "P2:Q20", "M18:Q35"],
                "4": ["J2:M20", "P2:Q20", "J18:M35", "P18:Q35"],
            },
        },
        "template_c_showcase": {
            "3": [
                {"title_cell": "J3", "image_cell": "J4", "width": 330, "height": 185},
                {"title_cell": "P3", "image_cell": "P4", "width": 330, "height": 185},
                {"title_cell": "M19", "image_cell": "M20", "width": 460, "height": 185},
            ],
            "4": [
                {"title_cell": "J3", "image_cell": "J4", "width": 330, "height": 185},
                {"title_cell": "P3", "image_cell": "P4", "width": 330, "height": 185},
                {"title_cell": "J19", "image_cell": "J20", "width": 330, "height": 185},
                {"title_cell": "P19", "image_cell": "P20", "width": 330, "height": 185},
            ],
            "frames": {
                "3": ["J3:M21", "P3:Q21", "M19:Q36"],
                "4": ["J3:M21", "P3:Q21", "J19:M36", "P19:Q36"],
            },
        },
    }

    for template_id, expected in expected_layouts.items():
        manifest = load_template_manifest(Path("templates"), template_id)
        chart_layout = manifest["chart_layout"]
        formal_layout = manifest["formal_layout"]
        assert chart_layout["layouts"]["3"] == expected["3"]
        assert chart_layout["layouts"]["4"] == expected["4"]
        assert formal_layout["chart_board"]["frames"]["3"] == expected["frames"]["3"]
        assert formal_layout["chart_board"]["frames"]["4"] == expected["frames"]["4"]
```

- [ ] **Step 2: Update the real export test so it locks the new title cells for 3-chart and 4-chart demo exports**

```python
@pytest.mark.parametrize(
    ("chart_count", "expected_title_cells"),
    [
        (3, ["H2", "N2", "K18"]),
        (4, ["H2", "N2", "H18", "N18"]),
    ],
)
def test_render_report_places_generated_charts_on_demo_summary_sheet(
    tmp_path: Path,
    chart_count: int,
    expected_title_cells: list[str],
) -> None:
    chart_paths = _build_chart_paths(tmp_path / f"charts-demo-{chart_count}", chart_count)
    report_file = render_report(
        report_spec=_build_report_spec("template_a_overview", list(chart_paths.keys())),
        chart_paths=chart_paths,
        templates_root=Path("templates"),
        output_path=tmp_path / f"demo-summary-layout-{chart_count}.xlsx",
    )

    workbook = openpyxl.load_workbook(report_file)
    summary_sheet = workbook["Summary"]

    assert "Charts" not in workbook.sheetnames
    assert len(getattr(summary_sheet, "_images", [])) == chart_count
    for title_cell, chart_id in zip(expected_title_cells, chart_paths):
        assert summary_sheet[title_cell].value == chart_id.replace("_", " ").title()
```

- [ ] **Step 3: Run the focused renderer tests and confirm the new density assertions fail first**

Run: `./.venv311/Scripts/python.exe -m pytest api/tests/test_excel_renderer.py -q -k "denser_three_and_four or generated_charts_on_demo_summary_sheet"`
Expected: FAIL because the shipped template manifests still contain the older, looser 3-chart and 4-chart anchors and sizes.

- [ ] **Step 4: Run the full renderer test file to capture the red baseline**

Run: `./.venv311/Scripts/python.exe -m pytest api/tests/test_excel_renderer.py -q`
Expected: FAIL with the new density-layout expectations while the previously passing summary-style tests remain green.

- [ ] **Step 5: Skip the Git commit in this workspace**

Run: `if (Test-Path .git) { git add api/tests/test_excel_renderer.py; git commit -m "test: lock denser three and four chart layouts" } else { "SKIP: no git repo in current workspace" }`
Expected: `SKIP: no git repo in current workspace`

---

### Task 2: Tune the three shipped template manifests for medium-tight 3-chart and 4-chart density

**Files:**
- Modify: `templates/template_a_overview/template_manifest.json:44`
- Modify: `templates/template_b_detailed/template_manifest.json:44`
- Modify: `templates/template_c_showcase/template_manifest.json:44`

- [ ] **Step 1: Update `template_a_overview` to enlarge charts and pull the lower row upward**

```json
{
  "chart_layout": {
    "layouts": {
      "3": [
        { "title_cell": "H2", "image_cell": "H3", "width": 330, "height": 185 },
        { "title_cell": "N2", "image_cell": "N3", "width": 330, "height": 185 },
        { "title_cell": "K18", "image_cell": "K19", "width": 460, "height": 185 }
      ],
      "4": [
        { "title_cell": "H2", "image_cell": "H3", "width": 330, "height": 185 },
        { "title_cell": "N2", "image_cell": "N3", "width": 330, "height": 185 },
        { "title_cell": "H18", "image_cell": "H19", "width": 330, "height": 185 },
        { "title_cell": "N18", "image_cell": "N19", "width": 330, "height": 185 }
      ]
    }
  },
  "formal_layout": {
    "chart_board": {
      "frames": {
        "3": ["H2:M20", "N2:Q20", "K18:P35"],
        "4": ["H2:M20", "N2:Q20", "H18:M35", "N18:Q35"]
      }
    }
  }
}
```

- [ ] **Step 2: Update `template_b_detailed` with the same density pattern in its shifted chart zone**

```json
{
  "chart_layout": {
    "layouts": {
      "3": [
        { "title_cell": "J2", "image_cell": "J3", "width": 330, "height": 185 },
        { "title_cell": "P2", "image_cell": "P3", "width": 330, "height": 185 },
        { "title_cell": "M18", "image_cell": "M19", "width": 460, "height": 185 }
      ],
      "4": [
        { "title_cell": "J2", "image_cell": "J3", "width": 330, "height": 185 },
        { "title_cell": "P2", "image_cell": "P3", "width": 330, "height": 185 },
        { "title_cell": "J18", "image_cell": "J19", "width": 330, "height": 185 },
        { "title_cell": "P18", "image_cell": "P19", "width": 330, "height": 185 }
      ]
    }
  },
  "formal_layout": {
    "chart_board": {
      "frames": {
        "3": ["J2:M20", "P2:Q20", "M18:Q35"],
        "4": ["J2:M20", "P2:Q20", "J18:M35", "P18:Q35"]
      }
    }
  }
}
```

- [ ] **Step 3: Update `template_c_showcase` using the same tuning, shifted one row lower**

```json
{
  "chart_layout": {
    "layouts": {
      "3": [
        { "title_cell": "J3", "image_cell": "J4", "width": 330, "height": 185 },
        { "title_cell": "P3", "image_cell": "P4", "width": 330, "height": 185 },
        { "title_cell": "M19", "image_cell": "M20", "width": 460, "height": 185 }
      ],
      "4": [
        { "title_cell": "J3", "image_cell": "J4", "width": 330, "height": 185 },
        { "title_cell": "P3", "image_cell": "P4", "width": 330, "height": 185 },
        { "title_cell": "J19", "image_cell": "J20", "width": 330, "height": 185 },
        { "title_cell": "P19", "image_cell": "P20", "width": 330, "height": 185 }
      ]
    }
  },
  "formal_layout": {
    "chart_board": {
      "frames": {
        "3": ["J3:M21", "P3:Q21", "M19:Q36"],
        "4": ["J3:M21", "P3:Q21", "J19:M36", "P19:Q36"]
      }
    }
  }
}
```

- [ ] **Step 4: Re-run the focused renderer tests and confirm the new density expectations pass**

Run: `./.venv311/Scripts/python.exe -m pytest api/tests/test_excel_renderer.py -q -k "denser_three_and_four or generated_charts_on_demo_summary_sheet"`
Expected: PASS after the three manifests reflect the denser 3-chart and 4-chart metadata.

- [ ] **Step 5: Skip the Git commit in this workspace**

Run: `if (Test-Path .git) { git add templates/template_a_overview/template_manifest.json templates/template_b_detailed/template_manifest.json templates/template_c_showcase/template_manifest.json; git commit -m "feat: tighten three and four chart summary layouts" } else { "SKIP: no git repo in current workspace" }`
Expected: `SKIP: no git repo in current workspace`

---

### Task 3: Run full regression and inspect real workbook exports

**Files:**
- Modify: `api/tests/test_excel_renderer.py:412`
- Test: `api/tests/test_excel_renderer.py`
- Test: `api/tests/test_charts.py`
- Test: `api/tests/test_demo_pipeline.py`
- Test: `api/tests/test_jobs_api.py`

- [ ] **Step 1: Re-run the full renderer test file and confirm no existing formal-report behavior regressed**

Run: `./.venv311/Scripts/python.exe -m pytest api/tests/test_excel_renderer.py -q`
Expected: PASS with `13 passed` after the new density test is added and the demo export check is parameterized for 3-chart and 4-chart cases.

- [ ] **Step 2: Run adjacent regression tests to prove same-sheet export behavior still holds**

Run: `./.venv311/Scripts/python.exe -m pytest api/tests/test_charts.py api/tests/test_demo_pipeline.py api/tests/test_jobs_api.py -q`
Expected: PASS with `3 passed`

- [ ] **Step 3: Export a real workbook with 3 charts and verify the tighter anchors landed on the `Summary` sheet**

Run: `./.venv311/Scripts/python.exe -c "from pathlib import Path; import openpyxl; from api.app.services.excel import render_report; from api.tests.test_excel_renderer import _build_chart_paths, _build_report_spec; tmp_path = Path('outputs/dev/dense-summary-check'); tmp_path.mkdir(parents=True, exist_ok=True); chart_paths = _build_chart_paths(tmp_path / 'charts', 3); report_file = render_report(report_spec=_build_report_spec('template_a_overview', list(chart_paths.keys())), chart_paths=chart_paths, templates_root=Path('templates'), output_path=tmp_path / 'dense-summary-report.xlsx'); workbook = openpyxl.load_workbook(report_file); summary_sheet = workbook['Summary']; print(workbook.sheetnames); print(len(getattr(summary_sheet, '_images', []))); print(summary_sheet['H2'].value); print(summary_sheet['N2'].value); print(summary_sheet['K18'].value)"`

Expected:
- `['Summary', 'Details']`
- `3`
- `Histogram`
- `Control Chart Imr`
- `Trend Line`

- [ ] **Step 4: Export a real workbook with 4 charts and verify the lower row shifted upward**

Run: `./.venv311/Scripts/python.exe -c "from pathlib import Path; import openpyxl; from api.app.services.excel import render_report; from api.tests.test_excel_renderer import _build_chart_paths, _build_report_spec; tmp_path = Path('outputs/dev/dense-summary-check'); tmp_path.mkdir(parents=True, exist_ok=True); chart_paths = _build_chart_paths(tmp_path / 'charts-4', 4); report_file = render_report(report_spec=_build_report_spec('template_a_overview', list(chart_paths.keys())), chart_paths=chart_paths, templates_root=Path('templates'), output_path=tmp_path / 'dense-summary-report-4.xlsx'); workbook = openpyxl.load_workbook(report_file); summary_sheet = workbook['Summary']; print(workbook.sheetnames); print(len(getattr(summary_sheet, '_images', []))); print(summary_sheet['H18'].value); print(summary_sheet['N18'].value)"`

Expected:
- `['Summary', 'Details']`
- `4`
- `Trend Line`
- `Spec Comparison`

- [ ] **Step 5: Skip the Git commit in this workspace**

Run: `if (Test-Path .git) { git add api/tests/test_excel_renderer.py templates/template_a_overview/template_manifest.json templates/template_b_detailed/template_manifest.json templates/template_c_showcase/template_manifest.json; git commit -m "test: verify denser summary chart layouts" } else { "SKIP: no git repo in current workspace" }`
Expected: `SKIP: no git repo in current workspace`
