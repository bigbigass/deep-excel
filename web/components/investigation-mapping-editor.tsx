"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import type {
  ColumnRole,
  SchemaMappingConfirmationInput,
  SchemaMappingProposal
} from "@/lib/investigations";

const ROLE_OPTIONS: Array<{ value: ColumnRole; label: string; group: string }> = [
  { value: "ignore", label: "不使用", group: "其他" },
  { value: "measurement_value", label: "测量值（必需）", group: "质量结果" },
  { value: "target", label: "目标值", group: "质量结果" },
  { value: "usl", label: "规格上限 USL", group: "质量结果" },
  { value: "lsl", label: "规格下限 LSL", group: "质量结果" },
  { value: "quality_feature", label: "质量特性 / 检测项目", group: "质量结果" },
  { value: "sample_id", label: "样本 / 序列号", group: "追溯" },
  { value: "batch_id", label: "生产批次", group: "追溯" },
  { value: "measured_at", label: "测量时间", group: "追溯" },
  { value: "sequence_index", label: "采样序号", group: "追溯" },
  { value: "machine_id", label: "设备 / 机台", group: "生产上下文" },
  { value: "station_id", label: "工位", group: "生产上下文" },
  { value: "cavity_id", label: "型腔 / 模穴", group: "生产上下文" },
  { value: "shift", label: "班次", group: "生产上下文" },
  { value: "operator_id", label: "操作员", group: "生产上下文" },
  { value: "material_lot", label: "材料批次", group: "生产上下文" },
  { value: "tool_id", label: "刀具 / 工装", group: "生产上下文" },
  { value: "tool_cycles", label: "刀具寿命 / 使用次数", group: "生产上下文" }
];

const ORIGIN_LABELS: Record<string, string> = {
  canonical: "标准字段",
  rule: "规则建议",
  ai: "AI 建议",
  human: "人工确认"
};

const GENERATED_BY_LABELS: Record<string, string> = {
  canonical: "标准字段自动识别",
  deterministic: "规则识别",
  ai: "AI 识别",
  hybrid: "规则 + AI",
  human: "人工确认"
};

function initialRoles(proposal: SchemaMappingProposal): Record<string, ColumnRole> {
  return Object.fromEntries(
    proposal.mappings.map((item) => [item.source_column, item.role])
  ) as Record<string, ColumnRole>;
}

function duplicateAssignedRoles(roles: Record<string, ColumnRole>): ColumnRole[] {
  const counts = new Map<ColumnRole, number>();
  Object.values(roles).forEach((role) => {
    if (role !== "ignore") {
      counts.set(role, (counts.get(role) ?? 0) + 1);
    }
  });
  return Array.from(counts.entries())
    .filter(([, count]) => count > 1)
    .map(([role]) => role);
}

function confidenceTone(confidence: number) {
  if (confidence >= 0.9) {
    return "mapping-confidence mapping-confidence--high";
  }
  if (confidence >= 0.65) {
    return "mapping-confidence mapping-confidence--medium";
  }
  return "mapping-confidence mapping-confidence--low";
}

type InvestigationMappingEditorProps = {
  proposal: SchemaMappingProposal;
  onConfirm: (input: SchemaMappingConfirmationInput) => Promise<void>;
};

export function InvestigationMappingEditor({
  proposal,
  onConfirm
}: InvestigationMappingEditorProps) {
  const [roles, setRoles] = useState<Record<string, ColumnRole>>(() => initialRoles(proposal));
  const [actorId, setActorId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setRoles(initialRoles(proposal));
    setError(null);
  }, [proposal]);

  const mappingBySource = useMemo(
    () => new Map(proposal.mappings.map((item) => [item.source_column, item])),
    [proposal]
  );
  const roleGroups = useMemo(
    () => Array.from(new Set(ROLE_OPTIONS.map((item) => item.group))),
    []
  );
  const assignedCount = Object.values(roles).filter((role) => role !== "ignore").length;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedActor = actorId.trim();
    if (!normalizedActor) {
      setError("请填写确认该字段映射的质量人员姓名或工号。");
      return;
    }
    if (!Object.values(roles).includes("measurement_value")) {
      setError("必须指定一个“测量值”字段，统计调查才能继续。");
      return;
    }
    const duplicates = duplicateAssignedRoles(roles);
    if (duplicates.length > 0) {
      setError(`同一个业务角色只能分配给一个源列：${duplicates.join("、")}`);
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await onConfirm({
        actor_id: normalizedActor,
        mappings: proposal.source_columns.map((sourceColumn) => ({
          source_column: sourceColumn,
          role: roles[sourceColumn] ?? "ignore"
        }))
      });
    } catch (confirmationError) {
      setError(
        confirmationError instanceof Error
          ? confirmationError.message
          : "字段映射确认失败"
      );
      setSubmitting(false);
    }
  }

  return (
    <section className="surface-card mapping-editor" data-testid="investigation-mapping-editor">
      <div className="mapping-editor__header">
        <div>
          <p className="section-heading__eyebrow">字段确认</p>
          <h2 className="section-heading__title">确认客户表格中的业务语义</h2>
          <p className="section-heading__subtitle">
            规则和 AI 只提供建议。只有你确认后的字段才会进入 SPC、变化点和因素关联分析。
          </p>
        </div>
        <div className="mapping-editor__summary">
          <span className="meta-chip"><strong>文件</strong>{proposal.file_name}</span>
          <span className="meta-chip"><strong>来源</strong>{GENERATED_BY_LABELS[proposal.generated_by]}</span>
          <span className="status-pill status-pill--warning">{assignedCount} 个有效字段</span>
        </div>
      </div>

      {proposal.warnings.length > 0 ? (
        <div className="mapping-warning-list" role="status">
          <strong>识别提示</strong>
          <ul>
            {proposal.warnings.map((warning) => <li key={warning}>{warning}</li>)}
          </ul>
        </div>
      ) : null}

      <form onSubmit={handleSubmit}>
        <div className="mapping-table-wrap">
          <table className="mapping-table">
            <thead>
              <tr>
                <th>源列</th>
                <th>业务角色</th>
                <th>可信度</th>
                <th>建议来源</th>
                <th>识别依据</th>
              </tr>
            </thead>
            <tbody>
              {proposal.source_columns.map((sourceColumn) => {
                const suggestion = mappingBySource.get(sourceColumn);
                if (!suggestion) {
                  return null;
                }
                return (
                  <tr key={sourceColumn}>
                    <td><code>{sourceColumn}</code></td>
                    <td>
                      <select
                        className="mapping-role-select"
                        aria-label={`字段 ${sourceColumn} 的角色`}
                        value={roles[sourceColumn] ?? "ignore"}
                        onChange={(event) => {
                          setRoles((current) => ({
                            ...current,
                            [sourceColumn]: event.target.value as ColumnRole
                          }));
                          setError(null);
                        }}
                      >
                        {roleGroups.map((group) => (
                          <optgroup key={group} label={group}>
                            {ROLE_OPTIONS.filter((option) => option.group === group).map((option) => (
                              <option key={option.value} value={option.value}>{option.label}</option>
                            ))}
                          </optgroup>
                        ))}
                      </select>
                    </td>
                    <td>
                      <span className={confidenceTone(suggestion.confidence)}>
                        {(suggestion.confidence * 100).toFixed(0)}%
                      </span>
                    </td>
                    <td>{ORIGIN_LABELS[suggestion.origin] ?? suggestion.origin}</td>
                    <td className="mapping-table__reasoning">{suggestion.reasoning}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="mapping-confirmation-bar">
          <label>
            <span>确认人员</span>
            <input
              className="investigation-input"
              value={actorId}
              onChange={(event) => setActorId(event.target.value)}
              placeholder="质量工程师姓名或工号"
            />
          </label>
          <div className="mapping-confirmation-bar__copy">
            确认后将立即标准化数据并运行确定性调查。原始文件保持不变。
          </div>
          <button className="button-primary" type="submit" disabled={submitting}>
            {submitting ? "正在验证并分析…" : "确认字段并开始调查"}
          </button>
        </div>

        {error ? <div className="feedback-error mapping-editor__error" role="alert">{error}</div> : null}
      </form>
    </section>
  );
}
