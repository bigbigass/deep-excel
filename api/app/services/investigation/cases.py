"""质量调查案件创建、执行、AI 增强、人工决策和固定导出服务。"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from threading import Thread
from typing import Literal
from uuid import uuid4

from api.app.agent.evidence_synthesizer import EvidenceSynthesizer
from api.app.agent.investigation_planner import InvestigationPlanner
from api.app.domain import HypothesisDecision, InvestigationCase
from api.app.domain.ai import EvidenceGroundedInvestigationResult
from api.app.services.ingestion import load_source_dataframe
from api.app.services.investigation.ai_pipeline import (
    apply_ai_result_to_case,
    run_evidence_grounded_ai,
)
from api.app.services.investigation.baseline import run_baseline_investigation
from api.app.services.investigation.export import render_investigation_report
from api.app.services.investigation.repository import InvestigationRepository
from api.app.services.investigation.tool_registry import InvestigationToolRegistry

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


def run_ai_investigation(
    case_id: str,
    *,
    repository: InvestigationRepository | None = None,
    planner: InvestigationPlanner | None = None,
    synthesizer: EvidenceSynthesizer | None = None,
    registry: InvestigationToolRegistry | None = None,
) -> EvidenceGroundedInvestigationResult:
    """基于已落盘源文件执行白名单工具规划与证据约束综合。"""
    repo = repository or _DEFAULT_REPOSITORY
    case = repo.load(case_id)
    if not case.source_refs:
        raise ValueError("investigation case has no source file reference")

    source_path = repo.resolve_source_ref(case_id, case.source_refs[0])
    frame = load_source_dataframe(source_path)
    result = run_evidence_grounded_ai(
        case,
        frame,
        planner=planner,
        synthesizer=synthesizer,
        registry=registry,
    )
    updated_case = apply_ai_result_to_case(case, result)
    repo.save(updated_case)
    repo.save_ai_result(case_id, result)
    return result


def load_ai_investigation_result(
    case_id: str,
    *,
    repository: InvestigationRepository | None = None,
) -> EvidenceGroundedInvestigationResult:
    repo = repository or _DEFAULT_REPOSITORY
    return repo.load_ai_result(case_id)


def decide_hypothesis(
    case_id: str,
    hypothesis_id: str,
    *,
    outcome: Literal["confirmed", "rejected"],
    actor_id: str,
    note: str,
    repository: InvestigationRepository | None = None,
) -> InvestigationCase:
    """仅接受人工确认或排除，并把决定写回候选假设。"""
    repo = repository or _DEFAULT_REPOSITORY
    case = repo.load(case_id)
    target = next((item for item in case.hypotheses if item.id == hypothesis_id), None)
    if target is None:
        raise KeyError(f"hypothesis not found: {hypothesis_id}")
    if target.status in {"confirmed", "rejected"}:
        raise ValueError("hypothesis already has a final decision")

    decision = HypothesisDecision(
        outcome=outcome,
        actor_type="human",
        actor_id=actor_id,
        note=note,
    )
    hypothesis_payload = target.model_dump()
    hypothesis_payload.update({"status": outcome, "decision": decision})
    updated_hypothesis = target.__class__.model_validate(hypothesis_payload)
    hypotheses = [
        updated_hypothesis if item.id == hypothesis_id else item
        for item in case.hypotheses
    ]
    updated_case = _replace_case(
        case,
        state="waiting_for_user",
        hypotheses=hypotheses,
        updated_at=datetime.now(UTC),
    )
    repo.save(updated_case)
    return updated_case


def export_investigation_report(
    case_id: str,
    *,
    repository: InvestigationRepository | None = None,
) -> Path:
    """生成固定结构的 Excel 调查报告；AI 无法控制模板或单元格。"""
    repo = repository or _DEFAULT_REPOSITORY
    case = repo.load(case_id)
    try:
        ai_result = repo.load_ai_result(case_id)
    except FileNotFoundError:
        ai_result = None
    return render_investigation_report(
        case=case,
        ai_result=ai_result,
        output_path=repo.export_path(case_id),
    )
