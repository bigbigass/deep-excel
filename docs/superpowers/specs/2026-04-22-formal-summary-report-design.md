# Formal SPC Summary Report Design

**Date:** 2026-04-22  
**Topic:** Make the exported Excel `Summary` sheet look like a formal industrial SPC inspection report  
**Status:** Design approved, awaiting spec review

---

## 1. Background

The current export already places the summary on the left side of the `Summary` sheet and charts on the right side of the same sheet. Functionally this solves the "summary and charts together" requirement, but the page still reads like a generated Excel output rather than a formal quality report.

The next goal is visual refinement: keep the existing data flow and chart generation, but redesign the `Summary` sheet so it resembles a professional industrial inspection / SPC report cover page.

---

## 2. Goal

Upgrade the `Summary` sheet into a formal report-style page with the following properties:

- industrial quality / SPC visual tone
- table-oriented layout rather than dashboard cards
- concise top title area
- left column prioritizes KPI metrics
- left column flows from KPI table to conclusion, risk, and actions
- right column remains a chart evidence area with 1–4 automatically arranged charts
- the page looks suitable for review, printing, and customer/internal quality handoff

---

## 3. Non-Goals

This design does **not** include:

- changes to analytics or chart calculation logic
- changes to chart recommendation logic
- changes to the `Details` worksheet layout
- user-configurable themes in the UI
- decorative BI-style dashboard visuals
- support for more than 4 charts on the `Summary` page

---

## 4. Confirmed Design Decisions

The user has explicitly approved the following:

- style direction: **industrial inspection / SPC**
- overall layout style: **table-oriented**
- top header style: **concise**
- left-side first focus: **key metrics**
- left-side reading order: **metrics first, then conclusion / risk / actions**
- chosen layout direction: **Plan A**

---

## 5. Options Considered

### Option A: Formal industrial summary sheet (chosen)

**Structure:**
- concise title band at the top
- left summary column built from bordered table blocks
- right chart column with titled chart grid
- restrained industrial color palette

**Why it wins:**
- best match for SPC / quality-review expectations
- feels like a report, not a dashboard
- preserves high readability inside Excel
- works with the existing summary-left / chart-right architecture

### Option B: Analysis-heavy SPC page

**Structure:**
- same left-right split, but with larger chart emphasis and lighter summary structure

**Why not chosen:**
- more like an engineering analysis page than a formal report cover page
- weaker table/report identity

### Option C: Record-sheet style

**Structure:**
- dense borders, highly formal document table style, compressed chart area

**Why not chosen:**
- formal, but too cramped
- reduces chart readability
- likely to feel more like raw paperwork than an executive-quality summary

---

## 6. Final Layout

### 6.1 Overall Page Structure

The `Summary` sheet should be treated as a single report cover page with two major vertical zones:

- **Left summary zone**: approximately 40% width
- **Right chart zone**: approximately 60% width
- **Center gutter**: a narrow blank spacer column separating text from charts

This keeps the page visually balanced and prevents text and charts from bleeding into each other.

### 6.2 Top Header

The header should be intentionally concise.

Recommended behavior:
- one title band only
- no dense metadata strip across the top
- title example: `SPC 检验报告` or `质量检验摘要`
- dark blue-gray background or accent band
- strong bold title text

The top area should communicate formality without turning the page into a form header.

### 6.3 Left Summary Zone

The left side is a stack of bordered report sections in this exact order:

1. **关键指标**
2. **综合结论**
3. **风险说明**
4. **建议动作**

Each section should have:
- a small section title band
- a bordered body area
- consistent spacing between sections

### 6.4 Right Chart Zone

The right side is a formal chart board with:
- section title: `SPC 图表总览`
- 1–4 chart blocks arranged automatically
- each chart block has a short title above the image
- consistent chart padding and visual framing

Chart arrangement rules remain:
- 1 chart: single large chart
- 2 charts: stacked vertically
- 3 charts: two on top, one on bottom
- 4 charts: 2×2 grid

---

## 7. Visual Language

### 7.1 Color Palette

Use a restrained industrial palette.

- **Primary color:** dark blue-gray for title bands and section headers
- **Neutral support:** white and light gray for backgrounds, tables, and spacing
- **Status emphasis only:**
  - pass / stable: dark green
  - warning / risk: brown-orange
  - fail / abnormal: dark red

Bright dashboard-like colors should be avoided.

### 7.2 Borders and Surfaces

- use thin solid borders throughout
- no heavy shadows
- no glossy card styling
- section bodies should feel like document blocks, not web widgets

### 7.3 Typography Tone

- bold, stable page title
- smaller bold section labels
- clean readable body text
- metric values may be bolded for emphasis
- avoid oversized decorative typography

The target feeling is “quality document” rather than “presentation slide”.

---

## 8. Detailed Section Rules

### 8.1 KPI Table

The KPI area must be the first thing the eye sees in the left column.

Recommended structure:
- two-column table
- left column: metric name
- right column: metric value
- metric value aligned center or right
- metric value in bold

Recommended fixed metrics:
- sample count
- mean
- standard deviation
- pass rate
- Cpk

This should look like a formal report table, not a series of independent cards.

### 8.2 Conclusion Block

The conclusion block should be short and report-like.

Rules:
- 1–2 lines maximum in normal cases
- written as a summary conclusion, not conversational prose
- should communicate overall process state quickly

### 8.3 Risk Block

The risk block should read like an audit or review note.

Rules:
- short structured statements
- no long paragraphs
- color emphasis only if the risk level is important to highlight

### 8.4 Action Block

The action block should contain short, scannable recommendations.

Rules:
- 2–4 bullet items preferred
- each bullet is short and action-oriented
- should resemble corrective / preventive actions in a quality report

### 8.5 Chart Block Titles

Each chart should include a short title above the chart image.

Recommended style:
- compact title line
- consistent wording across charts
- optionally formatted like `图1 控制图`, `图2 分布图`, etc.

This improves traceability and makes the right side feel like a curated chart plate.

---

## 9. Implementation Scope

This styling work should modify only the export presentation layer.

Expected implementation focus:
- `Summary` sheet cell styling
- section borders, fills, fonts, and spacing
- optional merged title regions where appropriate
- chart title styling and chart zone framing
- template manifest anchor adjustments if needed for better spacing

This styling work should **not** alter:
- analytics pipeline
- chart image generation logic
- chart ordering logic except for presentation labels
- `Details` worksheet structure

---

## 10. Technical Design Notes

### 10.1 Rendering Strategy

The renderer should continue using `openpyxl` and the current chart placement system.

The likely implementation approach is:
- keep chart images as PNGs
- keep chart placement on the `Summary` sheet
- add worksheet styling helpers for title band, section headers, KPI table, and text sections
- apply styles after data is written but before workbook save

### 10.2 Template Strategy

To keep the styling maintainable, layout anchors should continue to live in template manifests where possible.

If styling introduces new structured areas, the manifest may need additional slots for:
- title band range
- KPI table region
- conclusion block anchor
- risk block anchor
- action block anchor
- chart section title anchor

The goal is to avoid hard-coding all visual coordinates directly in Python.

### 10.3 Backward Compatibility

The current same-sheet chart support must remain intact.

If a template lacks the new styling metadata, the renderer should still be able to produce a valid report using the existing content population rules.

---

## 11. Acceptance Criteria

The work is considered successful when:

1. the `Summary` sheet visually resembles a formal industrial inspection report
2. KPI metrics are the first emphasis on the left side
3. the left-side section order is KPI → conclusion → risk → actions
4. the right-side chart board remains readable for 1–4 charts
5. charts and titles look like a unified report section, not loose pasted images
6. colors remain restrained and professional
7. the page feels printable and review-friendly
8. existing export functionality continues to pass regression tests

---

## 12. Risks and Tradeoffs

### Risk 1: Excel styling can become brittle

Because this is Excel rather than HTML/CSS, detailed styling may become fragile if too many coordinates are hard-coded.

**Mitigation:** keep structure in the manifest and keep styling helpers small and consistent.

### Risk 2: Too much decoration weakens formality

If the design adds large fills, gradients, or dashboard cards, the output will stop feeling like a quality report.

**Mitigation:** stay minimal, with thin borders and muted colors.

### Risk 3: Left column may become too dense

Adding too many text blocks can make the report look cramped.

**Mitigation:** keep text concise and use fixed section ordering with consistent spacing.

---

## 13. Recommended Next Implementation Phase

The next implementation plan should focus on:

1. styling helpers for `Summary` sheet sections
2. template manifest updates for formal report anchors
3. regression tests for styled summary output structure
4. end-to-end verification that exported workbooks still contain correct summary data and charts

---

## 14. Self-Review

Self-check completed:

- placeholder scan: no `TODO`, `TBD`, or unresolved sections
- internal consistency: layout, tone, and ordering all match the approved choices
- scope check: focused on report presentation only
- ambiguity check: section order, visual style, and chart behavior are explicit

Known limitation:
- this workspace is still not a Git repository, so the spec can be saved but not committed here