import { render, screen, waitFor } from "@testing-library/react";

jest.mock("next/navigation", () => ({
  useParams: () => ({ jobId: "JOB-DEMO-1" })
}));

jest.mock("../lib/api", () => ({
  API_BASE_URL: "http://127.0.0.1:8000",
  getJob: jest.fn(),
  renderJob: jest.fn()
}));

import AnalysisPage from "../app/analysis/[jobId]/page";
import { getJob } from "../lib/api";

beforeEach(() => {
  jest.clearAllMocks();
});

test("analysis page keeps the demo focused on process visibility instead of extra summary panels", async () => {
  jest.mocked(getJob).mockResolvedValue({
    job_id: "JOB-DEMO-1",
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
    report_id: "RPT-1",
    download_path: "outputs/reports/demo-report.xlsx",
    report_spec: {
      template_decision: {
        template_id: "template_b_detailed",
        reason: "当前波动偏大，适合使用更详细的分析模板。"
      },
      dataset_summary: {
        sample_count: 24,
        overall_pass_rate: 1
      },
      kpi_cards: [{ label: "Cpk", value: "0.48" }],
      chart_specs: [],
      anomalies: [{ summary: "过程波动偏大。" }],
      ai_narrative: {
        executive_summary: "当前批次整体合格，但过程波动仍需继续收敛。",
        quality_risk: "后续批次仍有超出规格的风险。",
        recommended_actions: ["复核量具偏移"]
      }
    }
  });

  render(<AnalysisPage />);

  await waitFor(() => expect(screen.getByRole("link", { name: "查看报告结果" })).toBeInTheDocument());
  expect(screen.getByText("AI 分析过程")).toBeInTheDocument();
  expect(screen.getByText("任务进度")).toBeInTheDocument();
  expect(screen.queryByText("AI 已整理出初步结果")).not.toBeInTheDocument();
});
