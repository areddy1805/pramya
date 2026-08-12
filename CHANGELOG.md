# Changelog

All notable changes to Pramya are recorded here.
Format based on [Keep a Changelog](https://keepachangelog.com/); versions follow [SemVer](https://semver.org/).

## [Unreleased]

### Added

- **Phase H — voice persistence & communication:** candidate audio persisted
  as WAV + `audio_segment` rows (opt-in `VOICE_STORE_AUDIO`, retention days);
  replay endpoints (`GET /interviews/{id}/voice/audio[/{segment_id}]`);
  WS heartbeat (`heartbeat` -> `heartbeat_ack`) and reconnect resync (`resume`
  event with authoritative state + last question); deterministic
  communication analysis (`GET /interviews/{id}/communication`) — verbosity,
  fillers, speaking time, response latency, interruptions — measured only,
  never fabricated.
- **Phase I — security hardening:** CORSMiddleware applied (previously parsed
  but never wired); optional bearer-token auth (`API_TOKENS`, HTTP + voice WS);
  per-IP fixed-window rate limit (`RATE_LIMIT_RPM`); security response headers;
  upload storage keys derived from content digest + whitelisted suffix;
  prompt-injection boundary tests; dependency audit clean.
- **Phase J — demo mode:** `demo/` fixtures for 4 roles; idempotent
  `POST /api/v1/demo/setup` (profile -> resume upload/index/extract -> role
  analysis -> readiness -> preparation); `make demo-setup`; Settings "Demo
  data" section; verified end-to-end with real oMLX embeddings + DeepSeek.
- **Phase K — memory/history/debrief:** interview record endpoint
  (`GET /interviews/{id}/transcript`); History, Debriefs (create + analyze),
  and Transcript pages; nav + routes.
- **Phase L — automated E2E:** Playwright suite (`frontend/e2e/`,
  `make e2e`): dashboard readiness + full typed-interview journey against the
  live stack. Fixed two real defects the suite exposed: text-mode UI never
  consumed SSE `evaluation` events, and the in-session score only rendered in
  voice mode.
- **Phase M — fresh-clone verification:** fresh-DB migration (23 tables from
  zero), example-env boot, documented quickstart commands verified.

### Changed

- Cost policy reconciliation: Langfuse pinned to OSS/self-hosted (MIT) — Cloud/Enterprise are not V1 dependencies; `LANGFUSE_HOST` default now self-hosted (`http://localhost:3000`). Added project-wide free/open-source-first infrastructure rule and dependency classification to `docs/DECISIONS.md`. Docs updated repo-wide (plan, ADR-008, observability, deployment, troubleshooting, memory).

### Added

- Master implementation plan (`docs/MASTER_IMPLEMENTATION_PLAN.md`): product vision, architecture, domain model, framework boundaries, AI/voice/retrieval/evaluation architecture, 13 implementation phases with tasks/tests/acceptance criteria, 30-day schedule, risk register, progress tracker.
- Decision records (`docs/DECISIONS.md` + `docs/architecture/ADR-001..014`): framework boundaries, LangGraph workflow, LlamaIndex knowledge layer, evidence-first evaluation, pgvector, observability, evaluation strategy, security/PII, model stack, oMLX runtime, speech stack, MCP boundary, persistence, modular monolith, deployment.
- Model catalog (`docs/MODEL_CATALOG.md`): 8-model definitive V1 stack with verified licenses, MLX weights, memory, fallbacks; alternative/research models documented.
- Architecture companions (`docs/ai/`): AI, Voice, Retrieval, Evaluation.
- Operations docs (`docs/operations/`): Deployment, Troubleshooting.
- Project memory refreshed with verified environment/model/framework facts.
- Updated `.env.example` (DeepSeek v4 flash, oMLX, voice retention, Langfuse, uploads).

### Changed

- **Phase 0 scaffold (2026-08):**
  - Backend: uv-managed `pyproject.toml` (FastAPI 0.139, Pydantic 2.13, SQLAlchemy 2.0, asyncpg, alembic, pgvector 0.5.x client), app skeleton (`core/`, `api/v1/`, `domain/`), lifespan + health endpoint, request-id middleware, structured JSON logging.
  - Domain: state enums (StrEnum), core schemas, typed errors.
  - Frontend: Vite 8 + React 19 + TS ~6.0 strict + Tailwind 4 + router/query/zustand app shell, placeholder screens, CI build.
  - Infra: `docker-compose.yml` (pgvector:pg17 + backend + frontend), Dockerfiles, nginx, Makefile targets.
  - CI: `.github/workflows/ci.yml` (ruff, mypy, pytest, oxlint, frontend build).
  - Tests relocated to repo-root `tests/` per plan §23 (unit layer active; 16 passing).
  - pgvector pin correction: Python client latest = 0.5.x (server extension 0.8.x in Docker image).

## [0.0.0] — 2026-08

### Added

- Initial repository: `AGENTS.md`, README, LICENSE, `.gitignore`, `.env.example`, docs stubs.
