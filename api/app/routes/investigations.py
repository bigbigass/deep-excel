"""质量调查案件 HTTP 接口。"""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from api.app.domain import InvestigationCase
from api.app.services.investigation.cases import create_investigation, load_investigation

router = APIRouter(prefix="/api/v1", tags=["investigations"])


@router.post("/investigations", status_code=202)
async def create_investigation_case(
    question: str = Form(...),
    file: UploadFile = File(...),
) -> JSONResponse:
    """上传标准化质量数据并启动确定性基线调查。"""
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
