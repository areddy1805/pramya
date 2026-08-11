# Pramya — Architectural Decisions

> Authoritative decision log for Pramya.
>
> Full ADRs live in `docs/architecture/` as `ADR-001…ADR-014` (canonical numbering,
> matches master plan §23 and spec §32). Project-foundation decisions are recorded
> inline below (they precede the architecture work). This file is the decision
> index + foundation record; it must stay consistent with the ADR files.
>
> Numbering rule: architecture ADRs are numbered by FILE (`ADR-NNN-*.md`).
> Do not renumber files to match older plan text — update the plan text instead.

---

## Project Foundation Decisions

Recorded here (not as separate ADR files) because they are project-level
starting points rather than architectural layers.

### Foundation-1 — Greenfield Project

**Status:** Accepted
**Date:** 2026-08

**Decision:** Pramya is built as a new greenfield project rather than adapted from an existing application.

**Context:** The repository starts with no application implementation.

**Rationale:** The architecture can be deliberately designed around product requirements rather than inherited from unrelated code.

**Consequences:** Project structure, tooling, testing strategy, and development workflow are established from scratch.

### Foundation-2 — Evidence-Driven Product Architecture

**Status:** Accepted
**Date:** 2026-08

**Decision:** Evidence is a first-class domain concept.

**Context:** Pramya must provide substantially more value than generic conversational AI.

**Rationale:** The product needs to understand candidate claims, demonstrated capability, supporting evidence, target-role requirements, weaknesses, and longitudinal progress.

**Consequences:** Evaluation, retrieval, candidate memory, and practice recommendations are designed around structured evidence (ledger, statuses claimed/observed/demonstrated/inferred/unknown, provenance).

### Foundation-3 — Model-Routed AI Architecture

**Status:** Accepted
**Date:** 2026-08

**Decision:** Pramya uses specialized models per workload through an InferenceRouter rather than routing every task through a single LLM.

**Context:** Reasoning, retrieval, reranking, ASR, TTS, and embeddings have different latency/quality/cost/hardware profiles.

**Rationale:** Local-first cost control + cloud quality where needed (spec §28).

**Consequences:** Providers sit behind a capability interface (`generate/embed/rerank/transcribe/synthesize`); routing decisions are observable; fallback chains exist per task class.

### Foundation-4 — Apple Silicon Local AI (MLX/oMLX)

**Status:** Accepted
**Date:** 2026-08

**Decision:** Local AI development targets the M4 16 GB machine using MLX/oMLX-compatible inference where appropriate.

**Context:** Primary development environment is an Apple Silicon MacBook Pro (M4, 16 GB, 512 GB).

**Rationale:** Native Apple Silicon inference provides practical local development without a GPU server.

**Consequences:** Model lifecycle management, quantization, resource awareness, bounded concurrency, lazy loading (ADR-011).

### Foundation-5 — Voice as a First-Class Capability

**Status:** Accepted
**Date:** 2026-08

**Decision:** Voice interviewing is part of V1, not a late-stage add-on.

**Context:** Real interview preparation requires natural spoken interaction; spec makes voice first-class.

**Rationale:** Spoken interaction is a materially different experience from text chat.

**Consequences:** ASR/TTS/streaming/interruption/cancellation/pause/resume/audio state are core architecture; explicit voice state machine; stale-TTS prohibition (ADR-012).

---

## Architecture Decision Records — Index

Canonical ADRs in `docs/architecture/`:

| ADR | Title | File | Status |
|---|---|---|---|
| ADR-001 | Framework Boundaries | `ADR-001-framework-boundaries.md` | Accepted |
| ADR-002 | LangGraph Interview Workflow | `ADR-002-langgraph-workflow.md` | Accepted |
| ADR-003 | LlamaIndex Knowledge Layer | `ADR-003-llamaindex-knowledge-layer.md` | Accepted |
| ADR-004 | Model Routing | `ADR-004-model-routing.md` | Accepted |
| ADR-005 | Evidence-First Evaluation | `ADR-005-evidence-first-evaluation.md` | Accepted |
| ADR-006 | MCP Boundary | `ADR-006-mcp-boundary.md` | Accepted |
| ADR-007 | pgvector | `ADR-007-pgvector.md` | Accepted |
| ADR-008 | Observability | `ADR-008-observability.md` | Accepted |
| ADR-009 | Evaluation | `ADR-009-evaluation.md` | Accepted |
| ADR-010 | Security and PII | `ADR-010-security-and-pii.md` | Accepted |
| ADR-011 | MLX Runtime + oMLX | `ADR-011-mlx-runtime-omlx.md` | Accepted |
| ADR-012 | Voice Model Stack (ASR/TTS) | `ADR-012-voice-models.md` | Accepted |
| ADR-013 | deepseek-v4-flash Cloud Reasoning + Thinking Policy | `ADR-013-deepseek-cloud.md` | Accepted |
| ADR-014 | Retrieval Models (BGE-M3 + Qwen3-Reranker-0.6B) | `ADR-014-retrieval-models.md` | Accepted |

Persistence, modular monolith, deployment, and API-first versioning decisions
are covered by the foundation decisions above + master plan §8/§9/§16/§19 +
ADR-001/ADR-007/ADR-010 — no separate ADR files were needed for those layers
(V1 scope discipline; can be split later if warranted).

---

## Decision Log

| Date | Decision | Reason | Impact |
|---|---|---|---|
| 2026-08 | All 8 definitive models verified compatible; no replacements | Verified licenses/runtimes/memory (MODEL_CATALOG.md, ADR-011..014) | Stack locked |
| 2026-08 | `mcp>=1.27,<2` pinned for V1 | MCP SDK v2.0.0 renamed FastMCP→MCPServer; protocol change too fresh | Stable FastMCP API (ADR-006) |
| 2026-08 | Embeddings/rerank via oMLX HTTP, not `mlx-embeddings` | `mlx-embeddings` reported GPL-3.0 — license conflict | License-clean retrieval (ADR-011) |
| 2026-08 | deepseek-v4-flash only (no legacy IDs) | Legacy `deepseek-chat`/`deepseek-reasoner` deprecated 2026-07-24 | API correctness (ADR-013) |
| 2026-08 | FastAPI native SSE (≥0.135) | Built-in `fastapi.sse`; no sse-starlette | Fewer deps |
| 2026-08 | SQLAlchemy 2 async + asyncpg + Alembic | Standard 2026 FastAPI pattern | Async persistence |
| 2026-08 | Redis default off | Spec: only when justified | Simpler ops |
| 2026-08 | Langfuse v4 + OpenInference for LlamaIndex | Native callbacks deprecated in v4 | Correct tracing (ADR-008) |
| 2026-08 | QueryFusionRetriever over pgvector built-in hybrid | Known top-k/alpha limitation in PGVectorStore hybrid | Hybrid retrieval quality (ADR-007/014) |
| 2026-08 | Text interview first; voice layered on same LangGraph | Voice is critical path but shares the engine | Phases 4 vs 7–9 (ADR-002/012) |

Full change history: `docs/CHANGELOG.md`. Execution state: `docs/MASTER_IMPLEMENTATION_PLAN.md`.
