import { render, screen } from "@testing-library/react";

jest.mock("next/navigation", () => ({
  usePathname: () => "/analysis/JOB-20260422"
}));

import { AppShell } from "../components/app-shell";

test("app shell exposes investigation and report demo navigation", () => {
  render(
    <AppShell>
      <div>analysis workspace body</div>
    </AppShell>
  );

  expect(screen.getByText("DeepExcel 质量调查")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "质量调查" })).toHaveAttribute(
    "href",
    "/investigations/new"
  );
  expect(screen.getByRole("link", { name: "报告演示" })).toHaveAttribute("href", "/");
  expect(screen.getByRole("link", { name: "报告演示" })).toHaveClass("app-nav__link--active");
  expect(screen.queryByText("上传数据后展示 AI 分析过程与报告结果")).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "上传数据" })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "分析过程" })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "报告结果" })).not.toBeInTheDocument();
  expect(screen.getByText("analysis workspace body")).toBeInTheDocument();
});
