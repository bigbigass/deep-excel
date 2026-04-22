import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { UpstreamCheckCard } from "../components/upstream-check-card";
import { checkUpstreamHealth } from "../lib/api";

jest.mock("../lib/api", () => ({
  checkUpstreamHealth: jest.fn()
}));

beforeEach(() => {
  jest.clearAllMocks();
});

test("upstream check card runs the probe and renders the latest result", async () => {
  const user = userEvent.setup();
  const mockCheckUpstreamHealth = jest.mocked(checkUpstreamHealth);
  mockCheckUpstreamHealth.mockResolvedValue({
    configured: true,
    reachable: true,
    model: "gpt-5.4",
    base_url: "http://14.102.239.172:8080/v1",
    latency_ms: 1059,
    response_preview: "PONG",
    error: null
  });

  render(<UpstreamCheckCard />);

  await user.click(screen.getByRole("button", { name: "检查模型状态" }));

  await waitFor(() => expect(mockCheckUpstreamHealth).toHaveBeenCalledTimes(1));
  expect(screen.getByText("可用")).toBeInTheDocument();
  expect(screen.getByText("gpt-5.4")).toBeInTheDocument();
  expect(screen.getByText("1059 ms")).toBeInTheDocument();
  expect(screen.getByText("PONG")).toBeInTheDocument();
});

test("upstream check card shows an error message and restores the button after a failed request", async () => {
  const user = userEvent.setup();
  const mockCheckUpstreamHealth = jest.mocked(checkUpstreamHealth);
  mockCheckUpstreamHealth.mockRejectedValue(new Error("network down"));

  render(<UpstreamCheckCard />);

  await user.click(screen.getByRole("button", { name: "检查模型状态" }));

  await waitFor(() => expect(screen.getByText("检测请求失败")).toBeInTheDocument());
  expect(screen.getByRole("button", { name: "检查模型状态" })).toBeEnabled();
  expect(screen.queryByText("可用")).not.toBeInTheDocument();
});

test("upstream check card distinguishes unconfigured upstream status", async () => {
  const user = userEvent.setup();
  const mockCheckUpstreamHealth = jest.mocked(checkUpstreamHealth);
  mockCheckUpstreamHealth.mockResolvedValue({
    configured: false,
    reachable: false,
    model: "gpt-5.4",
    base_url: null,
    latency_ms: null,
    response_preview: null,
    error: "Missing DEEPEXCEL_OPENAI_API_KEY"
  });

  render(<UpstreamCheckCard />);

  await user.click(screen.getByRole("button", { name: "检查模型状态" }));

  await waitFor(() => expect(mockCheckUpstreamHealth).toHaveBeenCalledTimes(1));
  expect(screen.getByText("未配置")).toBeInTheDocument();
  expect(screen.getByText("Missing DEEPEXCEL_OPENAI_API_KEY")).toBeInTheDocument();
});
