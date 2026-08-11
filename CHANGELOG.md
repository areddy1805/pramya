# Changelog

All notable changes to Pramya are recorded here.
Format based on [Keep a Changelog](https://keepachangelog.com/); versions follow [SemVer](https://semver.org/).

## [Unreleased]

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
