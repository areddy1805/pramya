# Pramya — Architectural Decisions

> Decision log + index. Full ADR files live in `docs/architecture/`
> (ADR-001 … ADR-014). This document is the authoritative decision log and
> index; project-foundation decisions are recorded inline as DEC entries.
>
> Rule: numbering here matches `docs/architecture/` file numbering exactly
> for ADR entries. Add a new ADR file first, then index it here.

---

# Decision Index

| ID | Title | Location | Status |
|---|---|---|---|
| ADR-001 | Framework boundaries | docs/architecture/ADR-001-framework-boundaries.md | Accepted |
| ADR-002 | LangGraph workflow | docs/architecture/ADR-002-langgraph-workflow.md | Accepted |
| ADR-003 | LlamaIndex knowledge layer | docs/architecture/ADR-003-llamaindex-knowledge-layer.md | Accepted |
| ADR-004 | Model routing | docs/architecture/ADR-004-model-routing.md | Accepted |
| ADR-005 | Evidence-first evaluation | docs/architecture/ADR-005-evidence-first-evaluation.md | Accepted |
| ADR-006 | MCP boundary | docs/architecture/ADR-006-mcp-boundary.md | Accepted |
| ADR-007 | pgvector | docs/architecture/ADR-007-pgvector.md | Accepted |
| ADR-008 | Observability | docs/architecture/ADR-008-observability.md | Accepted |
| ADR-009 | Evaluation | docs/architecture/ADR-009-evaluation.md | Accepted |
| ADR-010 | Security and PII | docs/architecture/ADR-010-security-and-pii.md | Accepted |
| ADR-011 | MLX local runtime + OMLX | docs/architecture/ADR-011-mlx-runtime-omlx.md | Accepted |
| ADR-012 | Voice model stack (ASR/TTS) | docs/architecture/ADR-012-voice-models.md | Accepted |
| ADR-013 | deepseek-v4-flash cloud + thinking policy | docs/architecture/ADR-013-deepseek-cloud.md | Accepted |
| ADR-014 | Retrieval models (BGE-M3 + reranker) | docs/architecture/ADR-014-retrieval-models.md | Accepted |

---

# Project Foundations (inline decisions)

These are product/project-level decisions recorded here for continuity.
They are no less binding than ADRs.

## DEC-001 — Greenfield Project

**Status:** Accepted
**Date:** 2026-08

**Decision:** Pramya is built as a new greenfield project.

**Context:** Repository starts with no application implementation.

**Rationale:** Architecture designed around product requirements, not inherited code.

**Consequences:** Establish project structure, tooling, testing, workflow from scratch.

## DEC-002 — Evidence-Driven Product Architecture

**Status:** Accepted
**Date:** 2026-08

**Decision:** Evidence is a first-class domain concept.

**Context:** Pramya must provide more value than generic conversational AI.

**Rationale:** Product must understand claims, demonstrated capability, evidence, target-role requirements, weaknesses, longitudinal progress.

**Consequences:** Evaluation, retrieval, memory, practice recommendations designed around structured evidence (ledger, provenance classes, immutability).

## DEC-003 — Voice as a First-Class Capability

**Status:** Accepted
**Date:** 2026-08

**Decision:** Voice interviewing is core V1, not an add-on.

**Rationale:** Real interview preparation requires spoken interaction.

**Consequences:** ASR/TTS/streaming/interruption/cancellation/pause/resume/audio state are core architecture; explicit voice state machine; stale-TTS prohibition.

## DEC-004 — Modular Monolith + API-First Versioning

**Status:** Accepted
**Date:** 2026-08

**Decision:** One FastAPI application, modular packages, `/api/v1` versioned API, OpenAPI generated. No microservices.

**Context:** 30-day constraint; spec prefers modular monolith.

**Rationale:** Simple architecture; deployable; replaceable parts.

**Consequences:** Package layout in master plan §8; contract tests on OpenAPI.

## DEC-005 — Persistence

**Status:** Accepted
**Date:** 2026-08

**Decision:** PostgreSQL 18 authoritative V1 database (SQLAlchemy 2.0 async + Alembic + asyncpg). SQLite only for tests if justified. Redis deferred until measurement justifies (rate limiting/coordination).

**Context:** Spec mandates PostgreSQL; Redis only when it solves a real requirement.

**Rationale:** Verified current stack; keeps infra proportional.

**Consequences:** Domain model in master plan §7; HNSW/FTS indexes; deletion/retention support.

## DEC-006 — Deterministic Readiness Model

**Status:** Accepted
**Date:** 2026-08

**Decision:** Readiness, progress, and queue aggregation are deterministic application logic; LLM provides evidence + semantic judgments only.

**Context:** "LLM → 8/10" is prohibited; scores must have observable reasons; no fabricated progress.

**Rationale:** Reproducibility, trust, testability.

**Consequences:** Readiness calculator, priority engine, progress aggregation are pure functions with golden tests.

## DEC-007 — SQLAlchemy 2.0 Async + Alembic

**Status:** Accepted
**Date:** 2026-08

**Decision:** Async SQLAlchemy 2.0 (`Mapped`/`mapped_column`, `select()`) + asyncpg + Alembic async migrations for all domain persistence.

**Context:** FastAPI async backend needs an async ORM.

**Rationale:** Standard, mature FastAPI+Postgres pattern in 2026.

**Consequences:** No lazy loading in async contexts (use `selectinload`); `expire_on_commit=False`; async engine lifecycle in FastAPI lifespan.

## DEC-008 — React 19 + Vite + TypeScript 7 Frontend

**Status:** Accepted
**Date:** 2026-08

**Decision:** React 19.2 + Vite SPA + TypeScript strict; TanStack Query v5; native EventSource + WebSocket; Vitest + Testing Library + MSW; Biome.

**Context:** Product UI must feel like a serious tool; SSE/WS required for live interview.

**Rationale:** Current recommended 2026 stack; type safety; React Compiler.

**Consequences:** Live Interview screen is flagship; loading/error states everywhere; no ChatGPT-like UI.

---

# Change Control

New ADR → write file in `docs/architecture/`, add to index above, record in
master plan §23 and CHANGELOG.md. Superseded ADR → mark status in the file,
keep history. Never silently renumber.
