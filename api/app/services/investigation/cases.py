"""质量调查案件创建、执行和状态读取服务。"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from threading import Thread
from uuid import uuid4

from api.app.domain import InvestigationCase
from api.app.services.ingestion import load_source_dataframe
from api.app.services.investigation.baseline import run_baseline_investigation
from api.app.services.investigation.repository import InvestigationRepository

_DEFAULT_REPOSITORY = InvestigationRepository()


def create_case_id() -> str:
    return f"CASE-{uuid4().hex[:8]}"


def _replace_case(case: InvestigationCase, **updates: object) -> InvestigationCase:
    payload = case.model_dump()
    payload.update(updates)
    return InvestigationCase.model_validate(payload)


def create_investigation(
    *,
    question: str,
    file_name: str | None,
    content: bytes,
    repository: InvestigationRepository | None = None,
    start_background: bool = True,
) -> dict[str, str]:
    """创建初始案件、保存源文件，并按需启动后台基线调查。"""
    normalized_question = question.strip()
    if not normalized_question:
        raise ValueError("question must not be empty")
    if not content:
        raise ValueError("investigation upload must not be empty")

    repo = repository or _DEFAULT_REPOSITORY
    case_id = create_case_id()
    upload_path = repo.save_upload(case_id, file_name, content)
    initial_case = InvestigationCase(
        case_id=case_id,
        question=normalized_question,
        state="created",
        source_refs=[str(upload_path)],
    )
    repo.save(initial_case)

    if start_background:
        Thread(
            target=run_investigation,
            args=(case_id, upload_path),
            kwargs={"repository": repo},
            daemon=True,
        ).start()
    return {"case_id": case_id}


def run_investigation(
    case_id: str,
    upload_path: Path,
    *,
    repository: InvestigationRepository | None = None,
) -> InvestigationCase:
    """同步执行基线调查；后台线程和测试都复用这个入口。"""
    repo = repository or _DEFAULT_REPOSITORY
    current = repo.load(case_id)
    investigating = _replace_case(
        current,
        state="investigating",
        error=None,
        updated_at=datetime.now(UTC),
    )
    repo.save(investigating)

    try:
        frame = load_source_dataframe(upload_path)
        completed = run_baseline_investigation(
            frame,
            question=current.question,
            case_id=case_id,
            source_refs=current.source_refs,
        )
        completed = _replace_case(
            completed,
            created_at=current.created_at,
            updated_at=datetime.now(UTC),
        )
        repo.save(completed)
        return completed
    except Exception as exc:
        failed = _replace_case(
            investigating,
            state="failed",
            error=str(exc),
            updated_at=datetime.now(UTC),
        )
        repo.save(failed)
        return failed


def load_investigation(
    case_id: str,
    *,
    repository: InvestigationRepository | None = None,
) -> InvestigationCase:
    repo = repository or _DEFAULT_REPOSITORY
    return repo.load(case_id)
