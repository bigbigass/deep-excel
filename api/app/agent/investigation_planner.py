"""Bounded AI planner for evidence-driven quality investigations."""

from __future__ import annotations

import json
from typing import Protocol

from api.app.agent.factory import build_agent_model
from api.app.config import get_settings
from api.app.domain import InvestigationCase
from api.app.domain.ai import InvestigationPlan, InvestigationToolDescription


class StructuredOutputInvoker(Protocol):
    def invoke(self, messages: list[dict[str, str]]) -> object:
        ...


class StructuredOutputModel(Protocol):
    def with_structured_output(self, schema: type[InvestigationPlan]) -> StructuredOutputInvoker:
        ...


def _build_planner_messages(
    *,
    case: InvestigationCase,
    available_columns: list[str],
    tools: list[InvestigationToolDescription],
) -> list[dict[str, str]]:
    evidence_payload = [
        {
            "id": item.id,
            "type": item.evidence_type,
            "title": item.title,
            "statement": item.statement,
            "confidence": item.confidence,
        }
        for item in case.evidence
    ]
    tool_payload = [item.model_dump(mode="json") for item in tools]
    user_payload = {
        "question": case.question,
        "scope": case.scope.model_dump(mode="json"),
        "available_columns": sorted(available_columns),
        "existing_evidence": evidence_payload,
        "tools": tool_payload,
    }

    return [
        {
            "role": "system",
            "content": (
                "You plan a Chinese manufacturing quality investigation. "
                "Select only tools explicitly marked available. "
                "Do not calculate metrics, write conclusions, or claim root causes. "
                "Use at most six steps, avoid repeating evidence that already answers the question, "
                "and use exact column names from available_columns. "
                "If deterministic evidence is already sufficient, return an empty steps list. "
                "Reasons and missing-information items must be concise Chinese text."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(user_payload, ensure_ascii=False, separators=(",", ":")),
        },
    ]


class InvestigationPlanner:
    """Uses structured model output and leaves tool execution to the registry."""

    def __init__(self, model: StructuredOutputModel | None = None) -> None:
        self.model = model or build_agent_model()

    def plan(
        self,
        *,
        case: InvestigationCase,
        available_columns: list[str],
        tools: list[InvestigationToolDescription],
    ) -> InvestigationPlan:
        structured_model = self.model.with_structured_output(InvestigationPlan)
        response = structured_model.invoke(
            _build_planner_messages(
                case=case,
                available_columns=available_columns,
                tools=tools,
            )
        )
        return InvestigationPlan.model_validate(response)


def build_investigation_planner() -> InvestigationPlanner:
    settings = get_settings()
    if not settings.openai_api_key:
        raise ValueError("DEEPEXCEL_OPENAI_API_KEY is required for AI investigation planning")
    return InvestigationPlanner()
