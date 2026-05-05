import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { UploadForm } from "../components/upload-form";

test("upload form renders the intake console copy and passes the selected file to the submit handler", async () => {
  const user = userEvent.setup();
  const file = new File(["demo"], "demo.csv", { type: "text/csv" });
  const handleSubmit = jest.fn().mockResolvedValue(undefined);

  render(<UploadForm onSubmit={handleSubmit} />);

  expect(screen.getByText("上传检测文件")).toBeInTheDocument();
  expect(screen.getByText("上传后会直接进入分析过程页，向客户展示 AI 如何判断数据并生成报告。")).toBeInTheDocument();
  expect(screen.getByText("支持 CSV / XLSX 格式")).toBeInTheDocument();
  expect(screen.queryByText("直接开始")).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "稳定过程 normal_batch.csv" })).toHaveAttribute(
    "href",
    "/sample-data/normal_batch.csv"
  );
  expect(screen.getByRole("link", { name: "均值偏移 shifted_mean_batch.csv" })).toHaveAttribute(
    "href",
    "/sample-data/shifted_mean_batch.csv"
  );
  expect(screen.getByRole("link", { name: "波动偏高 high_variation_batch.csv" })).toHaveAttribute(
    "href",
    "/sample-data/high_variation_batch.csv"
  );
  expect(screen.getByRole("link", { name: "超出规格 out_of_spec_batch.csv" })).toHaveAttribute(
    "href",
    "/sample-data/out_of_spec_batch.csv"
  );
  for (const link of screen.getAllByRole("link", { name: /batch\.csv$/ })) {
    expect(link).toHaveAttribute("download");
  }

  await user.upload(screen.getByLabelText("检测数据文件"), file);
  await user.click(screen.getByRole("button", { name: "开始分析" }));

  expect(handleSubmit).toHaveBeenCalledWith(file, expect.any(Function));
});

test("upload form shows progress and waiting status while submission is in flight", async () => {
  const user = userEvent.setup();
  const file = new File(["demo"], "demo.csv", { type: "text/csv" });
  let emitProgress: ((progress: number) => void) | undefined;
  let resolveSubmit: (() => void) | undefined;
  const handleSubmit = jest.fn().mockImplementation(
    (_file: File, onProgress: (progress: number) => void) =>
      new Promise<void>((resolve) => {
        emitProgress = onProgress;
        resolveSubmit = resolve;
      })
  );

  render(<UploadForm onSubmit={handleSubmit} />);

  await user.upload(screen.getByLabelText("检测数据文件"), file);
  await user.click(screen.getByRole("button", { name: "开始分析" }));

  expect(screen.getByRole("button", { name: "上传中..." })).toBeDisabled();
  expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "0");

  act(() => emitProgress?.(42));
  expect(screen.getByText("上传中 42%")).toBeInTheDocument();
  expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "42");

  act(() => emitProgress?.(100));
  expect(screen.getByText("上传完成，等待分析结果...")).toBeInTheDocument();

  act(() => resolveSubmit?.());
  await waitFor(() => expect(screen.getByRole("button", { name: "开始分析" })).toBeEnabled());
});
