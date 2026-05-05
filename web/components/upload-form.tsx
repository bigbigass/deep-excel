"use client";

import { useState } from "react";

const SAMPLE_FILES = [
  {
    label: "稳定过程",
    fileName: "normal_batch.csv",
    href: "/sample-data/normal_batch.csv"
  },
  {
    label: "均值偏移",
    fileName: "shifted_mean_batch.csv",
    href: "/sample-data/shifted_mean_batch.csv"
  },
  {
    label: "波动偏高",
    fileName: "high_variation_batch.csv",
    href: "/sample-data/high_variation_batch.csv"
  },
  {
    label: "超出规格",
    fileName: "out_of_spec_batch.csv",
    href: "/sample-data/out_of_spec_batch.csv"
  }
];

export function UploadForm({ onSubmit }: { onSubmit: (file: File, onProgress: (progress: number) => void) => Promise<void> }) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const progressLabel =
    uploadProgress >= 100 ? "上传完成，等待分析结果..." : `上传中 ${uploadProgress}%`;

  return (
    <form
      className="upload-console"
      onSubmit={async (event) => {
        event.preventDefault();
        if (!selectedFile || isSubmitting) {
          return;
        }

        setSubmitError(null);
        setUploadProgress(0);
        setIsSubmitting(true);

        try {
          await onSubmit(selectedFile, (progress) => setUploadProgress(progress));
        } catch {
          setSubmitError("上传失败，请重试");
        } finally {
          setIsSubmitting(false);
        }
      }}
    >
      <div className="section-heading">
        <div>
          <p className="section-heading__eyebrow">演示入口</p>
          <h2 className="section-heading__title">上传检测文件</h2>
          <p className="section-heading__subtitle">上传后会直接进入分析过程页，向客户展示 AI 如何判断数据并生成报告。</p>
        </div>
      </div>

      <div className="upload-dropzone">
        <label htmlFor="inspection-file">检测数据文件</label>
        <input
          id="inspection-file"
          name="inspection-file"
          type="file"
          accept=".csv,.xlsx"
          disabled={isSubmitting}
          onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
        />
        <p className="helper-text">支持 CSV / XLSX 格式</p>
        {selectedFile ? (
          <div className="file-chip">
            <strong>已选文件</strong>
            <span>{selectedFile.name}</span>
          </div>
        ) : (
          <p className="supporting-copy">建议包含测量值、规格上下限、批次或时间字段。</p>
        )}
      </div>

      <section className="sample-downloads" aria-labelledby="sample-downloads-title">
        <div>
          <h3 id="sample-downloads-title">测试文件下载</h3>
          <p>客户可以先下载任一样例，再上传到上方入口验证分析和导出流程。</p>
        </div>
        <div className="sample-downloads__grid">
          {SAMPLE_FILES.map((sample) => (
            <a className="sample-download" download href={sample.href} key={sample.fileName}>
              <span>{sample.label}</span>
              <strong>{sample.fileName}</strong>
            </a>
          ))}
        </div>
      </section>

      {isSubmitting ? (
        <div className="progress-panel" aria-live="polite">
          <div className="progress-bar">
            <div
              aria-label="上传进度"
              aria-valuemax={100}
              aria-valuemin={0}
              aria-valuenow={uploadProgress}
              className="progress-bar__value"
              role="progressbar"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
          <p className="helper-text">{progressLabel}</p>
        </div>
      ) : null}

      {submitError ? <p className="feedback-error">{submitError}</p> : null}

      <div className="upload-actions">
        <button className="button-primary" disabled={!selectedFile || isSubmitting} type="submit">
          {isSubmitting ? "上传中..." : "开始分析"}
        </button>
      </div>
    </form>
  );
}
