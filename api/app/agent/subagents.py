DATA_UNDERSTANDING_SUBAGENT = {
    "name": "data-understanding",
    "description": "Interpret schema and confirm which columns matter for quality analysis.",
    "system_prompt": "Work only with provided metrics and return concise schema insight.",
    "tools": [],
}

QUALITY_ANALYST_SUBAGENT = {
    "name": "quality-analyst",
    "description": "Explain SPC results in quality engineering language.",
    "system_prompt": "Produce concise quality-engineering narrative and recommendations.",
    "tools": [],
}
