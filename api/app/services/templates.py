"""Excel 模板清单和工作簿文件的读取工具。"""

from __future__ import annotations

import json
from pathlib import Path

def load_template_manifest(templates_root: Path, template_id: str) -> dict[str, object]:
    """读取模板目录下的 manifest 配置。"""
    manifest_path = templates_root / template_id / "template_manifest.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def ensure_demo_template_workbook(templates_root: Path, template_id: str) -> Path:
    """确认模板工作簿存在，不存在时给出明确错误。"""
    manifest = load_template_manifest(templates_root, template_id)
    workbook_path = templates_root / template_id / str(manifest["workbook_name"])
    if workbook_path.exists():
        return workbook_path
    raise FileNotFoundError(f"Template workbook not found: {workbook_path}")
