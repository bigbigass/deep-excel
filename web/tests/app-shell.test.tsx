import { render, screen } from "@testing-library/react";

jest.mock("next/navigation", () => ({
  usePathname: () => "/analysis/JOB-20260422"
}));

import { AppShell } from "../components/app-shell";

test("app shell stays minimal for the demo shell", () => {
  render(
    <AppShell>
      <div>analysis workspace body</div>
    </AppShell>
  );

  expect(screen.getByText("DeepExcel 质量分析演示")).toBeInTheDocument();
  expect(screen.queryByText("上传数据后展示 AI 分析过程与报告结果")).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "上传数据" })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "分析过程" })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "报告结果" })).not.toBeInTheDocument();
  expect(screen.queryByText("演示版")).not.toBeInTheDocument();
  expect(screen.queryByText("上传数据 · AI 分析 · 生成报告")).not.toBeInTheDocument();
  expect(screen.getByText("analysis workspace body")).toBeInTheDocument();
});
