from pathlib import Path

from api.app.services.jobs import analyze_uploaded_file, render_job_report


def test_demo_pipeline_from_sample_data() -> None:
    sample_path = Path("sample_data/out_of_spec_batch.csv")

    job_payload = analyze_uploaded_file(sample_path)
    render_payload = render_job_report(job_payload["job_id"])

    assert job_payload["template_id"] == "template_a_overview"
    assert Path(render_payload["download_path"]).exists()


def test_demo_pipeline_selects_detailed_template_for_borderline_sample() -> None:
    sample_path = Path("sample_data/high_variation_batch.csv")

    job_payload = analyze_uploaded_file(sample_path)

    assert job_payload["template_id"] == "template_b_detailed"
