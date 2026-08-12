# Pramya — Master Implementation Plan

> **Authoritative execution plan.**
> This document is the project's persistent source of truth for intent.
> The repository is the source of truth for actual state.
> Read it at the start of every session (Continuation Protocol, §46 of the spec).
> Last updated: 2026-08 (planning session).

---

## 0. How to Use This Document

Every future Pi session must:

1. Read this file (progress tracker in §35 is the entry point).
2. Read `docs/DECISIONS.md` and relevant ADRs in `docs/architecture/`.
3. Read `docs/MODEL_CATALOG.md` before touching any model code.
4. Inspect `git status` + recent commits.
5. Run relevant tests.
6. Identify current phase/task from §35.
7. Read the relevant implementation files.
8. Determine whether reality matches the plan; if it diverges, investigate, decide, update this file, continue.
9. Never assume previous context exists.

Source-of-truth hierarchy (spec): repository implementation → tests/evals → explicit user decisions → accepted ADRs → this plan → `docs/PROJECT_MEMORY.md`.

---

## 1. Product Vision

Pramya — **prove you're ready.**

An adaptive, evidence-driven interview preparation and assessment platform for technical and professional roles.

Pramya is NOT a chatbot, not a question generator, not an AI-interviewer wrapper, not AI-Engineer-only. It is a system that:

- builds an evidence model of the candidate (claims, observations, demonstrated ability),
- derives a role/competency model from the target JD,
- identifies gaps and generates a preparation plan,
- conducts adaptive assessments (text + voice),
- evaluates answers against evidence with confidence,
- updates the candidate model and readiness after every completed assessment,
- remembers across sessions and produces longitudinal progress,
- recommends the next highest-value practice.

Central loop:

```
Resume + JD → Candidate Intelligence + Role Intelligence → Competency Model
→ Gap Analysis → Preparation Plan → Practice/Assessment → Answer/Performance
→ Evidence Extraction → Evaluation → Candidate Model Update → Readiness Update
→ Next Highest-Value Practice
```

---

## 2. Product Principles

1. **Evidence-first.** Every important score has observable reasons. Never "LLM → 8/10" without evidence, confidence, strengths, weaknesses, missing evidence, hints used, evaluation version.
2. **Deterministic where possible.** Readiness aggregation, prioritization, scoring aggregation, and progress are deterministic application logic. LLMs provide semantic judgments; the application owns aggregation.
3. **Not a ChatGPT wrapper.** The product owns Candidate Model, Role Model, Competency Model, Evidence Ledger, Readiness Model, Preparation Queue, Historical Model.
4. **Voice is first-class.** Interruption/cancellation are correctness requirements. No stale TTS after interrupt.
5. **Local-first.** Minimize expensive cloud inference; route cheap/high-frequency work to local models via oMLX/MLX.
6. **Model-agnostic architecture.** Providers behind an InferenceRouter; nothing hard-codes DeepSeek/Qwen/NVIDIA behavior into business logic.
7. **Calm, professional, trustworthy UI.** No gimmicks, no fake confidence, no meaningless percentages.
8. **Treat AI output as untrusted data.** Structured proposal → validation → application logic → persistence.
9. **Small coherent integrations.** Every framework has a documented responsibility; removing one must not require rewriting unrelated domain logic.
10. **Respect the M4 16GB target.** Lazy loading, resource-aware lifecycle, bounded concurrency, no model zoo.
11. **Free/open-source-first infrastructure.** V1 framework/infrastructure selection must prefer the strongest viable free/open-source/self-hosted option. Hosted paid services require explicit architectural approval and must not enter the dependency graph implicitly.

---

## 3. User Personas

| Persona | Goals | Needs |
|---|---|---|
| **Alex — Senior SWE switching roles** | Prove readiness for a specific JD; avoid wasting interviews | JD analysis, resume deep dive, adaptive technical interviews, evidence-backed feedback, targeted practice |
| **Priya — Career switcher / student** | Build confidence and fundamentals from scratch | Competency map, progressive practice, story bank, structured feedback, progress visibility |
| **Dev — New grad** | Interview reps across formats | Mock interviews (technical/behavioral), hints, system-design practice, report |
| **Contributor / AI engineer** | Inspect, extend, evaluate Pramya | Clean architecture, ADRs, eval suite, runnable demo, documented model routing |

---

## 4. Core User Journeys

**Onboarding + Setup (first use, < 5 min):**
Create profile → upload resume (PDF/DOCX/TXT/MD) → paste JD → (optional) add profile notes → Pramya builds candidate evidence + role model → preparation map presented.

**Preparation map → practice:**
Map shows role, readiness %, top gaps (ranked by value), today's practice queue (competency, priority, est. time, reason, assessment type, expected improvement). Start practice → assessment (technical/behavioral/deep-dive/mock) → hints available → answer → evidence-backed evaluation → readiness update → next item.

**Live interview (text or voice):**
Set up interview (type, duration, focus areas) → interviewer asks adaptive question → candidate answers (typing or speaking) → live transcript → evaluation → adaptive follow-up → interruption/pause/resume/stop all work → completion → report.

**Return visit:**
Dashboard shows where am I / what to improve / what next / progress trend (Session 1 → 2 → 3…). Interview memory adapts new interviews to previous weaknesses.

**Debrief:** After a real interview, record company/role/round/questions/feedback/result; Pramya folds this into future recommendations.

---

## 5. Functional Requirements (V1)

1. Candidate profile creation + management.
2. Resume upload (PDF, DOCX, TXT, MD; size + type limits; untrusted-input handling) and structured extraction (experience, roles, companies, technologies, projects, achievements, claims, certifications, seniority indicators, strengths/gaps).
3. JD input + role analysis (required/preferred/implied skills, responsibilities, seniority, competency importance).
4. Candidate evidence profile (claimed vs observed vs demonstrated vs inferred vs unknown) with user correction.
5. Competency graph per target role (not hard-coded per role).
6. Gap analysis → preparation plan.
7. Interview modes: General Mock, Resume Deep Dive, JD Interview, Technical, Behavioral, Project Deep Dive, System Design (text), Coding/Technical Reasoning (verbal, no sandbox).
8. Adaptive questioning: next question depends on target competency, evidence, confidence, difficulty, seniority, previous answer, hints used, time budget, prep objective.
9. Progressive hints (nudge → direction → partial reasoning → worked approach); hints affect evaluation.
10. Evidence extraction from every answer; evaluation with dimensions (correctness, depth, clarity, structure, relevance, evidence, communication, tradeoff awareness, reasoning, specificity, seniority/role alignment, completeness, hallucination risk).
11. Deterministic readiness model (overall, per-competency, critical gaps, confidence, evidence coverage; knowledge-confidence vs demonstrated-ability separation).
12. Preparation queue (today's practice) with priority reasons.
13. Story bank: Situation/Task/Action/Result/Metrics/Conflict/Learning/Strength, mapped to competencies, with freshness/usage/coverage/strength/confidence tracking.
14. Progress tracking across sessions (trends, strengths, weaknesses, recurring issues, recommended practice).
15. Interview memory: longitudinal pattern identification.
16. Real-interview debrief ingestion.
17. Transcript analysis (pasted TXT/MD) → questions/answers/follow-ups/weaknesses.
18. Voice interviewing: mic capture, streaming ASR with partial transcripts, turn detection, interruption, stop/pause/resume/replay, streamed TTS, transcript sync, state preservation.
19. Communication analysis: answer duration, pauses, filler words, repeated phrases, verbosity, structure, response latency, hedging (measured characteristics only — no personality/deception claims).
20. Demo mode: synthetic candidate + role (Senior Full Stack Engineer) to evaluate without personal data.
21. Model/runtime status screen; provider/model routing visibility for debugging.
22. History: past interviews, transcripts, evaluations, reports.
23. Local-first / hybrid / cloud modes (configurable).
24. MCP server exposing a bounded read-oriented surface (candidate profile, evidence search, role requirements, interview/practice history).

**V1 must NOT include:** video, executable coding sandbox, whiteboard canvas, anti-cheating, browser monitoring, recruiter platform, enterprise teams, payments, mobile apps, LinkedIn integration/scraping.

---

## 6. Non-Functional Requirements

- **Performance targets** (thresholds finalized during implementation, then documented): voice time-to-first-transcript and time-to-first-audio as low as the local stack allows; immediate interruption (<~100ms perceived); no stale playback; bounded backend latency; controlled concurrency; predictable memory on M4 16GB; no sustained uncontrolled thermal load.
- **Reliability:** explicit retry/timeout/idempotency policy (§24 of spec); graceful degradation for every AI failure (DeepSeek down → local; TTS down → text; ASR down → manual transcript mode; retrieval down → degraded interview mode). Never a bare "Something went wrong."
- **Security:** secrets never committed/logged; candidate data treated as sensitive; upload validation; prompt-injection defenses; LLM output never mutates privileged state directly; PII not logged; observability uses IDs + redacted metadata.
- **Privacy:** data ownership, deletion (session/audio/transcript), configurable retention, no audio stored by default, local-only mode practical, privacy documentation.
- **Observability:** request_id/session_id/turn_id/graph_node/model/provider/latency/tokens/cache_hit/retrieval_count/ASR+TTS latency/time-to-first-audio/interruption_count/error/fallback.
- **Testability:** unit + integration + contract + E2E + AI evals; CI green on main.
- **Maintainability:** typed, small modules, explicit interfaces, Pydantic schemas, dependency injection where useful, no 500-line agent files, no magic strings, no untyped dicts for important state.
- **Portability:** Docker Compose for Postgres/pgvector (+ optional Redis/Langfuse); fresh-clone quickstart must work; demo dataset included.

---

## 7. Domain Model (Minimum Viable)

Tables (PostgreSQL). All ownership = `user_id`. Soft-delete or hard-delete per privacy policy (hard delete on user request).

| Entity | Key fields | Notes |
|---|---|---|
| `user` | id, email (optional), display_name, created_at | Auth optional in V1 (deployment-dependent); single-user default |
| `candidate_profile` | id, user_id, seniority_target, headline, timezone | one per user in V1 |
| `document` | id, user_id, kind (resume/jd/debrief/transcript), filename, mime, size, content_hash, storage_key, status (pending/parsing/parsed/failed), parsed_at | immutable content; re-upload = new doc |
| `document_chunk` | id, document_id, chunk_index, content, embedding vector(1024), metadata jsonb, fts tsvector | pgvector store; HNSW index |
| `role` | id, user_id, source_document_id, title, seniority, summary | analyzed JD |
| `competency` | id, role_id, name, category (frontend/backend/architecture/behavioral/domain…), level, importance (required/preferred/nice), weight | competency graph nodes |
| `candidate_competency` | id, candidate_profile_id, competency_id, score, confidence, evidence_coverage, demonstrated_level, updated_at | derived, deterministic + LLM inputs |
| `evidence` | id, user_id, source_kind (resume/jd/answer/debrief/correction/observation), source_ref, claim, status (claimed/observed/demonstrated/inferred/unknown), competency_id, strength, notes | the evidence ledger |
| `interview_session` | id, user_id, candidate_profile_id, role_id, kind, status (created/planning/questioning/paused/interrupted/completed/cancelled/error), started_at, ended_at, config jsonb, graph_thread_id | durable LangGraph thread |
| `interview_turn` | id, interview_session_id, seq, kind (question/answer/feedback), content, transcript, hints_used int, started_at, ended_at | |
| `audio_segment` | id, interview_session_id, turn_id, kind (input/output), storage_key, duration_ms, retention_until | stored only if user opts in |
| `transcript_segment` | id, interview_session_id, turn_id, seq, partial bool, text, timestamps | |
| `question` | id, interview_session_id, turn_id, competency_id, difficulty, type, text, hint_levels jsonb, rationale | |
| `answer` | id, question_id, interview_turn_id, text, mode (text/voice), raw_audio_ref | |
| `evaluation` | id, answer_id, dimensions jsonb, overall, confidence, strengths jsonb, weaknesses jsonb, evidence_refs jsonb, missing_evidence jsonb, hints_used, follow_ups jsonb, evaluator_version, created_at | immutable once written |
| `preparation_item` | id, user_id, competency_id, priority, estimated_minutes, reason, assessment_type, expected_improvement, status (open/done/dismissed) | the preparation queue |
| `practice_session` | id, user_id, preparation_item_id, kind, started_at, completed_at, outcome | |
| `story` | id, user_id, situation, task, action, result, metrics, conflict, learning, strength, competency_ids, freshness, usage_count, coverage, confidence | story bank |
| `readiness_snapshot` | id, user_id, role_id, overall, per_competency jsonb, confidence, evidence_coverage, critical_gaps jsonb, created_at | immutable append-only |
| `interview_debrief` | id, user_id, company, role, round, questions jsonb, feedback, result, analysis jsonb, created_at | |
| `evaluation_version` | id, name, version, prompt_hash, model_policy, created_at | prompt/evaluator registry |

**Design rules:**
- Append-only: `evaluation`, `readiness_snapshot`, `evidence` (with status transitions) — history is a feature.
- Versioned: every evaluation references `evaluation_version`.
- Immutable: `document` content.
- State transitions for `interview_session`: created → planning → questioning ⇄ paused/interrupted → completed | cancelled | error_recovery. Enforced in the interview service, mirrored in LangGraph thread.
- Audit: user data deletion cascades; retention policy on audio/transcripts.

---

## 8. Architecture

Modular monolith. One FastAPI app; clear package boundaries; no microservices.

```
┌───────────────────────────────────────────────┐
│  React 19 + TypeScript (Vite)                 │
│  Dashboard · Setup · Preparation Map ·        │
│  Live Interview · Transcript · Evaluation ·   │
│  Progress · Stories · Settings · Model Status │
└───────────────┬───────────────────────────────┘
                │ REST /api/v1 + SSE /events + WS /ws/voice
┌───────────────▼───────────────────────────────┐
│  FastAPI application layer                    │
│  routers → services (candidate, document,     │
│  role, interview, evaluation, preparation,    │
│  readiness, story, debrief, transcript,       │
│  progress, demo)                              │
└───────┬──────────────┬──────────────┬─────────┘
        │              │              │
┌───────▼───────┐ ┌────▼───────┐ ┌────▼─────────┐
│ Interview     │ │ Evidence / │ │ Voice        │
│ Engine        │ │ Retrieval  │ │ Engine       │
│ (LangGraph    │ │ Engine     │ │ (audio state │
│  state graph) │ │ (LlamaIndex│ │  machine,    │
│               │ │ + pgvector)│ │  ASR/TTS)    │
└───────┬───────┘ └────┬───────┘ └────┬─────────┘
        └──────────────┼──────────────┘
              ┌────────▼────────┐
              │ InferenceRouter │  task → policy → provider → model
              └───┬───────┬─────┘
        ┌─────────┴──┐  ┌─▼───────────────┐
        │ DeepSeek   │  │ oMLX (local)    │
        │ Provider   │  │ chat · embed ·  │
        │ (OpenAI-   │  │ rerank · STT ·  │
        │  compat)   │  │ TTS · MLX models│
        └────────────┘  └─────────────────┘
              ┌────────▼────────┐
              │ Persistence     │ PostgreSQL + pgvector
              └────────┬────────┘
              ┌────────▼────────┐
              │ Observability   │ Langfuse (+ structured logs)
              └─────────────────┘
   MCP server (bounded read surface) — separate process, same services
```

**Package layout (backend, `backend/app`):**

```
backend/app/
  main.py                      # FastAPI app, lifespan, routers
  core/                        # config, security, logging, db, deps
  api/v1/                      # routers (candidates, documents, roles,
                               #  interviews, preparation, stories,
                               #  debriefs, transcripts, demo, models)
  domain/                      # Pydantic schemas, state enums, errors
  models/                      # SQLAlchemy ORM models
  services/                    # candidate, document, role, evidence,
                               #  readiness, preparation, story, progress,
                               #  debrief, demo
  interview/                   # LangGraph graph: state.py, nodes.py,
                               #  workflow.py, checkpointer.py
  knowledge/                   # LlamaIndex ingestion + retrieval,
                               #  vector store, hybrid search, rerank
  ai/                          # InferenceRouter, providers (deepseek,
                               #  omlx), task_policies, structured outputs
  voice/                       # ASR, TTS, audio state machine, WS session
  mcp_server/                  # Pramya MCP server (separate entrypoint)
  observability/               # langfuse setup, structured logging,
                               #  redaction
  tests/                       # unit/ integration/ contract/ e2e/ evals/
  alembic/                     # migrations
```

**Frontend layout (`frontend/`):** Vite + React 19 + TS strict; TanStack Query (server state), Zustand (client/UI state), react-router; feature folders (`dashboard`, `setup`, `preparation`, `interview`, `voice`, `progress`, `stories`, `settings`, `model-status`); SSE client hook; WebSocket voice client (AudioWorklet); shared UI kit (accessible, responsive, loading/error states).

---

## 9. Framework Boundaries (summary — see ADR-001, ADR-002, ADR-003)

| Technology | Responsibility | Boundary rule |
|---|---|---|
| React 19 + TS | Product UI | All AI streaming via dedicated hooks; no AI logic in components |
| FastAPI 0.139 | API layer, orchestration, SSE/WS | Thin routers; logic in services |
| LangGraph 1.2 | Stateful interview orchestration, checkpoints, interrupts, resume | Interview workflow ONLY; nothing else depends on it |
| LangChain 1.x | Model abstraction, structured output, tools, prompts, middleware | Under the workflow layer; no LangChain in domain logic |
| LlamaIndex 0.14 | Document ingestion, indexing, retrieval pipeline | Knowledge layer only; never owns workflow state |
| BGE-M3 | Embeddings | via oMLX `/v1/embeddings` (MLX); 1024-dim |
| Qwen3-Reranker-0.6B | Reranking | via oMLX `/v1/rerank` |
| deepseek-v4-flash | ALL text/LLM inference (sole production text provider) | via DeepSeek API; thinking off by default, on where deliberately requested |
| Qwen3.5-4B (`pramya-4b`) | PROHIBITED in production text path (ADR-023); provider-construction compat only | via oMLX `/v1/chat/completions` (never routed) |
| Parakeet-TDT-0.6B-v3 | Live ASR | local (parakeet-mlx or oMLX STT); chunked streaming |
| Qwen3-ASR-1.7B | Recorded/archival ASR | local; offline reprocessing |
| Qwen3-TTS-0.6B | Interviewer voice | local; streaming via mlx-audio or oMLX TTS |
| MLX / oMLX | Apple Silicon local inference | behind providers; never in business logic |
| PostgreSQL | Durable application state | authoritative V1 DB; SQLite only for tests if justified |
| pgvector 0.8 | Vector persistence/retrieval | hybrid search (vector + FTS + RRF) |
| Redis | Only if justified (rate limiting, coordination, cache) | Decision deferred until Phase 10/11 measurement |
| Langfuse OSS (self-hosted, MIT) | LLM observability, traces, cost | Python SDK `@observe`; no candidate PII; Cloud/Enterprise not V1 deps |
| DeepEval 4.1 | AI evaluation suite | golden datasets + CI; judge = deepseek-v4-flash (not cloud gpt by default) |
| Docker | Dev + deployment | Compose: postgres+pgvector, backend, frontend, (langfuse OSS optional profile) |
| GitHub Actions | CI/CD | lint, typecheck, unit, integration, contract, e2e, evals, build |

---

## 10. AI Architecture

- **InferenceRouter**: task → task policy → provider → model. Observable: task, selected provider/model, reason, latency, tokens, errors, fallback, cache hit/miss, cost (cloud).
- **Canonical model roles (finalized 2026-08, ADR-023):** deepseek-v4-flash is the ONLY production text LLM — every text task routes to it (thinking off by default; reasoning deliberately requested where justified). Local oMLX is retained for AUDIO (Parakeet-TDT live ASR, Qwen3-ASR primary/recorded ASR, Qwen3-TTS) and RETRIEVAL (BGE-M3 embeddings, Qwen3-Reranker-0.6B). Local text-generation models (pramya-4b / qwen3.5-4b / qwen2.5-coder-7b) are PROHIBITED in the production path; Qwen3.5-9B is DEFERRED (not required, not a fallback, not a routing target). Architecture principle: **TEXT → DeepSeek; AUDIO → local oMLX; RETRIEVAL → local oMLX.**
- **Providers**: `DeepSeekProvider` (httpx, OpenAI-compatible, base_url `https://api.deepseek.com`, model `deepseek-v4-flash`, thinking emitted as `thinking: {type}` in the JSON body, JSON output, tool calls), `MLXProvider` (oMLX OpenAI-compatible endpoints for embed/rerank; audio via `app/voice` calling `/v1/audio/*`), future providers plug in behind `generate()/embed()/rerank()/transcribe()/synthesize()` capabilities.
- **Structured output**: Pydantic schemas; JSON-schema response_format where supported; validation + retry-with-feedback loop on schema failure; never trust raw LLM output.
- **Prompt management**: `prompts/` tree (role_analysis/, candidate_analysis/, question_generation/, answer_evaluation/, evidence_extraction/, follow_up/, report_generation/, transcript_analysis/, debrief_analysis/, system_design/, story_analysis/); every prompt versioned; `evaluation_version` records prompt_hash + model policy.
- **Prompt injection defenses**: strict separation of SYSTEM INSTRUCTIONS / USER DATA / DOCUMENT DATA / RETRIEVED EVIDENCE / MODEL OUTPUT with delimiters; document content never becomes privileged instructions; output validation gates state changes.
- **Cost control**: prompt minimization, context selection via retrieval (never whole profile), deterministic preprocessing, response caching where safe, local routing, request dedup, token/cost telemetry.
- **Task policies (initial)** — see ADR-004:

| Task class | Default model | Thinking mode |
|---|---|---|
| ALL text tasks: routine generation, extraction, classification, metadata, structured generation, semantic tasks, interview content generation, ordinary/deep evaluation, analysis, complex/adaptive reasoning, system design, final synthesis, difficult follow-ups | deepseek-v4-flash (sole text provider) | off by default; on where deliberately requested (deep eval, adaptive reasoning, system design) |
| Embeddings | BGE-M3 (local oMLX) | — |
| Reranking | Qwen3-Reranker-0.6B (local oMLX) | — |
| Live ASR | Parakeet-TDT-0.6B-v3 (local oMLX) | — |
| Recorded/primary ASR | Qwen3-ASR-1.7B (local oMLX) | — |
| TTS | Qwen3-TTS-0.6B (local oMLX) | — |

Routing decision flow: task-class policy — every text task → deepseek-v4-flash
(no fallback chain; a DeepSeek failure is a controlled provider error/retry
path, never a silent local text fallback). TEXT → DeepSeek; AUDIO → local
oMLX; RETRIEVAL → local oMLX.

Fallbacks (ADR-023): DeepSeek failure is a controlled provider error/retry — there is NO silent local-text fallback. Voice degrades: TTS down → text interviewer response; ASR down → manual/typed transcript. Retrieval failure → continue without context (logged). Mode selection observable in telemetry.

---

## 11. Model Routing (see §10, ADR-004, docs/MODEL_CATALOG.md)

Routing decision recorded as structured log event per call. Health checks per provider; runtime capability detection; graceful fallback chain per task class. No indiscriminate cloud calls.

---

## 12. RAG / Retrieval Architecture (see ADR-003, ADR-007, ADR-014, docs/ai/RETRIEVAL_ARCHITECTURE.md)

- **Ingestion** (LlamaIndex `IngestionPipeline`): documents → parsing (PDF/DOCX via pypdf/python-docx/markdown-it; untrusted-input guards) → chunking (text-splitters) → metadata → embed (BGE-M3 via oMLX, 1024-dim) → write to pgvector (document_chunks + vector index). Persistent docstore tracking to avoid re-indexing duplicates (known LlamaIndex 0.14 gotcha: `IngestionPipeline` does NOT dedupe against the vector store).
- **Retrieval pipeline**: query → BGE-M3 embedding → hybrid search (pgvector cosine + PostgreSQL FTS, RRF fusion) → Qwen3-Reranker-0.6B → top-K evidence selection → LLM. Never dump the whole profile into context.
- **Collections/namespaces**: resume-evidence, jd-requirements, interview-history, competency-library, story-library.
- **Capabilities used by**: evidence extraction, question generation context, follow-up selection, report generation, debrief/transcript analysis.
- LLM used only where embedding/retrieval insufficient.

---

## 13. LangGraph Design (see ADR-002, docs/ai/AI_ARCHITECTURE.md)

**Interview graph** (typed `StateGraph`, mandatory `state_schema`), nodes:

```
SESSION_INITIALIZING → PROFILE_LOADING → INTERVIEW_PLANNING → QUESTIONING
  → LISTENING (interrupt for user turn) → EVALUATING → FOLLOW_UP_DECISION
  → QUESTION_GENERATION → INTERVIEWER_RESPONSE → QUESTIONING …
  → COMPLETED | CANCELLED | ERROR_RECOVERY
```

Additional states: PAUSED, INTERRUPTED.

- **Checkpointing**: `langgraph-checkpoint-postgres` (PostgresSaver) with `thread_id = interview_session.id`; durability config; sessions survive browser refresh/process restart.
- **Interrupt/resume**: `interrupt()` + `Command(resume=...)` for user-turn boundaries (waiting for answer). Resume from correct node; no duplicated questions/evaluations (idempotency keys per turn).
- **Streaming**: LangGraph streaming events (v2 StreamPart/GraphOutput where appropriate) surfaced to the API layer as SSE events (graph_node, question, evaluation chunks, follow-up).
- **Timeouts**: per-node `TimeoutPolicy`; node error handlers for Saga/compensation (mark turn failed, offer retry, never corrupt session state).
- Graph state schema (typed, Pydantic): session_id, candidate_summary, role_model, competency_focus, turn_history, current_question, answer, hints_used, evaluation, evidence_refs, remaining_time, status, error.
- Tests: state init, route selection, checkpoint recovery, interrupt/resume, malformed-eval recovery, duplicate-answer idempotency, error_recovery transitions.

---

## 14. MCP Design (see ADR-006)

- **Boundary rule**: MCP is an interoperability boundary for external MCP clients, NOT the internal architecture. Application services never route through MCP.
- **Server**: standalone process (`backend/app/mcp_server/`) exposing bounded, read-oriented surface:
  - Tools: `get_candidate_profile`, `search_evidence`, `get_role_requirements`, `get_interview_history`, `get_practice_history`.
  - Resources: `candidate://{id}/profile`, `candidate://{id}/role`, `candidate://{id}/preparation-plan`.
- **Genuine external use case**: an external agent/LLM client can ask "what are Alex's demonstrated weaknesses?" without app UI; and our own eval harness drives the MCP server for contract tests.
- **Implementation**: official `mcp` SDK (v2, `MCPServer`) or pinned `mcp>=1.28,<2` if v2 protocol churn is a risk at implementation time — decision re-verified during Phase 11; transport streamable-http. Contract tests for every tool/resource.
- No write tools in V1 (read-only surface); no candidate content in tool descriptions beyond IDs/refs.

---

## 15. API Design (versioned; OpenAPI generated)

```
POST /api/v1/candidates
GET  /api/v1/candidates/{id}
POST /api/v1/documents                 (multipart; resume/JD/debrief/transcript)
GET  /api/v1/documents/{id}
POST /api/v1/roles/analyze             (JD → role model)
GET  /api/v1/roles/{id}
GET  /api/v1/candidates/{id}/evidence
PATCH /api/v1/candidates/{id}/evidence/{evidence_id}   (user corrections)
GET  /api/v1/preparation
POST /api/v1/interviews                (kind, role_id, duration, focus, mode)
GET  /api/v1/interviews/{id}
POST /api/v1/interviews/{id}/answers   (text; idempotency-key)
POST /api/v1/interviews/{id}/hint
POST /api/v1/interviews/{id}/pause | /resume | /stop | /cancel
GET  /api/v1/interviews/{id}/events    (SSE)
GET  /api/v1/interviews/{id}/report
GET  /api/v1/practice/next
POST /api/v1/practice/{id}/complete
GET  /api/v1/stories / POST /api/v1/stories / PATCH /api/v1/stories/{id}
GET  /api/v1/progress
POST /api/v1/debriefs
POST /api/v1/transcripts/analyze
GET  /api/v1/models/status             (routing + provider health)
POST /api/v1/demo/setup                (demo candidate + role + interview)
```

Every endpoint: Pydantic request/response models, validation, idempotency keys on answer submission, error codes with actionable messages, rate limiting at app layer.

---

## 16. Streaming / WebSocket Contracts (see docs/ai/VOICE_ARCHITECTURE.md)

- **Text/interview events**: SSE from `GET /interviews/{id}/events` — typed events: `session_status`, `graph_node`, `question`, `hint_available`, `partial_transcript`, `final_transcript`, `evaluation`, `evidence`, `follow_up`, `readiness_update`, `error`. NDJSON-style `data:` payloads.
- **Voice**: WebSocket `/ws/voice/{interview_id}` — client → server: audio chunks (PCM16 @16kHz) + control messages (`start_turn`, `end_turn`, `interrupt`, `pause`, `resume`, `stop`, `replay`); server → client: `partial_transcript`, `final_transcript`, `audio_chunk` (PCM @24kHz TTS), `tts_start`, `tts_stop`, `state` transitions, `error`. Binary audio frames over the same socket.
- **Cancellation**: `interrupt` clears TTS buffer server-side AND client-side (AudioWorklet buffer clear); in-flight LLM generation cancelled via task cancellation; stale audio never plays after interrupt.
- Auth: deployment-dependent; cookie/header on HTTP; token query param for WS.

---

## 17. Database Design (see ADR-007, §7)

- PostgreSQL 17 (Docker `pgvector/pgvector:pg17`), extension `vector`; pgvector 0.8 features (HNSW, `halfvec` optional, `sparsevec` optional).
- HNSW index on embeddings (`vector_cosine_ops`, m=16, ef_construction=64, tune `hnsw.ef_search` per query); GIN on FTS.
- Hybrid search: vector + `plainto_tsquery` FTS + RRF (k=60), top-k ×3 fetch.
- SQLAlchemy 2.0 async (asyncpg) + Alembic migrations. `CREATE EXTENSION vector` in first migration.
- Dimension locked at 1024 (BGE-M3) from day one.
- Indexing strategy: all lookups by user_id; interview session by id + user; turns by session+seq.

---

## 18. Frontend Architecture (see §8, §16)

- React 19, TypeScript strict, Vite 8, TanStack Query v5, Zustand, react-router.
- Screens: Dashboard ("where am I / what to improve / what next / how progressing"), Candidate Setup, Role/JD Setup, Preparation Map, Practice, Live Interview (flagship: interviewer voice state, live transcript, controls Pause/Interrupt/Stop/Replay), Interview Report, Progress, Stories, Settings, Model/Runtime Status.
- Voice client: `navigator.mediaDevices` → AudioContext + AudioWorklet capture; VAD-ish turn detection client-side (energy-based) with server-assisted endpoints; playback via AudioWorklet buffer with immediate clear on interrupt; full resource cleanup on unmount.
- SSE hook (fetch + ReadableStream, AbortController, buffered line parsing, rAF batching); WS hook with heartbeat/reconnect/backoff.
- Accessibility: aria-live on transcripts, keyboard controls, focus management; loading/error/empty states everywhere; responsive.
- Not a ChatGPT look: dashboard communicates evidence and next steps; calm professional design; no avatars/gimmicks.

---

## 19. Security Model (see ADR-010, docs/operations/DEPLOYMENT.md)

- Uploads: allowed types (pdf, docx, txt, md), size limit (e.g., 5MB), content-hash, parse in isolated worker with timeouts; reject archives/scripts.
- Prompt injection: system/user/document/evidence separation; delimiters; validation of extracted claims as data (never instructions); structured-output gate for any persistence.
- API: rate limiting; validation; CORS policy; secure headers; optional auth if deployment requires (must not threaten 30-day scope).
- Secrets: `.env` only, never committed; `.env.example` documented; no key material in logs/traces.
- Data: candidate content treated as sensitive; observability uses IDs + redacted metadata; PII scrubbers on error messages; retention policy; deletion endpoints.
- LLM output: structured proposal → validation (Pydantic + business rules) → application logic → persistence. Never direct mutation.
- Dependencies: pinned, `pip-audit`/`npm audit` in CI.

---

## 20. Observability (see ADR-008)

- Langfuse OSS v4 (self-hosted, MIT-licensed; optional Compose profile; Python SDK `@observe`; Cloud/Enterprise not V1 deps); traces: interview → LangGraph run → question gen, retrieval, evaluation, evidence extraction, tool calls.
- Structured JSON logs (request_id, session_id, turn_id, graph_node, model, provider, latency, tokens, cache_hit, retrieval_count, reranker_count, ASR latency, TTS latency, TTFA, interruption_count, error, fallback).
- No raw resume/answer content in traces; content-length + IDs + redacted snippets only.
- Routing events always logged (task, provider, model, reason).
- Health/metrics endpoints for providers and DB.

---

## 21. Evaluation Strategy (see ADR-009, docs/ai/EVALUATION.md)

- **Golden datasets** (deterministic fixtures) for: role analysis, candidate extraction, question generation, answer evaluation, evidence extraction, adaptive routing, RAG grounding, final report, transcript analysis, debrief analysis.
- **DeepEval 4.1** (judge = deepseek-v4-flash at temperature 0; avoid gpt default for cost/privacy) for semantic metrics: Faithfulness, AnswerRelevancy, ContextualPrecision/Recall/Relevancy; custom metrics for evidence relevance, evaluation consistency, question relevance, adaptive routing quality, hallucination risk.
- **Deterministic tests** for: structured-output validity, readiness math, prioritization, scoring aggregation, state transitions, routing table, idempotency.
- `tests/evals/` runnable via `deepeval test run` + plain pytest; CI gate.
- Regression: any prompt/evaluator version change reruns affected evals.

---

## 22. Testing Strategy

| Level | Scope | Tooling |
|---|---|---|
| Unit | domain logic, readiness calc, prioritization, validators, schemas, routing, state transitions, hint logic, idempotency | pytest |
| Integration | DB (pgvector), retrieval, LangGraph (with test checkpointer), LLM adapters (recorded fixtures + live optional), voice state machine, MCP server | pytest + testcontainers or Compose |
| Contract | API schema (OpenAPI), structured outputs, MCP tool signatures | pytest + openapi schema tests |
| E2E | onboarding → resume → JD → prep map → interview → answer → eval → evidence → report; voice: interruption/pause/resume/refresh/loss | Playwright (frontend) + API E2E |
| AI eval | golden datasets + DeepEval | deepeval |
| Voice matrix | normal/fast/slow/long/short, silence, noise, interruption, double-interruption, pause/resume/stop, refresh, network loss, ASR/TTS/LLM failures, partial/late/duplicate transcripts, stale TTS | integration + e2e scripts |

Definition of done for a task: implementation complete + tests pass + relevant evals pass + no known regression + architecture coherent + docs updated + plan updated + acceptance criteria verified.

---

## 23. Repository Structure (target)

```
README.md  CONTRIBUTING.md  SECURITY.md  PRIVACY.md  LICENSE  CHANGELOG.md
.env.example  docker-compose.yml  Makefile
backend/       # FastAPI app (layout in §8)
frontend/      # React 19 app
prompts/       # versioned prompt tree
demo/          # synthetic resumes/JDs/fixtures
docs/
  MASTER_IMPLEMENTATION_PLAN.md  PROJECT_MEMORY.md  DECISIONS.md  MODEL_CATALOG.md
  architecture/   # ADR-001..ADR-014
  ai/             # AI_ARCHITECTURE.md VOICE_ARCHITECTURE.md
                  # RETRIEVAL_ARCHITECTURE.md EVALUATION.md
  operations/     # DEPLOYMENT.md TROUBLESHOOTING.md OBSERVABILITY.md SECURITY.md
tests/           # unit/ integration/ contract/ e2e/ evals/ (backend)
frontend/src/**/__tests__/  # component/unit tests
.github/
  workflows/     # ci.yml, evals.yml, docker.yml
  ISSUE_TEMPLATE/
  pull_request_template.md
```

---

## 24. ADR Index

| ADR | Title | File | Status |
|---|---|---|---|
| ADR-001 | Framework Boundaries | `architecture/ADR-001-framework-boundaries.md` | Accepted |
| ADR-002 | LangGraph Interview Workflow | `architecture/ADR-002-langgraph-workflow.md` | Accepted |
| ADR-003 | LlamaIndex Knowledge Layer | `architecture/ADR-003-llamaindex-knowledge-layer.md` | Accepted |
| ADR-004 | Model Routing | `architecture/ADR-004-model-routing.md` | Accepted |
| ADR-005 | Evidence-First Evaluation | `architecture/ADR-005-evidence-first-evaluation.md` | Accepted |
| ADR-006 | MCP Boundary | `architecture/ADR-006-mcp-boundary.md` | Accepted |
| ADR-007 | pgvector | `architecture/ADR-007-pgvector.md` | Accepted |
| ADR-008 | Observability | `architecture/ADR-008-observability.md` | Accepted |
| ADR-009 | Evaluation | `architecture/ADR-009-evaluation.md` | Accepted |
| ADR-010 | Security and PII | `architecture/ADR-010-security-and-pii.md` | Accepted |
| ADR-011 | MLX Runtime + oMLX | `architecture/ADR-011-mlx-runtime-omlx.md` | Accepted |
| ADR-012 | Voice Model Stack (ASR/TTS) | `architecture/ADR-012-voice-models.md` | Accepted |
| ADR-013 | deepseek-v4-flash Cloud Reasoning + Thinking Policy | `architecture/ADR-013-deepseek-cloud.md` | Accepted |
| ADR-014 | Retrieval Models (BGE-M3 + Qwen3-Reranker-0.6B) | `architecture/ADR-014-retrieval-models.md` | Accepted |

Project-foundation decisions (greenfield, evidence-driven product, model-routed AI, Apple Silicon, voice-first) are recorded in `docs/DECISIONS.md`.

---

## 25. Implementation Phases

Phases are logical milestones, not equal calendar blocks. 30-day constraint applies to complete V1. Voice, interview orchestration, evidence loop are critical path.

### Phase 0 — Architecture + Scaffold (Days 1–2)
**Goal:** Repo skeleton, tooling, CI skeleton, docker-compose, domain schemas, testing harness.
**Tasks:**
- 0.1 Repo structure: backend/ frontend/ prompts/ demo/ docs/ tests/ (files per §23).
- 0.2 Backend scaffold: pyproject (uv), FastAPI app with lifespan, config from env (pydantic-settings), health endpoint, structured logging + request_id middleware.
- 0.3 Frontend scaffold: Vite + React 19 + TS strict + router + TanStack Query + Zustand + UI kit shell + CI build.
- 0.4 Docker compose: postgres+pgvector, backend, frontend; Makefile targets (up/down/test/evals/lint).
- 0.5 CI workflow: lint (ruff), typecheck (mypy/pyright), unit tests, frontend build.
- 0.6 Domain Pydantic schemas + state enums (interview/session/evidence/voice) — no DB yet.
- 0.7 Architecture docs finalized; ADRs 006–020 recorded; `.env.example` aligned to plan.
**Tests:** health endpoint; config loading; lint/typecheck green; frontend renders shell.
**Acceptance:** `make up` + `make test` green on fresh clone; CI green.

### Phase 1 — Core Domain + Persistence (Days 3–5)
**Goal:** PostgreSQL schema, ORM, migrations, repositories, base services.
**Tasks:**
- 1.1 SQLAlchemy 2.0 async models for §7 entities (vector column included).
- 1.2 Alembic init + first migration (CREATE EXTENSION vector; HNSW index).
- 1.3 Repository layer (typed, async) + transaction/unit-of-work helper.
- 1.4 Services: user/candidate/document/evidence base CRUD; deletion cascade + retention fields.
- 1.5 API routers: candidates, documents (upload validation, content-hash, status), evidence read/patch.
- 1.6 Idempotency util (answer submission keys) + error envelope.
**Tests:** migration up/down; CRUD integration (testcontainers pgvector); cascade delete; validation failures; idempotency.
**Acceptance:** DB schema matches §7; integration tests green; upload flow accepts valid types, rejects invalid.

### Phase 2 — Knowledge Layer: Ingestion + Retrieval (Days 6–8)
**Goal:** resume/JD ingestion, embedding, hybrid retrieval, reranking.
**Tasks:**
- 2.1 Document parsing (pdf/docx/txt/md) with size/type/timeout guards.
- 2.2 LlamaIndex 0.14 IngestionPipeline → chunk → metadata → BGE-M3 embed (oMLX) → pgvector write; persistent docstore dedup.
- 2.3 Hybrid search service: vector + FTS + RRF + rerank (Qwen3-Reranker via oMLX).
- 2.4 Candidate extraction pipeline: role/experience/projects/claims → evidence records (claimed status) — deepseek-v4-flash (sole text provider, ADR-023).
- 2.5 Role analysis pipeline: JD → role model + competency graph + importance — deepseek-v4-flash.
- 2.6 Evidence status model + user correction endpoint.
**Tests:** parsing fixtures; ingestion idempotency; hybrid retrieval recall checks; rerank ordering; extraction schema validity; role analysis on demo JDs.
**Acceptance:** demo resume → evidence profile; demo JD → competency graph; retrieval returns relevant evidence for competency queries.
**Note:** InferenceRouter + oMLX chat/embed provider built early here (task 2.0) — critical-path dependency for embedding.

### Phase 3 — Interview Engine: LangGraph + Text Interview (Days 8–11)
**Goal:** stateful, resumable, adaptive text interview.
**Tasks:**
- 3.1 InterviewGraph: typed state, nodes (planning, questioning, evaluating, follow-up decision, question generation, response, completion), edges + conditional routing.
- 3.2 Postgres checkpointer; thread_id = session id; durability config.
- 3.3 Question generation node (deepseek; adaptive: competency, evidence, confidence, difficulty, seniority, history, hints, time).
- 3.4 Evaluation node: answer + evidence retrieval → dimension scores + confidence + strengths/weaknesses + evidence refs + follow-up needs (deepseek; structured output).
- 3.5 Hint node (4 levels) + hints_used into evaluation.
- 3.6 Interrupt/resume: interrupt at LISTENING (user answer), Command(resume=...); pause/cancel/stop endpoints; idempotent answer handling.
- 3.7 SSE events from graph streaming.
- 3.8 Interview service + API (create/answer/hint/pause/resume/stop/report).
- 3.9 Evidence extraction from answers (claimed→observed/demonstrated transitions with provenance).
**Tests:** state init; route selection; checkpoint recovery; interrupt/resume; duplicate answer; malformed evaluation recovery; pause/resume; completion → report.
**Acceptance:** text interview survives refresh; next question chosen from evidence; evaluation persisted with version.

### Phase 4 — Model Routing + Local Inference (Days 11–13)
**Goal:** InferenceRouter + DeepSeek + oMLX providers, task policies, fallbacks.
**Tasks:**
- 4.1 InferenceRouter + capability interface (generate/embed/rerank/transcribe/synthesize).
- 4.2 DeepSeekProvider (OpenAI SDK, base_url, model id, thinking policy, JSON output, tool calls, streaming, usage/cost).
- 4.3 MLXProvider (oMLX HTTP: chat/embeddings/rerank; health + capability detection).
- 4.4 Task policy table (§10) + fallback chains; routing decision logging.
- 4.5 Model status endpoint (health, loaded models, memory).
- 4.6 Structured-output helper: Pydantic schema → JSON-schema prompt + validation + retry-feedback.
- 4.7 oMLX setup docs + Makefile target; model download pins (see MODEL_CATALOG; required set excludes 9B).
**Tests:** routing table unit tests; provider adapter tests against mocked/fixture responses; no-fallback behavior (DeepSeek failure → controlled error, no local text model); schema retry loop; no-9B-dependency + no-local-text-LLM checks.
**Acceptance:** router observable; task→model mapping matches §10 (all text → deepseek-v4-flash); degraded modes verified; retrieval baseline (BGE-M3 + reranker via oMLX) verified; voice models (Parakeet / Qwen3-ASR / Qwen3-TTS) verified through the voice engine; no local text LLM in the production path (ADR-023).

### Phase 5 — Evaluation + Evidence-Backed Feedback (Days 13–15)
**Goal:** deterministic readiness/preparation engine + reports.
**Tasks:**
- 5.1 Readiness calculator (deterministic): competency importance × score × confidence × evidence coverage × recency × consistency; overall + per-competency + critical gaps + evidence coverage; knowledge-confidence vs demonstrated-ability separation.
- 5.2 Preparation engine: gap → priority → today's queue (competency, priority, est time, reason, assessment type, expected improvement).
- 5.3 Progress/history aggregation (session trends; no fabricated progress).
- 5.4 Interview report generation (synthesis via deepseek; evidence-backed).
- 5.5 Evaluation version registry + prompt hashing; evaluation records versioned.
**Tests:** readiness math golden cases; queue ordering; progress aggregation from fixture sessions; report schema.
**Acceptance:** scores have observable reasons; queue actionable; progress only from completed assessments.

### Phase 6 — React Product UX + Text Vertical Slice (Days 15–18)
**Goal:** complete text product journey usable end-to-end.
**Tasks:**
- 6.1 Dashboard (where am I / what to improve / what next / progress).
- 6.2 Candidate Setup (profile + resume upload + progress UI).
- 6.3 Role/JD Setup (paste JD, analyze, show competency graph + importance).
- 6.4 Preparation Map (readiness %, top gaps, today's queue, start practice).
- 6.5 Live Interview screen (text): interviewer state, question, answer, hints, evaluation display with evidence, transcript view.
- 6.6 Interview Report screen; Progress screen; Stories screen (CRUD); Settings; Model Status screen.
- 6.7 SSE hook + typed event handling; error/loading/empty states; accessibility pass.
**Tests:** component tests; e2e journey (Playwright): onboarding → resume → JD → map → interview → answer → eval → report.
**Acceptance:** stranger can complete full text journey without dev help.

### Phase 7 — Voice Infrastructure + Audio State Machine (Days 18–20)
**Goal:** explicit voice state machine, audio capture, WS session.
**Tasks:**
- 7.1 Voice state machine (listening/processing/speaking/paused/interrupted/cancelled/completed/error; transitions enforced server-side; mirrored client-side).
- 7.2 WebSocket `/ws/voice/{id}` protocol (control + binary audio) with auth + session binding.
- 7.3 Browser capture: AudioWorklet mic pipeline, PCM16 16kHz, turn detection (energy + silence), partial-stream uplink.
- 7.4 Audio data model: audio_segment/transcript_segment with retention; storage behind interface (local FS dev / S3 later).
- 7.5 ASR service interface + Parakeet path (parakeet-mlx chunked streaming, context window) — integration, not yet tuned.
- 7.6 TTS service interface + Qwen3-TTS path (mlx-audio streaming) — integration, not yet tuned.
- 7.7 Server-side TTS chunk streaming over WS; browser playback via AudioWorklet.
**Tests:** state transition table; WS protocol contract; capture→stream→final transcript in integration env; TTS chunk ordering.
**Acceptance:** voice session starts, transcripts appear, TTS plays, states visible.

### Phase 8 — Streaming ASR/TTS + Turn Handling (Days 20–22)
**Goal:** low-latency streaming with partial transcripts, sentence-chunked TTS, TTFA targets measured.
**Tasks:**
- 8.1 Parakeet streaming tuning: chunk sizing, context window, local-agreement commit policy (VAD-gated pseudo-streaming), partial transcript events; latency instrumentation.
- 8.2 LLM token stream → sentence segmentation → TTS chunk queue → WS audio; TTFA measurement.
- 8.3 Turn finalization: partial→final transcript reconciliation; no duplicated segments.
- 8.4 Fallbacks: ASR down → manual transcript; TTS down → text.
**Tests:** voice matrix subset (normal/fast/slow/long/short/silence/noise); partial transcript flow; TTFA logged and below target.
**Acceptance:** natural back-and-forth voice interview; transcripts accurate enough for evaluation.

### Phase 9 — Interruption / Pause / Resume / Cancellation / Recovery (Days 22–24)
**Goal:** correctness-grade interruption; no stale TTS; robust recovery.
**Tasks:**
- 9.1 Interrupt pipeline: user interrupt → cancel in-flight LLM task + clear TTS queue (server) + clear AudioWorklet buffer (client) → capture new speech → continue same graph state (no duplicated question/eval).
- 9.2 Barge-in during TTS; double interruption; pause/resume mid-turn; stop/cancel.
- 9.3 Browser refresh / network loss / WS reconnect → state from Postgres checkpoint + transcript re-sync.
- 9.4 ASR/TTS/LLM failure handling in voice loop; error_recovery node.
- 9.5 Communication analysis (duration, pauses, fillers, verbosity, hedging) from transcript timestamps — measured only.
**Tests:** full voice test matrix (spec §42): normal, fast, slow, long, short, silence, noise, interruption, double interruption, pause, resume, stop, refresh, network loss, ASR failure, TTS failure, LLM timeout, LLM cancellation, partial/late/duplicate transcript, stale TTS.
**Acceptance:** all matrix cases recover cleanly; stale TTS never observed after interrupt (tested).

### Phase 10 — Progress / History / Practice / Memory (Days 24–26)
**Goal:** repeat-use product loops; longitudinal adaptation.
**Tasks:**
- 10.1 History screens (past interviews, transcripts, evals, reports).
- 10.2 Progress aggregation + trends visualization (per competency series).
- 10.3 Practice engine: weakness → root cause → targeted exercise → practice → eval → evidence update.
- 10.4 Interview memory: longitudinal pattern notes fed back into next interview planning.
- 10.5 Debrief feature (record real interview → analysis → recommendation updates).
- 10.6 Transcript analysis (paste TXT/MD → questions/answers/weaknesses).
- 10.7 Redis decision check: rate limiting/coordination needs measured; add only if justified.
**Tests:** progress math; practice loop integration; debrief → plan update; transcript analysis fixtures.
**Acceptance:** second interview adapts to first interview's weaknesses; progress trends real.

### Phase 11 — MCP + Observability + Security + Evaluation (Days 26–28)
**Goal:** MCP server, full observability, security hardening, eval suite complete.
**Tasks:**
- 11.1 MCP server (read-only tools/resources, streamable-http; contract tests; external-client demo script).
- 11.2 Langfuse OSS integration (self-hosted, MIT-licensed, in Compose): traces across interview graph, retrieval, routing; PII-safe. No Langfuse Cloud dependency.
- 11.3 Structured logs full event set (§20); redaction audit.
- 11.4 Security hardening: rate limiting, CORS/headers, upload guards, prompt-injection tests (adversarial docs fixture), secret audit (gitleaks in CI), pip/npm audit.
- 11.5 Eval suite: golden datasets (§21) + DeepEval runner + CI gate; routing/evidence/adaptive evals.
- 11.6 Demo data complete (4 roles: Frontend, Backend, Full Stack, AI Engineer) + demo script.
**Tests:** MCP contract; adversarial document suite; eval suite green; observability event assertions.
**Acceptance:** `make evals` green; MCP usable by external client; no secrets in repo; injection fixtures neutralized.

### Phase 12 — E2E + Deployment + Documentation + Polish (Days 28–30)
**Goal:** release-quality repo.
**Tasks:**
- 12.1 Full E2E suite green (Playwright + API).
- 12.2 README complete (what/why/screenshots/architecture/framework choices/setup/OMLX/DeepSeek/tests/evals/contributing); ARCHITECTURE.md, DEVELOPMENT.md, DEPLOYMENT.md, TROUBLESHOOTING.md; PRIVACY.md, SECURITY.md, CONTRIBUTING.md; CHANGELOG; license headers review.
- 12.3 Performance targets documented from measurements (latency, TTFA, memory, tokens, cost).
- 12.4 Fresh-clone verification: `git clone && cp .env.example .env && docker compose up` → product usable with demo mode; OMLX setup instructions verified.
- 12.5 Security review checklist completed; known limitations documented.
- 12.6 Release tag + GitHub release notes; screenshots current.
**Tests:** fresh-clone smoke; full suite; docs links checked.
**Acceptance:** spec §66 final acceptance test passes end-to-end for a real user (text + voice), no dev intervention.

---

## 26. Detailed Task Dependencies

- 0.x → all.
- 1.1–1.6 ← 0.x; 1.2 needs 1.1; 1.5 needs 1.3–1.4.
- 2.1–2.2 ← 1.2, 4.3 (embedding via oMLX) — build InferenceRouter + oMLX chat/embed provider early (task 2.0) as dependency; full routing in Phase 4.
- 3.x ← 2.x (evidence/retrieval), 4.x (question gen/eval via router), 1.x.
- 4.x ← 0.x; independent of 3.x except evaluation node uses router.
- 5.x ← 3.x (evaluations exist), 2.x.
- 6.x ← 5.x (prep map), 3.x (interview API), 4.x (streaming).
- 7.x ← 6.x (interview screen), 3.x (graph), 4.x (voice capabilities).
- 8.x ← 7.x.
- 9.x ← 8.x, 3.6 (graph interrupts).
- 10.x ← 5.x, 6.x, 3.x.
- 11.x ← most; 11.5 needs golden datasets from 2.x/3.x outputs.
- 12.x ← all.

**Parallelizable:** Phase 4 (routing) with Phase 3 (graph can use stub router); Phase 2 with 4.1/4.3; eval golden-data authoring alongside Phases 2–3; demo data authoring alongside 2–3; observability scaffolding in Phase 0.

**Critical path:** 0 → 1 → 2(+router) → 3 (graph) → 4 → 5 → 6 (text slice) → 7 → 8 → 9 (voice) → 10 → 11 → 12.

---

## 27. Acceptance Criteria (project-level)

1. Spec §66 final acceptance test passes (25-step journey, text + voice, no dev intervention).
2. Readiness is deterministic + evidence-backed; every score has observable reasons.
3. Interviews adapt based on demonstrated evidence; second interview reflects first interview's weaknesses.
4. Interruption correctness: no stale TTS; state preserved; tests prove it.
5. All framework boundaries respected (removable integrations).
6. Full test suite + eval suite green; CI green on main.
7. Fresh-clone quickstart works; demo mode usable without personal data.
8. No secrets; security checklist complete; adversarial-document tests pass.
9. Model stack per MODEL_CATALOG; routing observable; costs bounded.
10. Documentation truthful; plan matches repository state.

---

## 28. Definition of Done

**Task done:** implementation complete + tests pass + relevant evals pass + no known regression + architecture coherent + docs updated + plan updated + acceptance criteria verified.

**Phase done:** every phase-level acceptance criterion passes (listed per phase).

**V1 done:** all project-level acceptance criteria (§27) verified; release checklist (spec §57) complete.

---

## 29. Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Voice streaming latency/polish on 16GB M4 (ASR+TTS+LLM contention) | Medium | High | Resource-aware lifecycle; oMLX model pinning/TTL; chunk tuning; fallbacks; measure early (Phase 7/8) |
| 2 | Parakeet streaming = chunked (no true streaming) | Certain (verified) | Low | VAD-gated pseudo-streaming + local-agreement commit; Qwen3-ASR chunked/offline fallback (native streaming requires vLLM, not MLX); acceptable TTFA for interviews |
| 3 | LlamaIndex dedup gotcha (no vector-store dedup) | Certain (verified) | Medium | Persistent docstore + explicit dedup logic in ingestion service |
| 4 | LangGraph/MCP/LangChain API churn | Medium | Low | Pin exact versions in pyproject; re-verify at Phase 3/11 start |
| 5 | 30-day scope creep | High | High | §30 scope control; deferred features tracked; features classified MUST/SHOULD/NICE/V2/REJECT |
| 6 | DeepSeek cost creep | Medium | Medium | Local-first routing; prompt minimization; caching; cost telemetry |
| 7 | 16GB memory pressure with multiple local models | Medium | High | oMLX single process manages models; lazy load; 4-bit; artifacts coexist on disk, residency driven by demand/cache/TTL/pinning under the memory guard; lifecycle tests |
| 8 | Auth absent → multi-user confusion | Low (V1) | Low | Deployment-dependent; single-user default; auth isolated behind boundary if added |
| 9 | Model license drift | Low | Low | MODEL_CATALOG tracked; pre-release license audit (§57) |
| 10 | E2E voice tests flaky | Medium | Medium | Separate voice matrix script tier; deterministic fixtures; CI split |

---

## 30. Known Limitations (V1)

- Parakeet live ASR is chunked/buffered streaming, not cache-aware true streaming (acceptable for interview pacing; Qwen3-ASR on MLX as offline/chunked fallback — native streaming requires vLLM backend; noted upgrade candidate: NVIDIA Nemotron-3.5 ASR Streaming).
- No executable coding sandbox; coding = code-reading/review/debugging/algo reasoning discussions.
- No video/whiteboard/anti-cheating/recruiter/multi-tenant/payments.
- No official LinkedIn integration.
- Communication analysis is measured (duration/pauses/fillers/verbosity), never personality/deception inference.
- DeepSeek Responses API not required; Chat Completions API used (legacy model IDs `deepseek-chat`/`deepseek-reasoner` discontinued 2026-07-24 — do not use).
- Authentication optional per deployment; default single-user local deployment.
- Performance thresholds documented after measurement, not fabricated upfront.
- MLX models cannot run concurrently from multiple threads → serialized speech inference worker (ADR-012).
- oMLX audio endpoints (STT/TTS) support must be verified at Phase 7; direct parakeet-mlx/mlx-audio paths are the fallback.

---

## 31. Deferred Features (scope control)

Classify new feature requests here.

| Feature | Class | Note |
|---|---|---|
| System design with diagrams/whiteboard | V2 | text-only in V1 |
| Video interviews | V2 | |
| Executable coding sandbox | V2 | |
| Meeting-provider transcript integrations (Zoom/Meet) | V2 | paste-in works in V1 |
| Multi-tenant org/recruiter platform | V2 | |
| Payments/enterprise | REJECT (V1) | |
| LinkedIn scraping | REJECT | |
| True streaming ASR (Nemotron-3.5-ASR-Streaming) | SHOULD (upgrade candidate) | document in MODEL_CATALOG alternatives |
| Experimental TTS (Voxtral/Soprano/Kokoro/IndexTTS/Zonos/VibeVoice/Higgs/Magpie) | V2/research | do not add in V1 |
| Auth (if deployment needs it) | SHOULD | isolated, must not threaten deadline |
| Redis | SHOULD-if-justified | measure first |
| Semantic cache | NICE | measure first |
| LlamaCloud/managed ingestion | REJECT (V1) | self-hosted pipeline |
| Qwen3.5-9B as production local model | DEFERRED (experimental) | not required, not a fallback, not a routing target; catalog §2.3; only changeable via ADR + evidence |

---

## 32. OSS / Reference Analysis

Researched 2026-08. Ideas adopted; no code copied. Details in `docs/ai/AI_ARCHITECTURE.md` (appendix).

| Project | License | Adopted ideas |
|---|---|---|
| noamseg/interview-coach-skill | MIT | storybank concept, multi-dimension scoring (substance/structure/relevance/credibility → our 13 dims), root-cause diagnosis → targeted drills, outcome calibration idea, persistent coaching state |
| PrepLabsAI/InterviewMentor | (skills) | persona-structured interviews, phased flow (warm-up→core→live), 4-level progressive hints, rubric/scorecard output |
| 1146345502/aural-oss | MIT | dynamic follow-ups, structured scoring/reports, resumable practice attempts, pluggable providers, self-host |
| Also studied: streaming React patterns (SSE vs WS hybrid), AudioWorklet playback (Gemini Live console pattern), LangGraph durable-execution docs, pgvector hybrid RRF patterns, oMLX capabilities | | |

Rejected: skill-file-only architecture (Pramya needs owned state), Next.js/Supabase/tRPC stack (FastAPI + SQLAlchemy chosen for typed Python domain), video/whiteboard (scope), gpt-based DeepEval judge (cost/privacy → deepseek local judge).

---

## 33. Current Framework Versions (verified 2026-08)

| Component | Version | Notes |
|---|---|---|
| Python | 3.12/3.13 (3.14 supported by pydantic 2.13/SQLAlchemy 2.0.47+) | dev machine has 3.14.6 — pin 3.12/3.13 in pyproject for ecosystem stability |
| LangChain / langchain-core | 1.3.x / 1.4.x | no breaking changes until 2.0; use `langchain.agents.create_agent`/LCEL; avoid legacy chains |
| LangGraph | 1.2.x | `StateGraph(state_schema=...)`; `interrupt()`+`Command`; `langgraph.types`; PostgresSaver; durability; v2 streaming (StreamPart/GraphOutput) |
| langgraph-checkpoint-postgres | 1.x (align w/ LangGraph 1.2) | PostgresSaver/AsyncPostgresSaver |
| LlamaIndex | 0.14.x (0.14.23) | `IngestionPipeline`; no `QueryPipeline` (removed 0.13) |
| MCP Python SDK | 2.0.0 (`MCPServer`) or pinned 1.28–2 | v2 protocol 2026-07-28; re-verify at Phase 11 |
| DeepEval | 4.1.x | judge default gpt-5.4 → override to deepseek-v4-flash; RAG metrics; `RetrievedContextData` |
| Langfuse | v4 server / Python SDK 4.14.x | `@observe`, `propagate_attributes`; OTel-based; needs Pydantic v2; self-host Compose (pg+clickhouse+redis+s3) heavier — optional profile. **OSS/self-hosted (MIT), all product features MIT since 2025; Cloud/Enterprise (/ee: SCIM, extended audit logging, data retention policies, advanced RBAC) NOT V1 dependencies.** |
| FastAPI | 0.139.x | Python 3.10+; SSE via StreamingResponse; WS via websockets; `app.frontend()` optional |
| Pydantic | 2.13.x | v2 only; strict mode; discriminated unions |
| SQLAlchemy | 2.0.51 | async; `Mapped`/`mapped_column` |
| asyncpg | current | driver |
| Alembic | current | migrations; CREATE EXTENSION vector in first |
| pgvector | 0.8.x | HNSW, halfvec, sparsevec; python `pgvector>=0.8` |
| PostgreSQL | 17 | `pgvector/pgvector:pg17` image |
| React | 19.x | use/useOptimistic/useActionState; React Compiler |
| Vite | 8 | `@vitejs/plugin-react` |
| TypeScript | 5.7+ strict | |
| Tailwind | 4 | via @tailwindcss/vite |
| TanStack Query | v5 | server state |
| Zustand | current | client state |
| Radix + shadcn/ui | current | primitives |
| Playwright | current | e2e |
| ruff / mypy / pyright | current | lint/type |
| uv | current | package manager (fast, modern) |
| Docker | 27.x | compose v2 |

**Deprecated to avoid:** `create_react_agent`, `LLMChain`, `AgentExecutor`, `initialize_agent`, `ConversationBufferMemory`, `RunnableWithMessageHistory` (prefer checkpointer), `Interrupt.interrupt_id`/`NodeInterrupt`, `langgraph.constants.Send/Interrupt`, `QueryPipeline`, MCP `FastMCP` import from official SDK on v2 (renamed `MCPServer`), `deepseek-chat`/`deepseek-reasoner` model IDs, `frequency_penalty`/`presence_penalty` on DeepSeek, `mlx-embeddings` (GPL), `langfuse.llama_index` callback (use OpenInference), `sse-starlette` (FastAPI has native SSE), legacy `.on_event` (use lifespan).

---

## 34. Environment / Setup

- Target dev hardware: MacBook Pro M4, 16GB unified, 512GB.
- Python: uv-managed, 3.12/3.13. Node 24. Docker 27.
- Local AI: oMLX (brew or DMG; OpenAI-compatible endpoints; model pinning/TTL for memory). Model downloads per `docs/MODEL_CATALOG.md` (HF repos listed).
- `.env.example`: APP_ENV, APP_HOST/PORT, DATABASE_URL (postgresql+asyncpg://…), DEEPSEEK_API_KEY, OMLX_BASE_URL, OMLX_API_KEY(optional), LANGFUSE_* (optional; OSS self-hosted only), VOICE_RETENTION_DAYS, UPLOAD_MAX_MB, ROUTING config, frontend VITE_API_URL.
- Commands (Makefile): `make up`, `make down`, `make migrate`, `make dev-backend`, `make dev-frontend`, `make test`, `make test-unit`, `make test-integration`, `make evals`, `make lint`, `make typecheck`, `make models-pull`, `make demo-setup`.
- Never commit `.env`.

---

## 35. Progress Tracker (machine-readable)

```
PHASE STATUS
Phase 0  Architecture + Scaffold     COMPLETE
Phase 1  Core Domain + Persistence   COMPLETE
Phase 2  Knowledge Layer             IN PROGRESS (2.0, 2.1 done)
Phase 3  Interview Engine (LangGraph)NOT STARTED
Phase 4  Model Routing + Local       NOT STARTED
Phase 5  Evaluation + Readiness      NOT STARTED
Phase 6  React UX + Text Slice       NOT STARTED
Phase 7  Voice Infrastructure        NOT STARTED
Phase 8  Streaming ASR/TTS           NOT STARTED
Phase 9  Interrupt/Pause/Resume      COMPLETE (voice engine H.1-H.12; audio persistence, replay, reconnect/heartbeat, communication analysis)
Phase 10 Progress/History/Practice   COMPLETE (progress aggregation, practice sessions, history page, interview record endpoint, debrief UI, story bank)
Phase 11 MCP/Observability/Security  COMPLETE for V1 (Langfuse facade done; security done; demo done; evals done; MCP DEFERRED from V1 per ADR-006)
Phase 12 E2E/Deploy/Docs/Polish      COMPLETE (browser E2E; fresh-clone verified; release acceptance matrix + final docs pass)
```

- Current phase: Phase 2 (Knowledge Layer) — tasks 2.0, 2.1 COMPLETE (2026-08)
- Current task: 2.2 ingestion (next after 2.1)
- Blocked by: user confirmation to continue Phase 2
- Next task: 2.2 LlamaIndex IngestionPipeline (chunking + embedding + pgvector)
- Last verified commit: Phase 2.1 document parsing (see git log)
- Tests: 103 passing — 59 unit (Phase 0/1 + AI layer + parsing pdf/docx/md/txt + guards), 5 contract (OpenAPI surface, error envelope, provider capability contracts), 14 integration (unchanged 13 + upload FAILED-state/retry)
- Evals: none yet
- Known failures: none
- Phase 2.1 acceptance verified: pdf/docx/md/txt parse to normalized ParsedDocument; upload flow runs PENDING→PARSING→PARSED/FAILED; guards (size, mime, page count, timeout, DOCX uncompressed cap, empty extraction); parsed text in-memory handoff to 2.2 (never persisted); DOCUMENT_MAX_PAGES / DOCUMENT_PARSE_TIMEOUT_SECONDS configurable; no new API endpoint; mypy + pyright + ruff green.

---

## 36. Decision Log

| Date | Decision | Reason | Impact |
|---|---|---|---|
| 2026-08 | Definitive model stack verified compatible (§14 research) | deepseek-v4-flash live (1M ctx); all local models have MLX conversions + permissive licenses | Locked; only changeable via ADR + evidence |
| 2026-08 | oMLX as single local runtime (LLM/embed/rerank/STT/TTS) | OpenAI-compatible, resource-aware (SSD KV cache, model pinning/TTL), Apache-2.0 | MLXProvider behind router; avoids GPL mlx-embeddings linkage for embeddings |
| 2026-08 | LangGraph 1.2 + Postgres checkpointer | durable interview state, interrupts | Phase 3 |
| 2026-08 | LlamaIndex 0.14 ingestion + pgvector hybrid RRF | retrieval quality; dedup handled explicitly | Phase 2 |
| 2026-08 | DeepEval judge = deepseek-v4-flash (not gpt default) | cost + privacy | Phase 11 evals |
| 2026-08 | Parakeet chunked streaming accepted; Qwen3-ASR MLX = offline/chunked fallback only (native streaming requires vLLM, not MLX); Nemotron streaming documented as upgrade candidate | verified limitation | Voice matrix accounts for it |
| 2026-08 | Voice = WebSocket (control+audio); text events = SSE | bidirectional/interrupt needs | §16 |
| 2026-08 | Model stack finalization: 4B (`pramya-4b`) = primary local workhorse; deepseek-v4-flash = escalation only; 9B DEFERRED (not required/fallback/routing target) | 4B handles majority of workload; cloud reserved for justified escalation; strongest ≠ default | Routing tables/fallbacks/setup/evals updated repo-wide; ADR-004/013 amended; catalog §0/§2.3/§6; baseline verification at Phase 4 |

---

## 37. Change Log

| Date | Change | Author |
|---|---|---|
| 2026-08 | Voice engine concurrency rework (H.1–H.9): hot WS receive loop (never awaits TTS/ASR/DeepSeek/DB); TTS + answer pipeline as background tasks; auto (RMS silence watchdog) + manual (end_turn) turn finalization; full answer loop (final ASR → DeepSeek submit_answer → evaluation → next question); explicit live/offline ASR config split (Parakeet live, Qwen3-ASR offline); generation-id stale-audio protection server+client; TranscriptSegment persistence per turn; typed mic permission errors; AudioContext created synchronously in the click gesture. 10 new engine unit tests (hot-loop interrupt mid-TTS, generation bump, no stale chunks, auto+manual finalization, pause/resume/stop/cancel). Real-model E2E pending Mac memory relief. | Engineering session |
| 2026-08 | ADR-023 production text topology: all text/LLM inference → deepseek-v4-flash (sole text provider, no fallback chain — DeepSeek failure is a controlled provider error, never a silent local text fallback); local oMLX retained for AUDIO (Parakeet-TDT live ASR, Qwen3-ASR primary/recorded ASR, Qwen3-TTS) + RETRIEVAL (BGE-M3, Qwen3-Reranker-0.6B); local text-generation models (pramya-4b / qwen3.5-4b / qwen2.5-coder-7b) PROHIBITED in production path; thinking off by default; `LLM_PROVIDER=deepseek` / `VOICE_PROVIDER=omlx`; `/models/status` reports provider roles; catalog §0/§1/§2.1 rewritten; ADR-020 superseded for text routing; 124 unit + 9 contract + 29 integration tests green; one real DeepSeek smoke via router (provider=deepseek, model=deepseek-v4-flash, thinking off). | Engineering session |
| 2026-08 | Model stack reconciliation (pre-Phase 1): Qwen3.5-4B = primary local workhorse (alias `pramya-4b`, thinking off, local-first, majority of workload); deepseek-v4-flash = escalation model (not default); Qwen3.5-9B DEFERRED (historical entry preserved, not required/fallback/routing target). Routing tables, fallback chains, ADR-004/009/011/013, AI/VOICE architecture, DEPLOYMENT setup, catalog, memory, README, decision log updated consistently. Local verification baseline defined (catalog §6). Phase 1+ has no 9B dependency. | Engineering session |
| 2026-08 | Phase 0 scaffold: backend (uv/FastAPI/lifespan/health/request-id/logging), frontend (Vite 8 + React 19 + TS strict + router/query/zustand shell), compose + Makefile + CI, domain enums/schemas/errors, `.env.example` aligned. pgvector Python pin corrected to 0.5.x (client) — server ext 0.8.x in Docker image. Tests moved to repo-root `tests/` per §23 (plan §8 showed backend/app/tests; §23 target structure wins). | Implementation session |
| 2026-08 | Phase 1 core domain + persistence: SQLAlchemy 2.0 async models for all §7 entities (vector(1024) + generated tsvector + HNSW/GIN), Alembic async env + initial migration (CREATE EXTENSION vector), repository layer + unit-of-work, user/candidate/document/evidence services, candidates/documents/evidence API routers with upload validation + content-hash + error envelope, idempotency records (task 1.6). 47 tests (unit/contract/integration on real pgvector), mypy/pyright/ruff green, `alembic check` no drift, CI integration job + test-contract target added. | Implementation session |

(Coherent feature-level changes only. CHANGELOG.md tracks releases.)

---

## 38. Future Roadmap (post-V1)

- True streaming ASR (Nemotron-3.5 ASR Streaming) when stable on MLX.
- TTS upgrade candidates (Voxtral, Soprano, Kokoro, IndexTTS, Zonos, VibeVoice, Higgs Audio, Magpie) — evaluated for license + quality before adoption.
- System design with diagrams; video interviews; executable coding rounds.
- Meeting-provider transcript integrations.
- Auth + multi-user; optional managed observability.
- Semantic caching + Redis if measurements justify.
- Evaluation harness expansion (LLM-as-judge correlation vs human calibration).
- Distribution: Docker images, one-command installer, demo hosting.

---

## Continuation Protocol (every session)

1. Read this plan (§35 progress tracker first).
2. Read relevant ADRs (`docs/architecture/`).
3. Inspect `git status` + recent commits.
4. Run relevant tests.
5. Identify current phase/task.
6. Read relevant implementation files.
7. Verify reality matches plan; if not, investigate → decide → update plan → continue.
8. Never assume previous context exists.

## Feedback Protocol

Treat user feedback as first-class input: determine impact (requirements/architecture/UX/scope/framework/priority), update this plan + affected ADRs + task dependencies, preserve completed work unless justified, explain impact, continue.

## Scope Control

Classify every tempting feature: MUST HAVE / SHOULD HAVE / NICE TO HAVE / V2 / REJECT. If it threatens the 30-day deadline, defer it (§31 table).

## Research Protocol

When uncertain about a framework API: consult current official docs/repo/examples first; never guess; record discoveries here or in ADRs.

## Release Standard (v1)

All tests pass · eval suite passes · Docker setup works · fresh-clone works · demo works · README complete · screenshots current · architecture diagram current · no secrets · licenses checked · dependencies checked · security review completed · known limitations documented · changelog updated · release tag created.
