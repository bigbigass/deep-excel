import Link from "next/link";

import { API_BASE_URL } from "@/lib/api";

export default async function ReportPage({
  params,
  searchParams
}: {
  params: Promise<{ reportId: string }>;
  searchParams: Promise<{ file?: string }>;
}) {
  const { reportId } = await params;
  const { file } = await searchParams;
  const downloadUrl = `${API_BASE_URL}/api/v1/reports/${file ?? ""}`;

  return (
    <div className="page page-reveal">
      <section className="page-header">
        <p className="page-header__eyebrow">报告结果</p>
        <div className="page-header__title-row">
          <div>
            <h1 className="page-header__title">报告已生成</h1>
            <p className="page-header__subtitle">分析完成后，系统已经整理出可下载的 Excel 报告。</p>
          </div>
          <div className="page-header__meta">
            <span className="meta-chip">
              <strong>报告编号</strong>
              <span>{reportId}</span>
            </span>
            <span className="meta-chip">
              <strong>文件名</strong>
              <span>{file ?? "未提供"}</span>
            </span>
          </div>
        </div>
      </section>

      <div className="report-layout">
        <section className="report-download">
          <div className="section-heading">
            <div>
              <p className="section-heading__eyebrow">下载报告</p>
              <h2 className="section-heading__title">Excel 报告可直接交付</h2>
              <p className="section-heading__subtitle">适合用于现场演示、内部复核和结果留档。</p>
            </div>
            <span className="status-pill status-pill--success">可下载</span>
          </div>

          <div className="report-grid">
            <div className="report-grid__card">
              <p className="section-heading__eyebrow">报告信息</p>
              <div className="report-grid__title">本次交付内容</div>
              <p>当前报告与分析任务一一对应，便于后续追溯和再次演示。</p>
              <ul>
                <li>报告编号：{reportId}</li>
                <li>目标文件：{file ?? "未提供"}</li>
              </ul>
            </div>
            <div className="report-grid__card">
              <p className="section-heading__eyebrow">报告包含</p>
              <div className="report-grid__title">默认输出内容</div>
              <ul>
                <li>关键质量指标与执行摘要</li>
                <li>图表证据与异常说明</li>
                <li>风险提示与建议动作</li>
              </ul>
            </div>
          </div>

          <div className="report-download__actions">
            <a className="button-primary" href={downloadUrl}>
              下载 Excel 报告
            </a>
            <Link className="button-secondary" href="/">
              重新上传数据
            </Link>
          </div>
        </section>
      </div>
    </div>
  );
}
