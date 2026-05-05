# Remove AI Fallbacks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove Parse and Report planner fallback paths so missing config or invalid model output fails fast and surfaces the real error.

**Architecture:** Make both planner entry points strict: no rule-based fallback, no plain-JSON fallback, and no silent localization/default-content fallback. Keep job failure plumbing and frontend failure display as-is so errors surface directly.

**Tech Stack:** FastAPI, Pydantic, LangChain `ChatOpenAI`, pytest, Next.js, Jest

---

### Task 1: Lock backend tests to strict fail-fast behavior
- [ ] Update planner tests to expect direct failures instead of fallback behavior.
- [ ] Update pipeline/job tests to inject fake planners rather than relying on fallback implementations.
- [ ] Run targeted backend tests and confirm they fail for the right reason before code changes.

### Task 2: Remove Parse fallback code
- [ ] Delete rule-based field mapping fallback and plain-JSON fallback from the Parse planner.
- [ ] Validate model output strictly and raise on missing API key, invalid columns, non-numeric measurement columns, or non-Chinese reasoning.
- [ ] Run targeted Parse tests and confirm they pass.

### Task 3: Remove report planner fallback code
- [ ] Delete rule-based and plain-JSON fallback paths from `api/app/agent/factory.py`.
- [ ] Validate template id and Chinese narrative fields strictly and raise on invalid output.
- [ ] Run targeted planner tests and confirm they pass.

### Task 4: Re-verify job flow and UI
- [ ] Run backend suite and ensure failure plumbing still works with strict planners.
- [ ] Run frontend tests and build to confirm error surfacing UI still works.
