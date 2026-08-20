"use client";

import { useState } from "react";

import type {
  InvestigationCase,
  InvestigationHypothesis
} from "@/lib/investigations";

const STATE_LABELS: Record<InvestigationCase["state"], string> = {
  created: "已创建",
  mapping_required: "待确认字段",
  ready: "确定性分析完成",
  investigating: "调查中",
  waiting_for_user: "等待人工判断",
  completed: "已完成",
  failed: "失败"
};

const CONFIDENCE_LABELS = {
  low: "低",
  medium: "中",
  high: "高"
};

function HypothesisCard({
  hypothesis,
  onDecision
}: {
  hypothesis: InvestigationHypothesis;
  onDecision: (
    hypothesisId: string,
    outcome: "confirmed" | "rejected",
    actorId: string,
    note: string
  ) => Promise<void>;
}) {
  const [actorId, setActorId] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const final = hypothesis.status === "confirmed" || hypothesis.status === "rejected";

  const submitDecision = async (outcome: "confirmed" | "rejected") => {
    if (!actorId.trim() || !note.trim()) {
      setError("请填写操作人和现场判断依据。");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await onDecision(hypothesis.id, outcome, actorId.trim(), note.trim());
    } catch (decisionError) {
      setError(decisionError instanceof Error ? decisionError.message : "提交决定失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <article className="surface-card" data-testid={`hypothesis-${hypothesis.id}`}>
      <div className="section-heading">
        <div>
          <p className="section-heading__eyebrow">候选根因 {hypothesis.id}</p>
          <h3 className="section-heading__title">{hypothesis.statement}</h3>
        </div>
        <span
          className={`status-pill ${
            hypothesis.status === "confirmed"
              ? "status-pill--success"
              : hypothesis.status === "rejected"
                ? "status-pill--danger"
                : "status-pill--warning"
          }`}
        >
          {hypothesis.status === "candidate"
            ? "待验证"
            : hypothesis.status === "under_verification"
              ? "验证中"
              : hypothesis.status === "confirmed"
                ? "已确认"
                : "已排除"}
        </span>
      </div>

      <p className="section-heading__subtitle">
        置信度：{CONFIDENCE_LABELS[hypothesis.confidence]}。该置信度表示证据支持程度，不代表因果关系已经确认。
      </p>

      <div className="report-grid">
        <div className="report-grid__card">
          <p className="section-heading__eyebrow">支持证据</p>
          <div className="report-grid__title">
            {hypothesis.supporting_evidence_ids.join("、")}
          </div>
        </div>
        <div className="report-grid__card">
          <p className="section-heading__eyebrow">反向或排除证据</p>
          <div className="report-grid__title">
            {hypothesis.contradicting_evidence_ids.length > 0
              ? hypothesis.contradicting_evidence_ids.join("、")
              : "暂无"}
          </div>
        </div>
      </div>

      <div>
        <p className="section-heading__eyebrow">验证动作</p>
        <ul className="bullet-list">
          {hypothesis.verification_actions.map((action) => (
            <li key={action}>{action}</li>
          ))}
        </ul>
      </div>

      {final && hypothesis.decision ? (
        <div className="surface-card" data-testid={`hypothesis-decision-${hypothesis.id}`}>
          <p className="section-heading__eyebrow">人工决定</p>
          <p>
            {hypothesis.decision.actor_id}：{hypothesis.decision.note}
          </p>
        </div>
      ) : (
        <div className="surface-card">
          <p className="section-heading__eyebrow">人工验证结果</p>
          <label className="form-field">
            <span>操作人</span>
            <input
              aria-label={`${hypothesis.id} 操作人`}
              value={actorId}
              onChange={(event) => setActorId(event.target.value)}
              placeholder="例如：quality-engineer-01"
            />
          </label>
          <label className="form-field">
            <span>现场判断依据</span>
            <textarea
              aria-label={`${hypothesis.id} 现场判断依据`}
              rows={3}
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="说明检查、试验或复测结果。"
            />
          </label>
          {error ? <div className="feedback-error">{error}</div> : null}
          <div className="page-header__actions">
            <button
              className="button-primary"
              type="button"
              disabled={busy}
              onClick={() => void submitDecision("confirmed")}
            >
              确认该候选原因
            </button>
            <button
              className="button-secondary"
              type="button"
              disabled={busy}
              onClick={() => void submitDecision("rejected")}
            >
              排除该候选原因
            </button>
          </div>
        </div>
      )}
    </article>
  );
}

export function InvestigationCaseView({
  caseData,
  runningAi,
  onRunAi,
  onDecision
}: {
  caseData: InvestigationCase;
  runningAi: boolean;
  onRunAi: () => Promise<void>;
  onDecision: (
    hypothesisId: string,
    outcome: "confirmed" | "rejected",
    actorId: string,
    note: string
  ) => Promise<void>;
}) {
  return (
    <div className="analysis-layout" data-testid="investigation-case-view">
      <main className="analysis-main">
        <section className="surface-card">
          <div className="section-heading">
            <div>
              <p className="section-heading__eyebrow">调查问题</p>
              <h2 className="section-heading__title">{caseData.question}</h2>
              <p className="section-heading__subtitle">
                {caseData.scope.quality_feature
                  ? `质量特征：${caseData.scope.quality_feature}`
                  : "质量特征尚未明确"}
              </p>
            </div>
            <span className="status-pill status-pill--warning">
              {STATE_LABELS[caseData.state]}
            </span>
          </div>

          {caseData.state === "ready" ? (
            <div className="page-header__actions">
              <button
                className="button-primary"
                type="button"
                disabled={runningAi}
                onClick={() => void onRunAi()}
              >
                {runningAi ? "AI 正在整理证据..." : "让 AI 提出候选原因"}
              </button>
            </div>
          ) : null}

          {caseData.error ? <div className="feedback-error">{caseData.error}</div> : null}
        </section>

        <section className="surface-card">
          <div className="section-heading">
            <div>
              <p className="section-heading__eyebrow">证据台账</p>
              <h2 className="section-heading__title">确定性工具生成的调查证据</h2>
              <p className="section-heading__subtitle">
                AI 只能引用这些证据，不能自行补写统计数字。
              </p>
            </div>
            <span className="status-pill status-pill--success">
              {caseData.evidence.length} 条证据
            </span>
          </div>

          <div className="report-grid">
            {caseData.evidence.map((evidence) => (
              <article
                className="report-grid__card"
                key={evidence.id}
                data-testid={`evidence-${evidence.id}`}
              >
                <p className="section-heading__eyebrow">
                  {evidence.id} · 置信度 {CONFIDENCE_LABELS[evidence.confidence]}
                </p>
                <div className="report-grid__title">{evidence.title}</div>
                <p>{evidence.statement}</p>
              </article>
            ))}
          </div>
        </section>

        {caseData.hypotheses.length > 0 ? (
          <section>
            <div className="section-heading">
              <div>
                <p className="section-heading__eyebrow">候选根因</p>
                <h2 className="section-heading__title">等待现场验证与人工决定</h2>
              </div>
            </div>
            <div className="analysis-main">
              {caseData.hypotheses.map((hypothesis) => (
                <HypothesisCard
                  key={hypothesis.id}
                  hypothesis={hypothesis}
                  onDecision={onDecision}
                />
              ))}
            </div>
          </section>
        ) : null}
      </main>

      <aside className="analysis-side">
        <section className="surface-card">
          <div className="section-heading">
            <div>
              <p className="section-heading__eyebrow">案件信息</p>
              <h2 className="section-heading__title">{caseData.case_id}</h2>
            </div>
          </div>
          <ul className="bullet-list">
            <li>状态：{STATE_LABELS[caseData.state]}</li>
            <li>证据：{caseData.evidence.length} 条</li>
            <li>候选原因：{caseData.hypotheses.length} 条</li>
            <li>建议动作：{caseData.actions.length} 条</li>
          </ul>
        </section>

        {caseData.actions.length > 0 ? (
          <section className="surface-card">
            <p className="section-heading__eyebrow">建议动作</p>
            <ul className="bullet-list">
              {caseData.actions.map((action) => (
                <li key={action.id}>
                  <strong>{action.title}</strong>：{action.rationale}
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {caseData.missing_data.length > 0 ? (
          <section className="surface-card">
            <p className="section-heading__eyebrow">仍缺少的数据</p>
            <ul className="bullet-list">
              {caseData.missing_data.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </section>
        ) : null}
      </aside>
    </div>
  );
}
