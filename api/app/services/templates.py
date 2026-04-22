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
    workbook_path = templates_root / template_id / str(manifest["workbook_name"])
    workbook_path.parent.mkdir(parents=True, exist_ok=True)
    if workbook_path.exists():
        return workbook_path

    workbook = Workbook()
    summary = workbook.active
    summary.title = str(manifest["summary_sheet"])
    details = workbook.create_sheet(str(manifest["detail_sheet"]))

    summary["A1"] = "Template placeholder"
    summary["A1"].font = Font(size=18, bold=True)
    details["A1"] = "sample_id"
    details["B1"] = "measurement_value"
    details["C1"] = "status"

    workbook.save(workbook_path)
    return workbook_path
