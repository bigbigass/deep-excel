import { render, screen, within } from "@testing-library/react";

import { JobTaskList, type JobTaskItem } from "../components/job-task-list";

const tasks: JobTaskItem[] = [
  { id: "upload", label: "Upload file", status: "completed", error: null, reasoning: null },
  { id: "parse", label: "Parse dataset", status: "completed", error: null, reasoning: null },
  { id: "analyze", label: "Analyze SPC", status: "running", error: null, reasoning: null },
  { id: "charts", label: "Build charts", status: "pending", error: null, reasoning: null },
  { id: "ai", label: "Draft AI summary", status: "pending", error: null, reasoning: null },
  { id: "render", label: "Render Excel", status: "pending", error: null, reasoning: null }
];

test("job task list renders pipeline summary and per-task statuses", () => {
  const title = "Task Progress";
  const currentMessage = "Analyzing anomalies";
  const { container } = render(
    <JobTaskList currentMessage={currentMessage} elapsedSeconds={12} tasks={tasks} title={title} />
  );

  expect(screen.getByRole("heading", { name: title })).toBeInTheDocument();
  expect(screen.getByText(currentMessage)).toBeInTheDocument();
  expect(screen.getByText(/12/)).toBeInTheDocument();
  expect(screen.getByText(/2 \/ 6/)).toBeInTheDocument();
  expect(container.querySelectorAll(".task-board__status")).toHaveLength(6);
  expect(container.querySelector(".task-board__status.status-pill--warning")).not.toBeNull();
  expect(container.querySelectorAll(".task-board__status.status-pill--neutral").length).toBeGreaterThan(0);
  expect(within(container.querySelector(".task-board__rows") as HTMLElement).getByText("Upload file")).toBeInTheDocument();
});

test("job task list renders failure details", () => {
  render(
    <JobTaskList
      currentMessage="AI summary failed"
      elapsedSeconds={20}
      tasks={[
        ...tasks.slice(0, 4),
        { id: "ai", label: "Draft AI summary", status: "failed", error: "upstream unavailable", reasoning: null },
        tasks[5]
      ]}
      title="Task Progress"
    />
  );

  expect(document.querySelector(".task-board__status.status-pill--danger")).not.toBeNull();
  expect(screen.getByText("upstream unavailable")).toBeInTheDocument();
});

test("job task list shows reasoning details when available", () => {
  render(
    <JobTaskList
      currentMessage="Parsing dataset"
      elapsedSeconds={3}
      tasks={[
        tasks[0],
        {
          id: "parse",
          label: "Parse dataset",
          status: "completed",
          error: null,
          reasoning: "AI identified diameter_mm as the measurement column; spec_upper / spec_lower are the limits."
        },
        tasks[2],
        tasks[3],
        tasks[4],
        tasks[5]
      ]}
      title="Task Progress"
    />
  );

  expect(screen.getByText(/diameter_mm/)).toBeInTheDocument();
  expect(screen.getByText(/spec_upper \/ spec_lower/)).toBeInTheDocument();
});
