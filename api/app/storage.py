"""轻量级 JSON 存储工具，用于持久化作业状态。"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4


def save_json(path: Path, payload: dict[str, object]) -> None:
    """以原子替换方式写入 JSON，降低并发写坏文件的风险。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    # 先写临时文件，再原子替换正式文件，避免中途写入导致 JSON 损坏。
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def load_json(path: Path) -> dict[str, object]:
    """读取持久化的 JSON 载荷。"""
    return json.loads(path.read_text(encoding="utf-8"))
