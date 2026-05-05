import type { JobTaskItem, JobTaskStatus } from "@/lib/api";

export type { JobTaskItem };

const STATUS_LABELS: Record<JobTaskStatus, string> = {
  pending: "\u7b49\u5f85\u4e2d",
  running: "\u6267\u884c\u4e2d",
  completed: "\u5df2\u5b8c\u6210",
  failed: "\u5931\u8d25"
};

const STATUS_TONES: Record<JobTaskStatus, string> = {
  pending: "status-pill status-pill--neutral",
  running: "status-pill status-pill--warning",
  completed: "status-pill status-pill--success",
  failed: "status-pill status-pill--danger"
};

export function JobTaskList({
  title,
  currentMessage,
  elapsedSeconds,
  tasks
}: {
  title: string;
  currentMessage: string;
  elapsedSeconds: number;
  tasks: JobTaskItem[];
}) {
  const completedCount = tasks.filter((task) => task.status === "completed").length;
  const progressPercent = tasks.length === 0 ? 0 : Math.round((completedCount / tasks.length) * 100);

  return (
    <section className="surface-card task-board">
      <div className="task-board__header">
        <div className="task-board__summary">
          <p className="section-heading__eyebrow">{"\u6d41\u7a0b\u8ddf\u8e2a"}</p>
          <h2 className="section-heading__title">{title}</h2>
          <p className="section-heading__subtitle">{currentMessage}</p>
        </div>
        <div className="meta-cluster">
          <span className="meta-chip">{"\u5df2\u7528\u65f6 "}{elapsedSeconds}{" \u79d2"}</span>
          <span className="meta-chip">
            {"\u5df2\u5b8c\u6210 "}{completedCount} / {tasks.length}
          </span>
        </div>
      </div>

      <div className="task-board__progress-label">{"\u6574\u4f53\u5b8c\u6210\u5ea6"}</div>
      <div className="progress-bar" aria-hidden="true">
        <div className="progress-bar__value" style={{ width: `${progressPercent}%` }} />
      </div>

      <div className="task-board__rows">
        {tasks.map((task, index) => (
          <div key={task.id} className="task-board__row">
            <div className="task-board__row-main">
              <span className="task-board__index">{index + 1}</span>
              <div>
                <div className="task-board__label">{task.label}</div>
                {task.reasoning ? <div className="task-board__detail">{task.reasoning}</div> : null}
                {!task.reasoning && task.error ? <div className="task-board__detail">{task.error}</div> : null}
              </div>
            </div>
            <span className={`task-board__status ${STATUS_TONES[task.status]}`}>{STATUS_LABELS[task.status]}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
