import type { EvidenceConfidence, EvidenceItem } from "@/lib/investigations";

const EVIDENCE_TYPE_LABELS: Record<EvidenceItem["evidence_type"], string> = {
  data_quality: "数据质量",
  spc_signal: "SPC 信号",
  change_point: "变化点",
  group_difference: "分组差异",
  factor_association: "因素关联",
  event_comparison: "事件对比",
  historical_case: "历史案例",
  knowledge_document: "知识文档"
};

const CONFIDENCE_LABELS: Record<EvidenceConfidence, string> = {
  high: "高可信",
  medium: "中等可信",
  low: "低可信"
};

function confidenceTone(confidence: EvidenceConfidence) {
  if (confidence === "high") {
    return "status-pill status-pill--success";
  }
  if (confidence === "medium") {
    return "status-pill status-pill--warning";
  }
  return "status-pill status-pill--neutral";
}

export function InvestigationEvidenceList({ evidence }: { evidence: EvidenceItem[] }) {
  if (evidence.length === 0) {
    return (
      <div className="empty-state investigation-empty-state">
        <h3 className="section-heading__title">证据尚未生成</h3>
        <p>系统完成数据读取后，会在这里依次展示数据质量、SPC、变化点和生产因素证据。</p>
      </div>
    );
  }

  return (
    <div className="investigation-evidence-list" data-testid="investigation-evidence-list">
      {evidence.map((item, index) => (
        <article className="evidence-card" key={item.id} data-testid={`evidence-${item.id}`}>
          <div className="evidence-card__rail" aria-hidden="true">
            <span>{index + 1}</span>
          </div>
          <div className="evidence-card__body">
            <header className="evidence-card__header">
              <div className="evidence-card__identity">
                <span className="evidence-card__id">{item.id}</span>
                <span className="evidence-card__type">{EVIDENCE_TYPE_LABELS[item.evidence_type]}</span>
              </div>
              <span className={confidenceTone(item.confidence)}>{CONFIDENCE_LABELS[item.confidence]}</span>
            </header>
            <h3 className="evidence-card__title">{item.title}</h3>
            <p className="evidence-card__statement">{item.statement}</p>
            <footer className="evidence-card__meta">
              <span>样本量：{item.sample_size ?? "未提供"}</span>
              <span>{item.origin === "deterministic_tool" ? "确定性分析工具" : "外部证据来源"}</span>
            </footer>
          </div>
        </article>
      ))}
    </div>
  );
}
