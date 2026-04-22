# Repository Guidelines

## Project Structure & Module Organization
`api/app/` contains the FastAPI backend. Keep HTTP routes in `routes/`, business logic in `services/`, shared models in `schemas.py` and `report_models.py`, and AI orchestration in `agent/`. Backend tests live in `api/tests/`. `web/app/` holds Next.js App Router pages, `web/components/` contains reusable UI, `web/lib/api.ts` centralizes client-side API types and calls, and `web/tests/` covers UI behavior with Jest. `templates/` stores Excel report templates, `sample_data/` holds demo datasets, `outputs/` is runtime-generated and should stay untracked, and `docs/superpowers/` contains specs and implementation plans.

## Build, Test, and Development Commands
Use the repo root unless noted otherwise.

- `.\.venv\Scripts\python -m pip install -r api/requirements-dev.txt` installs backend dependencies.
- `.\.venv\Scripts\python -m uvicorn api.app.main:app --reload --port 8000` runs the API on `127.0.0.1:8000`.
- `cd web; npm install; npm run dev` installs frontend packages and starts Next.js on `127.0.0.1:3000`.
- `powershell -ExecutionPolicy Bypass -File .\scripts\start-local.ps1` starts both services and writes logs/PIDs to `outputs/dev/`.
- `powershell -ExecutionPolicy Bypass -File .\scripts\stop-local.ps1` stops the local stack.
- `.\.venv\Scripts\python -m pytest api/tests -v` runs backend tests.
- `cd web; npm test` runs frontend tests.
- `cd web; npm run build` verifies the production frontend build.

## Coding Style & Naming Conventions
Python uses 4-space indentation, type hints, and `snake_case` for modules, functions, and variables. TypeScript/React uses 2-space indentation, `PascalCase` for components, and `camelCase` for helpers and props. Follow the existing import style: backend imports from `api.app...`, frontend imports from `@/...`. Keep route files under `web/app/**/page.tsx`, and name tests `test_*.py` or `*.test.tsx`.

## Testing Guidelines
Add or update tests with every behavior change. Prefer API-level assertions in backend tests and user-visible assertions in frontend tests with Testing Library. For report rendering or template changes, verify with a file from `sample_data/` and note the dataset in the PR.

## Commit & Pull Request Guidelines
This repository currently has no established git history, so start with concise imperative commits such as `api: add upstream retry guard` or `web: refine upload progress state`. PRs should include a short summary, linked issue/spec when available, the commands you ran, screenshots for `web/` changes, and sample input/output notes for Excel or template updates.

## Security & Configuration Tips
Do not commit `.env`, `.env.*`, `outputs/`, `web/node_modules/`, or `web/.next/`. Backend settings are loaded from `.env` with the `DEEPEXCEL_` prefix; frontend runtime configuration uses `NEXT_PUBLIC_API_BASE_URL`.
