import { render, screen } from "@testing-library/react";

import { ReasoningTraceCard } from "../components/reasoning-trace-card";
import type { JobPayload } from "../lib/api";


const jobWithoutSpecifications: JobPayload = {
  job_id: "JOB-NO-SPEC",
  state: "analysis_completed",
  error: null,
  created_at: "2026-08-20T00:00:00Z",
  updated_at: "2026-08-20T00:01:00Z",
  source_file_name: "measurements.csv",
  tasks: [
    { id: "upload", label: "上传文件", status: "completed", error: null },
    { id: "parse", label: "读取数据", status: "completed", error: null },
    { id: "analyze", label: "识别异常", status: "completed", error: null },
    { id: "charts", label: "整理图表", status: "completed", error: null },
    { id: "ai", label: "形成判断", status: "completed", error: null },
    { id: "render", label: "生成报告", status: "pending", error: null }
  ],
  template_id: "template_a_overview",
  chart_paths: {},
  report_id: null,
  download_path: null,
  report_spec: {
    template_decision: {
      template_id: "template_a_overview",
      reason: "缺少规格限，先展示过程分布。"
    },
    dataset_summary: {
      sample_count: 3,
      overall_pass_rate: null
    },
    kpi_cards: [
      { label: "Mean", value: "10.020" },
      { label: "StdDev", value: "0.010" },
      { label: "PassRate", value: "n/a" },
      { label: "Cpk", value: "n/a" }
    ],
    chart_specs: [],
    anomalies: [],
    ai_narrative: {
      executive_summary: "当前仅能评估过程分布。",
      quality_risk: "缺少规格限会限制结论完整性。",
      recommended_actions: ["补充规格上下限", "确认检测标准"]
    }
  }
};


test("reasoning trace card does not turn a missing pass rate into zero percent", () => {
  render(<ReasoningTraceCard job={jobWithoutSpecifications} />);

  expect(screen.getByTestId("reasoning-signal-strip")).toHaveTextContent("合格率 N/A");
  expect(screen.getByTestId("reasoning-step-analyze")).toHaveTextContent("缺少完整规格限");
  expect(screen.getByTestId("reasoning-step-analyze")).not.toHaveTextContent("合格率 0.0%");
});
