from __future__ import annotations

from pathlib import Path

import openpyxl
from openpyxl.drawing.image import Image
from openpyxl.worksheet.worksheet import Worksheet

from api.app.report_models import ReportSpec
from api.app.services.excel_styles import apply_formal_summary_style
from api.app.services.report_localization import chart_title
from api.app.services.templates import ensure_demo_template_workbook, load_template_manifest


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
        ordered_charts.append((chart_title(chart_id), chart_path))

    return ordered_charts[:4]


def _embed_chart_images_on_charts_sheet(
    workbook: openpyxl.Workbook,
    chart_images: list[tuple[str, str]],
) -> None:
    if "Charts" in workbook.sheetnames:
        workbook.remove(workbook["Charts"])

    chart_sheet = workbook.create_sheet(title="Charts")
    chart_sheet["A1"] = "图表汇总"

    for offset, (title, chart_path) in enumerate(chart_images):
        title_row = 3 + (offset * 24)
        image_row = title_row + 1
        chart_sheet[f"A{title_row}"] = title
        chart_sheet.add_image(Image(chart_path), f"A{image_row}")


def _embed_chart_images_on_summary_sheet(
    workbook: openpyxl.Workbook,
    summary_sheet: Worksheet,
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
        chart_layout.get("area_title_text", "SPC 图表总览")
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
    summary_sheet: Worksheet,
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
    apply_formal_summary_style(summary_sheet=summary_sheet, manifest=manifest)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)
    return output_path
