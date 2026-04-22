# SPC Workstation UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the web frontend into a professional enterprise SPC workstation with a shared app shell and consistent upload, analysis, and report pages.

**Architecture:** Introduce a shared `AppShell` wrapper in the Next.js layout, replace inactive utility-style class usage with semantic CSS classes in `web/app/globals.css`, and reshape the home, analysis, and report pages into purpose-built workspaces while preserving the existing API interactions. Keep current business behavior intact and update Jest coverage around the new visible structure.

**Tech Stack:** Next.js App Router, React 19, TypeScript, global CSS, Jest, Testing Library

---

### Task 1: Lock the redesign surface with failing tests

**Files:**
- Create: `web/tests/app-shell.test.tsx`
- Modify: `web/tests/upload-form.test.tsx`
- Modify: `web/tests/job-task-list.test.tsx`

- [ ] Add a new shell test that expects product identity, navigation labels, and enterprise status tags.
- [ ] Update upload form tests so they continue to verify submit/progress behavior while also asserting the new operator-panel wording.
- [ ] Update the task list test to assert the new pipeline summary wording and section title.
- [ ] Run the targeted Jest command and confirm the new expectations fail before implementation.

### Task 2: Build the shared shell and design system

**Files:**
- Create: `web/components/app-shell.tsx`
- Modify: `web/app/layout.tsx`
- Modify: `web/app/globals.css`

- [ ] Add a shell component that renders the brand block, top navigation, system status chips, and footer strip.
- [ ] Wrap app content with the shell in `layout.tsx` while preserving `StaleChunkReload`.
- [ ] Replace the thin global styling with a full tokenized CSS system for surfaces, headers, grids, pills, buttons, motion, and responsive layout primitives.
- [ ] Run targeted tests for the shell and verify they pass.

### Task 3: Rebuild the home page as a launchpad

**Files:**
- Modify: `web/app/page.tsx`
- Modify: `web/components/upload-form.tsx`
- Modify: `web/components/upstream-check-card.tsx`

- [ ] Restructure the home page into overview, process, capability, and operations regions.
- [ ] Restyle the upload form into a professional intake console without changing submission semantics.
- [ ] Restyle the upstream check card into a system health panel without changing its request logic.
- [ ] Run upload and upstream Jest tests and verify they pass.

### Task 4: Rebuild the analysis and report workspaces

**Files:**
- Modify: `web/app/analysis/[jobId]/page.tsx`
- Modify: `web/app/report/[reportId]/page.tsx`
- Modify: `web/components/job-task-list.tsx`
- Modify: `web/components/kpi-grid.tsx`
- Modify: `web/components/chart-list.tsx`
- Modify: `web/components/reasoning-trace-card.tsx`

- [ ] Turn the analysis page into a two-column workspace with a state header, operational side rail, and evidence sections.
- [ ] Turn the report page into a completion and delivery surface with stronger metadata and a primary download path.
- [ ] Restyle the progress, KPI, chart, and reasoning components so they share one visual grammar.
- [ ] Run the relevant Jest suite and verify updated expectations pass.

### Task 5: Full verification

**Files:**
- Modify: `docs/superpowers/specs/2026-04-22-spc-workstation-ui-design.md`
- Modify: `docs/superpowers/plans/2026-04-22-spc-workstation-ui-implementation.md`

- [ ] Self-review the spec and plan for consistency with the implemented scope.
- [ ] Run `cd web; npm test` and inspect the full output.
- [ ] Run `cd web; npm run build` and inspect the full output.
- [ ] Only after fresh verification, summarize the UI changes, test evidence, and any residual risk.
