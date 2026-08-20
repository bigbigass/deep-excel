"""受控 AI 调查和人工根因决定接口。"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from api.app.services.investigation.ai_cases import run_persisted_ai_investigation
from api.app.services.investigation.decisions import decide_hypothesis

router = APIRouter(prefix="/api/v1", tags=["investigation-ai"])


class HypothesisDecisionRequest(BaseModel):
    outcome: Literal["confirmed", "rejected"]
    actor_id: str = Field(min_length=1)
    note: str = Field(min_length=1)

    @field_validator("actor_id", "note")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        candidate = value.strip()
        if not candidate:
            raise ValueError("decision fields must not be empty")
        return candidate


@router.post("/investigations/{case_id}/ai-run")
def run_ai_investigation_endpoint(case_id: str) -> dict[str, object]:
    """执行白名单计划、确定性工具和证据引用式综合。"""
    try:
        result = run_persisted_ai_investigation(case_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        message = str(exc)
        status_code = 503 if "OPENAI_API_KEY" in message else 409
        raise HTTPException(status_code=status_code, detail=message) from exc
    return result.model_dump(mode="json")


@router.post(
    "/investigations/{case_id}/hypotheses/{hypothesis_id}/decision"
)
def decide_hypothesis_endpoint(
    case_id: str,
    hypothesis_id: str,
    request: HypothesisDecisionRequest,
) -> dict[str, object]:
    """由具名人工确认或排除候选根因。"""
    try:
        case = decide_hypothesis(
            case_id,
            hypothesis_id,
            outcome=request.outcome,
            actor_id=request.actor_id,
            note=request.note,
        )
    except (FileNotFoundError, KeyError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return case.model_dump(mode="json")
