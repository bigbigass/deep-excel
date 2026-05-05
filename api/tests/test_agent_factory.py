import pytest
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


def test_build_report_planner_requires_api_key(monkeypatch) -> None:
    monkeypatch.setenv("DEEPEXCEL_OPENAI_API_KEY", "")
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        factory.build_report_planner()


def test_build_report_planner_uses_deep_agent_with_key(monkeypatch) -> None:
    monkeypatch.setenv("DEEPEXCEL_MODEL_NAME", "gpt-5.4")
    monkeypatch.setenv("DEEPEXCEL_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("DEEPEXCEL_OPENAI_BASE_URL", "http://example.test/v1")
    get_settings.cache_clear()

    planner = factory.build_report_planner()

    assert isinstance(planner, factory.DeepAgentPlanner)


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
                        template_reason="\u5df2\u9009\u62e9\u5c55\u793a\u578b\u62a5\u544a\u6a21\u677f\u3002",
                        executive_summary="\u8fc7\u7a0b\u6574\u4f53\u7a33\u5b9a\uff0c\u9002\u5408\u5bf9\u5916\u6f14\u793a\u3002",
                        quality_risk="\u5f53\u524d\u8d28\u91cf\u98ce\u9669\u8f83\u4f4e\uff0c\u4f46\u4ecd\u9700\u5173\u6ce8\u6279\u6b21\u6ce2\u52a8\u3002",
                        recommended_actions=["\u6301\u7eed\u8ddf\u8e2a\u540e\u7eed\u6279\u6b21", "\u4fdd\u7559\u5f53\u524d\u62bd\u68c0\u9891\u7387"],
                    )
                }

    monkeypatch.setattr(factory, "create_deep_agent", lambda **kwargs: FakeAgent())

    analysis = _analysis(recommended_charts=["xbar_r"], out_of_spec_count=0)
    planner = factory.DeepAgentPlanner()
    report = planner.plan(job_id="JOB-1234", analysis=analysis)

    assert report.template_decision.template_id == "template_c_showcase"
    assert report.template_decision.reason == "已选择展示型报告模板。"
    assert report.ai_narrative.executive_summary == "过程整体稳定，适合对外演示。"
    assert report.ai_narrative.quality_risk == "当前质量风险较低，但仍需关注批次波动。"
    assert report.ai_narrative.recommended_actions == ["持续跟踪后续批次", "保留当前抽检频率"]


def test_deep_agent_planner_rejects_english_agent_text(monkeypatch) -> None:
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
                    recommended_actions=["Recheck the flagged sample", "Keep the current sampling cadence"],
                )
            }

    monkeypatch.setattr(factory, "create_deep_agent", lambda **kwargs: FakeAgent())

    planner = factory.DeepAgentPlanner()

    with pytest.raises(ValueError, match="Chinese"):
        planner.plan(job_id="JOB-1234", analysis=_analysis())


def test_deep_agent_planner_rejects_invalid_template_id(monkeypatch) -> None:
    monkeypatch.setenv("DEEPEXCEL_MODEL_NAME", "gpt-5.4")
    monkeypatch.setenv("DEEPEXCEL_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("DEEPEXCEL_OPENAI_BASE_URL", "http://example.test/v1")
    get_settings.cache_clear()

    class FakeAgent:
        def invoke(self, payload):
                return {
                    "structured_response": factory.AgentPlanResponse(
                        template_id="template_not_allowed",
                        template_reason="\u6a21\u677f\u9009\u62e9\u8d85\u51fa\u5141\u8bb8\u8303\u56f4\u3002",
                        executive_summary="\u8fd9\u662f\u4e00\u6bb5\u4e2d\u6587\u603b\u7ed3\u3002",
                        quality_risk="\u8fd9\u662f\u4e00\u6bb5\u4e2d\u6587\u98ce\u9669\u63cf\u8ff0\u3002",
                        recommended_actions=["\u68c0\u67e5\u6a21\u677f\u914d\u7f6e", "\u91cd\u65b0\u751f\u6210\u8ba1\u5212"],
                    )
                }

    monkeypatch.setattr(factory, "create_deep_agent", lambda **kwargs: FakeAgent())

    planner = factory.DeepAgentPlanner()

    with pytest.raises(ValueError, match="template_id"):
        planner.plan(job_id="JOB-1234", analysis=_analysis(out_of_spec_count=0))
