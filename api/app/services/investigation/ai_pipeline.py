"""Orchestrates bounded planning, deterministic tool execution, and grounded synthesis."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from api.app.agent.evidence_synthesizer import (
    EvidenceSynthesizer,
    build_evidence_synthesizer,
    materialize_synthesis,
)
from api.app.agent.investigation_planner import (
    InvestigationPlanner,
    build_investigation_planner,
)
from api.app.domain import InvestigationCase
from api.app.domain.ai import EvidenceGroundedInvestigationResult
from api.app.services.investigation.tool_registry import (
    InvestigationToolRegistry,
    build_default_tool_registry,
)


def _deduplicate_text(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        candidate = value.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        result.append(candidate)
    return result


def run_evidence_grounded_ai(
    case: InvestigationCase,
    frame: pd.DataFrame,
    *,
    planner: InvestigationPlanner | None = None,
    synthesizer: EvidenceSynthesizer | None = None,
    registry: InvestigationToolRegistry | None = None,
) -> EvidenceGroundedInvestigationResult:
    """Run AI only around a whitelist of deterministic evidence-producing tools."""

    if case.state not in {"ready", "waiting_for_user"}:
        raise ValueError("AI investigation requires a ready or waiting_for_user case")

    resolved_registry = registry or build_default_tool_registry()
    resolved_planner = planner or build_investigation_planner()
    resolved_synthesizer = synthesizer or build_evidence_synthesizer()

    tool_descriptions = resolved_registry.describe(frame)
    plan = resolved_planner.plan(
        case=case,
        available_columns=[str(column) for column in frame.columns],
        tools=tool_descriptions,
    )
    resolved_registry.validate_plan(plan, frame)

    existing_evidence_ids = {item.id for item in case.evidence}
    added_evidence = resolved_registry.execute_plan(
        plan,
        frame,
        existing_evidence_ids=existing_evidence_ids,
        source_refs=case.source_refs,
    )
    all_evidence = [*case.evidence, *added_evidence]

    draft = resolved_synthesizer.synthesize(case=case, evidence=all_evidence)
    findings, hypotheses, actions = materialize_synthesis(
        draft,
        evidence=all_evidence,
        existing_hypothesis_ids={item.id for item in case.hypotheses},
        existing_action_ids={item.id for item in case.actions},
    )
    missing_data = _deduplicate_text(
        [
            *case.missing_data,
            *plan.missing_information,
            *draft.missing_data,
        ]
    )

    return EvidenceGroundedInvestigationResult(
        plan=plan,
        added_evidence=added_evidence,
        findings=findings,
        hypotheses=hypotheses,
        actions=actions,
        missing_data=missing_data,
    )


def apply_ai_result_to_case(
    case: InvestigationCase,
    result: EvidenceGroundedInvestigationResult,
) -> InvestigationCase:
    """Merge validated AI output into a case without creating a final conclusion."""

    payload = case.model_dump()
    payload.update(
        {
            "state": "waiting_for_user",
            "evidence": [*case.evidence, *result.added_evidence],
            "hypotheses": [*case.hypotheses, *result.hypotheses],
            "actions": [*case.actions, *result.actions],
            "missing_data": result.missing_data,
            "conclusion": None,
            "error": None,
            "updated_at": datetime.now(UTC),
        }
    )
    return InvestigationCase.model_validate(payload)
