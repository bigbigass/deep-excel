"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { UploadForm } from "@/components/upload-form";
import { createJob } from "@/lib/api";

const DEMO_STEPS = [
  {
    title: "上传数据",
    detail: "上传检测文件后，系统自动识别测量值、规格限和批次信息。"
  },
  {
    title: "AI 分析",
    detail: "页面会展示 AI 如何识别异常、整理证据并形成判断。"
  },
  {
    title: "生成报告",
    detail: "分析完成后自动生成 Excel 报告，便于下载与演示。"
  }
];

export default function HomePage() {
  const router = useRouter();

  return (
    <div className="page page-reveal">
      <section className="page-header">
        <p className="page-header__eyebrow">旧版能力演示</p>
        <div className="page-header__title-row">
          <div>
            <h1 className="page-header__title">上传检测文件，生成 SPC Excel 报告</h1>
            <p className="page-header__subtitle">
              这里保留原有报告 Demo，用于验证字段识别、SPC、图表和 Excel 渲染。真正的异常调查流程已迁移到“质量调查”。
            </p>
          </div>
        </div>
        <div className="page-header__actions">
          <Link className="button-primary" href="/investigations/new">进入质量调查</Link>
        </div>
      </section>

      <div className="home-layout">
        <div className="home-overview">
          <section className="hero-panel">
            <div>
              <p className="hero-panel__eyebrow">报告演示主线</p>
              <h2 className="hero-panel__title">上传后直接进入分析过程页</h2>
              <p className="hero-panel__subtitle">
                页面会连续展示任务进度、AI 分析步骤、关键指标和图表证据，最终生成固定结构的 Excel 报告。
              </p>
            </div>

            <div className="process-strip">
              {DEMO_STEPS.map((step, index) => (
                <div key={step.title} className="process-step">
                  <span className="process-step__index">{index + 1}</span>
                  <div className="process-step__title">{step.title}</div>
                  <p>{step.detail}</p>
                </div>
              ))}
            </div>
          </section>
        </div>

        <div className="home-operations">
          <UploadForm
            onSubmit={async (file, onUploadProgress) => {
              const job = await createJob(file, onUploadProgress);
              router.push(`/analysis/${job.job_id}`);
            }}
          />
        </div>
      </div>
    </div>
  );
}
