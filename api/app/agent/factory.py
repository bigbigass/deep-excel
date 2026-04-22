from __future__ import annotations

from dataclasses import dataclass
import json

from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from api.app.agent.subagents import DATA_UNDERSTANDING_SUBAGENT, QUALITY_ANALYST_SUBAGENT
from api.app.agent.tools import choose_template, summarize_quality
from api.app.config import get_settings, resolve_openai_base_url
from api.app.report_models import ChartSpec, KpiCard, NarrativeBlock, ReportMeta, ReportSpec, TemplateDecision
from api.app.services.report_localization import (
    DEFAULT_PRODUCT_NAME,
    DEFAULT_REPORT_TITLE,
    DEFAULT_TEMPLATE_REASON,
    build_executive_summary,
    build_quality_risk,
    build_recommended_actions,
    chart_title,
    choose_chinese_list,
    choose_chinese_text,
    report_metric_label,
)

ALLOWED_TEMPLATE_IDS = {
    "template_a_overview",
    "template_b_detailed",
    "template_c_showcase",
}


def _build_report_spec(
    *,
    job_id: str,
    analysis: dict[str, object],
    template_id: str,
    template_reason: str,
    executive_summary: str,
    quality_risk: str,
    recommended_actions: list[str],
) -> ReportSpec:
    return ReportSpec(
        report_meta=ReportMeta(
            title=DEFAULT_REPORT_TITLE,
            report_id=job_id,
            generated_at="2026-04-21T10:00:00Z",
            batch_id="DEMO-BATCH",
            product_name=DEFAULT_PRODUCT_NAME,
        ),
        template_decision=TemplateDecision(
            template_id=template_id,
            reason=template_reason,
        ),
        dataset_summary={
            "sample_count": 0,
            "overall_pass_rate": analysis["pass_rate"],
        },
        kpi_cards=[
            KpiCard(label=report_metric_label("mean"), value=f"{analysis['mean']:.3f}"),
            KpiCard(label=report_metric_label("std_dev"), value=f"{analysis['std_dev']:.3f}"),
            KpiCard(label=report_metric_label("pass_rate"), value=f"{analysis['pass_rate'] * 100:.1f}%"),
            KpiCard(label=report_metric_label("cpk"), value="n/a" if analysis["cpk"] is None else f"{analysis['cpk']:.2f}"),
        ],
        detail_rows=[],
        chart_specs=[
            ChartSpec(chart_id=name, chart_type=name, title=chart_title(name))
            for name in analysis["recommended_charts"]
        ],
        anomalies=analysis["anomalies"],
        ai_narrative=NarrativeBlock(
            executive_summary=executive_summary,
            quality_risk=quality_risk,
            recommended_actions=recommended_actions,
        ),
    )


def _default_template_id(analysis: dict[str, object]) -> str:
    return choose_template.invoke(
        {
            "has_failures": bool(analysis["out_of_spec_count"]),
            "cpk": analysis["cpk"],
        }
    )


def _normalize_template_id(template_id: str, analysis: dict[str, object]) -> str:
    default_template_id = _default_template_id(analysis)
    if bool(analysis["out_of_spec_count"]):
        return default_template_id

    candidate = template_id.strip()
    if candidate in ALLOWED_TEMPLATE_IDS:
        return candidate
    return default_template_id


def _build_agent_user_prompt(*, job_id: str, analysis: dict[str, object]) -> str:
    cpk_value = "n/a" if analysis["cpk"] is None else f"{float(analysis['cpk']):.4f}"
    return (
        f"Plan the SPC report for job {job_id}. "
        f"Mean={float(analysis['mean']):.4f}, "
        f"StdDev={float(analysis['std_dev']):.4f}, "
        f"PassRate={float(analysis['pass_rate']):.4f}, "
        f"Cpk={cpk_value}, "
        f"OutOfSpecCount={int(analysis['out_of_spec_count'])}, "
        f"RecommendedCharts={analysis['recommended_charts']}, "
        f"Anomalies={analysis['anomalies']}. "
        "Choose one template_id from template_a_overview, template_b_detailed, template_c_showcase."
    )


def _build_agent_payload(*, job_id: str, analysis: dict[str, object]) -> dict[str, object]:
    return {
        "messages": [
            {
                "role": "user",
                "content": (
                    _build_agent_user_prompt(job_id=job_id, analysis=analysis)
                    + " Return structured output with template choice, Chinese template reason, "
                    + "Chinese executive summary, Chinese quality risk, and two to three Chinese actions."
                ),
            }
        ]
    }


def _build_plain_json_messages(*, job_id: str, analysis: dict[str, object]) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are planning an SPC quality report. "
                "Return only one JSON object and no markdown. "
                "Use Chinese for template_reason, executive_summary, quality_risk, and recommended_actions. "
                "template_id must be one of template_a_overview, template_b_detailed, template_c_showcase."
            ),
        },
        {
            "role": "user",
            "content": (
                _build_agent_user_prompt(job_id=job_id, analysis=analysis)
                + ' JSON schema: {"template_id": str, "template_reason": str, '
                + '"executive_summary": str, "quality_risk": str, "recommended_actions": [str, str, ...]}.'
            ),
        },
    ]


def _coerce_message_text(content: object) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)

    return str(content)


def _extract_json_object(raw_text: str) -> str:
    candidate = raw_text.strip()

    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].startswith("```"):
            candidate = "\n".join(lines[1:-1]).strip()

    if candidate.startswith("{") and candidate.endswith("}"):
        json.loads(candidate)
        return candidate

    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model response")

    candidate = candidate[start : end + 1]
    json.loads(candidate)
    return candidate


@dataclass
class RuleBasedReportPlanner:
    def plan(self, *, job_id: str, analysis: dict[str, object]) -> ReportSpec:
        template_id = _default_template_id(analysis)
        summary = summarize_quality.invoke(
            {
                "mean_value": float(analysis["mean"]),
                "cpk": analysis["cpk"],
                "out_of_spec_count": int(analysis["out_of_spec_count"]),
            }
        )
        return _build_report_spec(
            job_id=job_id,
            analysis=analysis,
            template_id=template_id,
            template_reason=DEFAULT_TEMPLATE_REASON,
            executive_summary=summary,
            quality_risk=build_quality_risk(analysis),
            recommended_actions=build_recommended_actions(analysis),
        )


class AgentPlanResponse(BaseModel):
    template_id: str
    template_reason: str
    executive_summary: str
    quality_risk: str
    recommended_actions: list[str]


class DeepAgentPlanner(RuleBasedReportPlanner):
    def __init__(self) -> None:
        self.model = build_agent_model()
        self.agent = create_deep_agent(
            name="report-orchestrator",
            model=self.model,
            tools=[choose_template, summarize_quality],
            system_prompt=(
                "You are preparing a Chinese SPC quality report. "
                "Stay within the provided tools and keep the response concise."
            ),
            subagents=[DATA_UNDERSTANDING_SUBAGENT, QUALITY_ANALYST_SUBAGENT],
            response_format=AgentPlanResponse,
        )

    def _plan_from_plain_json_model(self, *, job_id: str, analysis: dict[str, object]) -> AgentPlanResponse:
        response = self.model.invoke(_build_plain_json_messages(job_id=job_id, analysis=analysis))
        raw_text = _coerce_message_text(getattr(response, "content", response))
        json_text = _extract_json_object(raw_text)
        return AgentPlanResponse.model_validate_json(json_text)

    def plan(self, *, job_id: str, analysis: dict[str, object]) -> ReportSpec:
        fallback_summary = build_executive_summary(analysis)
        fallback_risk = build_quality_risk(analysis)
        fallback_actions = build_recommended_actions(analysis)

        try:
            result = self.agent.invoke(_build_agent_payload(job_id=job_id, analysis=analysis))
            structured = AgentPlanResponse.model_validate(result["structured_response"])
        except Exception:
            try:
                structured = self._plan_from_plain_json_model(job_id=job_id, analysis=analysis)
            except Exception:
                return super().plan(job_id=job_id, analysis=analysis)

        return _build_report_spec(
            job_id=job_id,
            analysis=analysis,
            template_id=_default_template_id(analysis),
            template_reason=choose_chinese_text(structured.template_reason, DEFAULT_TEMPLATE_REASON),
            executive_summary=choose_chinese_text(structured.executive_summary, fallback_summary),
            quality_risk=choose_chinese_text(structured.quality_risk, fallback_risk),
            recommended_actions=choose_chinese_list(structured.recommended_actions, fallback_actions),
        )


def build_agent_model(**kwargs: object) -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(
        model=settings.model_name,
        api_key=settings.openai_api_key,
        base_url=resolve_openai_base_url(settings.openai_base_url),
        **kwargs,
    )


def build_report_planner() -> RuleBasedReportPlanner:
    settings = get_settings()
    if not settings.openai_api_key:
        return RuleBasedReportPlanner()
    return DeepAgentPlanner()
