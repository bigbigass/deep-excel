import pytest

from api.app.agent.investigation_planner import (
    InvestigationPlan,
    InvestigationPlanner,
)


AVAILABLE_COLUMNS = {
    "measurement_value",
    "lsl",
    "usl",
    "measured_at",
    "machine_id",
    "cavity_id",
    "material_lot",
    "tool_cycles",
}


class FakeStructuredModel:
    def __init__(self, output: dict[str, object]) -> None:
        self.output = output
        self.schema = None
        self.messages = None

    def with_structured_output(self, schema):
        self.schema = schema
        return self

    def invoke(self, messages):
        self.messages = messages
        return self.output


def test_planner_returns_only_validated_whitelist_steps() -> None:
    model = FakeStructuredModel(
        {
            "interpreted_question": "定位外径不良率升高的时间和生产条件。",
            "steps": [
                {
                    "tool_name": "detect_mean_change_point",
                    "arguments": {},
                    "reason": "先确定过程从何时开始变化。",
                },
                {
                    "tool_name": "compare_group_failure_rates",
                    "arguments": {"group_by": ["machine_id", "cavity_id"]},
                    "reason": "判断异常是否集中在特定设备与型腔。",
                },
                {
                    "tool_name": "rank_failure_associations",
                    "arguments": {
                        "candidate_columns": ["material_lot", "tool_cycles"]
                    },
                    "reason": "比较材料和刀具寿命与不良结果的关联。",
                },
            ],
            "missing_information": ["缺少维修事件时间。"],
        }
    )
    planner = InvestigationPlanner(model=model)

    plan = planner.plan(
        question="为什么最近外径不良率升高？",
        available_columns=AVAILABLE_COLUMNS,
    )

    assert isinstance(plan, InvestigationPlan)
    assert [step.tool_name for step in plan.steps] == [
        "detect_mean_change_point",
        "compare_group_failure_rates",
        "rank_failure_associations",
    ]
    assert plan.steps[1].arguments == {
        "group_by": ["machine_id", "cavity_id"]
    }
    assert model.schema is InvestigationPlan
    assert "run_arbitrary_python" not in str(model.messages)


def test_planner_rejects_unknown_tool_even_when_model_requests_it() -> None:
    planner = InvestigationPlanner(
        model=FakeStructuredModel(
            {
                "interpreted_question": "执行任意代码。",
                "steps": [
                    {
                        "tool_name": "run_arbitrary_python",
                        "arguments": {"code": "import os"},
                        "reason": "绕过白名单。",
                    }
                ],
                "missing_information": [],
            }
        )
    )

    with pytest.raises(ValueError, match="unknown investigation tool"):
        planner.plan(
            question="执行分析",
            available_columns=AVAILABLE_COLUMNS,
        )


def test_planner_rejects_columns_not_present_in_dataset() -> None:
    planner = InvestigationPlanner(
        model=FakeStructuredModel(
            {
                "interpreted_question": "按不存在的设备列比较。",
                "steps": [
                    {
                        "tool_name": "compare_group_failure_rates",
                        "arguments": {"group_by": ["imaginary_machine"]},
                        "reason": "比较设备。",
                    }
                ],
                "missing_information": [],
            }
        )
    )

    with pytest.raises(ValueError, match="unavailable columns"):
        planner.plan(
            question="哪个设备有问题？",
            available_columns=AVAILABLE_COLUMNS,
        )


def test_planner_rejects_duplicate_tool_requests() -> None:
    duplicate_step = {
        "tool_name": "detect_spc_signals",
        "arguments": {},
        "reason": "检查 SPC 信号。",
    }
    planner = InvestigationPlanner(
        model=FakeStructuredModel(
            {
                "interpreted_question": "检查过程信号。",
                "steps": [duplicate_step, duplicate_step],
                "missing_information": [],
            }
        )
    )

    with pytest.raises(ValueError, match="duplicate investigation plan step"):
        planner.plan(
            question="过程是否异常？",
            available_columns=AVAILABLE_COLUMNS,
        )
