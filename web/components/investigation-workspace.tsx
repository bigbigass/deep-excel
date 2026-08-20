"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { InvestigationEvidenceList } from "@/components/investigation-evidence-list";
import { InvestigationHypothesisList } from "@/components/investigation-hypothesis-list";
import {
  decideInvestigationHypothesis,
  getInvestigation,
  getInvestigationAiResult,
  getInvestigationExportUrl,
  runInvestigationAi,
  type EvidenceGroundedInvestigationResult,
  type HypothesisDecisionInput,
  type InvestigationCase,
  type InvestigationState
} from "@/lib/investigations";

const STATE_LABELS: Record<InvestigationState, string> = {
  created: "已创建",
  mapping_required: "待确认字段",
  ready: "证据已就绪",
  investigating: "正在分析",
  waiting_for_user: "等待人工判断",
  completed: "已完成",
  failed: "失败"
};

function stateTone(state: InvestigationState | undefined) {
  if (state === "failed") {
    return "status-pill status-pill--danger";
  }
  if (state === "completed") {
    return "status-pill status-pill--success";
  }
  if (state === "ready" || state === "waiting_for_user") {
    return "status-pill status-pill--warning";
  }
  return "status-pill status-pill--neutral";
}

function formatScopeDate(value: string | null) {
  if (!value) {
    return "未识别";
  }
  return new Date(value).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function isPollingState(state: InvestigationState) {
  return state === "created" || state === "investigating";
}

function InvestigationFindings({ result }: { result: EvidenceGroundedInvestigationResult }) {
  if (result.findings.length === 0) {
    return null;
  }

  return (
    <section className="surface-card investigation-section" data-testid="investigation-findings">
      <div className="section-heading">
        <div>
          <p className="section-heading__eyebrow">AI 归纳</p>
          <h2 className="section-heading__title">基于证据形成的发现</h2>
          <p className="section-heading__subtitle">
            每条发现都必须引用已有证据；这里不允许把统计关联写成已确认因果。
          </p>
        </div>
        <span className="status-pill status-pill--success">{result.findings.length} 条</span>
      </div>
      <div className="finding-list">
        {result.findings.map((finding) => (
          <article className="finding-row" key={finding.id}>
            <div className="finding-row__marker">{finding.finding_type === "fact" ? "事实" : "关联"}</div>
            <div>
              <div className="finding-row__id">{finding.id}</div>
              <p>{finding.statement}</p>
              <div className="evidence-reference-list">
                {finding.evidence_ids.map((evidenceId) => (
                  <span className="micro-chip" key={evidenceId}>{evidenceId}</span>
                ))}
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

export function InvestigationWorkspace({ caseId }: { caseId: string }) {
  const [caseData, setCaseData] = useState<InvestigationCase | null>(null);
  const [aiResult, setAiResult] = useState<EvidenceGroundedInvestigationResult | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [aiError, setAiError] = useState<string | null>(null);
  const [runningAi, setRunningAi] = useState(false);

  const refreshCase = useCallback(async () => {
    const payload = await getInvestigation(caseId);
    setCaseData(payload);
    setPageError(null);
    return payload;
  }, [caseId]);

  const refreshAiResult = useCallback(async () => {
    try {
      const payload = await getInvestigationAiResult(caseId);
      setAiResult(payload);
      return payload;
    } catch (error) {
      const message = error instanceof Error ? error.message : "读取 AI 调查结果失败";
      if (!message.includes("not found") && !message.includes("未找到")) {
        setAiError(message);
      }
      return null;
    }
  }, [caseId]);

  useEffect(() => {
    let disposed = false;
    let pollTimer: number | undefined;

    const poll = async () => {
      try {
        const payload = await getInvestigation(caseId);
        if (disposed) {
          return;
        }
        setCaseData(payload);
        setPageError(null);

        if (payload.state === "waiting_for_user" || payload.hypotheses.length > 0) {
          void refreshAiResult();
        }
        if (isPollingState(payload.state)) {
          pollTimer = window.setTimeout(poll, 1200);
        }
      } catch (error) {
        if (disposed) {
          return;
        }
        setPageError(error instanceof Error ? error.message : "读取调查案件失败");
        pollTimer = window.setTimeout(poll, 2000);
      }
    };

    void poll();
    return () => {
      disposed = true;
      if (pollTimer) {
        window.clearTimeout(pollTimer);
      }
    };
  }, [caseId, refreshAiResult]);

  async function handleRunAi() {
    setRunningAi(true);
    setAiError(null);
    try {
      const result = await runInvestigationAi(caseId);
      setAiResult(result);
      await refreshCase();
    } catch (error) {
      setAiError(error instanceof Error ? error.message : "生成候选根因失败");
    } finally {
      setRunningAi(false);
    }
  }

  async function handleDecision(hypothesisId: string, input: HypothesisDecisionInput) {
    const updated = await decideInvestigationHypothesis(caseId, hypothesisId, input);
    setCaseData(updated);
  }

  const containmentActions = useMemo(
    () => caseData?.actions.filter((action) => action.action_type === "containment") ?? [],
    [caseData]
  );

  const aiAvailable = caseData?.state === "ready" && !aiResult && caseData.hypotheses.length === 0;
  const exportAvailable = Boolean(
    caseData
      && !isPollingState(caseData.state)
      && caseData.state !== "failed"
      && caseData.state !== "mapping_required"
  );
  const evidenceCount = caseData?.evidence.length ?? 0;
  const hypothesisCount = caseData?.hypotheses.length ?? 0;

  return (
    <div className="page page-reveal">
      <section className="page-header investigation-page-header">
        <p className="page-header__eyebrow">质量异常调查</p>
        <div className="page-header__title-row">
          <div>
            <h1 className="page-header__title">{caseData?.question ?? "正在读取调查案件"}</h1>
            <p className="page-header__subtitle">
              先查看确定性证据，再让 AI 生成候选根因；最终确认权始终由现场人员掌握。
            </p>
          </div>
          <div className="page-header__meta">
            <span className="meta-chip"><strong>案件</strong>{caseId}</span>
            <span className={stateTone(caseData?.state)}>
              {caseData ? STATE_LABELS[caseData.state] : "加载中"}
            </span>
          </div>
        </div>
        <div className="page-header__actions">
          {exportAvailable ? (
            <a className="button-primary" href={getInvestigationExportUrl(caseId)}>
              下载调查报告
            </a>
          ) : null}
          <Link className="button-secondary" href="/investigations/new">新建调查</Link>
          <Link className="button-ghost" href="/">返回报告演示</Link>
        </div>
      </section>

      {pageError ? <div className="feedback-error" role="alert">{pageError}</div> : null}

      <div className="investigation-summary-grid">
        <div className="info-tile">
          <p className="info-tile__eyebrow">证据</p>
          <strong>{evidenceCount}</strong>
          <p>确定性分析与后续工具产生的可追溯证据。</p>
        </div>
        <div className="info-tile">
          <p className="info-tile__eyebrow">候选根因</p>
          <strong>{hypothesisCount}</strong>
          <p>默认仅为候选，未经人工验证不会变成结论。</p>
        </div>
        <div className="info-tile">
          <p className="info-tile__eyebrow">调查范围</p>
          <strong className="info-tile__compact-value">{caseData?.scope.quality_feature ?? "待识别"}</strong>
          <p>{formatScopeDate(caseData?.scope.start_at ?? null)} — {formatScopeDate(caseData?.scope.end_at ?? null)}</p>
        </div>
      </div>

      <div className="investigation-layout">
        <main className="investigation-main">
          <section className="surface-card investigation-section">
            <div className="section-heading">
              <div>
                <p className="section-heading__eyebrow">证据时间线</p>
                <h2 className="section-heading__title">系统已经观察到什么</h2>
                <p className="section-heading__subtitle">
                  证据按生成顺序排列。数字、设备编号和统计结论均来自确定性工具。
                </p>
              </div>
              <span className="status-pill status-pill--neutral">{evidenceCount} 条</span>
            </div>
            <InvestigationEvidenceList evidence={caseData?.evidence ?? []} />
          </section>

          {aiResult ? <InvestigationFindings result={aiResult} /> : null}

          <section className="surface-card investigation-section">
            <div className="section-heading">
              <div>
                <p className="section-heading__eyebrow">候选假设</p>
                <h2 className="section-heading__title">需要现场验证的可能原因</h2>
                <p className="section-heading__subtitle">
                  AI 只能提出候选假设和验证动作；确认或排除必须留下人工记录。
                </p>
              </div>
              <span className="status-pill status-pill--warning">{hypothesisCount} 项</span>
            </div>
            <InvestigationHypothesisList
              hypotheses={caseData?.hypotheses ?? []}
              actions={caseData?.actions ?? []}
              onDecision={handleDecision}
            />
          </section>
        </main>

        <aside className="investigation-side">
          <section className="surface-card investigation-control-card">
            <p className="section-heading__eyebrow">调查控制</p>
            <h2 className="section-heading__title">生成候选根因</h2>
            <p className="section-heading__subtitle">
              AI 将读取当前证据，必要时选择白名单分析工具，并输出带证据编号的候选假设。
            </p>
            <button
              className="button-primary investigation-control-card__button"
              type="button"
              onClick={handleRunAi}
              disabled={!aiAvailable || runningAi}
            >
              {runningAi ? "正在调查…" : aiResult || hypothesisCount > 0 ? "AI 调查已完成" : "运行证据约束 AI"}
            </button>
            {!aiAvailable && !aiResult && caseData?.state !== "failed" ? (
              <p className="supporting-copy">确定性证据完成后按钮会自动可用。</p>
            ) : null}
            {aiError ? <div className="feedback-error" role="alert">{aiError}</div> : null}
          </section>

          <section className="surface-card investigation-plan-card">
            <p className="section-heading__eyebrow">AI 调查计划</p>
            <h2 className="section-heading__title">本次调用了什么</h2>
            {aiResult ? (
              <>
                <p className="section-heading__subtitle">{aiResult.plan.interpreted_question}</p>
                {aiResult.plan.steps.length > 0 ? (
                  <ol className="investigation-plan-list">
                    {aiResult.plan.steps.map((step, index) => (
                      <li key={`${step.tool_name}-${index}`}>
                        <strong>{step.tool_name}</strong>
                        <span>{step.reason}</span>
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="supporting-copy">现有确定性证据已经足够，本次没有追加分析工具。</p>
                )}
              </>
            ) : (
              <p className="section-heading__subtitle">运行 AI 后，这里会公开展示工具名称和选择理由，不展示隐藏推理。</p>
            )}
          </section>

          {containmentActions.length > 0 ? (
            <section className="surface-card investigation-action-card">
              <p className="section-heading__eyebrow">风险控制</p>
              <h2 className="section-heading__title">建议的围堵动作</h2>
              <div className="investigation-action-list">
                {containmentActions.map((action) => (
                  <div key={action.id}>
                    <strong>{action.title}</strong>
                    <p>{action.rationale}</p>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          <section className="surface-card investigation-missing-card">
            <p className="section-heading__eyebrow">数据缺口</p>
            <h2 className="section-heading__title">还缺什么</h2>
            {caseData?.missing_data.length ? (
              <ul className="bullet-list">
                {caseData.missing_data.map((item) => <li key={item}>{item}</li>)}
              </ul>
            ) : (
              <p className="section-heading__subtitle">当前未记录阻断调查的数据缺口。</p>
            )}
          </section>

          {caseData?.state === "failed" ? (
            <section className="surface-card">
              <p className="section-heading__eyebrow">失败信息</p>
              <h2 className="section-heading__title">调查执行失败</h2>
              <p className="section-heading__subtitle">{caseData.error ?? "未知错误"}</p>
            </section>
          ) : null}
        </aside>
      </div>
    </div>
  );
}
