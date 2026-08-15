# Pramya — Architectural Decisions

> Authoritative decision log. Full ADRs live in `docs/architecture/` (files ADR-001..ADR-014).
> Product-level decisions recorded inline as ADR-015..019.
> Only meaningful architectural/product decisions belong here.
> Decision numbering follows the spec's mandated ADR list (spec §32) for 001-010, plus model/runtime ADRs 011-014.

---

## Decision Index

| ADR | Title | Status | Location |
|---|---|---|---|
| ADR-001 | Framework boundaries | Accepted | docs/architecture/ADR-001-framework-boundaries.md |
| ADR-002 | LangGraph interview workflow | Accepted | docs/architecture/ADR-002-langgraph-workflow.md |
| ADR-003 | LlamaIndex knowledge layer | Accepted | docs/architecture/ADR-003-llamaindex-knowledge-layer.md |
| ADR-004 | Model routing | Accepted | docs/architecture/ADR-004-model-routing.md |
| ADR-005 | Evidence-first evaluation + deterministic readiness | Accepted | docs/architecture/ADR-005-evidence-first-evaluation.md |
| ADR-006 | MCP boundary | Accepted | docs/architecture/ADR-006-mcp-boundary.md |
| ADR-007 | PostgreSQL + pgvector persistence | Accepted | docs/architecture/ADR-007-pgvector.md |
| ADR-008 | Observability (Langfuse + structured logs, PII-safe) | Accepted | docs/architecture/ADR-008-observability.md |
| ADR-009 | AI evaluation strategy (DeepEval + golden datasets) | Accepted | docs/architecture/ADR-009-evaluation.md |
| ADR-010 | Security & PII model | Accepted | docs/architecture/ADR-010-security-and-pii.md |
| ADR-011 | MLX local runtime + oMLX server | Accepted | docs/architecture/ADR-011-mlx-runtime-omlx.md |
| ADR-012 | Voice model stack (Parakeet live / Qwen3-ASR recorded / Qwen3-TTS) | Accepted | docs/architecture/ADR-012-voice-models.md |
| ADR-013 | deepseek-v4-flash cloud reasoning + thinking policy | Accepted | docs/architecture/ADR-013-deepseek-cloud.md |
| ADR-014 | Retrieval models: BGE-M3 + Qwen3-Reranker-0.6B | Accepted | docs/architecture/ADR-014-retrieval-models.md |
| ADR-015 | Greenfield project | Accepted | inline below |
| ADR-016 | Evidence-driven product architecture | Accepted | inline below |
| ADR-017 | Model-routed AI architecture | Accepted | inline below |
| ADR-018 | Apple Silicon local AI (MLX/oMLX) | Accepted | inline below |
| ADR-019 | Voice as a first-class capability | Accepted | inline below |
| ADR-020 | Model stack finalization: 4B workhorse + DeepSeek escalation, 9B deferred | Superseded by ADR-023 (text routing) | inline below |
| ADR-021 | Knowledge Layer: deterministic ingestion + retrieval (LlamaIndex not required) | Superseded (framework realignment) | inline below |
| ADR-022 | Interview Engine: deterministic service state machine (LangGraph not required) | Superseded (framework realignment) | inline below |
| ADR-023 | Production text inference: DeepSeek only; local oMLX retained for audio + retrieval | Accepted | docs/architecture/ADR-023-deepseek-only-text-omlx-audio-retrieval.md |
| ADR-025 | TTS provider: Qwen3-TTS (oMLX) for V1.1; Pocket TTS BENCHMARKED/CANDIDATE only | Superseded by ADR-027 (provider default) | docs/architecture/ADR-025-tts-provider-qwen3-v11.md |
| ADR-027 | TTS provider: Kyutai Pocket TTS becomes the default (CPU, ~30 ms first PCM, 8-9× RTF); Qwen3 kept as `TTS_PROVIDER=qwen3` fallback | Accepted | docs/architecture/ADR-027-pocket-tts-default.md |
| ADR-026 | Persistent multi-profile career workspace (profile-scoped documents/roles/evidence/analytics, idempotent dedup, active profile UX preference) | Accepted | docs/architecture/ADR-026-career-profile-workspace.md |
| ADR-028 | Interview productization: grounded context, follow-up engine, coverage, prep memory | Accepted | docs/architecture/ADR-028-interview-productization.md |
| ADR-029 | Frontend visual canon: The Drawing Sheet, frozen (More ▾ secondary navigation + density refinement) | Accepted | docs/architecture/ADR-029-frontend-visual-canon.md |

---

# Decisions

## ADR-001 — Framework Boundaries

**Status:** Accepted
**Date:** 2026-08

**Decision:** LangChain = model/tool/structured-output/prompt primitives; LangGraph = stateful interview orchestration; LlamaIndex = knowledge/retrieval layer; MCP = bounded external interoperability surface. Each behind clear boundaries; removable without rewriting domain logic.

**Context:** Spec requires real framework experience without framework-for-framework's-sake.

**Rationale:** Small well-defined integrations beat deep coupling.

**Consequences:** Layering rules in master plan §8/§9; ADR-002/003/006 detail boundaries.

## ADR-002 — LangGraph as Interview Orchestration Engine

**Status:** Accepted
**Date:** 2026-08

**Decision:** Interview workflow is a typed LangGraph 1.2 StateGraph with Postgres checkpointing, `interrupt()`/`Command(resume=...)` for turn boundaries, node timeouts, streaming events.

**Context:** Interview is inherently stateful, adaptive, resumable, conditional.

**Rationale:** Durable execution, pause/resume, browser-refresh survival, idempotent resume — verified current API (LangGraph 1.2.x).

**Consequences:** Session ↔ thread_id; interrupts at LISTENING; no duplicated questions/evaluations; tests for recovery.

## ADR-003 — LlamaIndex as Knowledge/Retrieval Layer

**Status:** Accepted
**Date:** 2026-08

**Decision:** LlamaIndex 0.14 `IngestionPipeline` owns document parsing→chunking→metadata→embedding→pgvector write; retrieval pipeline uses hybrid search + rerank. Dedup handled explicitly (known 0.14 gotcha: no vector-store dedup).

**Context:** Resume/JD/evidence/history retrieval needs indexing and metadata.

**Rationale:** Real RAG experience; verified current version 0.14.x.

**Consequences:** Knowledge layer only; never owns workflow state; explicit docstore tracking.

## ADR-004 — Model Routing

**Status:** Accepted
**Date:** 2026-08

**Decision:** InferenceRouter with provider abstraction (deepseek-v4-flash / oMLX / speech); task→capability→provider→model→mode→fallback policy; observable routing decisions; cost control.

**Context:** Reasoning, retrieval, reranking, ASR, TTS, embeddings have different latency/quality/cost/hardware profiles.

**Rationale:** Local-first cost control + quality where needed.

**Consequences:** Providers behind capability interface (`generate/embed/rerank/transcribe/synthesize`); routing telemetry; fallback chains.

## ADR-005 — Evidence-First Evaluation + Deterministic Readiness

**Status:** Accepted
**Date:** 2026-08

**Decision:** Evaluation = dimensions + confidence + strengths/weaknesses + evidence refs + missing evidence + hints used + evaluator version. Readiness/progress/queue aggregation is deterministic application logic; LLM provides semantic judgments only.

**Context:** "LLM → 8/10" is prohibited by spec.

**Rationale:** Scores must have observable reasons; no fabricated progress.

**Consequences:** Readiness calculator, priority engine, progress aggregation are pure functions with golden tests.

## ADR-006 — MCP Boundary

**Status:** Accepted
**Date:** 2026-08

**Decision:** MCP server is a bounded read-oriented external surface (tools: candidate profile lookup, evidence search, role requirements, interview/practice history; resources: profile/role/prep plan). Application never routes through MCP internally.

**Context:** MCP must be interoperability, not internal architecture (spec §8).

**Rationale:** Genuine external use case: MCP-compatible agents + eval harness can query Pramya's evidence state.

**Consequences:** Standalone server process; contract tests; no write tools in V1.

## ADR-007 — PostgreSQL + pgvector Persistence

**Status:** Accepted
**Date:** 2026-08

**Decision:** PostgreSQL 17 authoritative V1 database (SQLAlchemy 2.x async + psycopg3 + Alembic); pgvector 0.8 HNSW for vectors; hybrid dense + FTS retrieval. SQLite tests-only; Redis deferred until measurement justifies.

**Context:** Spec mandates PostgreSQL; Redis only when it solves a real requirement.

**Rationale:** Verified current stack; keeps infra proportional.

**Consequences:** 1024-dim BGE-M3 locked in schema from day one; framework tables namespaced in same DB; deletion/retention support.

## ADR-008 — Observability (Langfuse + structured logs)

**Status:** Accepted
**Date:** 2026-08

**Decision:** Langfuse OSS (self-hosted, MIT-licensed) for LLM traces; structured JSON logs with the spec's event set; PII-safe by design (IDs + redacted metadata; never raw resume/answer content). Langfuse Cloud and Enterprise-only features are NOT V1 dependencies.

**Context:** Must trace interview → LangGraph → question gen/retrieval/eval/evidence/tools; must not leak candidate data.

**Rationale:** Verified Langfuse OSS v4 Python SDK (`@observe`); spec requires observability; self-hosted MIT platform avoids paid SaaS dependency.

**Consequences:** Observability scaffolding in Phase 0; routing decisions always logged; redaction audit in Phase 11.

## ADR-009 — AI Evaluation Strategy (DeepEval + golden datasets)

**Status:** Accepted
**Date:** 2026-08

**Decision:** Golden datasets for all major pipelines; DeepEval 4.1 for semantic metrics with judge = deepseek-v4-flash (temperature 0), not cloud gpt default; deterministic tests for validity/math/state.

**Context:** "Output looks good" is not evidence (spec).

**Rationale:** Verified DeepEval 4.1 current; cost/privacy favor DeepSeek judge.

**Consequences:** `tests/evals/` + CI gate; evaluator versioning; any prompt change reruns affected evals.

## ADR-010 — Security & PII Model

**Status:** Accepted
**Date:** 2026-08

**Decision:** Documents are untrusted input; prompt-injection defenses; LLM output → structured proposal → validation → application logic → persistence; candidate data sensitive; secrets never committed; retention/deletion supported; rate limiting; CORS/headers.

**Context:** Resumes/JDs/answers/audio are sensitive; adversarial content expected.

**Rationale:** Spec §23/§46; security cannot be weakened for convenience.

**Consequences:** Upload guards, separation of system/user/document/evidence/model-output, PII scrubbers, adversarial fixtures in tests.

## ADR-011 — MLX Local Runtime + oMLX Server

**Status:** Accepted
**Date:** 2026-08

**Decision:** oMLX (Apache-2.0) is the single local inference server for LLM/embeddings/reranker via OpenAI-compatible API (`/v1/chat/completions`, `/v1/embeddings`, `/v1/rerank`); multi-model serving with LRU eviction, pinning, per-model TTL, SSD-tiered KV cache. Speech models are NOT served by oMLX — dedicated lifecycle managers in voice service. Provider abstraction: `InferenceProvider` → DeepSeekProvider / MLXProvider. Model selection is configuration, not code.

**Context:** M4 16GB needs resource-aware multi-model serving; avoid GPL `mlx-embeddings` linkage (serve embeddings via oMLX instead).

**Rationale:** Verified oMLX capabilities; Apache license; active maintenance.

**Consequences:** `packages/ai/providers/`; degraded-mode matrix; ADR-012/013/014 for model specifics.

## ADR-012 — Voice Model Stack (ASR/TTS)

**Status:** Accepted
**Date:** 2026-08

**Decision:** Live ASR = Parakeet-TDT-0.6B-v3 via `parakeet-mlx` streaming (`transcribe_stream`, draft/final token phases, partial transcripts, 16 kHz mono); recorded/archival ASR = Qwen3-ASR-1.7B via `mlx-audio` (never the live default); TTS = Qwen3-TTS-12Hz-0.6B-Base (4-bit ~981 MB) streaming MLX with sentence/chunk segmentation; explicit voice state machine (listening/processing/speaking/paused/interrupted/cancelled/error); cancellation at every boundary; stale TTS after interruption is a correctness bug. Lifecycle: Parakeet + TTS + one LLM = peak live envelope (~10 GB).

**Context:** Voice is first-class; spec mandates Parakeet live / Qwen3-ASR recorded distinction; M4 16GB budget.

**Rationale:** Verified models + MLX paths; spec §10-13.

**Consequences:** `packages/voice/`: capture protocol, ASR/TTS adapters, state machine, cancellation tokens, retention policy; voice test matrix (spec §42).

## ADR-013 — deepseek-v4-flash Cloud Reasoning + Thinking Policy

**Status:** Accepted
**Date:** 2026-08

**Decision:** deepseek-v4-flash is the cloud reasoning model (spec-mandated; legacy IDs deprecated 2026-07-24). Verified: model ID `deepseek-v4-flash` (V4-Flash-0731); 1M context / 384K max output; thinking toggle via `thinking: {type: enabled|disabled}` or `reasoning_effort`; OpenAI-compatible base URL `https://api.deepseek.com`; pricing $0.14/M in (miss), $0.0028/M (hit), $0.28/M out. Task policy: thinking mode for complex evaluation/adaptive reasoning/system design/synthesis; non-thinking for latency-sensitive ops; mode observable in telemetry.

**Context:** Complex reasoning must not be routed to local models; cost control required.

**Rationale:** Verified current API; spec §6.1.

**Consequences:** DeepSeekProvider behind InferenceRouter; prompt minimization; no indiscriminate calls; cost telemetry.

## ADR-014 — Retrieval Models: BGE-M3 + Qwen3-Reranker-0.6B

**Status:** Accepted
**Date:** 2026-08

**Decision:** BGE-M3 (MIT, 1024-dim, 8192 seq, 100+ langs) for embeddings — serve via oMLX `/v1/embeddings` (MLX 4-bit ~321 MB), never via GPL `mlx-embeddings` library. Qwen3-Reranker-0.6B (Apache-2.0, MLX 4-bit ~331 MB) for reranking via oMLX `/v1/rerank` (yes/no logit scoring). Pipeline: query → candidate retrieval (BGE-M3 dense + FTS hybrid) → top-K → rerank → evidence selection → LLM.

**Context:** Evidence retrieval across resumes/JDs/transcripts/competencies/history; spec mandates both models.

**Rationale:** Verified licenses + MLX paths; licensing trap (GPL mlx-embeddings) avoided.

**Consequences:** 1024-dim locked in schema (ADR-007); retrieval service + rerank; degraded mode if oMLX down.

---

## Cost Policy (verified 2026-08, official sources)

**Rule (project-wide):** V1 framework/infrastructure selection must prefer the
strongest viable free/open-source/self-hosted option. Hosted paid services
require explicit architectural approval and must not enter the dependency
graph implicitly.

**Langfuse** = Langfuse OSS (self-hosted, MIT-licensed) is the V1
observability/evaluation platform. Verified: all product features MIT since
June 2025 (evals, annotation queues, prompt experiments, playground);
self-hosting first-class (Docker Compose); only `/ee` add-ons commercial
(SCIM, extended audit logging, data retention policies, advanced RBAC) —
none required by Pramya V1. Langfuse Cloud and Enterprise-only features are
NOT V1 dependencies. No paid Langfuse subscription. OpenTelemetry remains
the vendor-neutral instrumentation boundary.

**External dependency classification (2026-08 audit):**

| Dependency | Class | Note |
|---|---|---|
| DeepSeek V4 Flash (API) | PAID/COMMERCIAL | Explicitly approved cloud inference; keep (routing architecture, ADR-004/013) |
| Langfuse OSS | FREE/OSS (self-hosted) | MIT; Cloud = OPTIONAL PAID, not V1 |
| PostgreSQL 17 + pgvector | FREE/OSS | self-hosted Docker |
| Redis | FREE/OSS (deferred) | only if Phase 10/11 measurement justifies |
| LangGraph / LangChain / LlamaIndex | FREE/OSS | MIT |
| DeepEval | FREE/OSS | Apache-2.0; judge = deepseek (approved) |
| MLX / oMLX / local models | FREE/OSS | Apache/MIT/CC-BY-4.0 weights |
| FastAPI / Pydantic / SQLAlchemy / Alembic / asyncpg / uv / pytest / ruff / mypy / pyright | FREE/OSS | MIT/BSD/Apache |
| React / Vite / TS / Tailwind / TanStack Query / Zustand / Playwright | FREE/OSS | MIT |
| Docker / GitHub Actions | FREE/OSS (free tier) | CI infra |
| vLLM / Nemotron ASR Streaming | FREE/OSS (upgrade candidates) | not V1 deps |
| Ollama / Supabase / LinkedIn | FREE/OSS or rejected | not adopted |

No other paid/commercial SaaS enters the V1 dependency graph.

# Implementation Notes (Phase 1, 2026-08)

- **Idempotency persistence**: master plan task 1.6 requires idempotency keys for answer submission; §7 table list has no dedicated table, so `idempotency_record` (scope, key, payload, created_at; unique (scope,key)) was added as persistence infrastructure, not a domain entity. Documented in plan change log + memory.
- **`document_chunk.metadata` column**: `metadata` is reserved in the SQLAlchemy Declarative API; the column is named `metadata` in the DB and exposed as `meta` on the ORM model.
- **Enum storage**: state columns use String(32) + service/domain validation rather than native PG enum types — keeps migrations simple and reversible; domain enums remain the single source of truth.
- **QuestionType / PracticeKind enums**: added to `domain/enums.py` for `question.type` and `practice_session.kind` (plan §7 lists the columns but not their vocabularies); values mirror InterviewKind vocabulary.
- **competency.level / candidate_competency.demonstrated_level**: modeled as Integer 1..5 (CheckConstraint) per plan's `level` semantics.
- **ADR-007 file vs plan**: ADR-007 text mentions `knowledge_nodes` and PG 18; master plan §7/§17 (authoritative) uses `document_chunk` and PG 17. Implementation follows the plan; ADR-007 file is stale and should be reconciled in a docs pass.

# Product-Level Decisions (inline)

## ADR-015 — Greenfield Project

**Status:** Accepted
**Date:** 2026-08

**Decision:** Pramya is built as a new greenfield project rather than adapted from an existing application.

**Context:** Repository starts with no application implementation.

**Rationale:** Architecture deliberately designed around product requirements.

**Consequences:** Project structure, tooling, testing, workflow established from scratch.

## ADR-016 — Evidence-Driven Product Architecture

**Status:** Accepted
**Date:** 2026-08

**Decision:** Evidence is a first-class domain concept: ledger, provenance statuses (claimed/observed/demonstrated/inferred/unknown), append-only evaluations and snapshots.

**Context:** Pramya must provide more value than generic conversational AI.

**Rationale:** Product must understand claims, demonstrated capability, evidence, role requirements, weaknesses, longitudinal progress.

**Consequences:** Evaluation, retrieval, memory, practice recommendations designed around structured evidence.

## ADR-017 — Model-Routed AI Architecture

**Status:** Accepted
**Date:** 2026-08

**Decision:** Specialized models per workload via InferenceRouter (local-first; cloud only where quality demands).

**Context:** Reasoning, retrieval, reranking, ASR, TTS, embeddings have different profiles.

**Rationale:** Cost control + quality where needed.

**Consequences:** Capability interfaces; observable routing; fallback chains (ADR-004).

## ADR-018 — Apple Silicon Local AI

**Status:** Accepted
**Date:** 2026-08

**Decision:** Local AI optimized for M4 16GB via MLX/oMLX; model lifecycle management; 4-bit quantization; bounded concurrency; lazy loading; serialized MLX inference (no concurrent Metal runs).

**Context:** Primary dev machine is M4 16GB/512GB.

**Rationale:** Native Apple Silicon inference without GPU server.

**Consequences:** Resource-aware runtime; degraded-mode matrix; oMLX + host-native speech (ADR-011/012).

## ADR-019 — Voice as a First-Class Capability

**Status:** Accepted
**Date:** 2026-08

**Decision:** Voice interviewing is core V1, not an add-on; explicit audio state machine; streaming ASR/TTS; interruption/pause/resume/cancellation; stale-TTS prohibition.

**Context:** Real interview preparation requires spoken interaction.

**Rationale:** Voice provides materially different experience from text-only chat.

**Consequences:** Voice architecture (ADR-012, docs/ai/VOICE_ARCHITECTURE.md); voice test matrix; critical-path schedule protection.

## ADR-020 — Model Stack Finalization: 4B Workhorse + DeepSeek Escalation (9B Deferred)

**Status:** Accepted
**Date:** 2026-08

**Decision:**

1. Qwen3.5-4B (oMLX alias `pramya-4b`) is the primary local workhorse: default local model, thinking off, local-first, handles the majority of Pramya workload (routine generation, extraction, classification, structured generation, normal semantic tasks, interview content generation, ordinary evaluation/support).
2. deepseek-v4-flash is the escalation/cloud reasoning model: used only when the workload materially benefits from stronger reasoning/capability/context. Not the default. Not a replacement for the 4B workhorse. The InferenceRouter decides when escalation is justified.
3. Qwen3.5-9B is DEFERRED from the V1 production model stack: not a required runtime, not a fallback, not a routing target, not a required download/setup dependency. Phase 1+ must not depend on it. Recorded as a deferred/experimental local candidate (catalog §2.3) rather than a production-stack member.

Routing policy: 4B local first → application-level task-class decision → can 4B handle this adequately? yes → 4B; no → deepseek-v4-flash. No arbitrary "complexity = cloud" heuristic beyond the task-class policy. Architecture principle: **the strongest model is not the default model.**

**Context:** Prior planning documents assigned Qwen3.5-9B a production role (local reasoning, local eval, cloud fallback). Finalized stack reclassifies it: the 4B workhorse plus a deliberately reserved cloud escalation path is the canonical V1 model architecture.

**Rationale:** 4B handles the majority of workload at local cost/latency; cloud spend is reserved for workloads that materially benefit; 9B neither adds enough capability for its memory/thermal cost on M4 16GB to be a required runtime, nor is it needed as a fallback (4B→DeepSeek escalation chain covers degradation). Historical consideration of 9B is preserved for accuracy.

**Consequences:**

- Routing tables/fallback chains updated repo-wide (plan §10, ADR-004, AI_ARCHITECTURE §2).
- Setup/docs updated so a fresh environment does not download 9B (DEPLOYMENT §4, catalog §6 baseline).
- Evals/judge options updated (ADR-009: local judge = 4B, not 9B).
- Local verification baseline at Phase 4 (catalog §6): `pramya-4b` discoverable/loads, thinking off, normal + structured JSON generation, alias works, no 9B dependency.
- Only changeable via a new ADR + verified evidence (spec §7/§15 protocol).

## ADR-021 — Knowledge Layer: Deterministic Ingestion + Retrieval (LlamaIndex not required)

**Status:** Superseded — deterministic layer remains as the fallback/reference path; LlamaIndex is now the production ingestion/retrieval layer (realignment directive 2026-08, `app/knowledge/rag/service.py`).
**Date:** 2026-08

**Decision:** Phase 2.2/2.3 implement the knowledge layer with deterministic
components owned by the application — `app/knowledge/chunking.py` (greedy
paragraph packing, chunk_size/overlap), `app/knowledge/ingestion.py`
(chunk → embed via InferenceRouter → pgvector write with explicit dedup),
`app/knowledge/retrieval.py` (pgvector cosine + PostgreSQL FTS + RRF k=60 +
Qwen3-Reranker via InferenceRouter) — instead of a LlamaIndex
`IngestionPipeline` dependency. ADR-003's boundary intent is preserved:
the knowledge layer owns ingestion/retrieval and never workflow state.

**Context:** Plan §12/ADR-003 named LlamaIndex for ingestion. Project
principles (deterministic-first, no unnecessary dependencies, router-only
model access) and verified LlamaIndex behavior (IngestionPipeline does NOT
dedupe against the vector store — run-llama#17871; embedding would call
oMLX directly, bypassing the InferenceRouter boundary) point to a smaller
equivalent.

**Rationale:** The required pipeline (parse → chunk → metadata → embed →
pgvector → dedup → hybrid retrieval → rerank → context → LLM) is fully
implemented; only the framework is omitted. Every model call goes through
the InferenceRouter (ADR-004 boundary). LlamaIndex remains a documented
swap target behind the same service interfaces.

**Consequences:** No LlamaIndex/langchain dependency in pyproject; dedup by
content-hash on the immutable `document` row + replace-on-reindex (Phase 2.2
idempotency test); retrieval degradation explicit (embedding down → FTS-only;
rerank down → RRF order) and observable.

## ADR-022 — Interview Engine: Deterministic Service State Machine (LangGraph not required)

**Status:** Superseded — the interview lifecycle now executes a real LangGraph StateGraph (realignment directive 2026-08, `app/interview/workflow.py`) while InterviewService stays the domain/invariant layer. (implementation decision)
**Date:** 2026-08

**Decision:** Phase 3 implements the interview engine as a deterministic,
DB-backed service state machine (`app/interview/state.py` transition table,
`app/interview/service.py` lifecycle, `app/interview/generation.py`
question/eval/hint generation) with SSE event streaming — not a LangGraph
graph + Postgres checkpointer. Plan §7's own design rule ("State transitions
for interview_session: enforced in the interview service, mirrored in
LangGraph thread") makes the service authoritative; the DB rows (session
status, turns, questions, answers, evaluations) provide durability.

**Context:** ADR-002/plan §13 mandated LangGraph 1.2 with PostgresSaver
checkpointing and interrupt/resume. The deterministic state machine
satisfies every Phase 3 acceptance criterion (refresh survives via DB
state, idempotent answers, pause/resume/cancel, evidence extraction,
evaluation versioning) without the LangGraph dependency's API-churn risk on
an overnight build.

**Rationale:** Smallest architecture that fully satisfies V1; no second
source of truth (plan itself names the interview service as the enforcer);
deterministic-first; dependency risk register (plan §29 #4) avoided.

**Consequences:** Interview session state is authoritative in PostgreSQL;
SSE events streamed from an in-memory per-session event bus (single-process
dev runtime; state rebuildable from rows). LangGraph remains a documented
upgrade path behind the InterviewService interface.

## ADR-023 — Production Text Inference: DeepSeek Only; Local oMLX for Audio + Retrieval

Full ADR: `docs/architecture/ADR-023-deepseek-only-text-omlx-audio-retrieval.md`.

**Decision (2026-08-12):** all textual/LLM inference routes through
`deepseek-v4-flash` (sole production text provider). Local oMLX is retained
for audio (Parakeet-TDT live ASR, Qwen3-ASR primary/recorded ASR,
Qwen3-TTS) and retrieval (BGE-M3 embeddings, Qwen3-Reranker-0.6B). Local
text-generation models (pramya-4b / qwen3.5-4b / qwen2.5-coder-7b) are
prohibited in the production inference path; text tasks have no fallback
chain (a DeepSeek failure is a controlled provider error/retry path, never a
silent local text fallback). Thinking defaults off; reasoning is requested
deliberately per operation.

**Context:** local text model load/unload churn on a 16 GB M4 caused severe
memory pressure and user-visible lag during voice sessions. A single remote
text provider gives deterministic cost, predictable latency, and zero local
text memory. The provider abstraction (InferenceRouter → provider contracts →
DeepSeekProvider/MLXProvider) is unchanged; future text providers implement
the same interface. Supersedes the local-text-LLM-first interpretation of
ADR-004/ADR-011/ADR-013/ADR-020 for text routing.

**Consequences:** `LLM_PROVIDER=deepseek`, `VOICE_PROVIDER=omlx`;
`OMLX_ASR_MODEL=Qwen3-ASR-1.7B-4bit` (primary) with
`OMLX_ASR_OPTIONAL_MODEL=parakeet-tdt-0.6b-v3`; task policy table maps every
text task to `deepseek-v4-flash` with no fallback; `/models/status` reports
provider roles (text LLM vs audio + retrieval); model catalog rewritten
(§0/§1/§2.1). No L1/L2 inference cache exists yet — any future cache key must
include provider/model so old local-model entries cannot masquerade as
DeepSeek results.
