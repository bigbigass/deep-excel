"use client";

import { useState } from "react";

import { checkUpstreamHealth, type UpstreamCheckPayload } from "@/lib/api";

export function UpstreamCheckCard() {
  const [result, setResult] = useState<UpstreamCheckPayload | null>(null);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const statusLabel = result ? (!result.configured ? "未配置" : result.reachable ? "可用" : "不可用") : null;
  const statusTone = result
    ? !result.configured
      ? "status-pill--warning"
      : result.reachable
        ? "status-pill--success"
        : "status-pill--danger"
    : "status-pill--neutral";

  return (
    <section aria-busy={isLoading} className="upstream-panel">
      <div className="section-heading">
        <div>
          <p className="section-heading__eyebrow">模型检查</p>
          <h2 className="section-heading__title">上游模型状态</h2>
          <p className="section-heading__subtitle">检查当前演示环境中的模型服务是否可访问。</p>
        </div>
        <button
          className="button-secondary"
          disabled={isLoading}
          onClick={async () => {
            setIsLoading(true);
            setRequestError(null);
            try {
              setResult(await checkUpstreamHealth());
            } catch {
              setRequestError("检测请求失败");
            } finally {
              setIsLoading(false);
            }
          }}
          type="button"
        >
          {isLoading ? "检查中..." : "检查模型状态"}
        </button>
      </div>

      {requestError ? <p className="feedback-error">{requestError}</p> : null}

      {result ? (
        <div className="overview-grid">
          <div className="info-tile">
            <p className="info-tile__eyebrow">状态</p>
            <div className="info-tile__title">连通结果</div>
            <p>
              <span className={`status-pill ${statusTone}`}>{statusLabel}</span>
            </p>
          </div>
          <div className="info-tile">
            <p className="info-tile__eyebrow">模型</p>
            <div className="info-tile__title">当前模型</div>
            <p>{result.model}</p>
          </div>
          <div className="info-tile">
            <p className="info-tile__eyebrow">延迟</p>
            <div className="info-tile__title">响应时间</div>
            <p>{result.latency_ms === null ? "n/a" : `${result.latency_ms} ms`}</p>
          </div>
          <div className="info-tile">
            <p className="info-tile__eyebrow">地址</p>
            <div className="info-tile__title">服务基址</div>
            <p>{result.base_url ?? "n/a"}</p>
          </div>
          <div className="info-tile">
            <p className="info-tile__eyebrow">预览</p>
            <div className="info-tile__title">返回内容</div>
            <p>{result.response_preview ?? "n/a"}</p>
          </div>
          <div className="info-tile">
            <p className="info-tile__eyebrow">错误</p>
            <div className="info-tile__title">错误信息</div>
            <p>{result.error ?? "无"}</p>
          </div>
        </div>
      ) : (
        <p className="panel-copy">尚未执行检查。</p>
      )}
    </section>
  );
}
