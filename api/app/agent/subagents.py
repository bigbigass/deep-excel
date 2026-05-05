"""Deep Agents 子代理配置。"""

# 负责解释输入数据结构，让主代理明确哪些列与质量分析最相关。
DATA_UNDERSTANDING_SUBAGENT = {
    "name": "data-understanding",
    "description": "Interpret schema and confirm which columns matter for quality analysis.",
    "system_prompt": "Work only with provided metrics and return concise schema insight.",
    "tools": [],
}

# 负责把统计结果翻译成质量工程语境下的中文结论。
QUALITY_ANALYST_SUBAGENT = {
    "name": "quality-analyst",
    "description": "Explain SPC results in quality engineering language.",
    "system_prompt": "Produce concise quality-engineering narrative and recommendations.",
    "tools": [],
}
