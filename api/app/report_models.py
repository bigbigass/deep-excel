from pydantic import BaseModel


class ReportMeta(BaseModel):
    title: str
    report_id: str
    generated_at: str
    batch_id: str
    product_name: str


class TemplateDecision(BaseModel):
    template_id: str
    reason: str


class KpiCard(BaseModel):
    label: str
    value: str


class ChartSpec(BaseModel):
    chart_id: str
    chart_type: str
    title: str


class NarrativeBlock(BaseModel):
    executive_summary: str
    quality_risk: str
    recommended_actions: list[str]


class ReportSpec(BaseModel):
    report_meta: ReportMeta
    template_decision: TemplateDecision
    dataset_summary: dict[str, object]
    kpi_cards: list[KpiCard]
    detail_rows: list[dict[str, object]]
    chart_specs: list[ChartSpec]
    anomalies: list[dict[str, object]]
    ai_narrative: NarrativeBlock
