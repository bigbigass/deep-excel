from api.app.agent import factory
from api.app.report_models import ReportSpec
from api.app.services.ingestion import infer_field_mapping


class FakeFieldMappingPlanner:
    def plan(self, frame, file_name):
        measurement_column = "diameter_mm" if "diameter_mm" in frame.columns else "value"
        lsl_column = "spec_lower" if "spec_lower" in frame.columns else "lsl"
        usl_column = "spec_upper" if "spec_upper" in frame.columns else "usl"
        return (
            infer_field_mapping(frame),
            f"AI 已识别 {measurement_column} 为测量列，{lsl_column} / {usl_column} 为规格上下限。",
        )


class FakeReportPlanner:
    def plan(self, *, job_id: str, analysis: dict[str, object]) -> ReportSpec:
        if int(analysis["out_of_spec_count"]):
            template_id = "template_a_overview"
        elif analysis["cpk"] is not None and float(analysis["cpk"]) < 1.0:
            template_id = "template_b_detailed"
        else:
            template_id = "template_c_showcase"

        return factory._build_report_spec(
            job_id=job_id,
            analysis=analysis,
            template_id=template_id,
            template_reason="AI 已完成报告模板选择。",
            executive_summary="过程表现稳定，可继续生成演示报告。",
            quality_risk="当前仅存在可控风险，建议持续关注波动。",
            recommended_actions=["复核关键样本", "继续观察后续批次"],
        )
