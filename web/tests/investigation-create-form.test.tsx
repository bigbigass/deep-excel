import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { InvestigationCreateForm } from "@/components/investigation-create-form";
import { createInvestigation } from "@/lib/investigations";

const push = jest.fn();

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push })
}));

jest.mock("@/lib/investigations", () => ({
  createInvestigation: jest.fn()
}));

const createInvestigationMock = createInvestigation as jest.MockedFunction<typeof createInvestigation>;

describe("InvestigationCreateForm", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test("creates a case and navigates to the investigation workspace", async () => {
    createInvestigationMock.mockResolvedValue({ case_id: "CASE-1234" });
    const user = userEvent.setup();
    render(<InvestigationCreateForm />);

    const file = new File(
      ["measurement_value,usl,lsl\n10.01,10.05,9.95\n"],
      "quality.csv",
      { type: "text/csv" }
    );
    await user.upload(screen.getByLabelText("质量数据文件"), file);
    await user.click(screen.getByRole("button", { name: "开始质量调查" }));

    await waitFor(() => {
      expect(createInvestigationMock).toHaveBeenCalledWith(
        "为什么最近一段时间外径不良率升高？",
        file
      );
    });
    expect(push).toHaveBeenCalledWith("/investigations/CASE-1234");
  });

  test("requires a source file before submitting", async () => {
    const user = userEvent.setup();
    render(<InvestigationCreateForm />);

    await user.click(screen.getByRole("button", { name: "开始质量调查" }));

    expect(screen.getByRole("alert")).toHaveTextContent("请选择包含测量值");
    expect(createInvestigationMock).not.toHaveBeenCalled();
  });
});
