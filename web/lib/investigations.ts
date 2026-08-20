import { API_BASE_URL } from "@/lib/api";

export type InvestigationState =
  | "created"
  | "mapping_required"
  | "ready"
  | "investigating"
  | "waiting_for_user"
  | "completed"
  | "failed";

export type EvidenceConfidence = "low" | "medium" | "high";
export type HypothesisStatus = "candidate" | "under_verification" | "confirmed" | "rejected";
export type ActionType = "containment" | "verification" | "corrective";
export type ActionStatus = "proposed" | "accepted" | "in_progress" | "completed" | "dismissed";

export type InvestigationScope = {
  quality_feature: string | null;
  start_at: string | null;
  end_at: string | null;
  filters: Record<string, unknown>;
};

export type EvidenceItem = {
  id: string;
  evidence_type:
    | "data_quality"
    | "spc_signal"
    | "change_point"
    | "group_difference"
    | "factor_association"
    | "event_comparison"
    | "historical_case"
    | "knowledge_document";
  title: string;
  statement: string;
  metrics: Record<string, unknown>;
  sample_size: number | null;
  filters: Record<string, unknown>;
  source_refs: string[];
  confidence: EvidenceConfidence;
  origin: "deterministic_tool" | "knowledge_source" | "human";
  created_at: string;
};

export type HypothesisDecision = {
  outcome: "confirmed" | "rejected";
  actor_type: "human";
  actor_id: string;
  note: string;
  decided_at: string;
};

export type InvestigationHypothesis = {
  id: string;
  statement: string;
  supporting_evidence_ids: string[];
  contradicting_evidence_ids: string[];
  confidence: EvidenceConfidence;
  status: HypothesisStatus;
  verification_actions: string[];
  decision: HypothesisDecision | null;
};

export type InvestigationAction = {
  id: string;
  action_type: ActionType;
  title: string;
  rationale: string;
  status: ActionStatus;
  related_hypothesis_ids: string[];
  supporting_evidence_ids: string[];
  owner: string | null;
  due_at: string | null;
  completed_at: string | null;
};

export type InvestigationCase = {
  case_id: string;
  question: string;
  scope: InvestigationScope;
  state: InvestigationState;
  source_refs: string[];
  evidence: EvidenceItem[];
  hypotheses: InvestigationHypothesis[];
  actions: InvestigationAction[];
  missing_data: string[];
  conclusion: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
};

export type InvestigationToolCall = {
  tool_name: string;
  arguments: Record<string, unknown>;
  reason: string;
};

export type InvestigationPlan = {
  interpreted_question: string;
  steps: InvestigationToolCall[];
  missing_information: string[];
};

export type InvestigationFinding = {
  id: string;
  finding_type: "fact" | "association";
  statement: string;
  evidence_ids: string[];
  confidence: EvidenceConfidence;
};

export type EvidenceGroundedInvestigationResult = {
  plan: InvestigationPlan;
  added_evidence: EvidenceItem[];
  findings: InvestigationFinding[];
  hypotheses: InvestigationHypothesis[];
  actions: InvestigationAction[];
  missing_data: string[];
};

export type HypothesisDecisionInput = {
  outcome: "confirmed" | "rejected";
  actor_id: string;
  note: string;
};

async function parseApiResponse<T>(response: Response): Promise<T> {
  if (response.ok) {
    return response.json() as Promise<T>;
  }

  let message = `Request failed with status ${response.status}`;
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string" && payload.detail.trim()) {
      message = payload.detail;
    }
  } catch {
    // Keep the status-based fallback when the upstream response is not JSON.
  }
  throw new Error(message);
}

export async function createInvestigation(question: string, file: File): Promise<{ case_id: string }> {
  const formData = new FormData();
  formData.append("question", question);
  formData.append("file", file);
  const response = await fetch(`${API_BASE_URL}/api/v1/investigations`, {
    method: "POST",
    body: formData
  });
  return parseApiResponse<{ case_id: string }>(response);
}

export async function getInvestigation(caseId: string): Promise<InvestigationCase> {
  const response = await fetch(`${API_BASE_URL}/api/v1/investigations/${caseId}`, {
    cache: "no-store"
  });
  return parseApiResponse<InvestigationCase>(response);
}

export async function runInvestigationAi(caseId: string): Promise<EvidenceGroundedInvestigationResult> {
  const response = await fetch(`${API_BASE_URL}/api/v1/investigations/${caseId}/ai`, {
    method: "POST"
  });
  return parseApiResponse<EvidenceGroundedInvestigationResult>(response);
}

export async function getInvestigationAiResult(caseId: string): Promise<EvidenceGroundedInvestigationResult> {
  const response = await fetch(`${API_BASE_URL}/api/v1/investigations/${caseId}/ai`, {
    cache: "no-store"
  });
  return parseApiResponse<EvidenceGroundedInvestigationResult>(response);
}

export async function decideInvestigationHypothesis(
  caseId: string,
  hypothesisId: string,
  input: HypothesisDecisionInput
): Promise<InvestigationCase> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/investigations/${caseId}/hypotheses/${hypothesisId}/decision`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input)
    }
  );
  return parseApiResponse<InvestigationCase>(response);
}
