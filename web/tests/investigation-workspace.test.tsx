import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { InvestigationWorkspace } from "@/components/investigation-workspace";
import {
  decideInvestigationHypothesis,
  getInvestigation,
  getInvestigationAiResult,
  runInvestigationAi,
  type EvidenceGroundedInvestigationResult,
  type InvestigationCase
} from "@/lib/investigations";

jest.mock("@/lib/investigations", () => ({
  getInvestigation: jest.fn(),
  getInvestigationAiResult: jest.fn(),
  runInvestigationAi: jest.fn(),
  decideInvestigationHypothesis: jest.fn()
}));

const getInvestigationMock = getInvestigation as jest.MockedFunction<typeof getInvestigation>;
const getInvestigationAiResultMock = getInvestigationAiResult as jest.MockedFunction<typeof getInvestigationAiResult>;
const runInvestigationAiMock = runInvestigationAi as jest.MockedFunction<typeof runInvestigationAi>;
const decideHypothesisMock = decideInvestigationHypothesis as jest.MockedFunction<typeof decideInvestigationHypothesis>;

const evidence = {
  id: "E-GROUP-MACHINE-ID-CAVITY-ID",
  evidence_type: "group_difference" as const,
  title: "生产上下文不良率分层比较",
  statement: "不良主要集中于 machine_id=M02 / cavity_id=4。",
  metrics: {},
  sample_size: 96,
  filters: { machine_id: "M02", cavity_id: 4 },
  source_refs: ["demo.csv"],
  confidence: "high" as const,
  origin: "deterministic_tool" as const,
  created_at: "2026-08-20T00:00:00Z"
};

const candidateHypothesis = {
  id: "H-AI-001",
  statement: "M02 的 4 号型腔或对应刀具可能是优先验证的候选因素。",
  supporting_evidence_ids: ["E-GROUP-MACHINE-ID-CAVITY-ID"],
  contradicting_evidence_ids: [],
  confidence: "medium" as const,
  status: "candidate" as const,
  verification_actions: ["检查型腔定位状态"],
  decision: null
};

const verificationAction = {
  id: "A-AI-001",
  action_type: "verification" as const,
  title: "检查型腔定位状态",
  rationale: "用于验证候选假设。",
  status: "proposed" as const,
  related_hypothesis_ids: ["H-AI-001"],
  supporting_evidence_ids: ["E-GROUP-MACHINE-ID-CAVITY-ID"],
  owner: null,
  due_at: null,
  completed_at: null
};

function createCase(overrides: Partial<InvestigationCase> = {}): InvestigationCase {
  return {
    case_id: "CASE-1234",
    question: "为什么外径不良率升高？",
    scope: {
      quality_feature: "outer_diameter",
      start_at: "2026-08-13T08:00:00Z",
      end_at: "2026-08-13T15:55:00Z",
      filters: {}
    },
    state: "ready",
    source_refs: ["demo.csv"],
    evidence: [evidence],
    hypotheses: [],
    actions: [],
    missing_data: [],
    conclusion: null,
    error: null,
    created_at: "2026-08-20T00:00:00Z",
    updated_at: "2026-08-20T00:01:00Z",
    ...overrides
  };
}

const aiResult: EvidenceGroundedInvestigationResult = {
  plan: {
    interpreted_question: "定位外径不良升高的生产关联因素。",
    steps: [],
    missing_information: []
  },
  added_evidence: [],
  findings: [
    {
      id: "F-AI-001",
      finding_type: "association",
      statement: "异常主要集中于 M02 的 4 号型腔。",
      evidence_ids: ["E-GROUP-MACHINE-ID-CAVITY-ID"],
      confidence: "high"
    }
  ],
  hypotheses: [candidateHypothesis],
  actions: [verificationAction],
  missing_data: []
};

describe("InvestigationWorkspace", () => {
  let currentCase: InvestigationCase;

  beforeEach(() => {
    jest.clearAllMocks();
    currentCase = createCase();
    getInvestigationMock.mockImplementation(async () => currentCase);
    getInvestigationAiResultMock.mockResolvedValue(aiResult);
    runInvestigationAiMock.mockImplementation(async () => {
      currentCase = createCase({
        state: "waiting_for_user",
        hypotheses: [candidateHypothesis],
        actions: [verificationAction]
      });
      return aiResult;
    });
    decideHypothesisMock.mockImplementation(async (_caseId, _hypothesisId, input) => {
      currentCase = createCase({
        state: "waiting_for_user",
        hypotheses: [
          {
            ...candidateHypothesis,
            status: input.outcome,
            decision: {
              outcome: input.outcome,
              actor_type: "human",
              actor_id: input.actor_id,
              note: input.note,
              decided_at: "2026-08-20T01:00:00Z"
            }
          }
        ],
        actions: [verificationAction]
      });
      return currentCase;
    });
  });

  test("shows deterministic evidence, runs AI, and records a human decision", async () => {
    const user = userEvent.setup();
    render(<InvestigationWorkspace caseId="CASE-1234" />);

    expect(await screen.findByTestId("evidence-E-GROUP-MACHINE-ID-CAVITY-ID")).toHaveTextContent(
      "machine_id=M02"
    );

    await user.click(screen.getByRole("button", { name: "运行证据约束 AI" }));

    expect(await screen.findByTestId("investigation-findings")).toHaveTextContent(
      "异常主要集中于 M02 的 4 号型腔"
    );
    expect(screen.getByTestId("hypothesis-H-AI-001")).toHaveTextContent("候选");
    expect(runInvestigationAiMock).toHaveBeenCalledWith("CASE-1234");

    await user.click(screen.getByRole("button", { name: "确认根因" }));
    await user.type(screen.getByLabelText("操作者"), "quality-engineer-01");
    await user.type(screen.getByLabelText("验证说明"), "现场检查并完成复测后确认。" );
    await user.click(screen.getByRole("button", { name: "保存人工决定" }));

    await waitFor(() => {
      expect(decideHypothesisMock).toHaveBeenCalledWith(
        "CASE-1234",
        "H-AI-001",
        {
          outcome: "confirmed",
          actor_id: "quality-engineer-01",
          note: "现场检查并完成复测后确认。"
        }
      );
    });
    expect(await screen.findByTestId("decision-H-AI-001")).toHaveTextContent("人工确认记录");
  });
});
