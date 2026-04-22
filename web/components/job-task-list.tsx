import type { JobTaskItem, JobTaskStatus } from "@/lib/api";

export type { JobTaskItem };

const STATUS_LABELS: Record<JobTaskStatus, string> = {
  pending: "等待中",
  running: "执行中",
  completed: "已完成",
  failed: "失败"
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
          <p className="section-heading__eyebrow">流程跟踪</p>
          <h2 className="section-heading__title">{title}</h2>
          <p className="section-heading__subtitle">{currentMessage}</p>
        </div>
        <div className="meta-cluster">
          <span className="meta-chip">已用时 {elapsedSeconds} 秒</span>
          <span className="meta-chip">
            已完成 {completedCount} / {tasks.length}
          </span>
        </div>
      </div>

      <div className="task-board__progress-label">整体完成度</div>
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
                {task.error ? <div className="task-board__detail">{task.error}</div> : null}
              </div>
            </div>
            <span className={`task-board__status ${STATUS_TONES[task.status]}`}>{STATUS_LABELS[task.status]}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
