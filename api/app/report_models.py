"""报表领域模型，描述 AI 规划后的 Excel 报表结构。"""

from pydantic import BaseModel


class ReportMeta(BaseModel):
    """报表头部元数据。"""

    title: str
    report_id: str
    generated_at: str
    batch_id: str
    product_name: str


class TemplateDecision(BaseModel):
    """模板选择结果及其原因说明。"""

    template_id: str
    reason: str


class KpiCard(BaseModel):
    """摘要区域展示的单个 KPI 卡片。"""

    label: str
    value: str


class ChartSpec(BaseModel):
    """报表中需要展示的图表定义。"""

    chart_id: str
    chart_type: str
    title: str


class NarrativeBlock(BaseModel):
    """AI 生成的中文叙述结论。"""

    executive_summary: str
    quality_risk: str
    recommended_actions: list[str]


class ReportSpec(BaseModel):
    """渲染 Excel 报表所需的完整规格对象。"""

    report_meta: ReportMeta
    template_decision: TemplateDecision
    dataset_summary: dict[str, object]
    kpi_cards: list[KpiCard]
    detail_rows: list[dict[str, object]]
    chart_specs: list[ChartSpec]
    anomalies: list[dict[str, object]]
    ai_narrative: NarrativeBlock
