from pathlib import Path

from api.app.config import get_settings
from api.app.services import jobs
from api.tests._planner_test_doubles import FakeFieldMappingPlanner, FakeReportPlanner

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "ambiguous_columns.csv"


def test_run_job_analysis_persists_parse_reasoning(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DEEPEXCEL_OUTPUTS_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("DEEPEXCEL_OPENAI_API_KEY", "")
    get_settings.cache_clear()

    monkeypatch.setattr(jobs, "build_field_mapping_planner", lambda: FakeFieldMappingPlanner())
    monkeypatch.setattr(jobs, "build_report_planner", lambda: FakeReportPlanner())
    monkeypatch.setattr(jobs, "generate_chart_bundle", lambda *args, **kwargs: {})

    jobs._create_job_record("JOB-TRACE01", FIXTURE_PATH)
    jobs.run_job_analysis("JOB-TRACE01", FIXTURE_PATH)

    payload = jobs.load_job("JOB-TRACE01")
    parse_task = next(task for task in payload["tasks"] if task["id"] == "parse")

    assert parse_task["status"] == "completed"
    assert parse_task["reasoning"] == "AI 已识别 diameter_mm 为测量列，spec_lower / spec_upper 为规格上下限。"
    assert any("一" <= char <= "鿿" for char in parse_task["reasoning"])
