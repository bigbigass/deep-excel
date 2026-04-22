import { render, screen } from "@testing-library/react";

import ReportPage from "../app/report/[reportId]/page";

test("report page renders simplified Chinese delivery content and download action", async () => {
  const page = await ReportPage({
    params: Promise.resolve({ reportId: "RPT-1001" }),
    searchParams: Promise.resolve({ file: "demo-report.xlsx" })
  });

  render(page);

  expect(screen.getByText("报告已生成")).toBeInTheDocument();
  expect(screen.getByText("报告编号")).toBeInTheDocument();
  expect(screen.getByText("demo-report.xlsx")).toBeInTheDocument();
  expect(screen.queryByText("如何继续演示")).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "下载 Excel 报告" })).toHaveAttribute(
    "href",
    "http://127.0.0.1:8000/api/v1/reports/demo-report.xlsx"
  );
  expect(screen.getByRole("link", { name: "重新上传数据" })).toBeInTheDocument();
});
