# TypeScript Parallel Backend Design

- Date: `2026-05-26`
- Project: `deep-excel`
- Scope: `Add a TypeScript backend that runs in parallel with the existing Python FastAPI backend`
- Status: `Draft for user review`

## 1. Summary

DeepExcel currently has a working Python FastAPI backend and a Next.js frontend. The TypeScript backend will be added as a parallel implementation under a new `api-ts/` directory. It will expose the same frontend-facing API contract as the Python backend so the web app can switch between implementations by changing `NEXT_PUBLIC_API_BASE_URL`.

The first TypeScript version should prioritize API compatibility, local development ergonomics, and a clear concurrent job architecture. It does not need to delete or replace the Python backend. The two backends should coexist while sharing the same high-level behavior, sample data, templates, and runtime output conventions.

## 2. Current Context

The existing Python backend performs this pipeline:

```text
upload file
  -> infer field mapping
  -> normalize measurement data
  -> compute SPC metrics
  -> generate charts
  -> generate AI narrative and template decision
  -> render Excel report
```

The frontend consumes the backend through `web/lib/api.ts` and currently expects:

- `POST /api/v1/jobs`
- `GET /api/v1/jobs/{job_id}`
- `POST /api/v1/jobs/{job_id}/render`
- `GET /api/v1/reports/{report_file_name}`
- `GET /health`
- `POST /api/v1/health/upstream-check`
- static files under `/outputs`

The Python backend stores runtime state in `outputs/jobs/{job_id}.json`, generated charts in `outputs/charts/{job_id}/`, reports in `outputs/reports/`, and uploads in `outputs/uploads/`.

## 3. Product Goal

Build a TypeScript backend that can run beside the Python backend and support the existing web UI without requiring frontend behavior changes. The TypeScript backend should be useful as an implementation base for future Node-based development while preserving the current demo flow.

Success means a developer can start the TypeScript backend on another port, point the frontend at it, upload sample data, watch job progress, render an Excel report, and download the result.

## 4. Goals

### 4.1 Functional Goals

- Add a new `api-ts/` backend without disturbing the existing `api/` Python backend.
- Match the existing frontend-facing API response shapes.
- Support local CSV and XLSX upload for sample datasets.
- Store job state in JSON files compatible with the current frontend expectations.
- Compute deterministic SPC metrics in TypeScript.
- Generate chart image assets or provide a compatible chart asset strategy.
- Generate an AI narrative and template decision through an OpenAI-compatible API.
- Render an `.xlsx` report using the existing template folder and manifest files.
- Serve generated outputs under `/outputs`.
- Provide a local development command for running only the TypeScript backend.
- Add tests for API contracts and core business logic.

### 4.2 Architecture Goals

- Keep route handlers thin.
- Put business orchestration in services.
- Separate deterministic calculations from AI generation.
- Use a job queue abstraction even if the first implementation runs in-process.
- Make concurrent job processing explicit and testable.
- Keep Python and TypeScript implementations easy to compare.

## 5. Non-goals

The first TypeScript backend will not:

- Remove the existing Python backend.
- Rewrite the frontend.
- Introduce a database.
- Add authentication or multi-tenant behavior.
- Guarantee byte-identical Excel output compared with Python.
- Reimplement every internal Python helper one-to-one when a simpler compatible TypeScript path is enough.
- Add distributed workers, Redis, BullMQ, or message brokers in the first phase.
- Support arbitrary customer templates beyond the existing manifest-driven demo templates.

## 6. Recommended Approach

Use a new Express-based TypeScript service in `api-ts/`. This keeps the backend familiar to most Node developers, makes multipart uploads straightforward, and avoids coupling the API implementation to Next.js server routes. The frontend can switch between Python and TypeScript by changing only `NEXT_PUBLIC_API_BASE_URL`.

The first implementation should use an in-process queue with a configurable concurrency limit. This gives the project the concurrency shape it needs without introducing external infrastructure too early.

## 7. Alternatives Considered

### 7.1 Express Service in `api-ts/` (Recommended)

This approach creates a standalone Node service with Express, Zod, and focused service modules.

Trade-offs:

- Pros: simple mental model, easy local startup, clean separation from Next.js, good fit for REST endpoints and uploads.
- Cons: requires a second Node package area or workspace configuration.

### 7.2 Next.js API Routes

This approach would place backend endpoints inside the existing Next.js app.

Trade-offs:

- Pros: fewer processes during development, shared TypeScript setup.
- Cons: long-running job processing and file generation are awkward inside Next app routes, and it blurs the boundary between frontend and backend.

### 7.3 Full Worker Platform

This approach would add Redis/BullMQ or another durable queue from the start.

Trade-offs:

- Pros: stronger production path for concurrency and retries.
- Cons: unnecessary infrastructure for the current local demo and a larger setup burden.

The recommended path is `7.1`, with queue interfaces designed so `7.3` remains possible later.

## 8. Repository Structure

Add:

```text
api-ts/
  package.json
  tsconfig.json
  jest.config.ts
  src/
    main.ts
    app.ts
    config.ts
    routes/
      health.ts
      jobs.ts
    services/
      jobs/
        jobModels.ts
        jobRepository.ts
        jobQueue.ts
        jobRunner.ts
      ingestion/
        loadSourceTable.ts
        normalizeMeasurements.ts
      analytics/
        computeAnalysis.ts
      charts/
        generateChartBundle.ts
      agent/
        fieldMappingPlanner.ts
        reportPlanner.ts
      excel/
        renderReport.ts
        templates.ts
      upstream/
        upstreamCheck.ts
    shared/
      errors.ts
      time.ts
      ids.ts
  tests/
    health.test.ts
    jobsApi.test.ts
    analytics.test.ts
    ingestion.test.ts
    reportPlanner.test.ts
```

Existing directories remain:

- `api/`: Python backend.
- `web/`: Next.js frontend.
- `templates/`: shared Excel templates.
- `sample_data/`: shared demo input files.
- `outputs/`: shared runtime output root.

## 9. Technology Choices

Recommended initial stack:

- Runtime: Node.js 22 or newer.
- Language: TypeScript.
- HTTP server: Express.
- Validation: Zod.
- Multipart uploads: Multer.
- CSV parsing: Papa Parse or csv-parse.
- XLSX parsing and rendering: ExcelJS.
- Chart generation: Chart.js with node-canvas, or a lightweight server-side plotting library.
- Testing: Jest and Supertest.
- Environment loading: dotenv.
- AI calls: OpenAI-compatible HTTP client using `fetch`.

The TypeScript backend should avoid adding heavy infrastructure until API compatibility and core behavior are proven.

## 10. Configuration

The TypeScript backend should mirror existing backend configuration names where practical:

- `DEEPEXCEL_APP_NAME`
- `DEEPEXCEL_OUTPUTS_DIR`
- `DEEPEXCEL_MODEL_NAME`
- `DEEPEXCEL_OPENAI_BASE_URL`
- `DEEPEXCEL_OPENAI_API_KEY`
- `DEEPEXCEL_JOB_CONCURRENCY`
- `DEEPEXCEL_TS_PORT`

Defaults:

- `DEEPEXCEL_APP_NAME`: `DeepExcel API TS`
- `DEEPEXCEL_OUTPUTS_DIR`: `outputs`
- `DEEPEXCEL_MODEL_NAME`: `gpt-5.4`
- `DEEPEXCEL_JOB_CONCURRENCY`: `2`
- `DEEPEXCEL_TS_PORT`: `8001`

The TypeScript backend should listen on `127.0.0.1:8001` by default so it can run beside the Python backend on `8000`.

## 11. API Contract

The TypeScript backend must preserve the frontend-facing shapes from `web/lib/api.ts`.

### 11.1 `GET /health`

Returns:

```json
{
  "status": "ok",
  "app": "DeepExcel API TS"
}
```

### 11.2 `POST /api/v1/jobs`

Accepts multipart form data with a `file` field.

Returns `202`:

```json
{
  "job_id": "JOB-1234abcd"
}
```

Behavior:

- Save uploaded file to `outputs/uploads/`.
- Create an initial job payload immediately.
- Enqueue analysis work.
- Return before analysis finishes.

### 11.3 `GET /api/v1/jobs/{job_id}`

Returns the full job payload:

```json
{
  "job_id": "JOB-1234abcd",
  "state": "queued",
  "error": null,
  "created_at": "2026-05-26T00:00:00.000Z",
  "updated_at": "2026-05-26T00:00:00.000Z",
  "source_file_name": "normal_batch.csv",
  "tasks": [],
  "template_id": null,
  "chart_paths": {},
  "report_id": null,
  "download_path": null,
  "report_spec": null
}
```

The actual `tasks` list must include the same IDs currently used by the frontend:

- `upload`
- `parse`
- `analyze`
- `charts`
- `ai`
- `render`

Task status values must remain:

- `pending`
- `running`
- `completed`
- `failed`

### 11.4 `POST /api/v1/jobs/{job_id}/render`

Returns `202`:

```json
{
  "job_id": "JOB-1234abcd"
}
```

Behavior:

- Reject jobs that have not reached `analysis_completed`.
- Return idempotently if the job is already rendering or completed.
- Enqueue render work.

### 11.5 `GET /api/v1/reports/{report_file_name}`

Downloads a generated report from `outputs/reports/`.

### 11.6 `POST /api/v1/health/upstream-check`

Returns:

```json
{
  "configured": true,
  "reachable": true,
  "model": "gpt-5.4",
  "base_url": "http://example.local/v1",
  "latency_ms": 120,
  "response_preview": "ok",
  "error": null
}
```

If credentials or base URL are missing, the endpoint should return a structured non-throwing response with `configured: false`.

## 12. Job State Model

The TypeScript backend should use a strongly typed `JobPayload` model that matches the frontend and Python backend.

Allowed job states:

- `queued`
- `running`
- `analysis_completed`
- `rendering`
- `completed`
- `failed`

Each job is stored at:

```text
outputs/jobs/{job_id}.json
```

State writes must be atomic:

1. Serialize the next payload to a temporary file in the same directory.
2. Rename it over the target JSON file.

The job repository must provide:

- `createJob(payload)`
- `loadJob(jobId)`
- `updateJob(jobId, mutator)`

This repository boundary keeps file locking and timestamp updates out of route handlers.

## 13. Queue and Concurrency Model

The first TypeScript backend should use an in-process queue with a configurable worker count.

### 13.1 Queue Responsibilities

- Accept analysis and render tasks.
- Run at most `DEEPEXCEL_JOB_CONCURRENCY` tasks at the same time.
- Keep task execution outside route handlers.
- Mark failures in job state.
- Avoid starting duplicate render tasks for the same completed or rendering job.

### 13.2 Task Types

```text
analysis job
  input: job_id, upload_path
  output: updated job JSON with report_spec and chart_paths

render job
  input: job_id
  output: updated job JSON with report_id and download_path
```

### 13.3 Failure Behavior

If a task throws:

- Set the current task status to `failed`.
- Set job `state` to `failed`.
- Set job `error` to a user-readable message.
- Preserve completed task statuses.

## 14. Data Ingestion and Normalization

The TypeScript backend should support:

- `.csv`
- `.xlsx`
- `.xlsm` if the parsing library can read it reliably

It should normalize source data into the canonical fields already used by Python:

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

Minimum valid input:

- At least one numeric measurement column.
- At least one row.

If no explicit sequence column exists, the TypeScript backend should use row order as `sequence_index`. This avoids chart failures when sample data lacks an index column.

## 15. Field Mapping Strategy

The first implementation should combine deterministic rules and AI mapping:

1. Try deterministic column matching for common names such as `measurement_value`, `measurement`, `value`, `lsl`, `usl`, `sample_id`, `batch`, `sequence`, and `timestamp`.
2. If deterministic mapping cannot find a measurement column, call the AI field mapping planner when upstream credentials are configured.
3. If AI is unavailable or invalid, fail with a clear parse-stage error.

The route response should not expose raw model output. It should store a concise `reasoning` string in the `parse` task when available, matching the current frontend behavior.

## 16. Analytics Strategy

SPC and quality metrics must be deterministic TypeScript code.

Required metrics:

- Mean.
- Population standard deviation.
- Minimum.
- Maximum.
- Pass rate.
- Out-of-spec count.
- Cp when `usl`, `lsl`, and nonzero standard deviation exist.
- Cpk when `usl`, `lsl`, and nonzero standard deviation exist.
- I-MR control limits when enough variation exists.

Required anomaly types:

- `out_of_spec`
- `control_limit`

The first TypeScript implementation should match Python formulas unless the implementation plan explicitly records a justified correction.

## 17. Chart Strategy

The TypeScript backend must produce chart paths keyed by chart ID, because the frontend and report renderer expect `chart_paths`.

Required chart IDs:

- `histogram`
- `control_chart_imr`
- `trend_line`
- `spec_comparison` when spec limits exist

Chart image files should be written to:

```text
outputs/charts/{job_id}/
```

Chart output format should be PNG.

If chart rendering is difficult on a local machine because of native canvas dependencies, the implementation may start with deterministic SVG generation converted or saved as image assets only if the Excel renderer can embed them reliably. The implementation plan must pick one concrete chart rendering path before coding.

## 18. AI Report Planner

The TypeScript backend should generate a `report_spec` compatible with the existing frontend and Excel renderer expectations.

AI may decide:

- Template ID from the existing whitelist.
- Template decision reason.
- Executive summary.
- Quality risk.
- Recommended actions.
- Chart titles and ordering.

AI must not decide:

- SPC formulas.
- Raw KPI values.
- Arbitrary file paths.
- Excel cell coordinates.
- Template IDs outside the whitelist.

Fallback behavior:

- If AI is not configured, generate deterministic fallback narrative from analysis results.
- If AI returns invalid JSON, use deterministic fallback narrative.
- If AI selects an unknown template, use `template_a_overview`.

## 19. Excel Rendering Strategy

The TypeScript backend should use `templates/{template_id}/template_manifest.json` and the matching `.xlsx` template. Rendering should remain manifest-driven.

Required behavior:

- Fill report metadata.
- Fill KPI rows.
- Fill narrative summary, risk, and actions.
- Fill detail rows.
- Embed up to four chart images using manifest chart layout.
- Save the final workbook to `outputs/reports/{report_id}.xlsx`.

The first TypeScript renderer does not need to produce byte-identical styling to Python, but the generated report must open successfully in Excel and contain the same core content.

## 20. Static Outputs

The TypeScript backend should serve the local `outputs/` directory at:

```text
/outputs
```

This keeps generated chart and report links compatible with existing UI behavior.

## 21. Development Commands

Add commands under `api-ts/package.json`:

```json
{
  "scripts": {
    "dev": "tsx watch src/main.ts",
    "build": "tsc -p tsconfig.json",
    "start": "node dist/main.js",
    "test": "jest --runInBand",
    "typecheck": "tsc -p tsconfig.json --noEmit"
  }
}
```

Recommended root documentation addition:

```powershell
cd api-ts
npm install
$env:DEEPEXCEL_TS_PORT="8001"
npm run dev
```

Frontend switch:

```powershell
cd web
$env:NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8001"
npm run dev
```

## 22. Testing Strategy

### 22.1 API Tests

Use Supertest to verify:

- `GET /health` returns `status: ok`.
- `POST /api/v1/jobs` accepts a sample CSV and returns `202`.
- `GET /api/v1/jobs/{job_id}` returns the expected job shape.
- `POST /api/v1/jobs/{job_id}/render` rejects jobs before analysis is ready.
- `POST /api/v1/health/upstream-check` returns a structured response when unconfigured.

### 22.2 Unit Tests

Cover:

- CSV ingestion.
- XLSX ingestion.
- Field mapping fallback.
- Normalization.
- Analytics formulas.
- Job repository atomic writes.
- Queue concurrency limit.
- AI fallback narrative.

### 22.3 Integration Test

Use `sample_data/normal_batch.csv` to verify the happy path:

1. Create a job.
2. Wait for `analysis_completed`.
3. Verify `report_spec` exists.
4. Verify chart paths exist.
5. Trigger render.
6. Wait for `completed`.
7. Verify report file exists.

## 23. Acceptance Criteria

The TypeScript parallel backend is acceptable when:

1. It can run on `127.0.0.1:8001` while the Python backend can still run on `127.0.0.1:8000`.
2. The existing frontend can use it by changing `NEXT_PUBLIC_API_BASE_URL`.
3. Uploading `sample_data/normal_batch.csv` creates a job and reaches `analysis_completed`.
4. The returned job payload matches the frontend `JobPayload` shape.
5. The backend computes mean, standard deviation, pass rate, and spec-based metrics where applicable.
6. The backend creates chart paths for the expected chart IDs.
7. Rendering creates an `.xlsx` report in `outputs/reports/`.
8. Health and upstream-check endpoints return compatible responses.
9. API and unit tests pass.
10. The Python backend remains untouched and still testable.

## 24. Risks and Mitigations

### 24.1 Risk: Excel output differs from Python

Mitigation:

- Define compatibility at the user-visible content level, not byte identity.
- Test workbook existence and key filled cells.
- Keep using existing template manifests.

### 24.2 Risk: Chart rendering dependencies are brittle

Mitigation:

- Choose and verify the rendering library early.
- Keep chart module isolated.
- Add tests that assert files are generated and non-empty.

### 24.3 Risk: AI responses drift from schema

Mitigation:

- Validate model output with Zod.
- Whitelist template IDs and chart IDs.
- Use deterministic fallback narrative.

### 24.4 Risk: Job state corruption under concurrency

Mitigation:

- Centralize job state writes in `jobRepository`.
- Use atomic write-and-rename behavior.
- Add queue concurrency and repository tests.

### 24.5 Risk: Two backends diverge silently

Mitigation:

- Keep API compatibility tests close to frontend types.
- Reuse sample data for both implementations.
- Document intentional differences in `api-ts/README.md`.

## 25. Implementation Phasing

### Phase 1: Skeleton and API Contract

- Create `api-ts/` project.
- Add Express app, config, health route, jobs route stubs.
- Add Jest and Supertest.
- Verify frontend-facing response shapes.

### Phase 2: Job State and Queue

- Add job repository.
- Add in-process queue.
- Add upload persistence.
- Add task status lifecycle.

### Phase 3: Deterministic Pipeline

- Add CSV/XLSX ingestion.
- Add field mapping fallback.
- Add normalization.
- Add analytics.
- Add chart generation.

### Phase 4: AI and Report Spec

- Add upstream check.
- Add AI field mapping when needed.
- Add AI report planner.
- Add deterministic fallback narrative.

### Phase 5: Excel Rendering and End-to-End Flow

- Add manifest-driven Excel renderer.
- Generate reports under `outputs/reports/`.
- Add integration test with sample data.
- Document local startup.

## 26. Open Decisions for the Implementation Plan

The implementation plan must make final choices for:

- Chart rendering package.
- XLSX parser and renderer package details.
- Whether `api-ts/` has an independent `package-lock.json` or participates in a root workspace.
- Whether local startup scripts should start Python, TypeScript, or both.

These are implementation choices, not product requirements. The design requirement is that the TypeScript backend remains parallel, compatible, and locally runnable.

## 27. Final Recommendation

Build `api-ts/` as a standalone Express TypeScript backend that mirrors the current Python backend's public contract. Keep the first version local and file-backed, but give it a real queue boundary and typed service modules so it can evolve toward stronger concurrency later.

This path provides the safest migration base: the Python backend remains available, the frontend contract stays stable, and the TypeScript backend can be implemented and verified one capability at a time.
