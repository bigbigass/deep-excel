import type { JobPayload, JobTaskStatus } from "@/lib/api";

type TraceStep = {
  id: string;
  title: string;
  detail: string;
  status: JobTaskStatus;
};

const STATUS_LABELS: Record<JobTaskStatus, string> = {
  pending: "等待中",
  running: "进行中",
  completed: "已完成",
  failed: "失败"
};

const STATUS_TONES: Record<JobTaskStatus, string> = {
  pending: "status-pill status-pill--neutral",
  running: "status-pill status-pill--warning",
  completed: "status-pill status-pill--success",
  failed: "status-pill status-pill--danger"
};

function getTaskStatus(job: JobPayload | null, taskId: string): JobTaskStatus {
  return job?.tasks.find((task) => task.id === taskId)?.status ?? "pending";
}

function getKpiValue(job: JobPayload | null, label: string): string | null {
  return job?.report_spec?.kpi_cards.find((item) => item.label.toLowerCase() === label.toLowerCase())?.value ?? null;
}

function buildSteps(job: JobPayload | null): TraceStep[] {
  const reportSpec = job?.report_spec;
  const sampleCount = reportSpec?.dataset_summary.sample_count ?? 0;
  const anomalyCount = reportSpec?.anomalies.length ?? 0;
  const cpk = getKpiValue(job, "Cpk") ?? "待计算";
  const passRate =
    reportSpec?.dataset_summary.overall_pass_rate === undefined
      ? null
      : `${(reportSpec.dataset_summary.overall_pass_rate * 100).toFixed(1)}%`;
  const chartTitles = reportSpec?.chart_specs.map((item) => item.title).join("、") ?? "";

  return [
    {
      id: "parse",
      title: "读取数据",
      detail:
        sampleCount > 0
          ? `已读取 ${sampleCount} 条检测记录，完成关键字段识别与标准化。`
          : "正在读取上传文件并识别测量值、规格限和批次字段。",
      status: getTaskStatus(job, "parse")
    },
    {
      id: "analyze",
      title: "识别异常",
      detail:
        reportSpec && passRate
          ? `当前合格率 ${passRate}，Cpk ${cpk}，识别到 ${anomalyCount} 个异常信号。`
          : "正在计算波动、过程能力和异常点。",
      status: getTaskStatus(job, "analyze")
    },
    {
      id: "charts",
      title: "整理证据",
      detail:
        reportSpec && chartTitles
          ? `已整理 ${reportSpec.chart_specs.length} 张图表证据：${chartTitles}。`
          : "正在整理直方图、控制图和趋势图等图表证据。",
      status: getTaskStatus(job, "charts")
    },
    {
      id: "ai",
      title: "形成判断",
      detail: reportSpec
        ? `系统已选择 ${job?.template_id ?? reportSpec.template_decision.template_id}，原因：${reportSpec.template_decision.reason}`
        : "正在形成面向客户展示的分析判断。",
      status: getTaskStatus(job, "ai")
    },
    {
      id: "render",
      title: "生成报告",
      detail: reportSpec
        ? `已整理报告摘要：${reportSpec.ai_narrative.executive_summary}`
        : "正在写入报告内容，准备生成 Excel 文件。",
      status: getTaskStatus(job, "render")
    }
  ];
}

export function ReasoningTraceCard({ job }: { job: JobPayload | null }) {
  const reportSpec = job?.report_spec;
  const steps = buildSteps(job);
  const sampleCount = reportSpec?.dataset_summary.sample_count ?? 0;
  const passRate =
    reportSpec?.dataset_summary.overall_pass_rate === undefined
      ? "待计算"
      : `${(reportSpec.dataset_summary.overall_pass_rate * 100).toFixed(1)}%`;
  const cpk = getKpiValue(job, "Cpk") ?? "待计算";
  const anomalyCount = reportSpec?.anomalies.length ?? 0;
  const templateId = job?.template_id ?? reportSpec?.template_decision.template_id ?? "待决策";

  return (
    <section className="surface-card trace-card" data-testid="reasoning-trace-card">
      <div className="trace-card__header">
        <div>
          <p className="section-heading__eyebrow">过程可见</p>
          <h2 className="section-heading__title">AI 分析过程</h2>
          <p className="section-heading__subtitle">展示客户可见的分析步骤与证据摘要，不展示模型原始隐藏推理。</p>
        </div>
        <span className={`status-pill ${reportSpec ? "status-pill--success" : "status-pill--warning"}`}>
          {reportSpec ? "分析依据已生成" : "正在整理分析依据"}
        </span>
      </div>

      {reportSpec ? (
        <div className="trace-card__signals" data-testid="reasoning-signal-strip">
          <span className="signal-chip">样本 {sampleCount}</span>
          <span className="signal-chip">合格率 {passRate}</span>
          <span className="signal-chip">Cpk {cpk}</span>
          <span className="signal-chip">异常 {anomalyCount}</span>
          <span className="signal-chip">模板 {templateId}</span>
        </div>
      ) : null}

      <div className="trace-card__steps">
        {steps.map((step, index) => (
          <div key={step.id} className="trace-step" data-testid={`reasoning-step-${step.id}`}>
            <div className="trace-step__body">
              <span className="trace-step__index">{index + 1}</span>
              <div>
                <div className="trace-step__title">{step.title}</div>
                <div className="trace-step__detail">{step.detail}</div>
              </div>
            </div>
            <span className={`trace-step__status ${STATUS_TONES[step.status]}`}>{STATUS_LABELS[step.status]}</span>
          </div>
        ))}
      </div>

      {reportSpec ? (
        <div className="trace-card__insights">
          <div className="surface-card" data-testid="reasoning-risk-panel">
            <p className="section-heading__eyebrow">风险提示</p>
            <h3 className="section-heading__title">当前风险</h3>
            <p className="section-heading__subtitle">{reportSpec.ai_narrative.quality_risk}</p>
          </div>
          <div className="surface-card" data-testid="reasoning-actions-panel">
            <p className="section-heading__eyebrow">建议动作</p>
            <h3 className="section-heading__title">下一步建议</h3>
            <ul className="bullet-list">
              {reportSpec.ai_narrative.recommended_actions.map((action) => (
                <li key={action}>{action}</li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}
    </section>
  );
}
