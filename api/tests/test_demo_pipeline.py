from pathlib import Path

from api.app.services import jobs
from api.tests._planner_test_doubles import FakeFieldMappingPlanner, FakeReportPlanner


def test_demo_pipeline_from_sample_data(monkeypatch) -> None:
    sample_path = Path("sample_data/out_of_spec_batch.csv")
    monkeypatch.setattr(jobs, "build_field_mapping_planner", lambda: FakeFieldMappingPlanner())
    monkeypatch.setattr(jobs, "build_report_planner", lambda: FakeReportPlanner())

    job_payload = jobs.analyze_uploaded_file(sample_path)
    render_payload = jobs.render_job_report(job_payload["job_id"])

    assert job_payload["template_id"] == "template_a_overview"
    assert Path(render_payload["download_path"]).exists()


def test_demo_pipeline_selects_detailed_template_for_borderline_sample(monkeypatch) -> None:
    sample_path = Path("sample_data/high_variation_batch.csv")
    monkeypatch.setattr(jobs, "build_field_mapping_planner", lambda: FakeFieldMappingPlanner())
    monkeypatch.setattr(jobs, "build_report_planner", lambda: FakeReportPlanner())

    job_payload = jobs.analyze_uploaded_file(sample_path)

    assert job_payload["template_id"] == "template_b_detailed"
