from api.app.agent import factory


def _analysis_without_specifications() -> dict[str, object]:
    return {
        "mean": 10.02,
        "std_dev": 0.01,
        "has_spec_limits": False,
        "pass_rate": None,
        "cp": None,
        "cpk": None,
        "out_of_spec_count": 0,
        "recommended_charts": ["histogram", "control_chart_imr", "trend_line"],
        "anomalies": [],
    }


def test_report_spec_preserves_unavailable_pass_rate() -> None:
    report = factory._build_report_spec(
        job_id="JOB-NO-SPEC",
        analysis=_analysis_without_specifications(),
        template_id="template_a_overview",
        template_reason="当前数据缺少规格限，使用概览模板。",
        executive_summary="当前仅能评估过程分布，无法判断规格合格率。",
        quality_risk="缺少规格限会限制质量结论的完整性。",
        recommended_actions=["补充规格上下限", "确认检测项目标准"],
    )

    assert report.dataset_summary["overall_pass_rate"] is None
    pass_rate_card = next(card for card in report.kpi_cards if card.label == "PassRate")
    assert pass_rate_card.value == "n/a"


def test_agent_prompt_marks_unavailable_pass_rate_explicitly() -> None:
    prompt = factory._build_agent_user_prompt(
        job_id="JOB-NO-SPEC",
        analysis=_analysis_without_specifications(),
    )

    assert "PassRate=n/a" in prompt
    assert "Cpk=n/a" in prompt
