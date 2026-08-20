"""候选根因的人工确认与排除。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from api.app.domain import Hypothesis, HypothesisDecision, InvestigationCase
from api.app.services.investigation.repository import InvestigationRepository

DecisionOutcome = Literal["confirmed", "rejected"]


def decide_hypothesis(
    case_id: str,
    hypothesis_id: str,
    *,
    outcome: DecisionOutcome,
    actor_id: str,
    note: str,
    repository: InvestigationRepository | None = None,
) -> InvestigationCase:
    """由明确的人工作出根因确认或排除决定，并保存审计信息。"""
    normalized_actor = actor_id.strip()
    normalized_note = note.strip()
    if not normalized_actor:
        raise ValueError("actor_id must not be empty")
    if not normalized_note:
        raise ValueError("decision note must not be empty")

    repo = repository or InvestigationRepository()
    case = repo.load(case_id)
    target_index = next(
        (index for index, item in enumerate(case.hypotheses) if item.id == hypothesis_id),
        None,
    )
    if target_index is None:
        raise KeyError(f"hypothesis not found: {hypothesis_id}")

    current = case.hypotheses[target_index]
    if current.status in {"confirmed", "rejected"}:
        raise ValueError(f"hypothesis {hypothesis_id} already has a final decision")

    decision = HypothesisDecision(
        outcome=outcome,
        actor_type="human",
        actor_id=normalized_actor,
        note=normalized_note,
    )
    hypothesis_payload = current.model_dump()
    hypothesis_payload.update(
        {
            "status": outcome,
            "decision": decision,
        }
    )
    decided = Hypothesis.model_validate(hypothesis_payload)

    hypotheses = list(case.hypotheses)
    hypotheses[target_index] = decided
    case_payload = case.model_dump()
    case_payload.update(
        {
            "state": "waiting_for_user",
            "hypotheses": hypotheses,
            "updated_at": datetime.now(UTC),
        }
    )
    updated = InvestigationCase.model_validate(case_payload)
    repo.save(updated)
    return updated
