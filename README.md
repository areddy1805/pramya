<div align="center">

<img src="assets/branding/logo.png" width="320" alt="Pramya" />

# Pramya — prove you're ready.

**Evidence-driven mock interviews with a live voice interviewer, a deterministic
readiness model, and an adaptive practice loop — powered by DeepSeek reasoning,
local speech models, and a real RAG knowledge layer over your own documents.**

![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13-3776AB?logo=python&logoColor=white)
![TypeScript](https://img.shields.io/badge/typescript-strict-3178C6?logo=typescript&logoColor=white)
![React](https://img.shields.io/badge/react-19-61DAFB?logo=react&logoColor=black)
![FastAPI](https://img.shields.io/badge/fastapi-0.139-009688?logo=fastapi&logoColor=white)
![LangChain](https://img.shields.io/badge/langchain-core-1C3C3C?logo=langchain&logoColor=white)
![LangGraph](https://img.shields.io/badge/langgraph-1C3C3C?logo=langgraph&logoColor=white)
![LlamaIndex](https://img.shields.io/badge/llama--index-0.14-000000)
![DeepSeek](https://img.shields.io/badge/llm-deepseek--v4--flash-4D6BFE)
![PostgreSQL](https://img.shields.io/badge/postgresql-17%20%2B%20pgvector-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/docker-compose-2496ED?logo=docker&logoColor=white)
![Tests](https://img.shields.io/badge/tests-218%20passing-2ea44f)

**Pramya — prove you're ready.**

</div>

---

## Table of contents

- [What Pramya is](#what-pramya-is)
- [Screenshots](#screenshots)
- [Core capabilities](#core-capabilities)
- [Architecture](#architecture)
- [Framework architecture](#framework-architecture)
- [Technology stack](#technology-stack)
- [AI / model topology](#ai--model-topology)
- [RAG architecture](#rag-architecture)
- [Interview architecture](#interview-architecture)
- [Voice architecture](#voice-architecture)
- [Observability (Langfuse OSS)](#observability-langfuse-oss)
- [Evaluation system](#evaluation-system)
- [Security model](#security-model)
- [Demo setup](#demo-setup)
- [Local development](#local-development)
- [Environment configuration](#environment-configuration)
- [Commands](#commands)
- [Testing](#testing)
- [E2E](#e2e)
- [Evals](#evals)
- [Docker / Langfuse](#docker--langfuse)
- [Project structure](#project-structure)
- [Architecture decisions](#architecture-decisions)
- [Gallery](#gallery)
- [Known limitations](#known-limitations)
- [License](#license)
- [Contributing](#contributing)
- [Changelog / releases](#changelog--releases)

---

## What Pramya is

Pramya is an evidence-driven interview preparation platform. Instead of
treating preparation as a pile of canned questions, Pramya builds a **closed
loop**: your resume and job description become a knowledge base and a
competency model; every practice answer is evaluated on 13 dimensions and
turned into **evidence**; readiness is computed deterministically from
demonstrated evidence — never from vibes — and the next interview adapts to
what you actually demonstrated.

The flagship experience is a **live spoken mock interview**: the AI
interviewer speaks (local Qwen3-TTS), listens to your real speech (local
Parakeet ASR), evaluates your answer with DeepSeek, extracts evidence, and
asks an adaptive follow-up — all over a WebSocket with first-class
interruption and pause/resume semantics.

The product is built as a **modular monolith**: React frontend, FastAPI
backend, PostgreSQL + pgvector, DeepSeek for all text reasoning, and local
speech/retrieval models through oMLX.

> **Honest status.** This repository implements the V1 product loop end to
> end (text and voice), with automated browser E2E and an evaluation harness.
> Two items from the original roadmap are explicitly **deferred**: the MCP
> server (ADR-006 accepted, not built) and full Langfuse/OpenTelemetry
> instrumentation (SDK facade implemented; see
> [Observability](#observability-langfuse-oss)). See
> [Known limitations](#known-limitations).

---

## Screenshots

Real screenshots from the running application (dark flagship theme).

| | | |
|---|---|---|
| <img src="assets/screenshots/dashboard.png" width="380" alt="Dashboard" /> | <img src="assets/screenshots/setup.png" width="380" alt="Candidate setup" /> | <img src="assets/screenshots/preparation.png" width="380" alt="Preparation" /> |
| <img src="assets/screenshots/interview.png" width="380" alt="Interview workspace" /> | <img src="assets/screenshots/evidence.png" width="380" alt="Evidence ledger" /> | <img src="assets/screenshots/progress.png" width="380" alt="Progress" /> |
| <img src="assets/screenshots/stories.png" width="380" alt="Story bank" /> | <img src="assets/screenshots/history.png" width="380" alt="History" /> | <img src="assets/screenshots/debriefs.png" width="380" alt="Debriefs" /> |
| <img src="assets/screenshots/settings.png" width="380" alt="Settings" /> | <img src="assets/screenshots/runtime.png" width="380" alt="Runtime status" /> | <img src="assets/screenshots/transcript.png" width="380" alt="Interview record" /> |
| <img src="assets/screenshots/voice.png" width="380" alt="Live voice interview" /> | <img src="assets/screenshots/report.png" width="380" alt="Interview report" /> | |

A full-page gallery is at the end of this document: [Gallery](#gallery).

---

## Core capabilities

| Capability | Description | Status |
|---|---|---|
| Candidate profile | Headline, seniority target, timezone; first-run bootstrap | ✅ Implemented |
| Resume intelligence | Upload (PDF/DOCX/TXT/MD) → parse → chunk → embed → index; structured extraction into a **claimed**-evidence ledger | ✅ Implemented |
| JD / role analysis | JD text → role model with required/preferred competencies, weights, seniority | ✅ Implemented |
| Evidence profile | Provenance ladder: claimed → observed → demonstrated → inferred → unknown; user corrections | ✅ Implemented |
| Competency graph | Per-role competencies with importance + level | ✅ Implemented |
| Readiness | Deterministic calculator: evidence coverage × importance × recency × demonstrated ability; critical gaps | ✅ Implemented |
| Preparation queue | Gap → priority → today's practice items with reasons | ✅ Implemented |
| Practice / text interview | 8 modes, adaptive questioning, progressive hints (4 levels), 13-dimension evaluation | ✅ Implemented |
| Live voice interview | Spoken Q&A over WebSocket: local TTS + ASR, interrupt/pause/resume, adaptive follow-ups | ✅ Implemented |
| Interview memory | Durable per-session record: questions, answers, scores, hint usage | ✅ Implemented |
| History & debriefs | Session history, interview-record view, real-interview debriefs with structured analysis | ✅ Implemented |
| Story bank | STAR stories mapped to competencies | ✅ Implemented |
| Progress tracking | Longitudinal aggregation across completed evaluations | ✅ Implemented |
| Communication analysis | Measured speaking time, latency, fillers, verbosity, interruptions (never fabricated) | ✅ Implemented |
| Model / runtime status | Live provider health + model inventory | ✅ Implemented |
| Demo mode | One-command, idempotent 4-role demo dataset | ✅ Implemented |
| Security | CORS, optional bearer tokens, rate limiting, security headers, upload hardening | ✅ Implemented |
| Evaluation harness | Golden-data AI eval suite (question gen, eval, extraction, RAG, adaptation, voice) | ✅ Implemented (variance recorded honestly) |
| MCP server | Read-oriented interop surface (ADR-006) | ⏸️ Deferred from V1 |
| Langfuse OSS | Self-hosted trace platform (SDK facade) | ⚠️ SDK wired; full OTel instrumentation deferred |

---

## Architecture

```mermaid
flowchart TB
    subgraph Browser
        UI[React 19 + TypeScript<br/>Vite · Tailwind 4]
    end
    subgraph Backend[FastAPI · Python 3.12]
        API[REST /api/v1 + SSE]
        WS[WebSocket /ws/voice]
        WG[LangGraph interview workflow]
        LC[LangChain AI composition]
        SVC[Domain / application services]
        DET[Deterministic engines:<br/>readiness · preparation · communication]
        REPO[Repositories]
    end
    subgraph Data[PostgreSQL 17 + pgvector]
        DB[(user · document · evidence · role<br/>competency · session · turn · evaluation<br/>chunk · transcript · audio · story · debrief)]
    end
    subgraph Inference
        DS[DeepSeek v4 flash<br/>all text reasoning]
        OMLX[oMLX · local models<br/>Parakeet ASR · Qwen3-TTS<br/>BGE-M3 embeddings · reranker]
    end
    UI --> API
    UI --> WS
    API --> WG
    WG --> LC
    LC --> SVC
    SVC --> DET
    SVC --> REPO
    REPO --> DB
    LC --> DS
    WG --> DS
    WS --> OMLX
    SVC --> OMLX
```

Every model invocation flows through the `InferenceRouter`: task-class
policy → provider → response, with telemetry on provider/model/latency/tokens.
Text tasks route to **DeepSeek only**; audio and retrieval stay **local**.
There is no local text LLM in the production path.

---

## Framework architecture

The frameworks are real execution layers with explicit boundaries — not
decorations. Each one composes the layer below it and never bypasses the
router or the domain invariants.

```mermaid
flowchart TB
    WG[LangGraph · StateGraph workflow<br/>load_session → retrieve_context → generate_question<br/>→ evaluate_answer → extract_evidence → next action]
    LC[LangChain · Runnable chains<br/>RouterChatModel → InferenceRouter<br/>structured_chain / text_chain]
    DOM[Domain / application services<br/>state machine · idempotency · persistence · SSE]
    DET[Deterministic invariants<br/>readiness · preparation · evaluation versioning]
    REPO[Repositories · SQLAlchemy async]
    DB[(PostgreSQL + pgvector)]
    WG --> LC
    WG --> DOM
    LC --> DOM
    DOM --> DET
    DOM --> REPO
    REPO --> DB
```

| Framework | Where it actually executes | Role |
|---|---|---|
| **LangGraph** | `backend/app/interview/workflow.py` — a `StateGraph` compiled with a `MemorySaver` checkpointer; `InterviewService` runs `workflow.ainvoke(thread_id=…)` for every question, answer, hint, and report action | Interview workflow orchestration: typed state, conditional routing (next / follow-up / repeat / finish), adaptive loop |
| **LangChain** | `backend/app/ai/langchain/` — `RouterChatModel(BaseChatModel)` delegates generation to the `InferenceRouter`; `structured_chain` (JSON-schema output with bounded retry-with-feedback) and `text_chain` are the production path for question generation, evaluation, hints, extraction, role analysis, and report synthesis | AI composition: prompts, runnables, structured-output parsing — never a router bypass |
| **LlamaIndex** | `backend/app/knowledge/rag/service.py` — `LlamaIndexIngestionService` (custom `RouterEmbeddings` + vector-store adapter over the existing `document_chunk` table) and `LlamaIndexRetriever` (retriever + custom rerank postprocessor) | Ingestion pipeline + retrieval; the deterministic hybrid retriever (pgvector + FTS + RRF) remains the fallback/reference path |
| **Langfuse** | `backend/app/observability/` — degradation-safe facade over the official SDK (see [Observability](#observability-langfuse-oss)) | Optional trace platform; structured logs when unconfigured |

```mermaid
flowchart LR
    LI[LlamaIndex] --> RAG[RAG / index / retrieval]
    RAG --> PG[pgvector]
    PG --> CTX[retrieved context]
    CTX --> CH[LangChain / LangGraph]
    CH --> DS[DeepSeek]
```

---

## Technology stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend | React 19 · TypeScript (strict) · Vite 8 · Tailwind 4 · TanStack Query 5 · Zustand | Dark-first semantic token design system; `prefers-reduced-motion` support |
| Backend | Python 3.12/3.13 · FastAPI 0.139 · Pydantic 2.13 · SQLAlchemy 2 (async) · Alembic | Modular monolith; SSE + WebSocket |
| Data | PostgreSQL 17 · pgvector (HNSW, Vector(1024)) | Single schema, single migration lineage |
| AI composition | langchain-core 1.5 | Runnable chains over the router |
| Workflow | langgraph 1.2 | Interview StateGraph, MemorySaver checkpointer |
| RAG | llama-index-core 0.14 | Ingestion + retrieval adapters over pgvector |
| Text LLM | DeepSeek v4 flash (`deepseek-v4-flash`, httpx-based provider) | Sole production text LLM (ADR-023) |
| Local runtime | oMLX (Apache-2.0) | Speech + retrieval models only |
| Observability | Langfuse OSS 4.x (SDK facade) | Optional, self-hosted compose profile |
| Tests | pytest · Playwright · ruff · mypy · pyright · oxlint | 218 backend checks + browser E2E |
| Infra | Docker Compose | Postgres, backend, frontend, Langfuse stack |

---

## AI / model topology

Text and reasoning are DeepSeek; speech and vectorization are local. This is
an explicit policy (ADR-023), enforced by the task-class routing table and by
the `MODEL_CATALOG` — not a runtime accident.

| Model | Provider | Responsibility |
|---|---|---|
| `deepseek-v4-flash` | DeepSeek (cloud, API key) | All text reasoning: question generation, evaluation, hints, extraction, role analysis, report synthesis, debrief/transcript analysis |
| `parakeet-tdt-0.6b-v3-int8` | oMLX (local) | **Live** ASR (`voice_live_asr_model`) |
| `Qwen3-ASR-1.7B-4bit` | oMLX (local) | Offline/archival ASR (`voice_offline_asr_model`) |
| `Qwen3-TTS-12Hz-0.6B-Base-MLX-4bit` | oMLX (local) | TTS — interviewer speech |
| `bge-m3-mlx-4bit` | oMLX (local) | Embeddings (1024-dim, pgvector column matches) |
| `Qwen3-Reranker-0.6B-4bit` | oMLX (local) | Retrieval reranking |

Local 4B/7B text models (`pramya-4b`, `qwen2.5-coder-7b`) are **prohibited
in the production path**; they exist only as provider-construction
compatibility and are never routed. DeepSeek failure is a controlled
provider error — there is no silent local-text fallback.

---

## RAG architecture

Documents are parsed into normalized text, chunked, embedded with BGE-M3
(local), and written to `document_chunk` (pgvector `vector(1024)` + FTS
tsvector + JSONB metadata). Retrieval fuses vector + FTS with RRF, reranks
with the local Qwen3-Reranker, and hands grounded context to the LangGraph
interview workflow.

```mermaid
flowchart LR
    DOC[Resume / JD / debrief documents] --> PARSE[parse: pdf · docx · txt · md]
    PARSE --> LI[LlamaIndex ingestion pipeline]
    LI --> EMB[RouterEmbeddings → BGE-M3 · 1024-dim]
    EMB --> PG[(pgvector document_chunk<br/>+ FTS tsvector + HNSW)]
    Q[query] --> VEC[vector search] --> PG
    Q --> FTS[full-text search] --> PG
    VEC --> RRF[RRF fusion]
    FTS --> RRF
    RRF --> RERANK[Qwen3-Reranker]
    RERANK --> CTX[grounded context]
    CTX --> WG[LangGraph workflow]
    WG --> DS[DeepSeek]
```

The deterministic hybrid retriever (`backend/app/knowledge/retrieval.py`)
remains as the tested fallback/reference path; the LlamaIndex retriever is
the production path used by the interview service.

---

## Interview architecture

Every interview action — question, answer, hint, report — runs the LangGraph
workflow with the session's `graph_thread_id` as the checkpointer thread.
The workflow nodes call the deterministic domain services:

`load_session → retrieve_context → generate_question → evaluate_answer →
extract_evidence → update_candidate_state → determine_next_action`

- **8 interview modes**: general, resume deep dive, JD interview, technical,
  behavioral, project deep dive, system design (text), coding reasoning
  (verbal).
- **Adaptive questioning**: the generator receives the session history +
  evidence summary, so follow-ups react to what you actually said.
- **Progressive hints**: 4 levels (nudge → direction → partial reasoning →
  worked approach); `hints_used` is persisted and penalizes the evaluation.
- **Evaluation**: 13 dimensions (correctness, technical depth, clarity,
  structure, relevance, evidence, communication, tradeoff awareness,
  reasoning, confidence, specificity, seniority alignment, completeness) with
  an overall 0–10 score, confidence, strengths/weaknesses/missing evidence,
  and follow-up suggestions. Every answer also emits **evidence rows**
  (observed) with provenance.
- **Interview memory**: the full record (questions, answers, scores, hint
  usage per turn) is exposed via `GET /interviews/{id}/transcript` and shown
  in the Transcript page; the report synthesizes it into a markdown report.

---

## Voice architecture

The live voice interview is a real spoken loop, not a demo shell:

```mermaid
flowchart LR
    MIC[Browser mic · PCM16 16kHz] --> WS[WebSocket /ws/voice/{id}]
    WS --> ENG[VoiceEngine · concurrent state machine]
    ENG --> ASR[Parakeet-TDT live ASR<br/>partial transcripts]
    ASR --> Q[answer → LangGraph workflow]
    Q --> DS[DeepSeek evaluation]
    DS --> NQ[adaptive next question]
    NQ --> TTS[Qwen3-TTS · PCM 24kHz]
    TTS --> WS --> SPK[Browser playback queue]
```

- **Server-authoritative states**: idle → starting → speaking → listening →
  processing → speaking, with interrupt / pause / resume / stop / cancel side
  transitions broadcast as WS `state` events.
- **Turn finalization**: automatic (RMS speech detection + silence watchdog)
  *and* manual (`end_turn` / Done speaking).
- **Interruption correctness (H.7)**: every TTS stream carries a `generation`
  id; interruption bumps it and cancels in-flight synthesis, so **stale audio
  is never transmitted or played**.
- **Concurrency**: the WS receive loop stays hot; TTS/ASR/DeepSeek run as
  background tasks; a single speech lock serializes the local models.
- **Persistence (H.8)**: per-turn interviewer + candidate transcripts, and
  opt-in candidate audio (`audio_segment` rows + WAV files) with retention,
  replayable via `GET /interviews/{id}/voice/audio`.
- **Reconnect + heartbeat**: `heartbeat` → `heartbeat_ack` keepalive;
  reconnecting to an in-progress session emits a `resume` event with the
  authoritative state and last question.
- **Degradation**: TTS down → text interviewer response; ASR down → typed
  transcript mode. Never a silent failure.

---

## Observability (Langfuse OSS)

Self-hosted Langfuse OSS (MIT) via `docker-compose.langfuse.yml`
(pg + Redis + ClickHouse + MinIO + worker + web at **http://localhost:3030**).
The backend ships a degradation-safe facade (`backend/app/observability/`):
when `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` are set it uses the
official Langfuse SDK; otherwise it falls back to structured JSON logs. The
facade never crashes the request path.

Traced spans (real production calls):

- question generation, answer evaluation, hint generation (LangChain path)
- hybrid/LlamaIndex retrieval
- voice: ASR latency, TTS latency, interruptions, audio bytes

What is **not** logged: candidate content, transcripts, resume text, keys.
Telemetry carries ids + redacted metadata only.

> Honest limitation: the facade calls the Langfuse SDK directly; OTel
> exporters/OpenInference and LangChain callback handlers are **not** wired.
> `OBSERVABILITY.md` documents the actual behavior.

---

## Evaluation system

Pramya separates two evaluation concerns:

1. **Candidate evaluation** (product feature): every practice answer is
   scored on 13 dimensions with evidence extraction and a versioned
   evaluator (`evaluation_version`).
2. **AI-system evaluation** (development tool): a golden-data pytest harness
   under `tests/evals/` that scores *Pramya itself* — question generation,
   answer evaluation, evidence extraction, RAG grounding, adaptation, voice
   behavior, and structured-output robustness — using `deepseek-v4-flash` as
   the judge through the `InferenceRouter` (no router bypass).

```bash
make evals        # run the golden-data harness
```

Results land in `tests/evals/results/` with machine-readable JSON + a human
summary. The recorded run: **95 checks, 0 FAIL, 3 WARNING**. Borderline
DeepSeek judge variance is classified **WARNING** and recorded — never gamed
to PASS. The judge is a custom router-bound adapter; DeepEval itself is
**not** used because it hard-depends on the OpenAI SDK, which conflicts with
the httpx-only provider constraint (ADR-024).

See `docs/EVALUATION.md` for datasets, thresholds, and how to add golden cases.

---

## Security model

- **CORS**: applied from `CORS_ORIGINS` (preflights resolve before auth).
- **API tokens**: optional bearer auth (`API_TOKENS`, comma-separated) on
  `/api/v1` (health + openapi exempt); voice WS accepts `?token=`.
- **Rate limiting**: per-IP fixed-window (`RATE_LIMIT_RPM`, 0 = off).
- **Headers**: nosniff, frame-deny, referrer policy, permissions policy on
  every response.
- **Uploads**: size/mime/page/timeout guards; storage keys derive from the
  content digest + a whitelisted suffix — never client filenames.
- **Prompt injection**: system prompts carry explicit
  data-vs-instruction boundaries; untrusted content stays in the user
  payload; adversarial-document tests cover the boundary.
- **LLM output gate**: model output → Pydantic validation → application
  logic → persistence. The model can never write privileged state.
- **Secrets**: env-only, `.env` gitignored, never logged. `pip-audit`:
  no known vulnerabilities.

There is no per-user account system in V1 — the product is a single-user
local model (plan §19); bearer tokens are the deployment-level boundary.

---

## Demo setup

A one-command, **idempotent** demo dataset for the full product:

```bash
make demo-setup
```

or via the UI: **Settings → Demo data → Load demo data**, or the API:
`POST /api/v1/demo/setup`.

It creates (for the default user):

- candidate profile,
- 4 demo roles (`demo/roles/`): Senior Full Stack Engineer, Senior Backend
  Engineer, Senior Frontend Engineer, Senior Product Manager — each with a
  resume + JD fixture,
- resume parse → chunk → embed → index,
- structured extraction → **claimed** evidence ledger,
- JD analysis → competency graph per role,
- readiness computation + critical gaps,
- preparation queue.

Re-running is safe: documents de-duplicate by content hash, roles by title,
evidence by source reference.

---

## Local development

Requirements: Docker, Python 3.12/3.13, Node 20+, `uv`, `pnpm`, and a
running oMLX runtime with the speech/retrieval models
(`docs/operations/DEPLOYMENT.md`, `docs/MODEL_CATALOG.md`).

```bash
git clone <your-fork>/pramya.git
cd pramya
cp .env.example .env              # then set DEEPSEEK_API_KEY (required for all text inference)

make up                           # Docker: postgres+pgvector, backend, frontend
make migrate                      # alembic upgrade head
make backend-install              # uv sync
make frontend-install             # pnpm install
make demo-setup                   # optional: seed the 4-role demo dataset
make dev-backend                  # uvicorn :8001 (oMLX owns :8000)
make dev-frontend                 # vite :3000
```

- Frontend → http://localhost:3000
- Backend API → http://localhost:8001
- API docs → http://localhost:8001/docs
- oMLX runtime → http://127.0.0.1:8000/v1
- Langfuse (optional) → http://localhost:3030

These commands were verified from a fresh clone: fresh-DB migration builds
all 23 tables, and the backend boots with an example-only `.env`
(DeepSeek shows `configured: false` until the key is added — honest health).

---

## Environment configuration

`.env.example` documents every variable (44 keys). The important ones:

| Variable | Purpose | Default |
|---|---|---|
| `DEEPSEEK_API_KEY` | Required — all text inference | — |
| `APP_PORT` | Backend port (oMLX owns 8000) | `8001` |
| `DATABASE_URL` | Asyncpg DSN | `postgresql+asyncpg://pramya:pramya@localhost:5432/pramya` |
| `OMLX_BASE_URL` / `OMLX_API_KEY` | Local oMLX runtime | `http://127.0.0.1:8000/v1` |
| `VOICE_LIVE_ASR_MODEL` / `VOICE_OFFLINE_ASR_MODEL` / `VOICE_TTS_MODEL` | Voice model routing (Parakeet / Qwen3-ASR / Qwen3-TTS) | set |
| `VOICE_STORE_AUDIO` / `VOICE_RETENTION_DAYS` | Opt-in audio persistence + retention | `true` / `30` |
| `CORS_ORIGINS` | Allowed browser origins | `http://localhost:3000` |
| `API_TOKENS` | Optional bearer tokens (empty = auth off) | — |
| `RATE_LIMIT_RPM` | Per-IP rate limit (0 = off) | `0` |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` | Optional Langfuse OSS | unset |

---

## Commands

```bash
make up              # Docker infra (postgres, backend, frontend)
make down
make migrate         # alembic upgrade head
make test            # unit + contract (182 passing)
make test-integration# integration suite on isolated pramya_test DB (36 passing)
make lint            # ruff + oxlint
make typecheck       # mypy + tsc
make e2e             # Playwright browser suite (2 journeys, real backend)
make evals           # golden-data AI eval harness (DeepSeek judge)
make demo-setup      # idempotent 4-role demo dataset
make dev-backend     # uvicorn :8001
make dev-frontend    # vite :3000
make backend-install # uv sync
make frontend-install# pnpm install
```

---

## Testing

| Suite | Command | Status |
|---|---|---|
| Unit + contract | `cd backend && uv run pytest ../tests/unit ../tests/contract` | ✅ 182 passing |
| Integration | `cd backend && PYTHONPATH=.. uv run pytest ../tests/integration` | ✅ 36 passing (isolated `pramya_test`, created/dropped per run) |
| Migration drift | `cd backend && uv run alembic check` | ✅ no new operations |
| Typecheck | `make typecheck` | ✅ mypy 91 files · pyright 0 errors · tsc 0 errors |
| Lint | `make lint` | ✅ ruff + oxlint clean |
| Frontend build | `cd frontend && pnpm build` | ✅ |
| E2E | `make e2e` | ✅ 2 Playwright journeys |
| Evals | `make evals` | ✅ golden-data harness (3 WARNING recorded, honest) |

Voice engine unit coverage (14 tests): hot-loop interrupt mid-TTS, generation
invalidation, auto + manual turn finalization, pause/resume/stop/cancel,
transcript + audio persistence, heartbeat, reconnect resume, audio opt-out.

---

## E2E

Playwright suite in `frontend/e2e/` (`make e2e`). It drives the **real UI
against the real backend** (vite :3000 → FastAPI :8001):

1. **Dashboard readiness** — renders real readiness from seeded demo data.
2. **Typed interview journey** — start → question (via SSE) → answer →
   evaluation → stop → history.

Requirements: `make up` (or local dev servers) + `make demo-setup` once.

Controlled voice testing: `frontend/scripts/voice_e2e_real.mjs` drives the
voice loop with a Playwright fake-device microphone fed a pre-recorded WAV,
asserting the observable event contract
(`tts_start → chunks → tts_stop → listening → audio_received → partial →
turn_ended → final → processing → answer_submitted → evaluation → next
tts_start`) plus an interrupt-mid-TTS stale-chunk check. Automated mic
testing is inherently limited (fake-device audio, no real acoustics); a
manual real-device acceptance checklist lives in
`docs/ai/VOICE_ARCHITECTURE.md`.

---

## Evals

See [Evaluation system](#evaluation-system) and `docs/EVALUATION.md`.

Golden datasets: `tests/evals/datasets/`. Judge: `deepseek-v4-flash` via the
router. Results: `tests/evals/results/`.

---

## Docker / Langfuse

- `docker-compose.yml` — postgres+pgvector (:5432), backend (:8001),
  frontend (:3000).
- `docker-compose.langfuse.yml` — self-hosted Langfuse OSS stack
  (postgres/redis/clickhouse/minio/worker/web at **:3030**), started with
  `docker compose -f docker-compose.langfuse.yml up -d`. Not auto-started
  (heavy; see `docs/operations/OBSERVABILITY.md` for startup + trace
  verification).

---

## Project structure

```
backend/app/
  ai/            # InferenceRouter · providers (deepseek httpx, oMLX) · policy · structured output
  ai/langchain/  # LangChain composition layer (RouterChatModel, chains)
  interview/     # InterviewService (state machine) · LangGraph workflow · generation
  knowledge/     # parsing · deterministic ingestion/retrieval · LlamaIndex RAG service
  voice/         # VoiceEngine (WS state machine) · ASR/TTS clients
  services/      # readiness · preparation · progress · extraction · role · demo · communication
  observability/ # Langfuse SDK facade (degradation-safe)
  api/v1/        # REST + SSE + WS routes
  domain/        # enums · schemas · errors
  repositories/  # SQLAlchemy async repos
  models/        # ORM (23 tables, one migration)
frontend/src/
  pages/         # Dashboard Setup Preparation Interview Report Progress Evidence
                 # Stories History Debrief Transcript Settings Runtime
  components/    # AppShell + design-system primitives (semantic tokens)
  hooks/         # TanStack Query hooks · useSSE
  lib/           # api client · voice client · theme
demo/            # 4-role demo fixtures (resume + JD)
prompts/         # versioned prompt files (question, eval, hints, extraction, role, report)
tests/           # unit · contract · integration · evals · (e2e lives in frontend/e2e)
docs/            # plan · ADRs · architecture · model catalog · operations
```

---

## Architecture decisions

`docs/DECISIONS.md` indexes every ADR. The ones that define the product:

- **ADR-001** framework boundaries; **ADR-002** LangGraph interview workflow
  (implemented deterministically first, realigned to LangGraph per the
  framework directive); **ADR-003** LlamaIndex knowledge layer; **ADR-004**
  router-only model access; **ADR-005** pgvector; **ADR-006** MCP boundary
  (accepted, **deferred**); **ADR-007** evidence-first evaluation;
  **ADR-008** observability; **ADR-009/024** evaluation strategy (DeepEval
  replaced by a router-bound golden-data harness — DeepEval excluded for the
  OpenAI-SDK conflict); **ADR-010** security/PII; **ADR-023** DeepSeek-only
  text + local audio/retrieval (supersedes the local-text-first reading);
  **ADR-021/022** deterministic replacement layers (superseded in the
  framework realignment).

---

## Gallery

<details>
<summary>Full-page product gallery (9 slides)</summary>

<div style="display:flex; overflow-x:auto; gap:1rem; scroll-snap-type:x mandatory; scroll-behavior:smooth; padding:1rem 0;">

<div style="flex:0 0 100%; scroll-snap-align:start;">
<h3>1 · Command center</h3>
<img src="assets/screenshots/dashboard.png" style="height:500px; width:auto; max-width:100%; object-fit:contain;" alt="Dashboard" />
</div>

<div style="flex:0 0 100%; scroll-snap-align:start;">
<h3>2 · Candidate setup</h3>
<img src="assets/screenshots/setup.png" style="height:500px; width:auto; max-width:100%; object-fit:contain;" alt="Candidate setup" />
</div>

<div style="flex:0 0 100%; scroll-snap-align:start;">
<h3>3 · Preparation</h3>
<img src="assets/screenshots/preparation.png" style="height:500px; width:auto; max-width:100%; object-fit:contain;" alt="Preparation" />
</div>

<div style="flex:0 0 100%; scroll-snap-align:start;">
<h3>4 · Evidence ledger</h3>
<img src="assets/screenshots/evidence.png" style="height:500px; width:auto; max-width:100%; object-fit:contain;" alt="Evidence" />
</div>

<div style="flex:0 0 100%; scroll-snap-align:start;">
<h3>5 · Interview workspace</h3>
<img src="assets/screenshots/interview.png" style="height:500px; width:auto; max-width:100%; object-fit:contain;" alt="Interview" />
</div>

<div style="flex:0 0 100%; scroll-snap-align:start;">
<h3>6 · Progress</h3>
<img src="assets/screenshots/progress.png" style="height:500px; width:auto; max-width:100%; object-fit:contain;" alt="Progress" />
</div>

<div style="flex:0 0 100%; scroll-snap-align:start;">
<h3>7 · Story bank</h3>
<img src="assets/screenshots/stories.png" style="height:500px; width:auto; max-width:100%; object-fit:contain;" alt="Stories" />
</div>

<div style="flex:0 0 100%; scroll-snap-align:start;">
<h3>8 · Settings</h3>
<img src="assets/screenshots/settings.png" style="height:500px; width:auto; max-width:100%; object-fit:contain;" alt="Settings" />
</div>

<div style="flex:0 0 100%; scroll-snap-align:start;">
<h3>9 · Runtime status</h3>
<img src="assets/screenshots/runtime.png" style="height:500px; width:auto; max-width:100%; object-fit:contain;" alt="Runtime" />
</div>

</div>
</details>

Light-theme variants are available in `assets/screenshots/light-*.png`; the
app ships Dark (default) / Light / System themes switchable from Settings.

---

## Known limitations

- **MCP server is deferred from V1** (ADR-006 accepted, stub only). Not
  advertised as a capability.
- **Langfuse**: SDK facade implemented; OpenTelemetry exporters and
  LangChain callbacks are **not** wired. Unconfigured → structured logs.
- **Auth**: bearer tokens for deployment-level API protection; no per-user
  accounts/sessions (single-user local model, plan §19).
- **Voice**: real-device E2E requires a microphone; automated tests use a
  fake-device WAV feed. ASR quality depends on the local Parakeet model.
- **Eval harness**: DeepSeek judge variance on borderline metrics is
  recorded as WARNING — the suite is honest, not green-washed.
- **License file is a placeholder** (see [License](#license)).
- **No CI badge**: the repository does not yet publish CI status.

---

## License

The repository ships a placeholder `LICENSE` (year/organization unfilled).
Pick a license (e.g. MIT) and fill it before publishing.

---

## Contributing

See `docs/CONTRIBUTING.md` for setup, conventions, and the definition of
done. Short version: run `make lint typecheck test`, keep the diff small and
coherent, commit per phase/feature with a human message, and never commit
secrets or local runtime state (`.runtime/`, `.pi/`).

---

## Changelog / releases

See `CHANGELOG.md` (Keep a Changelog format). Phases A–N are recorded:
framework realignment (LangChain/LangGraph/LlamaIndex), Langfuse facade,
evaluation harness, voice engine + persistence + communication analysis,
security hardening, demo mode, memory/history/debrief surfaces, browser E2E,
fresh-clone verification, and release acceptance matrix
(`docs/RELEASE_ACCEPTANCE.md`).
