import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const push = jest.fn();

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push })
}));

jest.mock("../lib/api", () => ({
  createJob: jest.fn()
}));

import HomePage from "../app/page";
import { createJob } from "../lib/api";

beforeEach(() => {
  jest.clearAllMocks();
});

test("home page renders a simplified Chinese demo flow and starts analysis after upload", async () => {
  const user = userEvent.setup();
  const file = new File(["demo"], "demo.csv", { type: "text/csv" });
  jest.mocked(createJob).mockResolvedValue({ job_id: "JOB-DEMO-1" });

  render(<HomePage />);

  expect(screen.getByText("上传检测文件，直接查看 AI 质量分析")).toBeInTheDocument();
  expect(screen.getByText("上传数据")).toBeInTheDocument();
  expect(screen.getByText("AI 分析")).toBeInTheDocument();
  expect(screen.getByText("生成报告")).toBeInTheDocument();
  expect(screen.queryByText("上游模型状态")).not.toBeInTheDocument();
  expect(screen.queryByText("形式")).not.toBeInTheDocument();
  expect(screen.queryByText("流程")).not.toBeInTheDocument();
  expect(screen.queryByText("界面")).not.toBeInTheDocument();
  expect(screen.queryByText("客户会看到什么")).not.toBeInTheDocument();
  expect(screen.queryByText("演示重点")).not.toBeInTheDocument();

  await user.upload(screen.getByLabelText("检测数据文件"), file);
  await user.click(screen.getByRole("button", { name: "开始分析" }));

  await waitFor(() => expect(createJob).toHaveBeenCalledTimes(1));
  expect(push).toHaveBeenCalledWith("/analysis/JOB-DEMO-1");
});
