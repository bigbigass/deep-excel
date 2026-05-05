"""AI 报表规划器工厂。

这里负责把“确定性统计结果”交给大模型，换回“适合报表展示的结构化内容”。

这个模块的边界很重要：
- 不在这里重新计算统计量；
- 不让模型随意输出任意结构；
- 最终仍然要把模型结果收敛成 `ReportSpec` 这种受控对象。
"""

from __future__ import annotations

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
    chart_title,
    has_cjk_text,
    report_metric_label,
)

ALLOWED_TEMPLATE_IDS = {
    "template_a_overview",
    "template_b_detailed",
    "template_c_showcase",
}
# 模型只能在这几个模板里选，避免输出仓库里不存在的模板编号。


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
    """把模型输出和统计结果装配成统一的报表规格。

    这里相当于 AI 层和渲染层之间的适配器：
    上游给的是分析结果和模型回答，下游要的是固定字段完整的 `ReportSpec`。
    """
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


def _build_agent_user_prompt(*, job_id: str, analysis: dict[str, object]) -> str:
    """把统计结果压缩成单条提示词，降低模型理解成本。

    这里故意只给“摘要统计”，不直接塞原始明细表，
    目的是把模型职责限制在“组织报表内容”而不是“重新做分析”。
    """
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
    """构造 Deep Agent 调用载荷。

    当前只发一条 user message，因为统计上下文已经被压缩得足够小，
    不需要额外的多轮对话历史。
    """
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


def _coerce_message_text(content: object) -> str:
    """兼容字符串和分块消息两种返回格式。

    这是为了兼容不同模型/SDK 可能返回的 content 结构差异。
    """
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
    """从模型原始文本中提取 JSON 主体，兼容代码块包裹。

    当前主流程依赖 `response_format`，这个函数更多是保留给测试或回退场景。
    """
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


def coerce_message_text(content: object) -> str:
    return _coerce_message_text(content)


def extract_json_object(raw_text: str) -> str:
    return _extract_json_object(raw_text)


def _require_allowed_template_id(template_id: str) -> str:
    """限制模板编号只能来自预定义演示模板。

    即使模型语义上回答正确，只要模板编号不在白名单里，也直接拒绝。
    """
    candidate = template_id.strip()
    if candidate not in ALLOWED_TEMPLATE_IDS:
        raise ValueError("template_id must be one of the allowed template ids")
    return candidate


def _require_chinese_text(value: str, field_name: str) -> str:
    """校验模型输出的关键叙述字段为非空中文文本。

    这里不是做语言学判断，只是做最基本的防线：
    防止模型返回空串、英文、或明显不符合前端展示预期的内容。
    """
    candidate = value.strip()
    if not candidate:
        raise ValueError(f"{field_name} must not be empty")
    if not has_cjk_text(candidate):
        raise ValueError(f"{field_name} must contain Chinese text")
    return candidate


def _require_chinese_list(values: list[str], field_name: str) -> list[str]:
    """校验动作建议列表具备最小数量且全部为中文。

    目前前端和模板都默认至少展示两条动作建议，所以这里把约束前置到后端。
    """
    candidates = [value.strip() for value in values if value.strip()]
    if len(candidates) < 2:
        raise ValueError(f"{field_name} must contain at least two Chinese items")
    if not all(has_cjk_text(value) for value in candidates):
        raise ValueError(f"{field_name} must contain Chinese text")
    return candidates


class AgentPlanResponse(BaseModel):
    """主代理结构化输出协议。

    Deep Agent 先生成这个轻量结构，再由代码进一步校验并拼成完整报表对象。
    """

    template_id: str
    template_reason: str
    executive_summary: str
    quality_risk: str
    recommended_actions: list[str]


class DeepAgentPlanner:
    """基于 Deep Agents 的报表规划器。

    这个类只关心一件事：把统计分析结果转成受控的中文报表规划结果。
    """

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.openai_api_key:
            raise ValueError("DEEPEXCEL_OPENAI_API_KEY is required for AI report planning")
        self.model = build_agent_model()
        # 主代理负责总体编排，子代理分别辅助理解数据和撰写质量结论。
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

    def plan(self, *, job_id: str, analysis: dict[str, object]) -> ReportSpec:
        """调用 AI 规划器，并把结果收敛为可渲染的 `ReportSpec`。

        这里不会盲信模型输出，而是经过三层收口：
        1. Pydantic 结构校验。
        2. 模板编号和中文文本约束校验。
        3. 用 `_build_report_spec()` 重组为内部标准对象。
        """
        result = self.agent.invoke(_build_agent_payload(job_id=job_id, analysis=analysis))
        structured = AgentPlanResponse.model_validate(result["structured_response"])

        return _build_report_spec(
            job_id=job_id,
            analysis=analysis,
            template_id=_require_allowed_template_id(structured.template_id),
            template_reason=_require_chinese_text(structured.template_reason, "template_reason"),
            executive_summary=_require_chinese_text(structured.executive_summary, "executive_summary"),
            quality_risk=_require_chinese_text(structured.quality_risk, "quality_risk"),
            recommended_actions=_require_chinese_list(structured.recommended_actions, "recommended_actions"),
        )


def build_agent_model(**kwargs: object) -> ChatOpenAI:
    """按项目统一配置构造 OpenAI 兼容聊天模型。

    这样字段映射规划器和报表规划器可以共享一套模型配置来源。
    """
    settings = get_settings()
    return ChatOpenAI(
        model=settings.model_name,
        api_key=settings.openai_api_key,
        base_url=resolve_openai_base_url(settings.openai_base_url),
        **kwargs,
    )


def build_report_planner() -> DeepAgentPlanner:
    """创建报表规划器实例，并提前校验关键配置。

    这里不做懒失败，缺少密钥时直接报错，避免任务线程跑到一半才发现 AI 不可用。
    """
    settings = get_settings()
    if not settings.openai_api_key:
        raise ValueError("DEEPEXCEL_OPENAI_API_KEY is required for AI report planning")
    return DeepAgentPlanner()
