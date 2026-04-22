# Summary Chart Density Tuning Design

**Date:** 2026-04-22  
**Topic:** Make the `Summary` sheet chart area denser for 3-chart and 4-chart exports without changing the left-right report balance  
**Status:** Design approved, awaiting spec review

---

## 1. Background

The current `Summary` sheet already satisfies the major report goals:

- summary content stays on the left
- charts stay on the right on the same sheet
- the page reads like a formal report instead of a raw export

After reviewing the latest output, the user feedback is now narrower and more specific:

- the charts look **too small** in some cases
- the spacing between charts feels **too loose**
- the issue is most visible in the **3-chart** and **4-chart** layouts

This means the next refinement is not a redesign of the page, but a density tuning pass for the right-side chart board.

---

## 2. Goal

Improve the right-side chart board so that:

- 3-chart and 4-chart layouts feel visibly tighter
- charts appear larger within the same overall page structure
- empty space between charts is reduced
- the report still looks formal and printable, not cramped or dashboard-like
- the left summary zone keeps its current visual priority and width relationship

---

## 3. Non-Goals

This design does **not** include:

- changes to analytics or chart generation
- changes to chart recommendation or ordering
- changes to the left summary block widths
- changes to 1-chart or 2-chart layout behavior
- changes to workbook rendering flow outside chart placement metadata
- changes to the `Details` worksheet

---

## 4. Confirmed User Decisions

The user has explicitly chosen the following:

- conversation language: **Chinese**
- adjustment scope: **make charts larger and reduce spacing together**
- page balance: **keep the left-right proportion basically unchanged**
- priority scenarios: **3-chart and 4-chart layouts**
- compactness level: **medium-tight** rather than ultra-dense

This means the correct direction is a targeted refinement of existing chart placement, not a structural report redesign.

---

## 5. Options Considered

### Option A: Conservative scaling only

**Approach:**
- increase chart image size a little
- keep most current anchors unchanged

**Why not chosen:**
- charts would improve somewhat, but the right side would still feel too loose
- does not directly solve the spacing complaint

### Option B: Medium-tight density tuning (chosen)

**Approach:**
- enlarge 3-chart and 4-chart images noticeably
- reduce horizontal and vertical gaps between chart blocks
- keep the left summary zone unchanged
- keep the overall chart board feeling formal and breathable

**Why it wins:**
- directly addresses both complaints: size and distance
- preserves the formal report tone
- avoids the risk of making the page look overcrowded

### Option C: Aggressive compression

**Approach:**
- minimize almost all whitespace in the chart board
- maximize image size above all else

**Why not chosen:**
- may weaken the formal report feel
- higher risk of charts, titles, and borders feeling crowded
- less robust across different chart-title lengths and Excel zoom levels

---

## 6. Final Design

### 6.1 Overall Direction

The chart board should become **denser, not narrower**.

Key rule:
- do **not** reclaim width from the left summary zone
- instead, use the existing right-side footprint more efficiently

This keeps the approved report composition intact while improving visual efficiency inside the chart board.

### 6.2 Scope of Layout Changes

Only the following cases should be changed:

- `chart_layout.layouts["3"]`
- `chart_layout.layouts["4"]`
- matching `formal_layout.chart_board.frames["3"]`
- matching `formal_layout.chart_board.frames["4"]`

The following cases should remain unchanged unless a regression is discovered:

- `chart_layout.layouts["1"]`
- `chart_layout.layouts["2"]`
- matching `formal_layout.chart_board.frames["1"]`
- matching `formal_layout.chart_board.frames["2"]`

### 6.3 Three-Chart Layout Behavior

The 3-chart layout should still read as:
- two charts on the top row
- one centered chart on the second row

But it should become denser in these ways:

- the two top charts should become wider than the current layout
- the gap between the two top charts should shrink
- the bottom chart should move upward closer to the top row
- the bottom chart should remain visually centered under the top pair
- chart titles should stay directly above each image with a small, consistent gap

Design intent:
- the board should feel like one compact evidence group, not two disconnected rows

### 6.4 Four-Chart Layout Behavior

The 4-chart layout should remain a `2 x 2` grid, but with tighter packing:

- each chart should become larger than the current `300 x 170` style footprint
- the horizontal gap between left and right columns should shrink
- the vertical gap between top and bottom rows should shrink
- the four blocks should feel like one balanced matrix rather than four separate islands

Design intent:
- a reviewer should see one unified chart plate with four comparable views

### 6.5 Frame Behavior

The chart board frames should be updated to follow the tighter image positions.

Rules:
- frame ranges should closely wrap the chart title + chart image region
- frames should not leave large dead zones around the images
- frames should preserve a small amount of breathing room so the result still looks formal

This keeps the current report framing language while avoiding the feeling that the borders are much larger than the actual charts.

---

## 7. Visual Language Rules

### 7.1 Density Target

The user selected a **medium-tight** compactness level.

Interpretation:
- charts should feel clearly larger than before
- whitespace should feel intentionally reduced
- there should still be visible separation between chart blocks
- the right side should not look squeezed to the edge of readability

### 7.2 Formality Guardrail

Even after tightening:
- chart titles must remain readable
- borders must remain clean and aligned
- the board must still look appropriate for a formal SPC or inspection report

This is a report refinement, not a dashboard compression pass.

---

## 8. Technical Design Notes

### 8.1 Manifest-Driven Change

This tuning should stay primarily in the template manifests.

Preferred implementation direction:
- adjust `chart_layout.layouts["3"]` and `chart_layout.layouts["4"]`
- adjust `formal_layout.chart_board.frames["3"]` and `formal_layout.chart_board.frames["4"]`
- avoid changing the renderer algorithm unless tests reveal a hard limitation

This keeps the behavior easy to tune later without pushing more layout logic into Python.

### 8.2 Renderer Compatibility

The current renderer already supports:
- same-sheet chart embedding
- chart title placement from manifest metadata
- frame styling via `formal_layout`

Therefore this density tuning should be a configuration-first change.

### 8.3 Testing Strategy

The implementation should verify at least:
- 3-chart and 4-chart layout metadata changed as expected
- exported workbooks still place chart titles on the `Summary` sheet
- same-sheet rendering still keeps charts out of the fallback `Charts` sheet
- formal frame ranges still align with the intended board layout

---

## 9. Acceptance Criteria

The work is successful when:

1. 3-chart exports show visibly larger charts than the current output
2. 4-chart exports show visibly larger charts than the current output
3. horizontal spacing between chart blocks is smaller than the current output
4. vertical spacing between chart rows is smaller than the current output
5. the left summary zone width relationship remains effectively unchanged
6. the page still reads like a formal report, not a crowded dashboard
7. existing summary-sheet chart placement tests continue to pass after updates
8. exported workbooks still contain `Summary` and `Details` as expected, without unintended fallback sheets

---

## 10. Risks and Tradeoffs

### Risk 1: Tighter layout may feel too crowded

If the gaps are reduced too aggressively, the formal tone may weaken.

**Mitigation:** use the approved medium-tight density level, not the aggressive variant.

### Risk 2: Frame ranges may lag behind image anchors

If only image anchors are updated but frame ranges are not, the board will look uneven.

**Mitigation:** always update `formal_layout.chart_board.frames` together with `chart_layout.layouts`.

### Risk 3: Template-specific drift

Because each template has slightly different anchor cells, density tuning might become inconsistent between templates.

**Mitigation:** apply the same design intent across all three templates and verify each one explicitly.

---

## 11. Recommended Next Phase

The next implementation plan should focus on:

1. adding tests for denser 3-chart and 4-chart metadata expectations
2. updating the three template manifests with tighter chart anchors and sizes
3. verifying that formal frames still match the tuned layouts
4. running renderer regression tests and a real workbook export check

---

## 12. Self-Review

Self-check completed:

- placeholder scan: no `TODO`, `TBD`, or unresolved sections
- internal consistency: the design preserves current left-right structure while tightening only the chart board
- scope check: focused on one narrow follow-up refinement and suitable for a single implementation plan
- ambiguity check: the changed scenarios, unchanged scenarios, and density target are explicit

Known limitation:
- this workspace is still not a Git repository, so the spec can be saved here but not committed in this environment
