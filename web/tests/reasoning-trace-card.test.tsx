import { render, screen } from "@testing-library/react";

import { ReasoningTraceCard } from "../components/reasoning-trace-card";
import type { JobPayload } from "../lib/api";

function createJob(overrides: Partial<JobPayload> = {}): JobPayload {
  return {
    job_id: "JOB-1234",
    state: "completed",
    error: null,
    created_at: "2026-04-22T00:00:00Z",
    updated_at: "2026-04-22T00:01:00Z",
    source_file_name: "demo.csv",
    tasks: [
      { id: "upload", label: "\u4e0a\u4f20\u6587\u4ef6", status: "completed", error: null, reasoning: null },
      { id: "parse", label: "\u8bfb\u53d6\u6570\u636e", status: "completed", error: null, reasoning: null },
      { id: "analyze", label: "\u8bc6\u522b\u5f02\u5e38", status: "completed", error: null, reasoning: null },
      { id: "charts", label: "\u6574\u7406\u56fe\u8868", status: "completed", error: null, reasoning: null },
      { id: "ai", label: "\u5f62\u6210\u5224\u65ad", status: "completed", error: null, reasoning: null },
      { id: "render", label: "\u751f\u6210\u62a5\u544a", status: "completed", error: null, reasoning: null }
    ],
    template_id: "template_b_detailed",
    chart_paths: {},
    report_id: "RPT-1234",
    download_path: "outputs/reports/RPT-1234.xlsx",
    report_spec: {
      template_decision: {
        template_id: "template_b_detailed",
        reason: "\u5f53\u524d\u6ce2\u52a8\u504f\u5927\uff0c\u9002\u5408\u4f7f\u7528\u66f4\u8be6\u7ec6\u7684\u5206\u6790\u6a21\u677f\u3002"
      },
      dataset_summary: {
        sample_count: 24,
        overall_pass_rate: 1
      },
      kpi_cards: [
        { label: "Mean", value: "10.007" },
        { label: "StdDev", value: "0.029" },
        { label: "PassRate", value: "100.0%" },
        { label: "Cpk", value: "0.48" }
      ],
      chart_specs: [
        { chart_id: "histogram", chart_type: "histogram", title: "\u76f4\u65b9\u56fe" },
        { chart_id: "control_chart_imr", chart_type: "control_chart_imr", title: "I-MR \u63a7\u5236\u56fe" }
      ],
      anomalies: [{ type: "control_limit", severity: "medium", summary: "\u8fc7\u7a0b\u6ce2\u52a8\u504f\u5927\u3002" }],
      ai_narrative: {
        executive_summary: "\u5f53\u524d\u6279\u6b21\u6574\u4f53\u5408\u683c\uff0c\u4f46\u8fc7\u7a0b\u6ce2\u52a8\u4ecd\u9700\u7ee7\u7eed\u6536\u655b\u3002",
        quality_risk: "\u540e\u7eed\u6279\u6b21\u4ecd\u6709\u8d85\u51fa\u89c4\u683c\u7684\u98ce\u9669\u3002",
        recommended_actions: ["\u590d\u6838\u91cf\u5177\u504f\u79fb", "\u4e0b\u4e00\u6279\u6b21\u52a0\u5bc6\u62bd\u6837"]
      }
    },
    ...overrides
  };
}

test("reasoning trace card renders completed evidence, template choice, and actions", () => {
  render(<ReasoningTraceCard job={createJob()} />);

  expect(screen.getByTestId("reasoning-trace-card")).toBeInTheDocument();
  expect(screen.getByText("AI \u5206\u6790\u8fc7\u7a0b")).toBeInTheDocument();
  expect(screen.getByTestId("reasoning-signal-strip")).toHaveTextContent("24");
  expect(screen.getByTestId("reasoning-step-ai")).toHaveTextContent("template_b_detailed");
  expect(screen.getByTestId("reasoning-step-render")).toHaveTextContent("\u5f53\u524d\u6279\u6b21\u6574\u4f53\u5408\u683c\uff0c\u4f46\u8fc7\u7a0b\u6ce2\u52a8\u4ecd\u9700\u7ee7\u7eed\u6536\u655b\u3002");
  expect(screen.getByTestId("reasoning-risk-panel")).toHaveTextContent("\u540e\u7eed\u6279\u6b21\u4ecd\u6709\u8d85\u51fa\u89c4\u683c\u7684\u98ce\u9669\u3002");
  expect(screen.getByTestId("reasoning-actions-panel")).toHaveTextContent("\u590d\u6838\u91cf\u5177\u504f\u79fb");
});

test("reasoning trace card shows in-flight placeholders before the report spec is ready", () => {
  render(
    <ReasoningTraceCard
      job={createJob({
        state: "running",
        template_id: null,
        report_spec: null,
        tasks: [
          { id: "upload", label: "\u4e0a\u4f20\u6587\u4ef6", status: "completed", error: null, reasoning: null },
          { id: "parse", label: "\u8bfb\u53d6\u6570\u636e", status: "completed", error: null, reasoning: null },
          { id: "analyze", label: "\u8bc6\u522b\u5f02\u5e38", status: "running", error: null, reasoning: null },
          { id: "charts", label: "\u6574\u7406\u56fe\u8868", status: "pending", error: null, reasoning: null },
          { id: "ai", label: "\u5f62\u6210\u5224\u65ad", status: "pending", error: null, reasoning: null },
          { id: "render", label: "\u751f\u6210\u62a5\u544a", status: "pending", error: null, reasoning: null }
        ]
      })}
    />
  );

  expect(screen.getByTestId("reasoning-step-parse")).toHaveTextContent("\u5df2\u5b8c\u6210");
  expect(screen.getByTestId("reasoning-step-analyze")).toHaveTextContent("\u8fdb\u884c\u4e2d");
  expect(screen.getByTestId("reasoning-step-ai")).toHaveTextContent("\u6b63\u5728\u5f62\u6210\u9762\u5411\u5ba2\u6237\u5c55\u793a\u7684\u5206\u6790\u5224\u65ad\u3002");
  expect(screen.queryByTestId("reasoning-risk-panel")).not.toBeInTheDocument();
});

test("reasoning trace card prefers backend parse reasoning when present", () => {
  render(
    <ReasoningTraceCard
      job={createJob({
        tasks: [
          { id: "upload", label: "\u4e0a\u4f20\u6587\u4ef6", status: "completed", error: null, reasoning: null },
          {
            id: "parse",
            label: "\u8bfb\u53d6\u6570\u636e",
            status: "completed",
            error: null,
            reasoning: "AI \u5df2\u8bc6\u522b diameter_mm \u4e3a\u6d4b\u91cf\u5217\uff0cspec_upper / spec_lower \u4e3a\u89c4\u683c\u4e0a\u4e0b\u9650\u3002"
          },
          { id: "analyze", label: "\u8bc6\u522b\u5f02\u5e38", status: "pending", error: null, reasoning: null },
          { id: "charts", label: "\u6574\u7406\u56fe\u8868", status: "pending", error: null, reasoning: null },
          { id: "ai", label: "\u5f62\u6210\u5224\u65ad", status: "pending", error: null, reasoning: null },
          { id: "render", label: "\u751f\u6210\u62a5\u544a", status: "pending", error: null, reasoning: null }
        ]
      })}
    />
  );

  expect(screen.getByTestId("reasoning-step-parse")).toHaveTextContent(
    "AI \u5df2\u8bc6\u522b diameter_mm \u4e3a\u6d4b\u91cf\u5217"
  );
});
