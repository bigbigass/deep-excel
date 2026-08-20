"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { createInvestigation } from "@/lib/investigations";

export function InvestigationCreateForm() {
  const router = useRouter();
  const [question, setQuestion] = useState("为什么最近一段时间外径不良率升高？");
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedQuestion = question.trim();
    if (!normalizedQuestion) {
      setError("请先填写需要调查的质量问题。以“为什么”开头通常更容易得到清晰结果。");
      return;
    }
    if (!file) {
      setError("请选择包含测量值、规格限和生产上下文的 CSV 或 Excel 文件。");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const payload = await createInvestigation(normalizedQuestion, file);
      router.push(`/investigations/${payload.case_id}`);
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : "创建调查失败");
      setSubmitting(false);
    }
  }

  return (
    <section className="upload-console investigation-create-panel" data-testid="investigation-create-form">
      <div className="section-heading">
        <div>
          <p className="section-heading__eyebrow">创建调查</p>
          <h2 className="section-heading__title">描述问题并上传数据</h2>
          <p className="section-heading__subtitle">
            系统先运行确定性统计，再由 AI 基于证据提出候选根因；任何根因都需要人工确认。
          </p>
        </div>
      </div>

      <form className="investigation-form" onSubmit={handleSubmit}>
        <label className="investigation-field">
          <span className="investigation-field__label">调查问题</span>
          <textarea
            className="investigation-input investigation-input--textarea"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            rows={4}
            maxLength={500}
            placeholder="例如：为什么最近三天外径不良率升高？"
          />
          <span className="helper-text">问题会成为整个证据链和后续 AI 调查计划的边界。</span>
        </label>

        <label className="investigation-field">
          <span className="investigation-field__label">质量数据文件</span>
          <span className="investigation-file-picker">
            <input
              type="file"
              accept=".csv,.xlsx,.xlsm"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
            <span>
              {file ? `${file.name} · ${(file.size / 1024).toFixed(1)} KB` : "选择 CSV、XLSX 或 XLSM"}
            </span>
          </span>
          <span className="helper-text">
            当前 MVP 建议包含 measurement_value、usl、lsl、measured_at，以及设备、型腔、班次、材料批次或刀具等上下文字段。
          </span>
        </label>

        {error ? <div className="feedback-error" role="alert">{error}</div> : null}

        <div className="investigation-form__actions">
          <button className="button-primary" type="submit" disabled={submitting}>
            {submitting ? "正在创建调查…" : "开始质量调查"}
          </button>
          <Link className="button-secondary" href="/sample-data/investigation_demo.csv" download>
            下载演示数据
          </Link>
        </div>
      </form>
    </section>
  );
}
