from __future__ import annotations

import re

DEFAULT_REPORT_TITLE = "轴承检测 SPC 报告"
DEFAULT_PRODUCT_NAME = "6205 轴承"
DEFAULT_TEMPLATE_REASON = "已根据异常数量和展示重点自动选择模板。"

_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]")

_CHART_TITLES = {
    "histogram": "测量值分布图",
    "control_chart_imr": "I-MR 控制图",
    "trend_line": "测量值趋势图",
    "spec_comparison": "测量值与规格对比图",
    "xbar_r": "Xbar-R 控制图",
}

_KPI_LABELS = {
    "mean": "均值",
    "std_dev": "标准差",
    "pass_rate": "合格率",
    "cpk": "Cpk",
}


def has_cjk_text(value: str) -> bool:
    return bool(_CJK_PATTERN.search(value))


def choose_chinese_text(value: str, fallback: str) -> str:
    candidate = value.strip()
    if candidate and has_cjk_text(candidate):
        return candidate
    return fallback


def choose_chinese_list(values: list[str], fallback: list[str]) -> list[str]:
    candidates = [value.strip() for value in values if value.strip()]
    if candidates and all(has_cjk_text(value) for value in candidates):
        return candidates
    return fallback


def report_metric_label(metric_key: str) -> str:
    return _KPI_LABELS.get(metric_key, metric_key)


def chart_title(chart_id: str) -> str:
    normalized = chart_id.strip().lower()
    return _CHART_TITLES.get(normalized, f"{chart_id} 图表")


def build_executive_summary(analysis: dict[str, object]) -> str:
    out_of_spec_count = int(analysis["out_of_spec_count"])
    cpk_value = analysis["cpk"]

    if out_of_spec_count:
        return f"发现 {out_of_spec_count} 个超出规格的点，过程需要重点复核。"
    if cpk_value is not None and float(cpk_value) < 1.0:
        return "当前未发现超规格点，但过程能力偏弱，需要持续关注波动趋势。"
    return "当前过程整体稳定，暂未发现超规格点。"


def build_quality_risk(analysis: dict[str, object]) -> str:
    out_of_spec_count = int(analysis["out_of_spec_count"])
    cpk_value = analysis["cpk"]

    if out_of_spec_count:
        return "当前批次存在超规格风险，建议优先复核过程能力与设备状态。"
    if cpk_value is not None and float(cpk_value) < 1.0:
        return "过程能力接近下限，建议持续监控并提前采取预防措施。"
    return "当前未见明显质量阻断风险，可继续按既定频率监控。"


def build_recommended_actions(analysis: dict[str, object]) -> list[str]:
    if int(analysis["out_of_spec_count"]):
        return [
            "复核超规格样本及其对应工序参数",
            "检查刀具磨损、设备漂移和最近一次调机记录",
        ]

    cpk_value = analysis["cpk"]
    if cpk_value is not None and float(cpk_value) < 1.0:
        return [
            "缩短下一批次的抽检间隔并重点关注边界样本",
            "检查设备设定与量具状态，确认过程中心是否持续漂移",
        ]

    return [
        "继续监控下一批次的过程波动",
        "保持当前抽检频率并记录关键设备参数",
    ]
