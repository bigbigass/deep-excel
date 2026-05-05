import type { JobPayload, JobTaskStatus } from "@/lib/api";

type TraceStep = {
  id: string;
  title: string;
  detail: string;
  status: JobTaskStatus;
};

const STATUS_LABELS: Record<JobTaskStatus, string> = {
  pending: "\u7b49\u5f85\u4e2d",
  running: "\u8fdb\u884c\u4e2d",
  completed: "\u5df2\u5b8c\u6210",
  failed: "\u5931\u8d25"
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
  const parseTask = job?.tasks.find((task) => task.id === "parse");
  const sampleCount = reportSpec?.dataset_summary.sample_count ?? 0;
  const anomalyCount = reportSpec?.anomalies.length ?? 0;
  const cpk = getKpiValue(job, "Cpk") ?? "\u5f85\u8ba1\u7b97";
  const passRate =
    reportSpec?.dataset_summary.overall_pass_rate === undefined
      ? null
      : `${(reportSpec.dataset_summary.overall_pass_rate * 100).toFixed(1)}%`;
  const chartTitles = reportSpec?.chart_specs.map((item) => item.title).join("\u3001") ?? "";

  return [
    {
      id: "parse",
      title: "\u8bfb\u53d6\u6570\u636e",
      detail: parseTask?.reasoning
        ? parseTask.reasoning
        : sampleCount > 0
          ? `\u5df2\u8bfb\u53d6 ${sampleCount} \u6761\u68c0\u6d4b\u8bb0\u5f55\uff0c\u5b8c\u6210\u5173\u952e\u5b57\u6bb5\u8bc6\u522b\u4e0e\u6807\u51c6\u5316\u3002`
          : "\u6b63\u5728\u8bfb\u53d6\u4e0a\u4f20\u6587\u4ef6\u5e76\u8bc6\u522b\u6d4b\u91cf\u503c\u3001\u89c4\u683c\u9650\u548c\u6279\u6b21\u5b57\u6bb5\u3002",
      status: getTaskStatus(job, "parse")
    },
    {
      id: "analyze",
      title: "\u8bc6\u522b\u5f02\u5e38",
      detail:
        reportSpec && passRate
          ? `\u5f53\u524d\u5408\u683c\u7387 ${passRate}\uff0cCpk ${cpk}\uff0c\u8bc6\u522b\u5230 ${anomalyCount} \u4e2a\u5f02\u5e38\u4fe1\u53f7\u3002`
          : "\u6b63\u5728\u8ba1\u7b97\u6ce2\u52a8\u3001\u8fc7\u7a0b\u80fd\u529b\u548c\u5f02\u5e38\u70b9\u3002",
      status: getTaskStatus(job, "analyze")
    },
    {
      id: "charts",
      title: "\u6574\u7406\u8bc1\u636e",
      detail:
        reportSpec && chartTitles
          ? `\u5df2\u6574\u7406 ${reportSpec.chart_specs.length} \u5f20\u56fe\u8868\u8bc1\u636e\uff1a${chartTitles}\u3002`
          : "\u6b63\u5728\u6574\u7406\u76f4\u65b9\u56fe\u3001\u63a7\u5236\u56fe\u548c\u8d8b\u52bf\u56fe\u7b49\u56fe\u8868\u8bc1\u636e\u3002",
      status: getTaskStatus(job, "charts")
    },
    {
      id: "ai",
      title: "\u5f62\u6210\u5224\u65ad",
      detail: reportSpec
        ? `\u7cfb\u7edf\u5df2\u9009\u62e9 ${job?.template_id ?? reportSpec.template_decision.template_id}\uff0c\u539f\u56e0\uff1a${reportSpec.template_decision.reason}`
        : "\u6b63\u5728\u5f62\u6210\u9762\u5411\u5ba2\u6237\u5c55\u793a\u7684\u5206\u6790\u5224\u65ad\u3002",
      status: getTaskStatus(job, "ai")
    },
    {
      id: "render",
      title: "\u751f\u6210\u62a5\u544a",
      detail: reportSpec
        ? `\u5df2\u6574\u7406\u62a5\u544a\u6458\u8981\uff1a${reportSpec.ai_narrative.executive_summary}`
        : "\u6b63\u5728\u5199\u5165\u62a5\u544a\u5185\u5bb9\uff0c\u51c6\u5907\u751f\u6210 Excel \u6587\u4ef6\u3002",
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
      ? "\u5f85\u8ba1\u7b97"
      : `${(reportSpec.dataset_summary.overall_pass_rate * 100).toFixed(1)}%`;
  const cpk = getKpiValue(job, "Cpk") ?? "\u5f85\u8ba1\u7b97";
  const anomalyCount = reportSpec?.anomalies.length ?? 0;
  const templateId = job?.template_id ?? reportSpec?.template_decision.template_id ?? "\u5f85\u51b3\u7b56";

  return (
    <section className="surface-card trace-card" data-testid="reasoning-trace-card">
      <div className="trace-card__header">
        <div>
          <p className="section-heading__eyebrow">{"\u8fc7\u7a0b\u53ef\u89c1"}</p>
          <h2 className="section-heading__title">{"AI \u5206\u6790\u8fc7\u7a0b"}</h2>
          <p className="section-heading__subtitle">{"\u5c55\u793a\u5ba2\u6237\u53ef\u89c1\u7684\u5206\u6790\u6b65\u9aa4\u4e0e\u8bc1\u636e\u6458\u8981\uff0c\u4e0d\u5c55\u793a\u6a21\u578b\u539f\u59cb\u9690\u85cf\u63a8\u7406\u3002"}</p>
        </div>
        <span className={`status-pill ${reportSpec ? "status-pill--success" : "status-pill--warning"}`}>
          {reportSpec ? "\u5206\u6790\u4f9d\u636e\u5df2\u751f\u6210" : "\u6b63\u5728\u6574\u7406\u5206\u6790\u4f9d\u636e"}
        </span>
      </div>

      {reportSpec ? (
        <div className="trace-card__signals" data-testid="reasoning-signal-strip">
          <span className="signal-chip">{"\u6837\u672c "}{sampleCount}</span>
          <span className="signal-chip">{"\u5408\u683c\u7387 "}{passRate}</span>
          <span className="signal-chip">{"Cpk "}{cpk}</span>
          <span className="signal-chip">{"\u5f02\u5e38 "}{anomalyCount}</span>
          <span className="signal-chip">{"\u6a21\u677f "}{templateId}</span>
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
            <p className="section-heading__eyebrow">{"\u98ce\u9669\u63d0\u793a"}</p>
            <h3 className="section-heading__title">{"\u5f53\u524d\u98ce\u9669"}</h3>
            <p className="section-heading__subtitle">{reportSpec.ai_narrative.quality_risk}</p>
          </div>
          <div className="surface-card" data-testid="reasoning-actions-panel">
            <p className="section-heading__eyebrow">{"\u5efa\u8bae\u52a8\u4f5c"}</p>
            <h3 className="section-heading__title">{"\u4e0b\u4e00\u6b65\u5efa\u8bae"}</h3>
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
