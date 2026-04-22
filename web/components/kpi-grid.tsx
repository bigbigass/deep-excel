const KPI_LABELS: Record<string, string> = {
  Mean: "均值",
  StdDev: "标准差",
  PassRate: "合格率",
  Cpk: "Cpk",
  Cp: "Cp"
};

function formatKpiLabel(label: string) {
  return KPI_LABELS[label] ?? label;
}

export function KpiGrid({ items }: { items: Array<{ label: string; value: string }> }) {
  return (
    <section className="surface-card">
      <div className="section-heading">
        <div>
          <p className="section-heading__eyebrow">关键指标</p>
          <h2 className="section-heading__title">分析结果摘要</h2>
          <p className="section-heading__subtitle">用最少的指标快速说明当前批次质量状态。</p>
        </div>
      </div>

      <div className="kpi-grid">
        {items.map((item) => (
          <div key={item.label} className="kpi-card">
            <div className="kpi-card__label">{formatKpiLabel(item.label)}</div>
            <div className="kpi-card__value">{item.value}</div>
          </div>
        ))}
      </div>
    </section>
  );
}
