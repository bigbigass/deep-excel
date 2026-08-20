"use client";

import { FormEvent, useMemo, useState } from "react";

import type {
  HypothesisDecisionInput,
  InvestigationAction,
  InvestigationHypothesis
} from "@/lib/investigations";

const STATUS_LABELS: Record<InvestigationHypothesis["status"], string> = {
  candidate: "候选",
  under_verification: "验证中",
  confirmed: "已确认",
  rejected: "已排除"
};

function statusTone(status: InvestigationHypothesis["status"]) {
  if (status === "confirmed") {
    return "status-pill status-pill--success";
  }
  if (status === "rejected") {
    return "status-pill status-pill--neutral";
  }
  return "status-pill status-pill--warning";
}

type HypothesisReviewProps = {
  hypothesis: InvestigationHypothesis;
  actions: InvestigationAction[];
  onDecision: (
    hypothesisId: string,
    input: HypothesisDecisionInput
  ) => Promise<void>;
};

function HypothesisReview({ hypothesis, actions, onDecision }: HypothesisReviewProps) {
  const [actorId, setActorId] = useState("");
  const [note, setNote] = useState("");
  const [outcome, setOutcome] = useState<"confirmed" | "rejected" | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const relatedActions = useMemo(
    () => actions.filter((action) => action.related_hypothesis_ids.includes(hypothesis.id)),
    [actions, hypothesis.id]
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!outcome) {
      setError("请选择确认或排除。");
      return;
    }
    if (!actorId.trim() || !note.trim()) {
      setError("人工决定必须记录操作者和验证说明。");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await onDecision(hypothesis.id, {
        outcome,
        actor_id: actorId.trim(),
        note: note.trim()
      });
    } catch (decisionError) {
      setError(decisionError instanceof Error ? decisionError.message : "提交人工决定失败");
      setSubmitting(false);
    }
  }

  const terminal = hypothesis.status === "confirmed" || hypothesis.status === "rejected";

  return (
    <article className="hypothesis-card" data-testid={`hypothesis-${hypothesis.id}`}>
      <header className="hypothesis-card__header">
        <div>
          <div className="hypothesis-card__id">{hypothesis.id}</div>
          <h3 className="hypothesis-card__title">{hypothesis.statement}</h3>
        </div>
        <span className={statusTone(hypothesis.status)}>{STATUS_LABELS[hypothesis.status]}</span>
      </header>

      <div className="hypothesis-card__evidence">
        <div>
          <strong>支持证据</strong>
          <div className="evidence-reference-list">
            {hypothesis.supporting_evidence_ids.map((evidenceId) => (
              <span className="micro-chip" key={evidenceId}>{evidenceId}</span>
            ))}
          </div>
        </div>
        {hypothesis.contradicting_evidence_ids.length > 0 ? (
          <div>
            <strong>反向证据</strong>
            <div className="evidence-reference-list">
              {hypothesis.contradicting_evidence_ids.map((evidenceId) => (
                <span className="micro-chip" key={evidenceId}>{evidenceId}</span>
              ))}
            </div>
          </div>
        ) : null}
      </div>

      {relatedActions.length > 0 ? (
        <div className="hypothesis-card__actions">
          <strong>验证动作</strong>
          <ol>
            {relatedActions.map((action) => (
              <li key={action.id}>
                <span>{action.title}</span>
                <small>{action.rationale}</small>
              </li>
            ))}
          </ol>
        </div>
      ) : null}

      {terminal && hypothesis.decision ? (
        <div className="human-decision-summary" data-testid={`decision-${hypothesis.id}`}>
          <strong>{hypothesis.status === "confirmed" ? "人工确认记录" : "人工排除记录"}</strong>
          <p>{hypothesis.decision.note}</p>
          <span>{hypothesis.decision.actor_id} · {new Date(hypothesis.decision.decided_at).toLocaleString("zh-CN")}</span>
        </div>
      ) : (
        <form className="hypothesis-decision-form" onSubmit={handleSubmit}>
          <div className="hypothesis-decision-form__choice" role="group" aria-label="人工判断">
            <button
              className={outcome === "confirmed" ? "decision-choice decision-choice--selected" : "decision-choice"}
              type="button"
              onClick={() => setOutcome("confirmed")}
            >
              确认根因
            </button>
            <button
              className={outcome === "rejected" ? "decision-choice decision-choice--selected" : "decision-choice"}
              type="button"
              onClick={() => setOutcome("rejected")}
            >
              排除候选
            </button>
          </div>
          <div className="hypothesis-decision-form__fields">
            <label>
              <span>操作者</span>
              <input
                className="investigation-input"
                value={actorId}
                onChange={(event) => setActorId(event.target.value)}
                placeholder="质量工程师姓名或工号"
              />
            </label>
            <label>
              <span>验证说明</span>
              <textarea
                className="investigation-input investigation-input--textarea"
                value={note}
                onChange={(event) => setNote(event.target.value)}
                rows={3}
                placeholder="记录现场检查、试验或复测依据"
              />
            </label>
          </div>
          {error ? <div className="feedback-error" role="alert">{error}</div> : null}
          <button className="button-primary" type="submit" disabled={submitting}>
            {submitting ? "正在保存…" : "保存人工决定"}
          </button>
        </form>
      )}
    </article>
  );
}

type InvestigationHypothesisListProps = {
  hypotheses: InvestigationHypothesis[];
  actions: InvestigationAction[];
  onDecision: HypothesisReviewProps["onDecision"];
};

export function InvestigationHypothesisList({
  hypotheses,
  actions,
  onDecision
}: InvestigationHypothesisListProps) {
  if (hypotheses.length === 0) {
    return (
      <div className="empty-state investigation-empty-state">
        <h3 className="section-heading__title">尚无候选根因</h3>
        <p>确定性证据准备完成后，可以调用 AI 生成有证据引用的候选假设和验证动作。</p>
      </div>
    );
  }

  return (
    <div className="investigation-hypothesis-list" data-testid="investigation-hypothesis-list">
      {hypotheses.map((hypothesis) => (
        <HypothesisReview
          key={hypothesis.id}
          hypothesis={hypothesis}
          actions={actions}
          onDecision={onDecision}
        />
      ))}
    </div>
  );
}
