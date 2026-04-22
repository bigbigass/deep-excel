# SPC Workstation UI Design

**Date:** 2026-04-22  
**Topic:** Redesign the web frontend into a professional enterprise SPC quality analysis workstation  
**Status:** Approved by user selection (`B` visual direction + scope `3`), implementation in progress

---

## 1. Background

The current frontend exposes the right workflow steps, but it still looks like a thin demo: the home page is a plain upload form, the analysis page is a stack of utility blocks, and the report page is only a download link. That visual mismatch makes the product feel temporary even when the backend workflow is useful.

The next step is not feature expansion. It is interface maturation: give the upload, analysis, and report flow a consistent software shell so the product reads like an enterprise quality platform rather than a prototype.

---

## 2. Goal

Turn the frontend into a coherent SPC workstation with these properties:

- shallow-learning enterprise quality platform style
- fixed application shell with navigation and system identity
- consistent visual language across home, analysis, and report pages
- stronger hierarchy for task state, quality indicators, and report delivery
- no change to the underlying API workflow or routing contract

---

## 3. Non-Goals

This redesign does **not** include:

- backend API changes
- new analysis logic or new report content fields
- authentication, user management, or persistent navigation history
- chart rendering changes on the backend
- theme switching or dark mode

---

## 4. Options Considered

### Option A: Marketing-style landing page refresh only

Refresh the home page hero and upload form, but leave analysis and report pages mostly intact.

**Rejected because:** the first click into analysis would immediately break the illusion of a professional application.

### Option B: Unified page styling without an application shell

Redesign all three pages with the same colors and card system, but keep them as independent standalone pages.

**Rejected because:** it improves polish, but still lacks the framing and navigation cues users expect from a real quality platform.

### Option C: Enterprise workstation shell with unified process pages (chosen)

Add a fixed top application shell, shared visual system, and page-specific workspaces for upload, in-flight analysis, and report delivery.

**Chosen because:** it creates the strongest professional identity without changing the workflow model.

---

## 5. Final Design

### 5.1 Visual Direction

The interface should look like an enterprise quality analysis platform:

- light neutral background with a subtle industrial grid texture
- slate, steel-blue, and cyan accents rather than generic bright blue
- soft elevated cards with thin borders and controlled shadows
- strong typography hierarchy that feels like software, not a brochure
- restrained motion: load-in reveal and card hover depth only

### 5.2 Application Shell

The entire app should live inside a shared shell with:

- product identity at the top-left
- module navigation for `Data Intake`, `Analysis Workspace`, and `Report Delivery`
- compact system tags such as runtime mode and SPC engine state
- a footer strip that reinforces traceability and enterprise tone

The shell should remain lightweight and should not pretend there are authenticated multi-tenant features that do not exist.

### 5.3 Home Page

The home page becomes a quality analysis launchpad.

It should include:

- a left-side overview area explaining what the workstation does
- a short process strip showing upload, analyze, export
- capability cards for SPC interpretation, anomaly review, and report generation
- a right-side operations panel containing the upstream connectivity panel and the upload form

The upload panel should feel like an operator console rather than a raw browser form.

### 5.4 Analysis Page

The analysis page becomes a live workspace.

It should include:

- a page header with job ID, source file, current state, and next action
- a two-column layout
- a right-side operational column for task progress and job state
- a main evidence column for KPI cards, chart evidence, reasoning trace, and template summary

When report data is not ready, the page should still look intentional rather than empty.

### 5.5 Report Page

The report page becomes a completion and handoff surface.

It should include:

- a completion status card
- report identity and delivery metadata
- a primary download action
- quick guidance on what the exported workbook contains

### 5.6 Component-Level Expectations

- `UploadForm` should preserve the current upload behavior and progress updates, but present them in a more structured operator-style panel.
- `UpstreamCheckCard` should feel like a system health block, not a loose utility button.
- `JobTaskList` should read like a production pipeline tracker.
- `KpiGrid`, `ChartList`, and `ReasoningTraceCard` should share the same card grammar and section headers.

---

## 6. Testing Strategy

The redesign changes user-visible structure, so frontend tests should be updated or added for:

- shared application shell rendering
- upload panel wording and retained submission behavior
- analysis progress component rendering under the new visual structure
- existing reasoning and upstream functionality after restyling

Build verification should include both Jest and a production `next build`.

---

## 7. Implementation Notes

- The repository currently has no initial git commit, so isolated git worktrees are unavailable for this task.
- Implementation should stay within the existing Next.js app structure and avoid introducing a new styling framework.
- Styling should be done with a deliberate global CSS system and semantic class names rather than relying on inactive utility class strings.
