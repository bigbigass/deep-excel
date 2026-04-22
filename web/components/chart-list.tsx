const CHART_LABELS: Record<string, string> = {
  histogram: "直方图",
  control_chart_imr: "I-MR 控制图",
  xbar_r_chart: "Xbar-R 控制图",
  trend_chart: "趋势图"
};

function formatChartLabel(key: string) {
  return CHART_LABELS[key] ?? key.replace(/_/g, " ");
}

export function ChartList({ charts }: { charts: Array<{ key: string; url: string }> }) {
  return (
    <section className="surface-card">
      <div className="section-heading">
        <div>
          <p className="section-heading__eyebrow">图表证据</p>
          <h2 className="section-heading__title">关键图表</h2>
          <p className="section-heading__subtitle">这些图表会跟随分析结果一起展示，帮助客户理解 AI 判断依据。</p>
        </div>
      </div>

      <div className="chart-grid">
        {charts.map((chart) => {
          const label = formatChartLabel(chart.key);

          return (
            <div key={chart.key} className="chart-card">
              <p className="info-tile__eyebrow">图表</p>
              <div className="chart-card__title">{label}</div>
              <div className="chart-card__media">
                <img alt={label} src={chart.url} />
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
