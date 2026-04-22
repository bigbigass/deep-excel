# Demo Front-End Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 DeepExcel 前端页面改成全中文、低元素密度的演示版界面，并突出上传驱动和可见 AI 分析过程。

**Architecture:** 保留现有页面路由和数据接口，只调整页面结构、文案和少量组件表达。首页聚焦上传入口，分析页聚焦 AI 过程可见性，报告页聚焦交付结果。

**Tech Stack:** Next.js App Router、React、TypeScript、Jest、Testing Library

---

### Task 1: 锁定新文案与页面结构

**Files:**
- Create: `web/tests/home-page.test.tsx`
- Create: `web/tests/report-page.test.tsx`
- Modify: `web/tests/app-shell.test.tsx`
- Modify: `web/tests/upload-form.test.tsx`
- Modify: `web/tests/job-task-list.test.tsx`
- Modify: `web/tests/reasoning-trace-card.test.tsx`

- [ ] **Step 1: Write failing tests**
- [ ] **Step 2: Run targeted Jest commands to confirm failures**
- [ ] **Step 3: Update copy and layout with minimal code**
- [ ] **Step 4: Re-run targeted Jest commands and confirm passes**

### Task 2: 实现首页、分析页、报告页精简

**Files:**
- Modify: `web/app/page.tsx`
- Modify: `web/app/analysis/[jobId]/page.tsx`
- Modify: `web/app/report/[reportId]/page.tsx`
- Modify: `web/components/app-shell.tsx`
- Modify: `web/components/upload-form.tsx`
- Modify: `web/components/job-task-list.tsx`
- Modify: `web/components/reasoning-trace-card.tsx`
- Modify: `web/components/chart-list.tsx`
- Modify: `web/components/kpi-grid.tsx`
- Modify: `web/components/upstream-check-card.tsx`

- [ ] **Step 1: Replace mixed-language copy with Chinese-only labels**
- [ ] **Step 2: Remove non-demo sections from home and analysis flows**
- [ ] **Step 3: Emphasize visible AI analysis steps and evidence**
- [ ] **Step 4: Keep report page focused on final delivery**

### Task 3: 验证前端结果

**Files:**
- Modify: `web/app/globals.css` (only if needed)

- [ ] **Step 1: Run targeted Jest suite for changed UI**
- [ ] **Step 2: Run `npm test` if targeted suite passes**
- [ ] **Step 3: Run `npm run build` to verify production build**

