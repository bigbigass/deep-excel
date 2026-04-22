# DeepExcel SPC AI Report Demo Design

- Date: `2026-04-21`
- Project: `deepexcel`
- Scope: `MVP demo for AI-assisted bearing inspection report generation`

## 1. Summary

This project will deliver a demo web application that accepts inspection data exported from measurement equipment in `Excel` or `CSV` format, performs deterministic statistical and SPC analysis, uses an AI agent to generate report narrative and choose an appropriate report template, and renders the final output into a polished `Excel` report.

The demo is intentionally designed to look like a real product while remaining technically reliable. The system will not ask AI to freely manipulate Excel layouts. Instead, it will use a controlled template system, deterministic computation for SPC and chart generation, and AI only for bounded decisions such as report emphasis, template selection, anomaly explanation, and recommendation text.

## 2. Current Context

- The current workspace is effectively empty and does not contain an existing application structure.
- There is no confirmed real customer sample data yet.
- There are no confirmed production report templates yet.
- The immediate goal is a convincing demo, not a production-complete platform.
- The demo should still align with realistic manufacturing quality and SPC practices so it does not feel like a generic AI showcase.

## 3. Product Goal

Build a demo that proves the following value proposition:

1. The system can understand uploaded inspection data.
2. The system can compute meaningful SPC and quality metrics.
3. The system can generate quality-engineering style narrative and recommendations.
4. The system can render the analysis into one of several polished Excel report templates.

The desired customer reaction is: this already looks like the foundation of a usable inspection reporting system.

## 4. Goals

### 4.1 Functional goals

- Upload `xlsx` or `csv` inspection data through a web interface.
- Normalize the uploaded data into a standard internal structure.
- Detect core semantic fields such as measurement value, batch, timestamp or sequence, and specification limits.
- Compute deterministic statistics and SPC outputs.
- Generate charts suitable for the available data.
- Produce AI-generated report summary, anomaly interpretation, and recommended actions.
- Select one of several predefined Excel report templates.
- Render a final `.xlsx` report with tables, charts, and narrative sections.
- Allow the user to preview results and download the Excel file.

### 4.2 Demo goals

- Look polished enough for a customer-facing demo.
- Show multiple templates to demonstrate flexibility.
- Show multiple SPC visuals to demonstrate domain relevance.
- Show an AI explanation layer without making the system depend on unstable free-form AI layout behavior.

## 5. Non-goals

The MVP demo will not attempt to do the following:

- Interpret arbitrary unknown customer Excel templates without configuration.
- Support PDF, scanned image, or OCR-based input.
- Connect directly to inspection hardware.
- Provide a multi-tenant business platform.
- Provide user roles, approvals, or enterprise auth.
- Support every SPC chart family.
- Offer full historical report management.
- Use AI to directly edit arbitrary Excel objects or perform uncontrolled layout generation.

## 6. Key Product Principles

### 6.1 AI decides, software renders

AI should decide what to emphasize in the report, which template fits best, how to explain anomalies, and which chart types should appear. Programmatic modules should perform calculations, draw charts, and write Excel content.

### 6.2 Deterministic quality calculations

Statistics, SPC formulas, pass or fail determination, and chart data must come from deterministic code rather than model inference.

### 6.3 Controlled template system

The system should not support free-form report editing in the MVP. It should support a small set of carefully designed templates with explicit content slots.

### 6.4 Demo reliability over surface novelty

The system should optimize for a successful demo path. A stable report generation flow is more important than attempting overly dynamic behavior.

## 7. Assumptions and Constraints

Because customer details are limited, the MVP will adopt the following explicit assumptions:

- Input data will be tabular and available as `xlsx` or `csv`.
- The target domain is bearing inspection or a similar dimensional quality workflow.
- The most useful first-pass measurements are continuous numeric values with optional `USL`, `LSL`, and target values.
- Some files will include a natural order field such as timestamp, sample index, or row order.
- Demo sample data can be synthetic but should look realistic.
- Charts will be generated as images and inserted into Excel instead of building complex native Excel chart objects.
- Only a small number of templates will exist in the MVP.

## 8. User Flow

### 8.1 Primary happy path

1. User opens the web app.
2. User uploads an `xlsx` or `csv` file.
3. System parses the file and infers data schema.
4. System computes quality metrics and SPC outputs.
5. AI agent selects a report emphasis and template.
6. AI agent generates narrative summary, anomaly explanation, and recommended actions.
7. Rendering pipeline creates charts and fills the chosen Excel template.
8. User sees a results preview page.
9. User downloads the final Excel report.

### 8.2 Assisted path for uncertain schema

If the schema inference is uncertain, the UI may ask the user to confirm key columns such as measurement value, `USL`, `LSL`, batch, or timestamp. The system should still aim to auto-complete the flow by default.

## 9. Architecture Overview

The recommended architecture is a lightweight web front end with a Python back end and a bounded Deep Agents orchestration layer.

### 9.1 High-level layers

- `Web UI`: file upload, analysis preview, template preview, download.
- `API layer`: upload handling, analysis orchestration, report generation endpoints.
- `Core analytics layer`: data normalization, SPC calculation, anomaly rules.
- `Agent layer`: schema interpretation assistance, template selection, narrative generation, report planning.
- `Rendering layer`: chart creation, template loading, Excel writing.

### 9.2 Why Deep Agents is the right top layer

This project is not a single prompt-and-response workflow. It requires multiple coordinated steps, tool usage, bounded planning, and room for future expansion into more templates and domain rules. Deep Agents is the right top-level framework because it provides planning and delegation while still allowing deterministic tools to do the real work.

### 9.3 Why not rely on LangGraph first

Custom LangGraph orchestration would be more precise but unnecessary for the first demo. The current workflow is complex enough to benefit from agent orchestration, but not so custom that a hand-built graph should be the starting point.

## 10. Recommended Technology Stack

### 10.1 Front end

- `Next.js`
- `React`
- `Tailwind CSS`

Rationale: suitable for a polished demo, easy file upload flow, and expandable for future productization.

### 10.2 Back end

- `FastAPI`

Rationale: fits naturally with Python data processing, Excel rendering, and Deep Agents integration.

### 10.3 Agent and model stack

- `deepagents`
- `langchain`
- `langchain-core`
- `langsmith`
- One model provider only in MVP, preferably either `langchain-openai` or `langchain-anthropic`

Rationale: keep model surface area small, focus on reliability, and keep tracing available.

### 10.4 Data and analysis stack

- `pandas`
- `numpy`
- `scipy`

### 10.5 Chart generation

- `matplotlib`

### 10.6 Excel rendering

- `openpyxl`

## 11. Proposed Repository Structure

```text
web/
api/
agent/
core/
rendering/
templates/
sample_data/
outputs/
docs/superpowers/specs/
```

### 11.1 Folder responsibilities

- `web/`: front-end app and pages.
- `api/`: FastAPI app and endpoints.
- `agent/`: Deep Agents configuration, tools, and subagent definitions.
- `core/`: schema inference, normalization, SPC calculations, anomaly rules, report data models.
- `rendering/`: chart image creation, template loader, and Excel renderer.
- `templates/`: Excel templates and template manifests.
- `sample_data/`: synthetic demo datasets.
- `outputs/`: generated charts and reports for local runs.

## 12. Standardized Input Model

The system will normalize uploaded source files into a standard measurement-oriented structure.

### 12.1 Canonical record fields

- `sample_id`
- `batch_id`
- `part_number`
- `inspection_item`
- `measurement_value`
- `target_value`
- `usl`
- `lsl`
- `unit`
- `measured_at`
- `sequence_index`
- `operator_name`
- `device_name`

Not every source file must contain every field. The normalized structure should preserve missing values while identifying the minimum viable analysis columns.

### 12.2 Minimum columns required for the demo

- At least one numeric measurement field.
- At least one ordering field, either an explicit timestamp, a sequence index, or row order.
- Optional but strongly preferred: `USL` and `LSL`.

## 13. Template System Design

### 13.1 Controlled template model

Each report template consists of two parts:

1. `template.xlsx`: the Excel visual skeleton.
2. `template_manifest.json`: the slot map and rendering rules.

### 13.2 Template slot philosophy

The renderer owns cell ranges and style behavior. The agent does not output raw cell coordinates. Instead, templates expose semantic slots such as:

- `title_slot`
- `meta_slot`
- `summary_slot`
- `kpi_slot`
- `detail_table_slot`
- `chart_slot_1`
- `chart_slot_2`
- `chart_slot_3`
- `conclusion_slot`
- `image_slot_1`

### 13.3 Initial template set

- `template_a_overview`: management-style summary report.
- `template_b_detailed`: engineering-style detailed report.
- `template_c_showcase`: demo-oriented polished customer report.

### 13.4 Template selection rules

The agent can choose only from the registered template IDs. If selection confidence is low or generation fails, the system must fall back to `template_a_overview`.

## 14. Core Intermediate Contract: report_spec

The most important system contract is `report_spec`. All upstream processing must converge into this structure, and the renderer must consume only this structure.

### 14.1 report_spec responsibilities

- Capture chosen template.
- Capture report metadata.
- Capture summary metrics.
- Capture chart requirements.
- Capture anomaly findings.
- Capture AI narrative.
- Capture rendering options.

### 14.2 Proposed report_spec shape

```json
{
  "report_meta": {
    "title": "Bearing Inspection SPC Report",
    "report_id": "RPT-20260421-001",
    "generated_at": "2026-04-21T10:00:00Z",
    "batch_id": "BATCH-001",
    "product_name": "6205 Bearing"
  },
  "template_decision": {
    "template_id": "template_a_overview",
    "reason": "Data includes clear specification limits and is best presented with summary-first layout"
  },
  "dataset_summary": {
    "sample_count": 125,
    "inspection_item_count": 1,
    "has_spec_limits": true,
    "has_sequence": true,
    "overall_pass_rate": 0.964
  },
  "kpi_cards": [
    {"label": "Mean", "value": "10.022"},
    {"label": "Std Dev", "value": "0.018"},
    {"label": "Pass Rate", "value": "96.4%"},
    {"label": "Cp", "value": "1.24"},
    {"label": "Cpk", "value": "0.91"}
  ],
  "detail_tables": [
    {
      "table_id": "measurement_detail",
      "title": "Measurement Detail",
      "columns": ["sample_id", "measurement_value", "lsl", "usl", "status"],
      "rows": []
    }
  ],
  "chart_specs": [
    {"chart_id": "hist_1", "chart_type": "histogram", "title": "Value Distribution"},
    {"chart_id": "imr_1", "chart_type": "control_chart_imr", "title": "I-MR Control Chart"},
    {"chart_id": "trend_1", "chart_type": "trend_line", "title": "Measurement Trend"}
  ],
  "anomalies": [
    {
      "severity": "medium",
      "type": "rule_violation",
      "summary": "Two points exceed the upper control limit",
      "evidence": ["sample_018", "sample_019"]
    }
  ],
  "ai_narrative": {
    "executive_summary": "Process center is drifting upward and short-term variability increased in the final section of the batch.",
    "quality_risk": "Capability is marginal because Cpk is below the target threshold.",
    "recommended_actions": [
      "Check machine condition during the final third of the batch",
      "Review gauge stability and operator change timing"
    ]
  },
  "image_assets": [],
  "render_options": {
    "include_detail_page": true,
    "include_appendix": false
  }
}
```

### 14.3 Allowed chart types in MVP

- `histogram`
- `control_chart_imr`
- `control_chart_xbar_r`
- `trend_line`
- `capability_summary`
- `spec_comparison`

The renderer should reject unknown chart types and fall back gracefully.

## 15. SPC and Statistical Strategy

### 15.1 Deterministic calculations only

The following outputs must be computed in code:

- Mean
- Standard deviation
- Max and min
- Pass rate
- Control limits
- Capability metrics such as `Cp` and `Cpk`

### 15.2 First chart family set

The MVP should support:

- `I-MR` control chart
- `Histogram`
- `Trend line`
- `Specification comparison`
- `Cp/Cpk` summary card

### 15.3 Conditional chart selection rules

- If there is one primary numeric series and a valid order field, generate `I-MR`, `Histogram`, and `Trend line`.
- If `USL` and `LSL` are present, compute and display `Cp/Cpk` and specification comparison.
- If valid subgroup data is explicitly present, `Xbar-R` may be used.
- If there is not enough data for a chart, display a professional explanation instead of failing.

### 15.4 Rules the system must respect

- Do not compute `Cpk` without valid spec limits.
- Do not claim trend behavior without an order field.
- Do not default to `Xbar-R` unless subgroup structure is clearly known.

## 16. Anomaly Detection Strategy

The MVP should combine deterministic rule detection with AI explanation.

### 16.1 Deterministic rule examples

- Value beyond `USL` or `LSL`
- Value beyond `UCL` or `LCL`
- Sustained upward or downward trend
- Multiple consecutive points on one side of center line
- Sudden increase in moving range or variability

### 16.2 AI explanation examples

AI should transform rule outcomes into quality-engineering language such as:

- Process center appears shifted toward the upper specification limit.
- Short-term variability increased during the latter portion of the batch.
- Current capability is insufficient for a stable release recommendation.

The language should sound like a quality or process engineer, not generic AI prose.

## 17. Agent Design

### 17.1 Main orchestration agent

- Name: `report-orchestrator`
- Role: coordinate end-to-end analysis and report planning

### 17.2 Initial subagents

- `data-understanding`
  - infers semantic column roles
  - decides whether schema confidence is sufficient
- `quality-analyst`
  - interprets computed metrics and anomaly signals
  - generates summary, risk statement, and recommended actions

The report-planning logic may begin inside the main agent and later be extracted into its own subagent if needed.

### 17.3 Tools exposed to the main agent

- `parse_input_file`
- `infer_schema`
- `compute_spc_metrics`
- `detect_anomalies`
- `build_chart_specs`
- `generate_chart_images`
- `render_excel_report`
- `save_report_assets`

### 17.4 Agent boundary rules

- Agents do not calculate formulas directly.
- Agents do not write Excel cell coordinates.
- Agents do not create arbitrary layout instructions.
- Agents only produce bounded decisions and structured narrative.

## 18. Web Experience Design

### 18.1 Page set

The MVP should include three pages:

1. `Upload page`
2. `Analysis results page`
3. `Report output page`

### 18.2 Upload page

Should include:

- File upload area
- Supported format note
- Demo sample download
- Brief value statement

### 18.3 Analysis results page

Should include:

- Schema recognition summary
- Data quality summary
- KPI cards
- Chart previews
- AI analysis summary
- Chosen template and reason

This is the strongest customer-facing page because it shows that the system understands the data before generating the report.

### 18.4 Report output page

Should include:

- Final report summary
- Generated chart count
- Template used
- Download Excel button
- Re-run analysis button

## 19. Rendering Strategy

### 19.1 Tables

Tables are rendered by code into predefined template regions.

### 19.2 Charts

Charts are generated as image files and embedded into template slots.

### 19.3 Images

If source images are available in the future, they should be inserted into predefined image slots. Images are out of scope for initial demo input but the slot design remains in place.

### 19.4 Fallback behavior

- If AI template selection fails, use `template_a_overview`.
- If AI narrative generation fails, use rule-based fallback text.
- If a chart cannot be generated, render an explanatory placeholder section.
- If a non-critical slot cannot be filled, continue report generation and log the issue.

## 20. Demo Dataset Strategy

Because no real data is currently available, the demo should include synthetic but realistic bearing inspection datasets.

### 20.1 Required demo scenarios

- `normal_batch`: stable process, in control, good capability
- `shifted_mean_batch`: mean drifts toward one specification limit
- `out_of_spec_batch`: a few values exceed spec limits
- `high_variation_batch`: variability increases later in the run

### 20.2 Why this matters

These scenarios create believable charts and make the AI narrative visibly useful during the demo.

## 21. MVP Scope Definition

### 21.1 Must-have scope

- Upload `xlsx` and `csv`
- Normalize data into canonical schema
- Compute basic statistics and SPC outputs
- Generate at least two chart types
- Produce AI narrative
- Render one final `.xlsx`
- Support at least two templates, with three preferred
- Provide web preview and download flow

### 21.2 Explicitly deferred

- Arbitrary template ingestion
- OCR and PDF processing
- Native Excel chart generation as a primary strategy
- Database-backed historical platform features
- Complex role management
- Full manufacturing execution integration

## 22. Acceptance Criteria

The MVP is acceptable when all of the following are true:

1. A user can upload a sample `xlsx` or `csv` file.
2. The system can correctly identify the main measurement column and ordering field.
3. The system generates at least two chart outputs for supported data.
4. The system computes and displays key metrics including mean, standard deviation, and pass rate.
5. When spec limits exist, the system computes and displays `Cp` and `Cpk`.
6. The system generates a concise AI summary, risk statement, and recommended actions.
7. The system exports a formatted Excel report.
8. The system supports at least two distinct templates.
9. The happy path completes within a reasonable demo time window, targeted at under thirty seconds on local sample data.

## 23. Risks and Mitigations

### 23.1 Risk: schema inference errors

Mitigation:

- keep canonical field set small
- add lightweight user confirmation for uncertain fields
- provide sample files with known-good structure for demos

### 23.2 Risk: AI overreaches into layout logic

Mitigation:

- strict `report_spec` schema
- whitelist template IDs and chart types
- renderer ignores unsupported free-form instructions

### 23.3 Risk: SPC misuse on unsuitable data

Mitigation:

- explicit preconditions for each chart family
- professional fallback messages for insufficient data

### 23.4 Risk: demo instability

Mitigation:

- deterministic chart generation
- deterministic Excel rendering
- default template fallback
- rule-based narrative fallback

## 24. Implementation Phasing

### Phase 1: deterministic reporting pipeline

- upload parsing
- schema normalization
- metrics calculation
- chart generation
- one fixed template render

### Phase 2: AI augmentation

- AI summary
- anomaly explanation
- template selection
- `report_spec` generation

### Phase 3: web experience refinement

- analysis preview page
- template explanation
- final report page polish

### Phase 4: multi-template demo polish

- add second and third templates
- add richer synthetic sample data
- improve narrative tone and chart styling

## 25. Final Recommendation

The correct MVP is not an AI that freely designs Excel reports. The correct MVP is a system that combines deterministic SPC analysis and template rendering with bounded AI-based report planning and explanation. This path is both demo-friendly and realistic for eventual productization.

The recommended build order is:

1. deterministic reporting pipeline
2. AI enhancement through Deep Agents
3. polished web flow
4. additional templates and demo polish

This keeps the project grounded, stable, and impressive.
