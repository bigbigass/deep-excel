from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

from api.app.agent import factory
from api.app.config import get_settings


def _analysis(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "mean": 10.01,
        "std_dev": 0.01,
        "pass_rate": 0.99,
        "cpk": 1.42,
        "out_of_spec_count": 1,
        "recommended_charts": ["control_chart_imr", "histogram"],
        "anomalies": [{"sample_id": "A-003", "reason": "above usl"}],
    }
    payload.update(overrides)
    return payload


def test_deep_agent_planner_builds_openai_compatible_model(monkeypatch) -> None:
    monkeypatch.setenv("DEEPEXCEL_MODEL_NAME", "gpt-5.4")
    monkeypatch.setenv("DEEPEXCEL_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("DEEPEXCEL_OPENAI_BASE_URL", "http://example.test/v1")
    get_settings.cache_clear()

    captured: dict[str, object] = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(factory, "create_deep_agent", fake_create_deep_agent)

    factory.DeepAgentPlanner()

    assert isinstance(captured["model"], ChatOpenAI)
    model = captured["model"].model_dump()
    assert model["model_name"] == "gpt-5.4"
    assert model["openai_api_base"] == "http://example.test/v1"


def test_build_report_planner_keeps_rule_fallback_without_key(monkeypatch) -> None:
    monkeypatch.setenv("DEEPEXCEL_OPENAI_API_KEY", "")
    monkeypatch.setenv("DEEPEXCEL_OPENAI_BASE_URL", "http://example.test/v1")
    get_settings.cache_clear()

    planner = factory.build_report_planner()

    assert isinstance(planner, factory.RuleBasedReportPlanner)
    assert not isinstance(planner, factory.DeepAgentPlanner)


def test_build_report_planner_uses_deep_agent_with_key(monkeypatch) -> None:
    monkeypatch.setenv("DEEPEXCEL_MODEL_NAME", "gpt-5.4")
    monkeypatch.setenv("DEEPEXCEL_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("DEEPEXCEL_OPENAI_BASE_URL", "http://example.test/v1")
    get_settings.cache_clear()

    planner = factory.build_report_planner()

    assert isinstance(planner, factory.DeepAgentPlanner)


def test_rule_based_report_planner_outputs_chinese_content() -> None:
    planner = factory.RuleBasedReportPlanner()
    analysis = _analysis(cpk=0.88)

    report = planner.plan(job_id="JOB-LOCAL", analysis=analysis)

    assert report.report_meta.title == factory.DEFAULT_REPORT_TITLE
    assert report.kpi_cards[0].label == factory.report_metric_label("mean")
    assert report.chart_specs[0].title == factory.chart_title("control_chart_imr")
    assert report.ai_narrative.executive_summary == factory.build_executive_summary(analysis)
    assert report.ai_narrative.quality_risk == factory.build_quality_risk(analysis)
    assert report.ai_narrative.recommended_actions == factory.build_recommended_actions(analysis)


def test_rule_based_report_planner_uses_detailed_template_for_borderline_process() -> None:
    planner = factory.RuleBasedReportPlanner()

    report = planner.plan(
        job_id="JOB-BORDERLINE",
        analysis=_analysis(
            cpk=0.92,
            out_of_spec_count=0,
            pass_rate=1.0,
            anomalies=[{"type": "control_limit", "severity": "medium"}],
        ),
    )

    assert report.template_decision.template_id == "template_b_detailed"


def test_build_agent_model_normalizes_root_base_url(monkeypatch) -> None:
    monkeypatch.setenv("DEEPEXCEL_MODEL_NAME", "gpt-5.4")
    monkeypatch.setenv("DEEPEXCEL_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("DEEPEXCEL_OPENAI_BASE_URL", "http://example.test:8080")
    get_settings.cache_clear()

    model = factory.build_agent_model()

    assert model.model_dump()["openai_api_base"] == "http://example.test:8080/v1"


def test_deep_agent_planner_plan_uses_agent_response(monkeypatch) -> None:
    monkeypatch.setenv("DEEPEXCEL_MODEL_NAME", "gpt-5.4")
    monkeypatch.setenv("DEEPEXCEL_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("DEEPEXCEL_OPENAI_BASE_URL", "http://example.test/v1")
    get_settings.cache_clear()

    class FakeAgent:
        def invoke(self, payload):
            return {
                "structured_response": factory.AgentPlanResponse(
                    template_id="template_c_showcase",
                    template_reason="\u9002\u5408\u7528\u4e8e\u7ba1\u7406\u5c42\u603b\u89c8\u5c55\u793a",
                    executive_summary="\u8fc7\u7a0b\u6574\u4f53\u7a33\u5b9a\uff0c\u4f46\u5b58\u5728\u4e00\u4e2a\u5f02\u5e38\u70b9\u3002",
                    quality_risk="\u5efa\u8bae\u6301\u7eed\u5173\u6ce8\u4e0b\u4e00\u6279\u6b21\u7684\u6f02\u79fb\u60c5\u51b5\u3002",
                    recommended_actions=[
                        "\u590d\u6838\u5f02\u5e38\u6837\u672c",
                        "\u4fdd\u6301\u5f53\u524d\u62bd\u68c0\u9891\u7387",
                    ],
                )
            }

    monkeypatch.setattr(factory, "create_deep_agent", lambda **kwargs: FakeAgent())

    planner = factory.DeepAgentPlanner()
    report = planner.plan(
        job_id="JOB-1234",
        analysis=_analysis(
            recommended_charts=["xbar_r", "histogram"],
            out_of_spec_count=0,
            pass_rate=1.0,
            anomalies=[{"type": "control_limit", "severity": "medium"}],
        ),
    )

    assert report.template_decision.template_id == "template_c_showcase"
    assert report.report_meta.title == factory.DEFAULT_REPORT_TITLE
    assert report.kpi_cards[0].label == factory.report_metric_label("mean")
    assert report.chart_specs[0].title == factory.chart_title("xbar_r")
    assert report.template_decision.reason == "\u9002\u5408\u7528\u4e8e\u7ba1\u7406\u5c42\u603b\u89c8\u5c55\u793a"
    assert report.ai_narrative.executive_summary == "\u8fc7\u7a0b\u6574\u4f53\u7a33\u5b9a\uff0c\u4f46\u5b58\u5728\u4e00\u4e2a\u5f02\u5e38\u70b9\u3002"
    assert report.ai_narrative.quality_risk == "\u5efa\u8bae\u6301\u7eed\u5173\u6ce8\u4e0b\u4e00\u6279\u6b21\u7684\u6f02\u79fb\u60c5\u51b5\u3002"


def test_deep_agent_planner_localizes_english_agent_text(monkeypatch) -> None:
    monkeypatch.setenv("DEEPEXCEL_MODEL_NAME", "gpt-5.4")
    monkeypatch.setenv("DEEPEXCEL_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("DEEPEXCEL_OPENAI_BASE_URL", "http://example.test/v1")
    get_settings.cache_clear()

    class FakeAgent:
        def invoke(self, payload):
            return {
                "structured_response": factory.AgentPlanResponse(
                    template_id="template_c_showcase",
                    template_reason="Chosen for executive review",
                    executive_summary="Process is stable with one visible anomaly.",
                    quality_risk="Monitor drift on the next batch.",
                    recommended_actions=[
                        "Recheck the flagged sample",
                        "Keep the current sampling cadence",
                    ],
                )
            }

    monkeypatch.setattr(factory, "create_deep_agent", lambda **kwargs: FakeAgent())

    analysis = _analysis()
    planner = factory.DeepAgentPlanner()
    report = planner.plan(job_id="JOB-1234", analysis=analysis)

    assert report.template_decision.reason == factory.DEFAULT_TEMPLATE_REASON
    assert report.ai_narrative.executive_summary == factory.build_executive_summary(analysis)
    assert report.ai_narrative.quality_risk == factory.build_quality_risk(analysis)
    assert report.ai_narrative.recommended_actions == factory.build_recommended_actions(analysis)


def test_deep_agent_planner_falls_back_to_plain_json_model_response(monkeypatch) -> None:
    monkeypatch.setenv("DEEPEXCEL_MODEL_NAME", "gpt-5.4")
    monkeypatch.setenv("DEEPEXCEL_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("DEEPEXCEL_OPENAI_BASE_URL", "http://example.test/v1")
    get_settings.cache_clear()

    class FakeAgent:
        def invoke(self, payload):
            raise ValueError("native structured output failed")

    class FakeModel:
        def invoke(self, messages):
            return AIMessage(
                content=(
                    "```json\n"
                    "{\n"
                    '  "template_id": "template_b_detailed",\n'
                    '  "template_reason": "\u8fc7\u7a0b\u4ecd\u5728\u89c4\u683c\u5185\uff0c\u4f46\u80fd\u529b\u504f\u5f31\uff0c\u9002\u5408\u8be6\u7ec6\u590d\u6838\u3002",\n'
                    '  "executive_summary": "\u8fc7\u7a0b\u5747\u503c\u8d34\u8fd1\u4e0a\u9650\uff0c\u5efa\u8bae\u5de5\u7a0b\u4fa7\u7ee7\u7eed\u8ffd\u8e2a\u6f02\u79fb\u3002",\n'
                    '  "quality_risk": "\u77ed\u671f\u5185\u65e0\u505c\u7ebf\u98ce\u9669\uff0c\u4f46\u540e\u7eed\u6279\u6b21\u5b58\u5728\u8fb9\u754c\u5931\u63a7\u53ef\u80fd\u3002",\n'
                    '  "recommended_actions": ["\u590d\u6838\u91cf\u5177\u504f\u79fb", "\u589e\u52a0\u4e0b\u4e00\u6279\u6b21\u62bd\u68c0\u9891\u7387"]\n'
                    "}\n"
                    "```"
                )
            )

    monkeypatch.setattr(factory, "build_agent_model", lambda **kwargs: FakeModel())
    monkeypatch.setattr(factory, "create_deep_agent", lambda **kwargs: FakeAgent())

    planner = factory.DeepAgentPlanner()
    report = planner.plan(
        job_id="JOB-1234",
        analysis=_analysis(
            cpk=0.92,
            out_of_spec_count=0,
            pass_rate=1.0,
            anomalies=[{"type": "control_limit", "severity": "medium"}],
        ),
    )

    assert report.template_decision.template_id == "template_b_detailed"
    assert report.template_decision.reason == "\u8fc7\u7a0b\u4ecd\u5728\u89c4\u683c\u5185\uff0c\u4f46\u80fd\u529b\u504f\u5f31\uff0c\u9002\u5408\u8be6\u7ec6\u590d\u6838\u3002"
    assert report.ai_narrative.executive_summary == "\u8fc7\u7a0b\u5747\u503c\u8d34\u8fd1\u4e0a\u9650\uff0c\u5efa\u8bae\u5de5\u7a0b\u4fa7\u7ee7\u7eed\u8ffd\u8e2a\u6f02\u79fb\u3002"
    assert report.ai_narrative.quality_risk == "\u77ed\u671f\u5185\u65e0\u505c\u7ebf\u98ce\u9669\uff0c\u4f46\u540e\u7eed\u6279\u6b21\u5b58\u5728\u8fb9\u754c\u5931\u63a7\u53ef\u80fd\u3002"
    assert report.ai_narrative.recommended_actions == [
        "\u590d\u6838\u91cf\u5177\u504f\u79fb",
        "\u589e\u52a0\u4e0b\u4e00\u6279\u6b21\u62bd\u68c0\u9891\u7387",
    ]
