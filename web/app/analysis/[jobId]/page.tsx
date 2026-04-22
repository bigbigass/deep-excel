"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { ChartList } from "@/components/chart-list";
import { JobTaskList } from "@/components/job-task-list";
import { KpiGrid } from "@/components/kpi-grid";
import { ReasoningTraceCard } from "@/components/reasoning-trace-card";
import { API_BASE_URL, getJob, renderJob, type JobPayload, type JobTaskItem } from "@/lib/api";

function normalizeOsPath(path: string) {
  return path.replace(/\\/g, "/").replace(/^\/+/, "");
}

function createInitialTasks(): JobTaskItem[] {
  return [
    { id: "upload", label: "上传文件", status: "completed", error: null },
    { id: "parse", label: "读取数据", status: "running", error: null },
    { id: "analyze", label: "识别异常", status: "pending", error: null },
    { id: "charts", label: "整理图表", status: "pending", error: null },
    { id: "ai", label: "形成判断", status: "pending", error: null },
    { id: "render", label: "生成报告", status: "pending", error: null }
  ];
}

function getCurrentMessage(job: JobPayload | null): string {
  if (!job) {
    return "正在获取分析进度...";
  }

  if (job.state === "failed") {
    return job.error ?? "任务执行失败";
  }

  const runningTask = job.tasks.find((task) => task.status === "running");
  if (runningTask) {
    return `正在${runningTask.label}`;
  }

  if (job.state === "analysis_completed") {
    return "分析已完成，正在生成报告。";
  }

  if (job.state === "completed") {
    return "分析和报告都已完成。";
  }

  return "文件已上传，系统正在排队分析。";
}

function getStateLabel(state: JobPayload["state"] | undefined) {
  switch (state) {
    case "queued":
      return "排队中";
    case "running":
      return "分析中";
    case "analysis_completed":
      return "待生成报告";
    case "rendering":
      return "生成报告中";
    case "completed":
      return "已完成";
    case "failed":
      return "失败";
    default:
      return "初始化";
  }
}

function getStateTone(state: JobPayload["state"] | undefined, hasError: boolean) {
  if (hasError || state === "failed") {
    return "status-pill status-pill--danger";
  }

  if (state === "completed") {
    return "status-pill status-pill--success";
  }

  if (state === "analysis_completed" || state === "rendering") {
    return "status-pill status-pill--warning";
  }

  return "status-pill status-pill--neutral";
}

export default function AnalysisPage() {
  const params = useParams<{ jobId: string }>();
  const jobId = String(params.jobId);
  const [job, setJob] = useState<JobPayload | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const renderRequestedRef = useRef(false);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setElapsedSeconds((current) => current + 1);
    }, 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    let disposed = false;
    let pollTimer: number | undefined;

    const pollJob = async () => {
      try {
        const payload = await getJob(jobId);
        if (disposed) {
          return;
        }

        setJob(payload);
        setPageError(null);

        const renderTask = payload.tasks.find((task) => task.id === "render");
        if (
          payload.state === "analysis_completed" &&
          renderTask?.status === "pending" &&
          !renderRequestedRef.current
        ) {
          renderRequestedRef.current = true;
          await renderJob(jobId);
        }

        if (!["completed", "failed"].includes(payload.state)) {
          pollTimer = window.setTimeout(pollJob, 1200);
        }
      } catch (error) {
        if (disposed) {
          return;
        }

        const message = error instanceof Error ? error.message : "获取任务状态失败";
        setPageError(message);
        pollTimer = window.setTimeout(pollJob, 2000);
      }
    };

    void pollJob();

    return () => {
      disposed = true;
      if (pollTimer) {
        window.clearTimeout(pollTimer);
      }
    };
  }, [jobId]);

  const tasks = job?.tasks ?? createInitialTasks();
  const currentMessage = pageError ?? getCurrentMessage(job);
  const charts = useMemo(
    () =>
      job?.chart_paths
        ? Object.entries(job.chart_paths).map(([key, url]) => ({
            key,
            url: `${API_BASE_URL}/${normalizeOsPath(String(url))}`
          }))
        : [],
    [job]
  );
  const reportFileName = job?.download_path ? normalizeOsPath(job.download_path).split("/").pop() ?? "" : "";
  const templateId = job?.template_id ?? job?.report_spec?.template_decision.template_id ?? "待决策";

  return (
    <div className="page page-reveal">
      <section className="page-header">
        <p className="page-header__eyebrow">分析过程</p>
        <div className="page-header__title-row">
          <div>
            <h1 className="page-header__title">AI 质量分析</h1>
            <p className="page-header__subtitle">这里按步骤展示系统如何读取数据、识别异常、整理证据并生成报告。</p>
          </div>
          <div className="page-header__meta">
            <span className="meta-chip">
              <strong>任务编号</strong>
              <span>{jobId}</span>
            </span>
            <span className="meta-chip">
              <strong>源文件</strong>
              <span>{job?.source_file_name ?? "识别中"}</span>
            </span>
            <span className={getStateTone(job?.state, Boolean(pageError))}>{getStateLabel(job?.state)}</span>
          </div>
        </div>
        <div className="page-header__actions">
          {job?.state === "completed" && job.report_id && reportFileName ? (
            <Link className="button-primary" href={`/report/${job.report_id}?file=${encodeURIComponent(reportFileName)}`}>
              查看报告结果
            </Link>
          ) : (
            <Link className="button-secondary" href="/">
              返回上传页面
            </Link>
          )}
        </div>
      </section>

      <div className="analysis-layout">
        <div className="analysis-main">
          <ReasoningTraceCard job={job} />

          {job?.report_spec ? <KpiGrid items={job.report_spec.kpi_cards} /> : null}

          {charts.length > 0 ? (
            <ChartList charts={charts} />
          ) : (
            <section className="empty-state">
              <p className="section-heading__eyebrow">图表生成中</p>
              <h2 className="section-heading__title">图表证据尚未就绪</h2>
              <p>系统会在分析完成后把关键图表展示到这里，用于支撑 AI 判断和报告内容。</p>
            </section>
          )}
        </div>

        <div className="analysis-side">
          <JobTaskList currentMessage={currentMessage} elapsedSeconds={elapsedSeconds} tasks={tasks} title="任务进度" />

          {pageError ? <div className="feedback-error">{pageError}</div> : null}

          {job?.state === "failed" ? (
            <section className="surface-card">
              <div className="section-heading">
                <div>
                  <p className="section-heading__eyebrow">失败信息</p>
                  <h2 className="section-heading__title">任务执行失败</h2>
                  <p className="section-heading__subtitle">{job.error ?? "未知错误"}</p>
                </div>
              </div>
            </section>
          ) : null}
        </div>
      </div>
    </div>
  );
}
