import { render, screen } from "@testing-library/react";

import { JobTaskList, type JobTaskItem } from "../components/job-task-list";

const tasks: JobTaskItem[] = [
  { id: "upload", label: "上传文件", status: "completed", error: null },
  { id: "parse", label: "解析检测数据", status: "completed", error: null },
  { id: "analyze", label: "执行 SPC 分析", status: "running", error: null },
  { id: "charts", label: "生成图表", status: "pending", error: null },
  { id: "ai", label: "生成 AI 结论", status: "pending", error: null },
  { id: "render", label: "渲染 Excel 报告", status: "pending", error: null }
];

test("job task list renders pipeline summary and per-task statuses", () => {
  render(
    <JobTaskList currentMessage="正在识别异常并生成判断" elapsedSeconds={12} tasks={tasks} title="任务进度" />
  );

  expect(screen.getByText("任务进度")).toBeInTheDocument();
  expect(screen.getByText("任务进度")).toBeInTheDocument();
  expect(screen.getByText("整体完成度")).toBeInTheDocument();
  expect(screen.getByText("正在识别异常并生成判断")).toBeInTheDocument();
  expect(screen.getByText("已用时 12 秒")).toBeInTheDocument();
  expect(screen.getByText("已完成 2 / 6")).toBeInTheDocument();
  expect(screen.getByText("执行中")).toBeInTheDocument();
  expect(screen.getAllByText("等待中").length).toBeGreaterThan(0);
});

test("job task list renders failure details", () => {
  render(
    <JobTaskList
      currentMessage="生成 AI 结论失败"
      elapsedSeconds={20}
      tasks={[
        ...tasks.slice(0, 4),
        { id: "ai", label: "生成 AI 结论", status: "failed", error: "upstream unavailable" },
        tasks[5]
      ]}
      title="任务进度"
    />
  );

  expect(screen.getByText("失败")).toBeInTheDocument();
  expect(screen.getByText("upstream unavailable")).toBeInTheDocument();
});
