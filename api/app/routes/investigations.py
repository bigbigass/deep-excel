"""质量调查案件 HTTP 接口。"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from api.app.domain import (
    InvestigationCase,
    SchemaMappingConfirmation,
    SchemaMappingProposal,
)
from api.app.domain.ai import EvidenceGroundedInvestigationResult
from api.app.services.investigation.cases import (
    confirm_investigation_mapping,
    create_investigation,
    decide_hypothesis,
    export_investigation_report,
    load_ai_investigation_result,
    load_investigation,
    load_investigation_mapping,
    run_ai_investigation,
)

router = APIRouter(prefix="/api/v1", tags=["investigations"])

_XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class HypothesisDecisionRequest(BaseModel):
    outcome: Literal["confirmed", "rejected"]
    actor_id: str = Field(min_length=1)
    note: str = Field(min_length=1)


def _value_error_status(exc: ValueError) -> int:
    message = str(exc)
    if "OPENAI_API_KEY" in message:
        return 503
    if "invalid investigation case id" in message:
        return 400
    return 409


@router.post("/investigations", status_code=202)
async def create_investigation_case(
    question: str = Form(...),
    file: UploadFile = File(...),
) -> JSONResponse:
    """上传质量数据并启动字段识别和确定性基线调查。"""
    try:
        payload = create_investigation(
            question=question,
            file_name=file.filename,
            content=await file.read(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse(status_code=202, content=payload)


@router.get("/investigations/{case_id}", response_model=InvestigationCase)
def get_investigation_case(case_id: str) -> InvestigationCase:
    """读取案件当前状态、证据、缺失数据和后续假设。"""
    try:
        return load_investigation(case_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation case not found") from exc


@router.get(
    "/investigations/{case_id}/mapping",
    response_model=SchemaMappingProposal,
)
def get_investigation_mapping(case_id: str) -> SchemaMappingProposal:
    """读取规则/AI 产生的字段语义建议，供用户确认或修订。"""
    try:
        return load_investigation_mapping(case_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Schema mapping not found") from exc


@router.post(
    "/investigations/{case_id}/mapping/confirm",
    response_model=InvestigationCase,
)
def confirm_investigation_case_mapping(
    case_id: str,
    request: SchemaMappingConfirmation,
) -> InvestigationCase:
    """保存人工字段确认，并用确认后的标准数据运行确定性调查。"""
    try:
        return confirm_investigation_mapping(case_id, request)
    except ValueError as exc:
        raise HTTPException(status_code=_value_error_status(exc), detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/investigations/{case_id}/ai",
    response_model=EvidenceGroundedInvestigationResult,
)
def run_investigation_ai(case_id: str) -> EvidenceGroundedInvestigationResult:
    """对 ready 案件执行白名单工具规划和证据约束综合。"""
    try:
        return run_ai_investigation(case_id)
    except ValueError as exc:
        raise HTTPException(status_code=_value_error_status(exc), detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/investigations/{case_id}/ai",
    response_model=EvidenceGroundedInvestigationResult,
)
def get_investigation_ai_result(case_id: str) -> EvidenceGroundedInvestigationResult:
    """读取最近一次持久化的 AI 调查计划和综合结果。"""
    try:
        return load_ai_investigation_result(case_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="AI investigation result not found") from exc


@router.post(
    "/investigations/{case_id}/hypotheses/{hypothesis_id}/decision",
    response_model=InvestigationCase,
)
def decide_investigation_hypothesis(
    case_id: str,
    hypothesis_id: str,
    request: HypothesisDecisionRequest,
) -> InvestigationCase:
    """由人工确认或排除候选根因；AI 无法调用该内部决策逻辑。"""
    try:
        return decide_hypothesis(
            case_id,
            hypothesis_id,
            outcome=request.outcome,
            actor_id=request.actor_id,
            note=request.note,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=_value_error_status(exc), detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation case not found") from exc


@router.get("/investigations/{case_id}/export")
def download_investigation_report(case_id: str) -> FileResponse:
    """生成并下载固定结构的 Excel 调查报告。"""
    try:
        report_path = export_investigation_report(case_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation case not found") from exc
    return FileResponse(
        report_path,
        media_type=_XLSX_MEDIA_TYPE,
        filename=f"{case_id}-investigation.xlsx",
    )
