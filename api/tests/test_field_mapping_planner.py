from pathlib import Path

import pandas as pd
import pytest

from api.app.agent import field_mapping_planner
from api.app.config import get_settings

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "ambiguous_columns.csv"


def load_fixture_frame() -> pd.DataFrame:
    return pd.read_csv(FIXTURE_PATH)


class FakeStructuredInvoker:
    def __init__(self, response: object) -> None:
        self.response = response

    def invoke(self, messages: object) -> object:
        return self.response


class FakeModel:
    def __init__(self, response: object) -> None:
        self.response = response

    def with_structured_output(self, schema: object) -> FakeStructuredInvoker:
        return FakeStructuredInvoker(self.response)


class FakePlainJsonModel(FakeModel):
    def invoke(self, messages: object) -> object:
        raise AssertionError("plain JSON fallback should not be used")


def test_build_field_mapping_planner_requires_api_key(monkeypatch) -> None:
    monkeypatch.setenv("DEEPEXCEL_OPENAI_API_KEY", "")
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        field_mapping_planner.build_field_mapping_planner()


def test_llm_planner_uses_mocked_response(monkeypatch) -> None:
    monkeypatch.setenv("DEEPEXCEL_OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()

    fake_response = field_mapping_planner.FieldMappingPlanResponse(
        sample_id_column="sample_code",
        batch_column="batch_code",
        measurement_column="diameter_mm",
        lsl_column="spec_lower",
        usl_column="spec_upper",
        target_column=None,
        timestamp_column="measured_time",
        sequence_column=None,
        reasoning="AI \u5df2\u8bc6\u522b diameter_mm \u4e3a\u6d4b\u91cf\u5217\uff0cspec_upper / spec_lower \u4e3a\u89c4\u683c\u4e0a\u4e0b\u9650\u3002",
    )
    monkeypatch.setattr(field_mapping_planner, "build_agent_model", lambda **kwargs: FakePlainJsonModel(fake_response))

    planner = field_mapping_planner.FieldMappingPlanner()
    mapping, reasoning = planner.plan(load_fixture_frame(), "ambiguous_columns.csv")

    assert mapping.measurement_column == "diameter_mm"
    assert mapping.lsl_column == "spec_lower"
    assert mapping.usl_column == "spec_upper"
    assert mapping.timestamp_column == "measured_time"
    assert reasoning == "AI 已识别 diameter_mm 为测量列，spec_upper / spec_lower 为规格上下限。"


def test_llm_planner_rejects_hallucinated_column(monkeypatch) -> None:
    monkeypatch.setenv("DEEPEXCEL_OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()

    fake_response = field_mapping_planner.FieldMappingPlanResponse(
        sample_id_column="sample_code",
        batch_column="batch_code",
        measurement_column="not_a_real_column",
        lsl_column="spec_lower",
        usl_column="spec_upper",
        target_column=None,
        timestamp_column="measured_time",
        sequence_column=None,
        reasoning="AI \u8fd4\u56de\u4e86\u4e0d\u5b58\u5728\u7684\u5217\u540d\u3002",
    )
    monkeypatch.setattr(field_mapping_planner, "build_agent_model", lambda **kwargs: FakePlainJsonModel(fake_response))

    planner = field_mapping_planner.FieldMappingPlanner()

    with pytest.raises(ValueError, match="measurement"):
        planner.plan(load_fixture_frame(), "ambiguous_columns.csv")


def test_llm_planner_rejects_english_reasoning(monkeypatch) -> None:
    monkeypatch.setenv("DEEPEXCEL_OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()

    fake_response = field_mapping_planner.FieldMappingPlanResponse(
        sample_id_column="sample_code",
        batch_column="batch_code",
        measurement_column="diameter_mm",
        lsl_column="spec_lower",
        usl_column="spec_upper",
        target_column=None,
        timestamp_column="measured_time",
        sequence_column=None,
        reasoning="Mapped diameter_mm as the measurement column.",
    )
    monkeypatch.setattr(field_mapping_planner, "build_agent_model", lambda **kwargs: FakePlainJsonModel(fake_response))

    planner = field_mapping_planner.FieldMappingPlanner()

    with pytest.raises(ValueError, match="Chinese"):
        planner.plan(load_fixture_frame(), "ambiguous_columns.csv")
