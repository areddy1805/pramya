<div align="center">

<img src="assets/branding/logo.png" width="320" alt="Pramya" />

# Pramya — prove you're ready.

**An evidence-driven interview preparation workspace: persistent career
profiles, deterministic readiness, an adaptive AI interviewer (text + live
voice), and a report loop that remembers what you actually demonstrated.**

![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13-3776AB?logo=python&logoColor=white)
![TypeScript](https://img.shields.io/badge/typescript-strict-3178C6?logo=typescript&logoColor=white)
![React](https://img.shields.io/badge/react-19-61DAFB?logo=react&logoColor=black)
![FastAPI](https://img.shields.io/badge/fastapi-0.139-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/postgresql-17%20%2B%20pgvector-4169E1?logo=postgresql&logoColor=white)
![TTS](https://img.shields.io/badge/tts-pocket--tts--default-2ea44f)
![Tests](https://img.shields.io/badge/tests-322%20passing-2ea44f)

</div>

---

## Table of contents

- [Current status](#current-status)
- [What Pramya is](#what-pramya-is)
- [Screenshots](#screenshots)
- [Product demo](#product-demo)
- [Capability matrix](#capability-matrix)
- [Architecture](#architecture)
- [Profile workspace](#profile-workspace)
- [Interview intelligence](#interview-intelligence)
- [Voice architecture](#voice-architecture)
- [TTS: why Pocket is the default (measured)](#tts-why-pocket-is-the-default-measured)
- [Engineering decisions](#engineering-decisions)
- [AI / model topology](#ai--model-topology)
- [RAG architecture](#rag-architecture)
- [Observability (Langfuse)](#observability-langfuse)
- [Security model](#security-model)
- [Quick start](#quick-start)
- [Environment configuration](#environment-configuration)
- [Commands](#commands)
- [Testing / validation](#testing--validation)
- [Demo data](#demo-data)
- [Project structure](#project-structure)
- [Known limitations](#known-limitations)
- [Roadmap boundary](#roadmap-boundary)
- [License](#license)
- [Contributing](#contributing)
- [Changelog / releases](#changelog--releases)

---

## Current status

**Pramya v1.0.0** — the V1 product loop is implemented and validated for
**personal / local use**. This is the frozen v1.0 baseline; future work comes
from real usage and the post-v1 roadmap, not from a continuing build phase.

| Dimension | State |
|---|---|
| Product loop (profile → resume → role → readiness → practice → interview → report) | Implemented + validated |
| Text interview (8 modes, adaptive, voice-capable) | Implemented + validated |
| Live voice interview (Pocket TTS, Parakeet ASR, WS streaming) | Implemented + validated |
| Persistent multi-profile workspace + isolation | Implemented + validated |
| Automated suite (unit + contract + integration) | **322 passing** (233 unit/contract + 89 integration), 0 failures |
| Static checks | ruff · mypy · pyright · tsc clean; `alembic check` clean |
| Controlled browser validation | 14/14 routes clean (HTTP 200, 0 console errors) |
| Release audit (2026-08-16) | 6 P1 findings fixed, **0 P0** — see [Release acceptance](docs/RELEASE_ACCEPTANCE.md) |
| Authentication | **Known limitation** — local/dev ownership model, no multi-user auth |
| MCP server | Deferred from V1 (ADR-006, accepted) |
| Jobs / applications | **Not part of v1.0** — out of scope; see [Roadmap boundary](#roadmap-boundary) |

> **Release boundary.** v1.0.0 is validated for a single-user, local-first
> deployment on Apple Silicon with a local PostgreSQL. It is **not** a public
> multi-user SaaS: there is no per-user account system (bearer tokens are the
> deployment-level boundary, opt-in). Do not expose it to the open internet
> without an auth layer.

---

## What Pramya is

Pramya is a **persistent AI career workspace**, not an interview chatbot.
Your resume and job descriptions become a knowledge base and a competency
model; every practice answer is evaluated on 13 dimensions and turned into
**evidence**; readiness is computed deterministically from demonstrated
evidence — never from vibes; and the next interview adapts to what you
actually demonstrated.

The flagship experience is a **live spoken mock interview**: the AI
interviewer speaks (local **Pocket TTS**, Qwen3 fallback), listens to your
real speech (local Parakeet ASR), evaluates your answer with DeepSeek,
extracts evidence, and asks an adaptive follow-up — all over a WebSocket
with first-class interruption and pause/resume semantics.

The product is built as a **modular monolith**: React 19 frontend, FastAPI
backend, PostgreSQL + pgvector, DeepSeek for all text reasoning, and local
speech/retrieval models through oMLX.

Conceptual flow (as implemented):

```
User
 ↓  Career profiles (USER != PROFILE — one user owns many profiles)
 ↓  Resume · Target roles · Documents/JDs · Evidence (profile-scoped)
 ↓  Career intelligence (role analysis, competency graph, readiness)
 ↓  Interview preparation (gap-driven queue, story bank, progress)
 ↓  AI interviewer (grounded context → adaptive questions → evaluation)
 ↓  STT / LLM / TTS (Parakeet / DeepSeek / Pocket)
 ↓  Report + preparation memory (fed into the next interview)
```

There is **no static question bank**: every question is generated per
session from the candidate's own material (see
[Interview intelligence](#interview-intelligence)).

---

## Screenshots

Real captures of the frozen v1.0.0 UI (ADR-029 **Drawing Sheet**, dark
"drafting field" theme, 1440×900 viewport). The full-resolution images are
committed under `assets/screenshots/`.

<details>
<summary>View Pramya v1.0 screenshots</summary>

<table>
  <tr>
    <td align="center"><a href="assets/screenshots/dashboard.png"><img src="assets/screenshots/dashboard.png" width="300" alt="Pramya v1.0 Dashboard workspace"></a></td>
    <td align="center"><a href="assets/screenshots/profile.png"><img src="assets/screenshots/profile.png" width="300" alt="Pramya v1.0 Career profiles workspace"></a></td>
    <td align="center"><a href="assets/screenshots/preparation.png"><img src="assets/screenshots/preparation.png" width="300" alt="Pramya v1.0 Readiness and preparation orders"></a></td>
    <td align="center"><a href="assets/screenshots/interview.png"><img src="assets/screenshots/interview.png" width="300" alt="Pramya v1.0 Live voice interview setup"></a></td>
  </tr>
  <tr>
    <td align="center"><a href="assets/screenshots/report.png"><img src="assets/screenshots/report.png" width="300" alt="Pramya v1.0 Interview report with scorecard"></a></td>
    <td align="center"><a href="assets/screenshots/evidence.png"><img src="assets/screenshots/evidence.png" width="300" alt="Pramya v1.0 Evidence ledger"></a></td>
    <td align="center"><a href="assets/screenshots/progress.png"><img src="assets/screenshots/progress.png" width="300" alt="Pramya v1.0 Progress tracking"></a></td>
    <td align="center"><a href="assets/screenshots/history.png"><img src="assets/screenshots/history.png" width="300" alt="Pramya v1.0 Interview history"></a></td>
  </tr>
</table>

</details>

## Product demo

<details>
<summary>Watch the Pramya v1.0 walkthrough</summary>

> **VIDEO / GIF DEMO — COMING SOON**
>
> A short end-to-end walkthrough will be published here. It will show:
>
> Profile selection → resume/JD grounding → interview → live voice
> interaction → follow-ups → evaluation → report → preparation memory.

</details>

---

## Capability matrix

| Capability | Status | Evidence / notes |
|---|---|---|
| Persistent multi-profile workspace | Implemented + validated | `candidate_profile` container; unique `(user_id, name)`; 18+ isolation tests (ADR-026) |
| Profile switching | Implemented + validated | `user.active_profile_id` is a persisted UX preference only — server-authoritative, never an authorization boundary |
| Resume persistence | Implemented + validated | Upload (PDF/DOCX/TXT/MD) → parse → chunk → embed → index; preferred-resume pointer |
| JD persistence | Implemented + validated | Same pipeline; preferred-JD pointer; JD optional except JD-driven modes |
| Idempotent document upload | Implemented + validated | Content-hash dedup scoped to (user, profile) → `200 {status: "deduplicated"}` |
| Profile-scoped target roles | Implemented + validated | JD analysis → role model + competency graph, owned by profile |
| Profile-scoped evidence | Implemented + validated | Provenance ladder: claimed → observed → demonstrated → inferred → unknown |
| Interview grounding | Implemented + validated | Immutable per-session context snapshot (profile/resume/JD/role/evidence/prior feedback) |
| Question provenance | Implemented + validated | Every question carries `category` + `source` + `source_ref` (20-category taxonomy) |
| Follow-up reasoning | Implemented + validated | Interviewer-reasoning directives drive the next question (ADR-028) |
| Coverage + gap detection | Implemented + validated | Deterministic coverage rotation (seeded per session) + JD gap detection |
| Preparation memory | Implemented + validated | `interview_feedback` written at stop(), read by the next session |
| Deterministic scorecard + per-question feedback | Implemented + validated | Report v2: 13-dimension scorecard + per-question feedback |
| Text interview (8 modes) | Implemented + validated | general · resume · JD · technical · behavioral · project · system design · coding |
| Live voice interview | Implemented + validated | WS state machine, interrupt/pause/resume, adaptive follow-ups |
| Pocket TTS (default) | Implemented + validated | Measured 30 ms first PCM vs Qwen3 634–4333 ms (ADR-027, benchmark below) |
| Qwen3 TTS (fallback) | Implemented | `TTS_PROVIDER=qwen3`; retained for fallback/benchmarking |
| Readiness (deterministic) | Implemented + validated | Pure-function calculator; evidence coverage × importance × recency × demonstrated ability |
| Preparation queue | Implemented + validated | Gap → priority → practice items with reasons |
| History / transcript / debriefs / stories | Implemented + validated | Durable per-session record + secondary surfaces |
| Communication analysis | Implemented + validated | Measured only (speaking time, fillers, latency, interruptions); never fabricated |
| Observability (Langfuse) | Optional / OFF by default | `LANGFUSE_ENABLED=false` → no client, no worker, no network (see below) |
| Authentication | **Known limitation** | Local/dev ownership model; bearer tokens opt-in; no multi-user accounts |
| MCP server | Deferred | ADR-006 accepted, stub only |
| Jobs / applications | **Not in v1.0** | Out of scope — see [Roadmap boundary](#roadmap-boundary) |

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
        DET[Deterministic engines:<br/>readiness · preparation · coverage · communication]
        REPO[Repositories]
    end
    subgraph Data[PostgreSQL 17 + pgvector]
        DB[(user · candidate_profile · document · role · evidence<br/>session · question · answer · evaluation · chunk<br/>transcript · audio · story · debrief · feedback)]
    end
    subgraph Inference
        DS[DeepSeek v4 flash<br/>all text reasoning]
        OMLX[oMLX · local models<br/>Parakeet ASR · Qwen3-ASR<br/>BGE-M3 embeddings · reranker]
        TTS[Pocket TTS · local CPU<br/>Qwen3 fallback]
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
    WS --> TTS
    SVC --> OMLX
```

Every model invocation flows through the `InferenceRouter`: task-class
policy → provider → response, with telemetry on provider/model/latency/
tokens. Text tasks route to **DeepSeek only**; audio and retrieval stay
**local**. There is no local text LLM in the production path (ADR-023).

### Layer responsibilities

| Layer | Where | Responsibility |
|---|---|---|
| Frontend | `frontend/src/` — 14 routes, TanStack Query server state | Thin client; **never authoritative** — server state wins |
| API | `backend/app/api/v1/` — REST + SSE + WS | Contract boundary, ownership checks, error envelope |
| Services | `backend/app/services/`, `app/interview/`, `app/voice/` | Domain logic, state machines, grounding |
| Deterministic engines | readiness · preparation · coverage · progress · communication | Pure functions with golden tests — no LLM |
| Repositories | `backend/app/repositories/` | SQLAlchemy async data access |
| Database | PostgreSQL 17 + pgvector | 23 tables, migrations 0001–0007, `alembic check` clean |

Framework posture: LangGraph owns the interview workflow (MemorySaver
checkpointer; durable domain state lives in PostgreSQL); LangChain owns AI
composition over the router; LlamaIndex adapts ingestion/retrieval over
pgvector. Each is a real execution layer with explicit boundaries — see
`docs/architecture/` for the ADRs.

---

## Profile workspace

The persistence model (ADR-026) is **USER ≠ PROFILE**:

```
USER
 ├── Career Profile: "AI Engineer"
 │     ├── Resume (preferred pointer + processed chunks)
 │     ├── Target roles (analyzed JD → competency graph)
 │     ├── Documents / JDs
 │     ├── Evidence ledger
 │     └── Interview / readiness / preparation state
 └── Career Profile: "Forward Deployed Engineer"
       ├── Resume
       ├── Target roles
       ├── Documents / JDs
       ├── Evidence
       └── Interview / readiness / preparation state
```

Invariants (enforced server-side, verified by integration tests):

- **Database is authoritative.** The frontend zustand store is a UX mirror
  only; the server resolves the active profile and re-validates every
  `profile_id`.
- **Ownership path:** entity → profile → user. `document`, `role`,
  `evidence`, `readiness_snapshot`, `preparation_item`, `practice_session`
  carry `profile_id` (CASCADE); `interview_session.candidate_profile_id` is
  populated at creation.
- **`profile_id=None` never silently resolves** to a first/seed profile —
  explicit profile resolution (or the persisted active profile) or a clear
  validation error.
- **Cross-profile leakage is rejected:** documents, evidence, resumes/JDs,
  and roles are resolved strictly within the requested profile (legacy
  `profile_id IS NULL` rows are the only global rows, and only for
  explicitly legacy callers). A foreign profile's role cannot ground an
  interview or readiness computation (release-audit fix, 2026-08-16).
- **Active profile = UX preference.** `user.active_profile_id` (SET NULL)
  survives restart and switching, but is never an authorization boundary.
- **Duplicate uploads are idempotent:** identical content in the same
  (user, profile) returns `200 {status: "deduplicated"}`; the same file in a
  different profile is a distinct document.

The UI exposes profile CRUD + a header switcher (`/profile`); the current
profile drives every workspace query.

---

## Interview intelligence

Every interview is dynamically generated from the candidate's own material
(ADR-028). There is **no question bank**.

```
Profile → Resume → JD → Target role → Evidence → prior preparation memory
   ↓
Context snapshot (immutable, per session, profile-scoped)
   ↓
Question generation (grounded prompt + entity guard)
   ↓
Provenance: category · source · source_ref
   ↓
Answer evaluation (13 dimensions, evidence extraction)
   ↓
Interviewer reasoning → follow-up directive
   ↓
Next question consumes the directive (or rotates coverage)
   ↓
Coverage / gap detection → Report → preparation memory
```

- **Grounding:** the context builder assembles a snapshot (profile identity,
  resume text, JD text, role + competency graph, profile-scoped evidence,
  prior feedback) stored in `session.config["context"]` and injected into
  the question prompt. Missing pieces fail fast with an actionable message
  (profile + resume required; JD required only in JD modes).
- **Provenance:** every question records a `category` from the
  **20-category taxonomy** (`app/services/coverage.py` — single source of
  truth for prompt, guard, and tests) plus `source` and `source_ref` that
  correspond to actual available context. Provenance persists per question.
- **Anti-hallucination:** a deterministic entity guard blocks questions that
  name facts outside the snapshot; profile A's material can never appear in
  profile B's interview (context-integrity tests).
- **Follow-up reasoning:** the answer lane produces interviewer reasoning
  and a follow-up directive; the next question consumes it (deep-dive,
  clarification, challenge, topic switch) instead of blindly rotating.
- **Coverage + gaps:** deterministic coverage rotation seeded by session id
  ensures all competencies are visited; JD gap detection feeds the report.
- **Readiness:** deterministic calculator over demonstrated evidence —
  coverage × importance × recency × demonstrated ability — with confidence
  and critical gaps; versioned snapshots.
- **Report + memory:** report v2 is a deterministic scorecard (13 dimensions,
  verdict thresholds) with per-question feedback; preparation memory
  (`interview_feedback`) is written at session stop and read by the next
  session — the second interview adapts to the first.
- **Evaluation:** 13 dimensions (correctness, technical depth, clarity,
  structure, relevance, evidence, communication, tradeoff awareness,
  reasoning, confidence, specificity, seniority alignment, completeness);
  answers also emit observed-evidence rows with provenance.
- **7 interviewer styles + duration presets** in the UI (single source of
  truth in `app/services/coverage.py`).

---

## Voice architecture

The live voice interview is a real spoken loop:

```mermaid
flowchart LR
    MIC[Browser mic · PCM16 16kHz] --> WS[WebSocket /ws/voice per session]
    WS --> ENG[VoiceEngine · server-authoritative state machine]
    ENG --> ASR[Parakeet-TDT live ASR<br/>partial transcripts]
    ASR --> Q[answer → LangGraph workflow]
    Q --> DS[DeepSeek evaluation]
    DS --> NQ[adaptive next question]
    NQ --> TTS[Pocket TTS · 24 kHz PCM16<br/>Qwen3 fallback]
    TTS --> WS --> SPK[Browser playback queue]
```

- **Server-authoritative states**: idle → starting → speaking → listening →
  processing → speaking, with interrupt / pause / resume / stop / cancel
  side transitions broadcast as WS `state` events.
- **TTS provider boundary**: the engine consumes a duck-typed
  `TTSSynthesizer` seam (`synthesize` / `synthesize_stream` / `warmup`).
  Selection is configuration-driven: `TTS_PROVIDER=pocket` (default) |
  `qwen3` (fallback). No provider-specific logic in the engine (ADR-027).
- **Interruption correctness**: every TTS stream carries a `generation` id;
  interruption bumps it and cancels in-flight synthesis — **stale audio is
  never transmitted or played** (verified: 0 stale frames after interrupt).
- **Turn finalization**: automatic (RMS speech detection + silence
  watchdog) and manual (`end_turn`).
- **Playback-completion gating**: the engine stays SPEAKING until the client
  confirms real playback completion — the interviewer can never become the
  candidate through the microphone (physical-mic E2E passed 2026-08-13).
- **Barge-in**: opt-in (`VOICE_BARGE_IN_ENABLED=false` default; the
  Interrupt button is the guaranteed path).
- **Audio persistence**: **opt-in, OFF by default** (`VOICE_STORE_AUDIO`);
  when enabled, WAV + `audio_segment` rows with retention + replay endpoints.
- **Reconnect + heartbeat**: `heartbeat` → `heartbeat_ack`; reconnecting to
  an in-progress session emits `resume` with the authoritative state.
- **Degradation**: TTS down → text interviewer response; ASR down → typed
  mode. Never a silent failure.

---

## TTS: why Pocket is the default (measured)

Pocket TTS was selected from **measurement, not preference** (ADR-027).
Both providers were benchmarked on the actual development machine
(Apple Silicon M4, 16 GB) inside the actual Pramya voice path
(`scripts/tts_bench.py`, committed). These are Pramya's own results, not
upstream marketing numbers.

### TTS first PCM (warm, same machine, same texts)

| Provider | SHORT | MEDIUM | LONG |
|---|---:|---:|---:|
| Qwen3 (oMLX) | 634 ms | 2 152 ms | 4 333 ms |
| **Pocket (CPU)** | **30 ms** | **31 ms** | **31 ms** |

### TTS total generation / RTF

| Provider | Total (LONG ~12 s audio) | RTF (real-time factor) |
|---|---:|---:|
| Qwen3 | 4 333 ms | 2.9–3.0× |
| **Pocket** | **1 281 ms** | **8.3–9.0×** |

### Real Pramya voice path (WS, fake-mic, real DeepSeek + Parakeet)

| Metric | Qwen3 | Pocket |
|---|---:|---:|
| Q1 tts_start → first PCM frame | 7.35 s | **1.62 s** |
| Q2 final_transcript → first PCM frame | 9.13 s | **5.67 s** |
| 10-turn sustained first-audio median | — | **3.34 s** (3.06–3.81, no drift) |
| Stale frames after interrupt | 0 | 0 |

### Model memory

| Provider | Model RSS |
|---|---:|
| Qwen3 (oMLX resident) | ~1.71 GB |
| **Pocket (backend process)** | **~0.84–0.96 GB** (−44%) |

### Quality & lifecycle validation

- ASR round-trip (Parakeet) on both providers' output: word-perfect for
  both — no intelligibility regression on English interview speech.
- Cancellation: prompt (in-flight sentence tail burns ≤ ~1 s bounded CPU);
  0 stale WS frames; thread count returns to baseline.
- Sustained: 20-utterance sequences stable (no RSS growth); in-pipeline
  10-turn loop stable (no first-audio drift). 20–30-turn in-pipeline runs
  remain **NOT_VERIFIED**.
- Licensing: `pocket-tts` 2.1.0 MIT; weights CC-BY-4.0 (attribution);
  reference voice "alba".

> **Reading the numbers correctly.** The 30 ms figure is the TTS first-PCM
> latency, not end-to-end interview latency. The real voice-path numbers
> (1.62 s / 5.67 s) include LLM generation and ASR. Qwen3 remains available
> as `TTS_PROVIDER=qwen3` for fallback/benchmarking, with the streaming
> pipeline (segmenter, generation guards, voice profile) fully intact.

---

## Engineering decisions

Every major architectural choice is documented as an ADR with alternatives,
evidence, and consequences (`docs/DECISIONS.md`). The defining ones:

### Pocket TTS as default (ADR-027)

- **Alternatives evaluated:** Qwen3-TTS via oMLX (previous default, ADR-025)
  vs Kyutai Pocket TTS (CPU, in-process).
- **Selected:** Pocket — 21–140× lower warm first-PCM, ~3× RTF, −44% model
  RSS, real voice-path Q1 first-audio 7.35 s → 1.62 s, streaming +
  cancellation + barge-in verified. Qwen3 retained as fallback.
- **Trade-off:** Pocket adds ~1.1 GB RSS to the backend process and a torch
  dependency; it is English/single-voice.

### DeepSeek-only text inference (ADR-023)

- **Alternatives evaluated:** local 4B text model as primary (ADR-004/020
  reading), DeepSeek as escalation.
- **Selected:** DeepSeek `deepseek-v4-flash` is the **sole** production text
  LLM; local oMLX retained for audio + retrieval only. DeepSeek failure is a
  controlled provider error — no silent local-text fallback.

### Langfuse optionalization (ADR-008)

- **Selected:** observability must never be a runtime dependency.
  `LANGFUSE_ENABLED=false` (default) → no client/worker/network; structured
  logs always work; opt-in degrades safely if Langfuse is broken.

### Profile/database authority (ADR-026)

- **Selected:** PostgreSQL is authoritative; every profile-scoped operation
  is re-validated server-side; the frontend holds only a UX mirror. Isolation
  invariants are enforced in services and covered by integration tests.

### Interview orchestration (ADR-002 / ADR-022 / ADR-028)

- Deterministic service state machine first, realigned to LangGraph for the
  workflow with domain state in PostgreSQL; interview intelligence
  (grounding, provenance, follow-ups, coverage, prep memory) is deterministic
  around the LLM calls.

### Frontend freeze (ADR-029)

- The 14-route UI is frozen in the Drawing Sheet visual language
  (`DESIGN.md`); future changes are bug fixes only, smallest possible.

---

## AI / model topology

Text and reasoning are DeepSeek; speech and vectorization are local
(ADR-023), enforced by the task-class routing table and `MODEL_CATALOG`.

| Model | Provider | Responsibility |
|---|---|---|
| `deepseek-v4-flash` | DeepSeek (cloud, API key) | All text reasoning: question generation, evaluation, hints, extraction, role analysis, report synthesis, debrief/transcript analysis |
| `parakeet-tdt-0.6b-v3-int8` | oMLX (local) | **Live** ASR (`voice_live_asr_model`) |
| `Qwen3-ASR-1.7B-4bit` | oMLX (local) | Offline/archival ASR (`voice_offline_asr_model`) |
| Pocket TTS (`kyutai/pocket-tts`) | local CPU (in-process) | Default TTS — interviewer speech (`TTS_PROVIDER=pocket`) |
| `Qwen3-TTS-12Hz-0.6B-Base-MLX-4bit` | oMLX (local) | TTS fallback/benchmark (`TTS_PROVIDER=qwen3`) |
| `bge-m3-mlx-4bit` | oMLX (local) | Embeddings (1024-dim, pgvector column matches) |
| `Qwen3-Reranker-0.6B-4bit` | oMLX (local) | Retrieval reranking |

Local text-generation models (`pramya-4b`, `qwen2.5-coder-7b`) are
**prohibited in the production path**; they exist only as provider
compatibility and are never routed.

---

## RAG architecture

Documents are parsed into normalized text, chunked, embedded with BGE-M3
(local), and written to `document_chunk` (pgvector `vector(1024)` + FTS
tsvector + JSONB metadata). Retrieval fuses vector + FTS with RRF, reranks
with the local Qwen3-Reranker, and hands grounded context to the interview
workflow.

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
remains the tested fallback/reference path; the LlamaIndex retriever is the
production path used by the interview service.

---

## Observability (Langfuse)

`LANGFUSE_ENABLED` is the **one authoritative switch** — and it defaults to
**false**.

**Default (`LANGFUSE_ENABLED=false`):**

- structured telemetry remains fully active (structured JSON logs: request
  ids, spans, voice waterfall metrics);
- **no** Langfuse client initialization, **no** background worker, **no**
  network dependency;
- the Langfuse stack is not required to run Pramya.

**Opt-in (`LANGFUSE_ENABLED=true` + keys + self-hosted stack):**

```bash
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_HOST=http://127.0.0.1:3030
docker compose -f docker-compose.langfuse.yml --profile langfuse up -d
# or: PRAMYA_DEV_LANGFUSE=1 make dev
```

The backend ships a degradation-safe facade (`backend/app/observability/`):
keys alone never enable Langfuse; a broken/slow Langfuse degrades to
structured logs and **never blocks the interview/voice path** (bounded flush
at shutdown).

Traced spans: question generation, answer evaluation, hints, retrieval,
voice ASR/TTS latency, interruptions. What is **not** logged: candidate
content, transcripts, resume text, keys — telemetry carries ids + redacted
metadata only (enforced by tests).

> Honest limitation: the facade calls the Langfuse SDK directly; OTel
> exporters/OpenInference and LangChain callback handlers are not wired.
> `docs/operations/OBSERVABILITY.md` documents the actual behavior.

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
- **Ownership**: every profile-scoped operation re-validates
  user/profile server-side (404 on mismatch); session metadata + grounding
  snapshots are ownership-checked (release-audit fix).
- **Prompt injection**: system prompts carry explicit data-vs-instruction
  boundaries; untrusted content stays in the user payload;
  adversarial-document tests cover the boundary.
- **LLM output gate**: model output → Pydantic validation → application
  logic → persistence. The model can never write privileged state.
- **Secrets**: env-only, `.env` gitignored, never logged. `pip-audit`: no
  known vulnerabilities.

**Authentication limitation:** there is no per-user account system in V1 —
the product is a single-user local model; bearer tokens are the
deployment-level boundary. See [Known limitations](#known-limitations).

---

## Quick start

Requirements: Docker, Python 3.12/3.13, Node 20+, `uv`, `pnpm`, and a
running oMLX runtime with the speech/retrieval models for voice + retrieval
(`docs/operations/DEPLOYMENT.md`, `docs/MODEL_CATALOG.md`). A
`DEEPSEEK_API_KEY` is required for all text inference.

```bash
git clone https://github.com/areddy1805/pramya.git
cd pramya
cp .env.example .env              # then set DEEPSEEK_API_KEY

make up                           # Docker: postgres+pgvector (+ backend/frontend images)
make migrate                      # alembic upgrade head (0001 → 0007)
make backend-install              # uv sync
make frontend-install             # pnpm install
make demo-setup                   # optional: idempotent 4-role demo dataset
make dev-backend                  # uvicorn :8001 (oMLX owns :8000)
make dev-frontend                 # vite :3000
```

- Frontend → http://localhost:3000
- Backend API → http://localhost:8001
- API docs → http://localhost:8001/docs
- oMLX runtime → http://127.0.0.1:8000/v1
- Langfuse (optional) → http://localhost:3030

Verified from a fresh clone: fresh-DB migration builds all 23 tables, and
the backend boots with an example-only `.env` (DeepSeek shows
`configured: false` until the key is added — honest health).

---

## Environment configuration

`.env.example` documents every variable (53 keys). The important ones:

| Variable | Purpose | Default |
|---|---|---|
| `DEEPSEEK_API_KEY` | Required — all text inference | — |
| `APP_PORT` | Backend port (oMLX owns 8000) | `8001` |
| `DATABASE_URL` | Asyncpg DSN | `postgresql+asyncpg://pramya:pramya@localhost:5432/pramya` |
| `OMLX_BASE_URL` / `OMLX_API_KEY` | Local oMLX runtime | `http://127.0.0.1:8000/v1` |
| `TTS_PROVIDER` | Pocket (default) or qwen3 fallback | `pocket` |
| `VOICE_LIVE_ASR_MODEL` / `VOICE_OFFLINE_ASR_MODEL` / `VOICE_TTS_MODEL` | Voice model routing (Parakeet / Qwen3-ASR / Qwen3-TTS) | set |
| `VOICE_BARGE_IN_ENABLED` | Voice-triggered barge-in (opt-in) | `false` |
| `VOICE_STORE_AUDIO` / `VOICE_RETENTION_DAYS` | Audio persistence — **opt-in** | `false` / `30` |
| `LANGFUSE_ENABLED` | ONE switch for observability | `false` |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` | Optional Langfuse OSS | unset |
| `CORS_ORIGINS` | Allowed browser origins | `http://localhost:3000` |
| `API_TOKENS` | Optional bearer tokens (empty = auth off) | — |
| `RATE_LIMIT_RPM` | Per-IP rate limit (0 = off) | `0` |

---

## Commands

```bash
make up                # Docker infra (postgres, backend, frontend)
make down
make migrate           # alembic upgrade head
make test              # unit + contract (233 passing)
make test-integration  # integration suite on isolated pramya_test DB (89 passing)
make lint              # ruff + oxlint
make typecheck         # mypy + tsc
make e2e               # Playwright browser suite (2 journeys, real backend)
make evals             # golden-data AI eval harness (DeepSeek judge)
make demo-setup        # idempotent 4-role demo dataset
make dev-backend       # uvicorn :8001
make dev-frontend      # vite :3000
make backend-install   # uv sync
make frontend-install  # pnpm install
```

---

## Testing / validation

| Suite | Command | Result |
|---|---|---|
| Unit + contract | `cd backend && uv run pytest ../tests/unit ../tests/contract` | ✅ **233 passing** |
| Integration (real pgvector) | `cd backend && PYTHONPATH=.. uv run pytest ../tests/integration` | ✅ **89 passing** (isolated `pramya_test`, created/dropped per run; migrations exercised from zero) |
| Migration drift | `cd backend && uv run alembic check` | ✅ no new operations |
| Lint | `make lint` | ✅ ruff (app + tests) + oxlint clean |
| Typecheck | `make typecheck` | ✅ mypy 98 files · pyright 0 errors · tsc 0 errors |
| Frontend build | `cd frontend && pnpm build` | ✅ production build succeeds |
| Controlled browser probe | 14 routes vs live backend | ✅ 14/14 HTTP 200, 0 console errors |
| E2E | `make e2e` | ✅ 2 Playwright journeys (real backend) |
| Evals | `make evals` | Golden-data harness; recorded run 95 checks, 0 FAIL, 3 WARNING |

Coverage highlights:

- **Profile isolation** — `tests/integration/test_context_integrity.py` (21):
  resume strictly profile-scoped, no-resume never borrows, foreign role
  rejected, ownership on session reads.
- **Interview productization** — `test_interview_productization.py`:
  grounding, provenance, follow-up directives, coverage, prep memory.
- **Voice engine** — `test_voice_engine.py` + `test_realtime_voice.py` +
  `test_tts_providers.py`: hot-loop interrupt mid-TTS, generation
  invalidation, auto + manual finalization, pause/resume/stop/cancel,
  persistence, reconnect, opt-out paths.
- **Security/observability** — `test_security.py`, `test_prompt_injection.py`,
  `test_observability.py` (PII redaction).

Distinct validation kinds (not collapsed):

| Kind | Status |
|---|---|
| Automated tests | ✅ 233 unit/contract + 89 integration, all green |
| Controlled browser validation | ✅ 14/14 routes, 0 console errors (release audit 2026-08-16) |
| Real E2E evidence | ✅ text journey + physical-mic voice E2E passed earlier (recorded); **not re-run in the release audit** |
| Benchmark evidence | ✅ TTS benchmark (ADR-027) + real voice-path measurements |
| Eval suite (DeepSeek judge) | Recorded 95 checks / 0 FAIL / 3 WARNING; not re-run post-audit (costs live LLM inference) |

---

## Demo data

A one-command, **idempotent** demo dataset for the full product:

```bash
make demo-setup
```

or via the UI: **Settings → Demo data → Load demo data**, or the API:
`POST /api/v1/demo/setup`.

It creates (for the default user) a candidate profile, 4 demo roles
(`demo/roles/`: Senior Full Stack / Backend / Frontend Engineer, Senior
Product Manager — each with a resume + JD fixture), then runs the real
pipeline: resume parse → chunk → embed → index → extraction → claimed
evidence ledger; JD analysis → competency graph; readiness + critical gaps;
preparation queue. Re-running is safe: documents de-duplicate by content
hash, roles by title, evidence by source reference.

---

## Project structure

```
backend/app/
  ai/            # InferenceRouter · providers (deepseek httpx, oMLX) · policy · structured output
  ai/langchain/  # LangChain composition layer (RouterChatModel, chains)
  interview/     # InterviewService (state machine) · LangGraph workflow · generation
  knowledge/     # parsing · deterministic ingestion/retrieval · LlamaIndex RAG service
  voice/         # VoiceEngine (WS state machine) · ASR/TTS clients · Pocket provider
  services/      # readiness · preparation · progress · extraction · role · demo · communication
  observability/ # Langfuse SDK facade (degradation-safe, off by default)
  api/v1/        # REST + SSE + WS routes
  domain/        # enums · schemas · errors
  repositories/  # SQLAlchemy async repos
  models/        # ORM (23 tables, one migration lineage)
frontend/src/
  pages/         # Dashboard Setup Preparation Interview Report Progress Evidence
                 # Stories History Debrief Transcript Settings Runtime (+Profile)
  components/    # AppShell + design-system primitives (Drawing Sheet canon)
  hooks/         # TanStack Query hooks · useSSE
  lib/           # api client · voice client · theme
demo/            # 4-role demo fixtures (resume + JD)
prompts/         # versioned prompt files (question, eval, hints, extraction, role, report)
tests/           # unit · contract · integration · evals (e2e lives in frontend/e2e)
docs/            # plan · ADRs · architecture · model catalog · operations · memory
```

---

## Known limitations

- **Authentication** — no per-user account system in V1: local/dev ownership
  model (client-supplied `user_id`), bearer tokens opt-in. Not a public
  multi-user deployment.
- **Pocket TTS** — English-only, single voice ("alba"); no multilingual
  switching. Adds ~1.1 GB RSS to the backend process once loaded (net memory
  still lower than Qwen3-in-oMLX).
- **Voice validation** — 20–30-turn in-pipeline runs NOT_VERIFIED; real-device
  E2E requires a microphone (automated tests use fake-device WAV).
- **Audio persistence** — opt-in, OFF by default (`VOICE_STORE_AUDIO=false`);
  enable only with an explicit decision.
- **MCP server** — deferred from V1 (ADR-006 accepted, stub only).
- **Langfuse** — SDK facade implemented; OTel exporters and LangChain
  callbacks not wired. Off by default.
- **Eval harness** — DeepSeek judge variance on borderline metrics recorded
  as WARNING, not gamed to PASS.
- **Jobs / applications** — not implemented in v1.0 (out of scope; the
  repository holds the career-workspace foundation, not an application
  submission pipeline).
- **License file is a placeholder** (see [License](#license)).

---

## Roadmap boundary

| Bucket | Content |
|---|---|
| **CURRENT (v1.0.0)** | Persistent multi-profile workspace, resume/JD/role/evidence pipelines, deterministic readiness + preparation, dynamic grounded interviews (text + voice), reports + preparation memory, history/debriefs/stories, observability facade |
| **VALIDATED** | 322 automated tests green; ruff/mypy/pyright/tsc clean; alembic check clean; 14/14 route probe; TTS + voice-path benchmarks; physical-mic + text E2E evidence (recorded) |
| **KNOWN LIMITATIONS** | Auth (local ownership model), Pocket English/single-voice, audio opt-in, MCP deferred, eval variance, jobs/applications out of scope |
| **POST-v1 (future)** | Auth + multi-user, MCP read surface, OTel instrumentation, streaming-ASR upgrade path (Nemotron), TTS candidates, distribution packaging, real-world-usage-driven improvements |

---

## License

The repository ships a placeholder `LICENSE` (year/organization unfilled).
Pick a license (e.g. MIT) and fill it before publishing.

---

## Contributing

See `docs/CONTRIBUTING.md` for setup, conventions, and the definition of
done. Short version: run `make lint typecheck test`, keep the diff small and
coherent, commit per feature with a human message, and never commit secrets
or local runtime state (`.runtime/`, `.pi/`).

---

## Changelog / releases

See `CHANGELOG.md` (Keep a Changelog format). v1.0.0 is the current release;
the `[Unreleased]` section is reserved for post-v1.0 work.
