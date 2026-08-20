"""文件型质量调查案件仓储。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from threading import Lock
from uuid import uuid4

from api.app.config import get_settings
from api.app.domain import InvestigationCase

_CASE_ID_PATTERN = re.compile(r"^CASE-[A-Za-z0-9][A-Za-z0-9-]*$")
_ALLOWED_UPLOAD_SUFFIXES = {".csv", ".xlsx", ".xlsm"}
_REPOSITORY_LOCK = Lock()


class InvestigationRepository:
    """在 outputs/investigations 下持久化案件、上传文件和后续产物。"""

    def __init__(self, root: Path | None = None) -> None:
        settings = get_settings()
        self.root = (root or (Path(settings.outputs_dir) / "investigations")).resolve()

    @staticmethod
    def validate_case_id(case_id: str) -> str:
        candidate = case_id.strip()
        if not _CASE_ID_PATTERN.fullmatch(candidate):
            raise ValueError("invalid investigation case id")
        return candidate

    def case_dir(self, case_id: str) -> Path:
        validated = self.validate_case_id(case_id)
        candidate = (self.root / validated).resolve()
        if candidate.parent != self.root:
            raise ValueError("invalid investigation case path")
        return candidate

    def case_path(self, case_id: str) -> Path:
        return self.case_dir(case_id) / "case.json"

    def save(self, case: InvestigationCase) -> Path:
        """使用同目录临时文件和原子替换，避免读到半写入 JSON。"""
        case_directory = self.case_dir(case.case_id)
        case_directory.mkdir(parents=True, exist_ok=True)
        target_path = case_directory / "case.json"
        temporary_path = case_directory / f".case-{uuid4().hex}.tmp"
        payload = json.dumps(
            case.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
        with _REPOSITORY_LOCK:
            temporary_path.write_text(payload, encoding="utf-8")
            temporary_path.replace(target_path)
        return target_path

    def load(self, case_id: str) -> InvestigationCase:
        target_path = self.case_path(case_id)
        with _REPOSITORY_LOCK:
            if not target_path.is_file():
                raise FileNotFoundError(f"investigation case not found: {case_id}")
            payload = target_path.read_text(encoding="utf-8")
        return InvestigationCase.model_validate_json(payload)

    def save_upload(self, case_id: str, file_name: str | None, content: bytes) -> Path:
        """把上传文件隔离到案件目录，并拒绝路径穿越和不支持的后缀。"""
        safe_name = Path(file_name or "upload").name
        if not safe_name or safe_name in {".", ".."}:
            raise ValueError("invalid upload file name")
        suffix = Path(safe_name).suffix.lower()
        if suffix not in _ALLOWED_UPLOAD_SUFFIXES:
            raise ValueError(f"unsupported investigation file type: {suffix or '<none>'}")

        upload_dir = self.case_dir(case_id) / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        target_path = (upload_dir / safe_name).resolve()
        if target_path.parent != upload_dir.resolve():
            raise ValueError("invalid upload file path")
        target_path.write_bytes(content)
        return target_path
