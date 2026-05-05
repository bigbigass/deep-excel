"""供 AI 规划器调用的受限工具。"""

from __future__ import annotations

from langchain_core.tools import tool

from api.app.services.report_localization import build_executive_summary


def choose_template_id(*, has_failures: bool, cpk: float | None) -> str:
    """基于是否超规和能力指数返回演示模板编号。"""
    if has_failures:
        return "template_a_overview"
    if cpk is not None and float(cpk) < 1.33:
        return "template_b_detailed"
    return "template_c_showcase"


@tool
def choose_template(has_failures: bool, cpk: float | None = None) -> str:
    """根据基础质量状态选择演示用报表模板。"""
    return choose_template_id(has_failures=has_failures, cpk=cpk)


@tool
def summarize_quality(mean_value: float, cpk: float | None, out_of_spec_count: int) -> str:
    """生成用于报表结论区的简短质量摘要。"""
    return build_executive_summary(
        {
            "mean": mean_value,
            "cpk": cpk,
            "out_of_spec_count": out_of_spec_count,
        }
    )
