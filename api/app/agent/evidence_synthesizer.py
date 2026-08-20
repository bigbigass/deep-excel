"""Evidence-referenced synthesis for quality investigation findings and hypotheses."""

from __future__ import annotations

import json
import re
from typing import Protocol

from api.app.agent.factory import build_agent_model
from api.app.config import get_settings
from api.app.domain import EvidenceItem, Hypothesis, InvestigationAction, InvestigationCase
from api.app.domain.ai import InvestigationFinding, InvestigationSynthesisDraft

_UNCERTAINTY_MARKERS = ("可能", "候选", "待验证", "需要验证", "优先验证", "疑似")
_FORBIDDEN_CONFIRMATION_PATTERNS = (
    re.compile(r"已确认"),
    re.compile(r"根因(?:就)?是"),
    re.compile(r"确定由"),
    re.compile(r"证明.{0,12}导致"),
    re.compile(r"必然由"),
    re.compile(r"就是.{0,12}导致"),
)
_CAUSAL_WORDS = ("根因", "导致", "造成")
_NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?%?")
_ALPHANUMERIC_PATTERN = re.compile(r"[A-Za-z]+\d+[A-Za-z0-9]*")


class StructuredOutputInvoker(Protocol):
    def invoke(self, messages: list[dict[str, str]]) -> object:
        ...


class StructuredOutputModel(Protocol):
    def with_structured_output(
        self,
        schema: type[InvestigationSynthesisDraft],
    ) -> StructuredOutputInvoker:
        ...


def _compact_json_value(value: object, *, list_limit: int = 12) -> object:
    if isinstance(value, dict):
        return {
            str(key): _compact_json_value(item, list_limit=list_limit)
            for key, item in value.items()
        }
    if isinstance(value, list):
        compacted = [
            _compact_json_value(item, list_limit=list_limit)
            for item in value[:list_limit]
        ]
        if len(value) > list_limit:
            compacted.append({"truncated_item_count": len(value) - list_limit})
        return compacted
    if isinstance(value, str) and len(value) > 800:
        return value[:800] + "…"
    return value


def _build_synthesis_messages(
    *,
    case: InvestigationCase,
    evidence: list[EvidenceItem],
) -> list[dict[str, str]]:
    payload = {
        "question": case.question,
        "scope": case.scope.model_dump(mode="json"),
        "evidence": [
            _compact_json_value(item.model_dump(mode="json"))
            for item in evidence
        ],
    }
    return [
        {
            "role": "system",
            "content": (
                "You synthesize a Chinese manufacturing quality investigation from supplied evidence only. "
                "Every finding and action must cite evidence IDs. "
                "Findings may describe observed facts or statistical associations, never confirmed causality. "
                "Every root-cause statement must remain an uncertain candidate and include language such as "
                "可能、候选、待验证 or 需要验证. "
                "Do not invent measurements, percentages, dates, equipment IDs, sample sizes, or events. "
                "Do not call a hypothesis confirmed or rejected. "
                "Return no more than eight findings, four hypotheses, and four containment actions."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        },
    ]


def _evidence_by_id(evidence: list[EvidenceItem]) -> dict[str, EvidenceItem]:
    result = {item.id: item for item in evidence}
    if len(result) != len(evidence):
        raise ValueError("evidence ids must be unique before AI synthesis")
    return result


def _require_known_evidence(
    evidence_ids: list[str],
    *,
    known_evidence: dict[str, EvidenceItem],
    label: str,
) -> list[EvidenceItem]:
    unknown = sorted(set(evidence_ids) - set(known_evidence))
    if unknown:
        raise ValueError(f"{label} references unknown evidence ids: {unknown}")
    return [known_evidence[evidence_id] for evidence_id in evidence_ids]


def _reject_confirmed_language(value: str, *, label: str) -> None:
    for pattern in _FORBIDDEN_CONFIRMATION_PATTERNS:
        if pattern.search(value):
            raise ValueError(f"{label} contains confirmed root-cause language")


def _validate_grounded_tokens(
    value: str,
    *,
    cited_evidence: list[EvidenceItem],
    label: str,
) -> None:
    corpus = json.dumps(
        [item.model_dump(mode="json") for item in cited_evidence],
        ensure_ascii=False,
        sort_keys=True,
    ).lower()
    tokens = set(_NUMBER_PATTERN.findall(value))
    tokens.update(token.lower() for token in _ALPHANUMERIC_PATTERN.findall(value))
    unsupported = sorted(token for token in tokens if token.lower() not in corpus)
    if unsupported:
        raise ValueError(f"{label} contains values not present in cited evidence: {unsupported}")


def validate_synthesis_grounding(
    draft: InvestigationSynthesisDraft,
    *,
    evidence: list[EvidenceItem],
) -> None:
    known_evidence = _evidence_by_id(evidence)

    for index, finding in enumerate(draft.findings, start=1):
        cited = _require_known_evidence(
            finding.evidence_ids,
            known_evidence=known_evidence,
            label=f"finding {index}",
        )
        _reject_confirmed_language(finding.statement, label=f"finding {index}")
        if finding.finding_type == "fact" and any(word in finding.statement for word in _CAUSAL_WORDS):
            raise ValueError(f"finding {index} labels a causal claim as fact")
        _validate_grounded_tokens(
            finding.statement,
            cited_evidence=cited,
            label=f"finding {index}",
        )

    for hypothesis in draft.hypotheses:
        cited_ids = hypothesis.supporting_evidence_ids + hypothesis.contradicting_evidence_ids
        cited = _require_known_evidence(
            cited_ids,
            known_evidence=known_evidence,
            label=f"hypothesis {hypothesis.key}",
        )
        _reject_confirmed_language(
            hypothesis.statement,
            label=f"hypothesis {hypothesis.key}",
        )
        if not any(marker in hypothesis.statement for marker in _UNCERTAINTY_MARKERS):
            raise ValueError(
                f"hypothesis {hypothesis.key} must use explicit uncertainty language"
            )
        _validate_grounded_tokens(
            hypothesis.statement,
            cited_evidence=cited,
            label=f"hypothesis {hypothesis.key}",
        )

    for index, action in enumerate(draft.containment_actions, start=1):
        _require_known_evidence(
            action.supporting_evidence_ids,
            known_evidence=known_evidence,
            label=f"containment action {index}",
        )


def _next_generated_id(prefix: str, used_ids: set[str], start: int) -> tuple[str, int]:
    number = start
    while True:
        candidate = f"{prefix}-{number:03d}"
        number += 1
        if candidate not in used_ids:
            used_ids.add(candidate)
            return candidate, number


def materialize_synthesis(
    draft: InvestigationSynthesisDraft,
    *,
    evidence: list[EvidenceItem],
    existing_finding_ids: set[str] | None = None,
    existing_hypothesis_ids: set[str] | None = None,
    existing_action_ids: set[str] | None = None,
) -> tuple[
    list[InvestigationFinding],
    list[Hypothesis],
    list[InvestigationAction],
]:
    validate_synthesis_grounding(draft, evidence=evidence)

    used_finding_ids = set(existing_finding_ids or set())
    used_hypothesis_ids = set(existing_hypothesis_ids or set())
    used_action_ids = set(existing_action_ids or set())

    findings: list[InvestigationFinding] = []
    finding_number = 1
    for item in draft.findings:
        finding_id, finding_number = _next_generated_id(
            "F-AI",
            used_finding_ids,
            finding_number,
        )
        findings.append(
            InvestigationFinding(
                id=finding_id,
                finding_type=item.finding_type,
                statement=item.statement,
                evidence_ids=item.evidence_ids,
                confidence=item.confidence,
            )
        )

    hypotheses: list[Hypothesis] = []
    hypothesis_number = 1
    for item in draft.hypotheses:
        hypothesis_id, hypothesis_number = _next_generated_id(
            "H-AI",
            used_hypothesis_ids,
            hypothesis_number,
        )
        hypotheses.append(
            Hypothesis(
                id=hypothesis_id,
                statement=item.statement,
                supporting_evidence_ids=item.supporting_evidence_ids,
                contradicting_evidence_ids=item.contradicting_evidence_ids,
                confidence=item.confidence,
                status="candidate",
                verification_actions=item.verification_actions,
                decision=None,
            )
        )

    actions: list[InvestigationAction] = []
    action_number = 1
    for item in draft.containment_actions:
        action_id, action_number = _next_generated_id(
            "A-AI",
            used_action_ids,
            action_number,
        )
        actions.append(
            InvestigationAction(
                id=action_id,
                action_type="containment",
                title=item.title,
                rationale=item.rationale,
                status="proposed",
                supporting_evidence_ids=item.supporting_evidence_ids,
            )
        )

    seen_verification_actions: set[tuple[str, str]] = set()
    for draft_hypothesis, hypothesis in zip(draft.hypotheses, hypotheses):
        for action_title in draft_hypothesis.verification_actions:
            deduplication_key = (hypothesis.id, action_title)
            if deduplication_key in seen_verification_actions:
                continue
            seen_verification_actions.add(deduplication_key)
            action_id, action_number = _next_generated_id(
                "A-AI",
                used_action_ids,
                action_number,
            )
            actions.append(
                InvestigationAction(
                    id=action_id,
                    action_type="verification",
                    title=action_title,
                    rationale=f"用于验证候选假设：{hypothesis.statement}",
                    status="proposed",
                    related_hypothesis_ids=[hypothesis.id],
                    supporting_evidence_ids=hypothesis.supporting_evidence_ids,
                )
            )

    return findings, hypotheses, actions


class EvidenceSynthesizer:
    """Produces structured drafts; code performs the actual grounding checks."""

    def __init__(self, model: StructuredOutputModel | None = None) -> None:
        self.model = model or build_agent_model()

    def synthesize(
        self,
        *,
        case: InvestigationCase,
        evidence: list[EvidenceItem],
    ) -> InvestigationSynthesisDraft:
        structured_model = self.model.with_structured_output(InvestigationSynthesisDraft)
        response = structured_model.invoke(
            _build_synthesis_messages(
                case=case,
                evidence=evidence,
            )
        )
        draft = InvestigationSynthesisDraft.model_validate(response)
        validate_synthesis_grounding(draft, evidence=evidence)
        return draft


def build_evidence_synthesizer() -> EvidenceSynthesizer:
    settings = get_settings()
    if not settings.openai_api_key:
        raise ValueError("DEEPEXCEL_OPENAI_API_KEY is required for evidence synthesis")
    return EvidenceSynthesizer()
