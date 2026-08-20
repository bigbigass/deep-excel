import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { InvestigationCaseView } from "../components/investigation-case-view";
import type { InvestigationCase } from "../lib/investigations";


function createCase(overrides: Partial<InvestigationCase> = {}): InvestigationCase {
  return {
    case_id: "CASE-UI-001",
    question: "为什么外径不良率升高？",
    scope: {
      quality_feature: "outer_diameter",
      start_at: "2026-08-13T08:00:00Z",
      end_at: "2026-08-13T16:00:00Z",
      filters: {}
    },
    state: "ready",
    source_refs: ["sample_data/investigation_demo.csv"],
    evidence: [
      {
        id: "E-CHANGE-POINT",
        evidence_type: "change_point",
        title: "过程均值变化",
        statement: "过程均值在指定时间后发生显著上移。",
        metrics: { detected: true },
        sample_size: 96,
        filters: {},
        source_refs: ["sample_data/investigation_demo.csv"],
        confidence: "high",
        origin: "deterministic_tool"
      },
      {
        id: "E-GROUP-MACHINE-ID-CAVITY-ID",
        evidence_type: "group_difference",
        title: "设备型腔分层比较",
        statement: "不良集中于特定设备和型腔组合。",
        metrics: { difference_detected: true },
        sample_size: 96,
        filters: { machine_id: "M02", cavity_id: 4 },
        source_refs: ["sample_data/investigation_demo.csv"],
        confidence: "high",
        origin: "deterministic_tool"
      }
    ],
    hypotheses: [],
    actions: [],
    missing_data: ["缺少维修事件时间。"],
    conclusion: null,
    error: null,
    created_at: "2026-08-13T16:10:00Z",
    updated_at: "2026-08-13T16:11:00Z",
    ...overrides
  };
}


test("ready investigation displays deterministic evidence and runs AI on demand", async () => {
  const user = userEvent.setup();
  const onRunAi = jest.fn().mockResolvedValue(undefined);
  const onDecision = jest.fn().mockResolvedValue(undefined);
  render(
    <InvestigationCaseView
      caseData={createCase()}
      runningAi={false}
      onRunAi={onRunAi}
      onDecision={onDecision}
    />
  );

  expect(screen.getByTestId("evidence-E-CHANGE-POINT")).toHaveTextContent(
    "过程均值变化"
  );
  expect(
    screen.getByTestId("evidence-E-GROUP-MACHINE-ID-CAVITY-ID")
  ).toHaveTextContent("设备型腔分层比较");
  expect(screen.getByText("缺少维修事件时间。")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "让 AI 提出候选原因" }));
  expect(onRunAi).toHaveBeenCalledTimes(1);
});


test("candidate hypothesis requires a named human and note before confirmation", async () => {
  const user = userEvent.setup();
  const onDecision = jest.fn().mockResolvedValue(undefined);
  const caseData = createCase({
    state: "waiting_for_user",
    hypotheses: [
      {
        id: "H-001",
        statement: "设备型腔或刀具状态可能是候选因素。",
        supporting_evidence_ids: ["E-GROUP-MACHINE-ID-CAVITY-ID"],
        contradicting_evidence_ids: [],
        confidence: "high",
        status: "candidate",
        verification_actions: ["检查型腔定位和刀具磨损。"],
        decision: null
      }
    ],
    actions: [
      {
        id: "A-001",
        action_type: "verification",
        title: "开展现场检查",
        rationale: "先验证高风险生产组合。",
        status: "proposed",
        related_hypothesis_ids: ["H-001"],
        supporting_evidence_ids: ["E-GROUP-MACHINE-ID-CAVITY-ID"],
        owner: null,
        due_at: null,
        completed_at: null
      }
    ]
  });

  render(
    <InvestigationCaseView
      caseData={caseData}
      runningAi={false}
      onRunAi={jest.fn().mockResolvedValue(undefined)}
      onDecision={onDecision}
    />
  );

  await user.click(screen.getByRole("button", { name: "确认该候选原因" }));
  expect(screen.getByText("请填写操作人和现场判断依据。")).toBeInTheDocument();
  expect(onDecision).not.toHaveBeenCalled();

  await user.type(screen.getByLabelText("H-001 操作人"), "quality-engineer-01");
  await user.type(
    screen.getByLabelText("H-001 现场判断依据"),
    "现场检查确认定位块松动。"
  );
  await user.click(screen.getByRole("button", { name: "确认该候选原因" }));

  await waitFor(() => {
    expect(onDecision).toHaveBeenCalledWith(
      "H-001",
      "confirmed",
      "quality-engineer-01",
      "现场检查确认定位块松动。"
    );
  });
});


test("final hypothesis displays the audited decision instead of decision controls", () => {
  const caseData = createCase({
    state: "waiting_for_user",
    hypotheses: [
      {
        id: "H-001",
        statement: "设备型腔定位异常。",
        supporting_evidence_ids: ["E-GROUP-MACHINE-ID-CAVITY-ID"],
        contradicting_evidence_ids: [],
        confidence: "high",
        status: "confirmed",
        verification_actions: ["复测确认。"],
        decision: {
          outcome: "confirmed",
          actor_type: "human",
          actor_id: "quality-engineer-01",
          note: "现场检查确认定位块松动。",
          decided_at: "2026-08-13T17:00:00Z"
        }
      }
    ]
  });

  render(
    <InvestigationCaseView
      caseData={caseData}
      runningAi={false}
      onRunAi={jest.fn().mockResolvedValue(undefined)}
      onDecision={jest.fn().mockResolvedValue(undefined)}
    />
  );

  expect(screen.getByTestId("hypothesis-decision-H-001")).toHaveTextContent(
    "quality-engineer-01"
  );
  expect(screen.queryByRole("button", { name: "确认该候选原因" })).not.toBeInTheDocument();
});
