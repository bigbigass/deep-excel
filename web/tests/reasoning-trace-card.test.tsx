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
      { id: "upload", label: "上传文件", status: "completed", error: null },
      { id: "parse", label: "读取数据", status: "completed", error: null },
      { id: "analyze", label: "识别异常", status: "completed", error: null },
      { id: "charts", label: "整理图表", status: "completed", error: null },
      { id: "ai", label: "形成判断", status: "completed", error: null },
      { id: "render", label: "生成报告", status: "completed", error: null }
    ],
    template_id: "template_b_detailed",
    chart_paths: {},
    report_id: "RPT-1234",
    download_path: "outputs/reports/RPT-1234.xlsx",
    report_spec: {
      template_decision: {
        template_id: "template_b_detailed",
        reason: "当前波动偏大，适合使用更详细的分析模板。"
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
        { chart_id: "histogram", chart_type: "histogram", title: "直方图" },
        { chart_id: "control_chart_imr", chart_type: "control_chart_imr", title: "I-MR 控制图" }
      ],
      anomalies: [{ type: "control_limit", severity: "medium", summary: "过程波动偏大。" }],
      ai_narrative: {
        executive_summary: "当前批次整体合格，但过程波动仍需继续收敛。",
        quality_risk: "后续批次仍有超出规格的风险。",
        recommended_actions: ["复核量具偏移", "下一批次加密抽样"]
      }
    },
    ...overrides
  };
}

test("reasoning trace card renders completed evidence, template choice, and actions", () => {
  render(<ReasoningTraceCard job={createJob()} />);

  expect(screen.getByTestId("reasoning-trace-card")).toBeInTheDocument();
  expect(screen.getByText("AI 分析过程")).toBeInTheDocument();
  expect(screen.getByTestId("reasoning-signal-strip")).toHaveTextContent("24");
  expect(screen.getByTestId("reasoning-step-ai")).toHaveTextContent("template_b_detailed");
  expect(screen.getByTestId("reasoning-step-render")).toHaveTextContent("当前批次整体合格，但过程波动仍需继续收敛。");
  expect(screen.getByTestId("reasoning-risk-panel")).toHaveTextContent("后续批次仍有超出规格的风险。");
  expect(screen.getByTestId("reasoning-actions-panel")).toHaveTextContent("复核量具偏移");
});

test("reasoning trace card shows in-flight placeholders before the report spec is ready", () => {
  render(
    <ReasoningTraceCard
      job={createJob({
        state: "running",
        template_id: null,
        report_spec: null,
        tasks: [
          { id: "upload", label: "上传文件", status: "completed", error: null },
          { id: "parse", label: "读取数据", status: "completed", error: null },
          { id: "analyze", label: "识别异常", status: "running", error: null },
          { id: "charts", label: "整理图表", status: "pending", error: null },
          { id: "ai", label: "形成判断", status: "pending", error: null },
          { id: "render", label: "生成报告", status: "pending", error: null }
        ]
      })}
    />
  );

  expect(screen.getByTestId("reasoning-step-parse")).toHaveTextContent("已完成");
  expect(screen.getByTestId("reasoning-step-analyze")).toHaveTextContent("进行中");
  expect(screen.getByTestId("reasoning-step-ai")).toHaveTextContent("正在形成面向客户展示的分析判断。");
  expect(screen.queryByTestId("reasoning-risk-panel")).not.toBeInTheDocument();
});
