"""把受控 AI 调查管线应用到已持久化案件。"""

from __future__ import annotations

from pathlib import Path

from api.app.agent.evidence_synthesizer import EvidenceGroundedSynthesizer
from api.app.agent.investigation_planner import InvestigationPlanner
from api.app.services.ingestion import load_source_dataframe
from api.app.services.investigation.ai_pipeline import (
    AIInvestigationRun,
    run_ai_investigation,
)
from api.app.services.investigation.repository import InvestigationRepository
from api.app.services.investigation.tool_registry import InvestigationToolRegistry


def run_persisted_ai_investigation(
    case_id: str,
    *,
    repository: InvestigationRepository | None = None,
    planner: InvestigationPlanner | None = None,
    synthesizer: EvidenceGroundedSynthesizer | None = None,
    registry: InvestigationToolRegistry | None = None,
) -> AIInvestigationRun:
    """读取案件源数据，执行一轮受控 AI 调查并原子保存结果。"""
    repo = repository or InvestigationRepository()
    case = repo.load(case_id)
    if not case.source_refs:
        raise ValueError("investigation case does not contain a source data reference")

    source_path = Path(case.source_refs[0])
    if not source_path.is_file():
        raise FileNotFoundError(f"investigation source file not found: {source_path}")

    frame = load_source_dataframe(source_path)
    result = run_ai_investigation(
        case,
        frame,
        planner=planner,
        synthesizer=synthesizer,
        registry=registry,
    )
    repo.save(result.case)
    return result
