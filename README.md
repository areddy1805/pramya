<p align="center">
  <img src="assets/branding/logo.png" alt="Pramya" width="320" height="320">
</p>

<p align="center">
  <strong>Evidence-driven AI interview preparation.</strong>
</p>

<p align="center">
  Turn a resume, a target role, and interview performance into a measurable,
  evidence-backed competency model — then practice it in adaptive text and
  live voice interviews.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12%20%7C%203.13-3776AB" alt="Python 3.12 | 3.13">
  <img src="https://img.shields.io/badge/React-19-61DAFB" alt="React 19">
  <img src="https://img.shields.io/badge/TypeScript-strict-3178C6" alt="TypeScript strict">
  <img src="https://img.shields.io/badge/FastAPI-0.139-009688" alt="FastAPI">
  <img src="https://img.shields.io/badge/PostgreSQL-17%20%2B%20pgvector-4169E1" alt="PostgreSQL 17 + pgvector">
  <img src="https://img.shields.io/badge/Docker-compose-2496ED" alt="Docker compose">
  <img src="https://img.shields.io/badge/DeepSeek-deepseek--v4--flash-4D6BFE" alt="DeepSeek V4 Flash">
  <img src="https://img.shields.io/badge/oMLX-local%20MLX-8B5CF6" alt="oMLX local runtime">
  <img src="https://img.shields.io/badge/tests-164%20passing-2EA44F" alt="164 tests passing (local run)">
  <img src="https://img.shields.io/badge/MIT-lightgrey" alt="License undeclared">
</p>

<p align="center">
  <a href="#architecture">Architecture</a> ·
  <a href="#ai-architecture">AI architecture</a> ·
  <a href="#retrieval-rag">RAG</a> ·
  <a href="#live-voice-interview">Voice</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="#documentation">Documentation</a>
</p>

---

## One sentence

**Pramya turns a resume and a target job description into an evidence-backed
competency model, then continuously improves that model through adaptive text
and live voice interviews.**

## The core loop

```mermaid
flowchart LR
    A[Resume + Job Description] --> B[Candidate Evidence]
    A --> C[Competency Model]
    C --> D[Readiness]
    D --> E[Preparation]
    E --> F[Adaptive Interview]
    F --> G[Evaluation]
    G --> B
```

Pramya is a closed learning loop. Interview performance does not disappear
after a session — it becomes new evidence that updates the candidate model,
which changes the next interview, which produces more evidence.

---

## Product overview

Pramya is a single-user interview preparation workspace for engineers who want
more than a chatbot. It ingests a resume and a job description, builds a
competency model for the target role, tracks evidence about the candidate
(claimed → observed → demonstrated → inferred → unknown), computes a
deterministic readiness score with explicit reasons, generates a prioritized
preparation queue, and runs mock interviews that produce real evaluations and
new evidence.

The system is deliberately split: **deterministic engines** own readiness math,
gap analysis, state invariants, and persistence; **LLMs** are used only where
semantic reasoning is required (question generation, answer evaluation,
extraction, reports) — and every LLM decision flows through one observable
inference boundary.

## Why Pramya?

Four engineering principles shape the system:

1. **Evidence over scores.** A readiness number without evidence is not useful.
   Every score is traceable to evidence records with provenance status, and
   every evaluation persists the claims it observed.

2. **Deterministic where possible.** Readiness calculation, gap detection,
   preparation queueing, interview state transitions, and answer idempotency
   are pure, golden-test-verified logic — not LLM output. LLMs are reserved
   for semantic reasoning.

3. **Frameworks where they create leverage.** The plan called for LangGraph,
   LlamaIndex, LangChain, and Langfuse. After implementation, the interview
   orchestration and knowledge layers were built as **deterministic
   application engines** (ADRs [021](docs/DECISIONS.md) and
   [022](docs/DECISIONS.md)) because they satisfy every acceptance criterion
   with less churn and no loss of boundary integrity. LangChain / LangGraph /
   LlamaIndex / Langfuse are **not dependencies** of the current implementation.

4. **Closed-loop improvement.** Answers become evidence; evidence becomes
   readiness; readiness becomes the next interview.

## Features

| Capability | What it does | Status |
|---|---|---|
| Candidate intelligence | Builds an evidence-backed candidate model from a resume | Implemented |
| Role intelligence | Converts a JD into competency requirements with importance | Implemented |
| Evidence ledger | Tracks claimed / observed / demonstrated / inferred evidence with correction | Implemented |
| Hybrid retrieval (RAG) | Vector + FTS + RRF + rerank grounded in candidate/role context | Implemented (pipeline) — runtime data not yet indexed |
| Adaptive interviews | Questioning changes with history, evidence, difficulty, seniority | Implemented |
| Evaluation | Scores answers across 13 structured dimensions with evidence extraction | Implemented |
| Live voice interviews | Real-time ASR → reasoning → TTS with interrupt-safe state machine | Implemented (experimental — see [Voice](#live-voice-interview)) |
| Readiness | Deterministic competency readiness with critical gaps | Implemented |
| Preparation | Converts gaps into a prioritized practice queue | Implemented |
| Reports | Evidence-backed final interview synthesis | Implemented |
| Progress | Longitudinal aggregation across completed evaluations | Implemented |
| Story bank | Situation/Task/Action/Result records | Implemented |
| Transcript analysis | Paste a transcript → structured questions/answers/weaknesses | Implemented |
| Observability | Structured JSON logs, request IDs, routing decisions | Implemented (Langfuse: not integrated) |
| Evals | Golden-data harness: question-gen, answer-eval, extraction, RAG, adaptation, voice | Implemented (`make evals`, judge = deepseek-v4-flash) |
| MCP | Expose Pramya capabilities to external AI clients | Not implemented (ADR-006 accepted, unbuilt) |
| Interview memory | Durable per-session record: questions, answers, scores, hints | Implemented (interview record + transcript view) |
| History & debriefs | Session history, real-interview debriefs with structured analysis | Implemented |
| Demo mode | Idempotent 4-role demo dataset via API/`make demo-setup` | Implemented |

---

## Visual tour

<details>
<summary><b>▶ View product tour</b> (click to open; swipe or use the arrows to browse)</summary>

<div style="display:flex; overflow-x:auto; scroll-snap-type:x mandatory; scroll-behavior:smooth; padding:4px 0;">

<!-- 1 / 9 -->
<div id="tour-1" style="flex:0 0 100%; scroll-snap-align:center; text-align:center; padding:0 8px;">
  <h3 align="center">Command center</h3>
  <p align="center">
    <img src="assets/screenshots/dashboard.png" alt="Pramya dashboard" style="height:500px; width:auto; max-width:100%; object-fit:contain;">
  </p>
  <p align="center"><em>Readiness with its reasons — evidence coverage, critical gaps, confidence — and the next recommended practice. Not an unexplained percentage.</em></p>
  <p align="center"><a href="#tour-9" aria-label="Previous slide">←</a>&nbsp; 1 / 9 &nbsp;<a href="#tour-2" aria-label="Next slide">→</a></p>
</div>

<!-- 2 / 9 -->
<div id="tour-2" style="flex:0 0 100%; scroll-snap-align:center; text-align:center; padding:0 8px;">
  <h3 align="center">Candidate setup</h3>
  <p align="center">
    <img src="assets/screenshots/setup.png" alt="Pramya setup" style="height:500px; width:auto; max-width:100%; object-fit:contain;">
  </p>
  <p align="center"><em>Profile + resume upload + JD analysis. The pipeline is staged visibly: upload → parse → index → extract → analyze.</em></p>
  <p align="center"><a href="#tour-1" aria-label="Previous slide">←</a>&nbsp; 2 / 9 &nbsp;<a href="#tour-3" aria-label="Next slide">→</a></p>
</div>

<!-- 3 / 9 -->
<div id="tour-3" style="flex:0 0 100%; scroll-snap-align:center; text-align:center; padding:0 8px;">
  <h3 align="center">Preparation map</h3>
  <p align="center">
    <img src="assets/screenshots/preparation.png" alt="Pramya preparation" style="height:500px; width:auto; max-width:100%; object-fit:contain;">
  </p>
  <p align="center"><em>Readiness per competency, critical gaps, and the prioritized practice queue — every item has a reason.</em></p>
  <p align="center"><a href="#tour-2" aria-label="Previous slide">←</a>&nbsp; 3 / 9 &nbsp;<a href="#tour-4" aria-label="Next slide">→</a></p>
</div>

<!-- 4 / 9 -->
<div id="tour-4" style="flex:0 0 100%; scroll-snap-align:center; text-align:center; padding:0 8px;">
  <h3 align="center">Evidence ledger</h3>
  <p align="center">
    <img src="assets/screenshots/evidence.png" alt="Pramya evidence ledger" style="height:500px; width:auto; max-width:100%; object-fit:contain;">
  </p>
  <p align="center"><em>Every claim with provenance status — claimed, observed, demonstrated, inferred — and correction controls (promote / demote).</em></p>
  <p align="center"><a href="#tour-3" aria-label="Previous slide">←</a>&nbsp; 4 / 9 &nbsp;<a href="#tour-5" aria-label="Next slide">→</a></p>
</div>

<!-- 5 / 9 -->
<div id="tour-5" style="flex:0 0 100%; scroll-snap-align:center; text-align:center; padding:0 8px;">
  <h3 align="center">Interview workspace</h3>
  <p align="center">
    <img src="assets/screenshots/interview.png" alt="Pramya text interview" style="height:500px; width:auto; max-width:100%; object-fit:contain;">
  </p>
  <p align="center"><em>The focused text-interview workspace: interviewer state, question, progressive hints, answer, and live evaluation events over SSE.</em></p>
  <p align="center"><a href="#tour-4" aria-label="Previous slide">←</a>&nbsp; 5 / 9 &nbsp;<a href="#tour-6" aria-label="Next slide">→</a></p>
</div>

<!-- 6 / 9 -->
<div id="tour-6" style="flex:0 0 100%; scroll-snap-align:center; text-align:center; padding:0 8px;">
  <h3 align="center">Progress</h3>
  <p align="center">
    <img src="assets/screenshots/progress.png" alt="Pramya progress" style="height:500px; width:auto; max-width:100%; object-fit:contain;">
  </p>
  <p align="center"><em>Competency trends and interview history across sessions — progress is aggregated only from completed evaluations.</em></p>
  <p align="center"><a href="#tour-5" aria-label="Previous slide">←</a>&nbsp; 6 / 9 &nbsp;<a href="#tour-7" aria-label="Next slide">→</a></p>
</div>

<!-- 7 / 9 -->
<div id="tour-7" style="flex:0 0 100%; scroll-snap-align:center; text-align:center; padding:0 8px;">
  <h3 align="center">Story bank</h3>
  <p align="center">
    <img src="assets/screenshots/stories.png" alt="Pramya stories" style="height:500px; width:auto; max-width:100%; object-fit:contain;">
  </p>
  <p align="center"><em>Situation / Task / Action / Result records with metrics — the raw material for behavioral answers.</em></p>
  <p align="center"><a href="#tour-6" aria-label="Previous slide">←</a>&nbsp; 7 / 9 &nbsp;<a href="#tour-8" aria-label="Next slide">→</a></p>
</div>

<!-- 8 / 9 -->
<div id="tour-8" style="flex:0 0 100%; scroll-snap-align:center; text-align:center; padding:0 8px;">
  <h3 align="center">Settings</h3>
  <p align="center">
    <img src="assets/screenshots/settings.png" alt="Pramya settings" style="height:500px; width:auto; max-width:100%; object-fit:contain;">
  </p>
  <p align="center"><em>Appearance — Dark (default) / Light / System — plus application status and paste-a-transcript analysis.</em></p>
  <p align="center"><a href="#tour-7" aria-label="Previous slide">←</a>&nbsp; 8 / 9 &nbsp;<a href="#tour-9" aria-label="Next slide">→</a></p>
</div>

<!-- 9 / 9 -->
<div id="tour-9" style="flex:0 0 100%; scroll-snap-align:center; text-align:center; padding:0 8px;">
  <h3 align="center">Runtime</h3>
  <p align="center">
    <img src="assets/screenshots/runtime.png" alt="Pramya runtime status" style="height:500px; width:auto; max-width:100%; object-fit:contain;">
  </p>
  <p align="center"><em>Provider health, model registry, and the deterministic routing policy — text → DeepSeek, audio + retrieval → oMLX (ADR-023).</em></p>
  <p align="center"><a href="#tour-8" aria-label="Previous slide">←</a>&nbsp; 9 / 9 &nbsp;<a href="#tour-1" aria-label="Next slide">→</a></p>
</div>

</div>

> A committed live-voice interview screenshot does not exist yet — it is the
> next capture to add once the voice workspace is polished. The voice feature
> itself is functional and described below.

</details>

---

## Architecture

```mermaid
flowchart TB
    subgraph FE["Frontend — React 19 · TypeScript strict · Vite"]
        UI["Pages: Dashboard, Setup, Preparation, Interview,\nReport, Progress, Evidence, Stories, Settings, Runtime"]
        VC["VoiceClient — AudioWorklet capture + playback"]
    end

    subgraph API["API — FastAPI :8001"]
        REST["REST /api/v1 · 40+ endpoints"]
        SSE["SSE /interviews/{id}/events"]
        WS["WS /ws/voice/{id} — control + binary PCM16"]
    end

    subgraph APP["Application layer — deterministic engines"]
        IS["InterviewService — state machine\n(create/begin/question/answer/hint/\npause/resume/stop/cancel/report)"]
        RS["Readiness · Preparation · Progress"]
        KS["Knowledge — parse → chunk → embed →\npgvector → hybrid retrieval → rerank"]
        EV["Evidence · Role · Extraction services"]
        V["VoiceEngine — hot receive loop,\nbackground TTS/ASR/LLM tasks"]
    end

    subgraph AI["Inference boundary"]
        R["InferenceRouter"]
        POL["Task policy — ADR-023\nall text → deepseek-v4-flash, no fallback"]
        SO["Structured output — schema validate,\nbounded retry, typed error"]
    end

    subgraph EXT["External + local"]
        DS["DeepSeek API — text reasoning"]
        O["oMLX :8000 — Parakeet ASR · Qwen3-TTS\nBGE-M3 embed · Qwen3-Reranker"]
    end

    subgraph DB["Persistence"]
        PG[("PostgreSQL 17 + pgvector\n22 tables — user, evidence, interview,\nevaluation, transcript_segment, …")]
    end

    UI --> REST & SSE
    VC --> WS
    REST --> IS & RS & KS & EV
    WS --> V
    IS --> R & KS & PG
    RS --> PG
    KS --> R
    EV --> R
    V --> IS
    R --> POL
    POL --> DS
    R --> O
    KS --> O
    V --> O
    V --> PG
```

**Deliberately absent from the diagram:** LangGraph, LlamaIndex, LangChain,
and Langfuse are not part of the runtime. Interview orchestration is a
deterministic service state machine (ADR-022); knowledge ingestion/retrieval
is deterministic application code (ADR-021); observability is structured JSON
logs with request correlation. See [AI architecture](#ai-architecture) for the
division of responsibility and the documented swap targets.

### Runtime flows

**Text interview**

```
POST /interviews (mode=text)
  → begin → questions (DeepSeek, adaptive)
  → answers (idempotency-keyed)
      → retrieval context (top_k=3, degrades gracefully)
      → DeepSeek evaluation (13 dimensions) → evaluation row
      → evidence rows (OBSERVED, source=answer)
  → SSE: question / evaluation / hint / session_status
  → GET /interviews/{id}/report (DeepSeek synthesis)
```

**Live voice interview**

```
WS /ws/voice/{id}?user_id=N
  question → tts_start{generation} → PCM16 24kHz chunks → tts_stop → listening
  mic PCM16 16kHz frames → Parakeet partials (~2s) → silence watchdog / end_turn
  final transcript → DeepSeek submit_answer → evaluation → next question
  interrupt → generation bump → stale chunks dropped on both sides
```

---

## AI architecture

```mermaid
flowchart LR
    U["Interview Engine / Services"] --> R["InferenceRouter"]
    R --> POL["Task policy — ADR-023"]
    POL -->|all text| DS["DeepSeek V4 Flash"]
    POL -->|embedding| B["BGE-M3 · oMLX"]
    POL -->|rerank| Q["Qwen3-Reranker · oMLX"]
    POL -->|live ASR| P["Parakeet-TDT · oMLX"]
    POL -->|TTS| T["Qwen3-TTS · oMLX"]
    DS --> SO["Structured output — validate, retry, reject"]
    R --> LOG["routing decision log — task, model, provider, latency, tokens"]
```

**Division of responsibility:**

| Component | Actual role in Pramya |
|---|---|
| InferenceRouter | Single entry point for all model access; logs every routing decision (task, model, provider, degraded flag, latency, tokens) |
| Task policy | Maps task classes to models. All text → `deepseek-v4-flash` with **no fallback chain** (a DeepSeek failure is a controlled provider error, never a silent local swap). Embedding/rerank → oMLX. Voice models are configured outside the router and called by the voice layer directly |
| Structured output | Pydantic schema → JSON-schema prompt → generation → validation → bounded retry with feedback → typed error. Invalid model output never becomes application state |
| DeepSeek | All text reasoning: question generation, answer evaluation, extraction, role analysis, hints, reports, transcript analysis. httpx-based OpenAI-compatible provider; thinking off by default |
| oMLX | Local runtime for Parakeet-TDT 0.6B v3 (live ASR), Qwen3-ASR 1.7B (offline/archival), Qwen3-TTS 12Hz 0.6B (interviewer speech), BGE-M3 (embeddings), Qwen3-Reranker-0.6B (rerank) |
| Langfuse | **Not integrated.** Config fields exist; no SDK, no traces. Structured JSON logs are the operational mechanism today |
| LangGraph / LangChain / LlamaIndex | **Not dependencies.** Interview orchestration and knowledge layers are deterministic engines (ADR-021/022) that satisfy the same acceptance criteria; the ADRs document them as swap targets behind the same service interfaces |
| MCP | **Not implemented.** ADR-006 accepted; planned read-only surface (see [MCP](#mcp)) |

---

## Retrieval (RAG)

```mermaid
flowchart LR
    DOC["Resume / Role documents"] --> PARSE["Parsing — pypdf / python-docx / markdown-it-py"]
    PARSE --> CHUNK["Deterministic chunker — 1200 chars / 200 overlap"]
    CHUNK --> EMBED["BGE-M3 embedding · oMLX"]
    EMBED --> PG[("PostgreSQL + pgvector — vector(1024)")]
    PG --> RETR["Hybrid retrieval — vector cosine + FTS"]
    RETR --> RRF["RRF fusion — k=60"]
    RRF --> RERANK["Qwen3-Reranker · oMLX"]
    RERANK --> CTX["Context assembly — top_k=3"]
    CTX --> EVAL["Evaluation / question generation"]
    EMBED -.embedding down.-> FTS["FTS-only degradation"]
    RERANK -.rerank down.-> RRF["RRF order fallback"]
```

The pipeline is implemented and integration-tested (idempotent re-indexing,
hybrid recall, rerank ordering). **Operational caveat:** in the reference
environment, documents were parsed but never indexed at runtime, so the live
retrieval store is currently empty — indexing (`POST /documents/{id}/index`)
is exercised by tests, not yet by a populated demo run.

## Live voice interview

**Status: implemented and partially verified.** One controlled real-model
end-to-end run (2026-08-12) passed the full loop with real oMLX models
(Parakeet ASR, Qwen3-TTS) and DeepSeek: question TTS → mic PCM → partial
transcripts → turn end → evaluation → next question TTS — plus an interrupt
mid-TTS with **zero stale chunks**. This is a single verified run against a
fake microphone device fed with real TTS speech; it is not yet release-grade.

```mermaid
flowchart LR
    MIC["Microphone"] --> AW["AudioWorklet — PCM16 16kHz"]
    AW --> WS1["WebSocket"]
    WS1 --> VE["VoiceEngine — server-authoritative state machine"]
    VE -->|accumulated audio ~2s| ASR["Parakeet ASR — partials"]
    VE -->|end_turn — final transcript| SUB["DeepSeek submit_answer"]
    SUB --> EVAL["Evaluation + evidence"]
    EVAL --> QN["Next question"]
    QN --> TTS["Qwen3-TTS — full utterance"]
    TTS --> CH["200ms PCM16 24kHz chunks — generation-gated"]
    CH --> WS2["WebSocket"]
    WS2 --> PLAY["AudioWorklet playback"]
    INT["interrupt / pause / stop"] --> GEN["generation bump"]
    GEN --> CH
    INT --> PLAY
```

**Correctness guarantees implemented and tested:**

- The WS receive loop never awaits TTS/ASR/LLM/DB work — those run as
  background tasks, so interrupt/pause/stop are always receivable mid-speech.
- Every TTS stream carries a `generation` id (`tts_start{generation}` /
  `tts_stop{generation}`). Server skips chunks whose generation no longer
  matches; the client drops binary frames unless state is `speaking` and the
  generation is current. Interrupt invalidates both sides.
- Turn finalization is dual: automatic (RMS energy → silence watchdog,
  `voice_silence_seconds`) and manual (`end_turn` / "Done speaking").
- Completed turns persist `transcript_segment` rows (verified in the
  reference DB); audio segments are **not** persisted.
- Mic permission failures map to typed, actionable codes
  (`permission_denied` / `device_unavailable` / `mic_unavailable`).
- TTS failure degrades to a text interviewer response (`tts_unavailable`);
  ASR failure surfaces as a typed error.

**Incomplete / experimental:**

- No audio persistence, replay, reconnect, or heartbeat (connection loss needs
  manual reconnect; server state survives).
- No automated real-microphone test — the passing E2E used a fake device.
- No communication analysis (fillers, pauses, verbosity).
- Offline ASR (Qwen3-ASR) path and manual-transcript ASR fallback not exercised.

Protocol details: [voice WebSocket](#api--websocket) and
[docs/ai/VOICE_ARCHITECTURE.md](docs/ai/VOICE_ARCHITECTURE.md).

---

## Observability

**Honest status: structured logs, not Langfuse.**

- Structured single-line JSON logs with a `request_id` contextvar; middleware
  assigns/echoes `X-Request-ID` for request correlation.
- Every AI routing decision is logged: task, provider, model, degraded flag,
  latency (ms), and token usage. DeepSeek usage includes cache-hit/miss tokens
  for cost visibility.
- **Langfuse is NOT integrated.** `.env.example` and `Settings` carry
  `LANGFUSE_*` fields; there is no SDK dependency, no Docker service, and no
  trace emission. `docs/operations/OBSERVABILITY.md` describes the intended
  wiring, not current behavior.
- ASR/TTS latency, time-to-first-audio, and interruption counts are **not**
  yet instrumented.

---

## Evaluation

Two distinct meanings — Pramya separates them:

1. **Product scoring:** the interview evaluates the *candidate* across 13
   dimensions (correctness, depth, clarity, structure, relevance, evidence,
   communication, tradeoff awareness, reasoning, confidence, specificity,
   seniority alignment, completeness) with structured DeepSeek output. This is
   a product feature with versioned evaluation records.
2. **AI-system evaluation:** a suite that evaluates *Pramya itself* (question
   generation quality, evaluation accuracy, RAG grounding, adaptation,
   structured-output robustness, voice behavior). Implemented as a
   golden-data pytest harness under `tests/evals` with deepseek-v4-flash as
   the judge (via the InferenceRouter — no router bypass). Phase F status:
   COMPLETE WITH KNOWN WARNINGS (borderline DeepSeek judge variance is
   recorded as WARNING, never gamed to PASS).

---

## MCP

**Not implemented.** ADR-006 (`docs/architecture/ADR-006-mcp-boundary.md`)
defines the intended surface: a bounded, read-only interoperability boundary
(separate process, same services) so external AI clients can query Pramya
state. Planned tools (not yet built):

- `get_candidate_profile`
- `get_role`
- `get_readiness`
- `get_preparation`
- `get_evidence`
- `get_interview_history`

The boundary rule is fixed: MCP must never duplicate domain logic or become
the internal application architecture.

---

## Technology stack

| Layer | Technology | Purpose | Status |
|---|---|---|---|
| UI | React 19 · TypeScript strict · Vite | Product interface | Used |
| State/data | TanStack Query · Zustand | Server state, theme store | Used |
| Styling | Tailwind CSS 4 — semantic tokens | Dark-first design system (Dark/Light/System) | Used |
| API | FastAPI 0.139 · uvicorn | REST + SSE + WebSocket | Used |
| Workflow | — (deterministic state machine) | Interview orchestration | Used (ADR-022) |
| RAG | — (deterministic pipeline) | Ingestion + hybrid retrieval | Used (ADR-021) |
| LLM | DeepSeek V4 Flash (`deepseek-v4-flash`) | All text reasoning | Used (cloud) |
| ASR | Parakeet-TDT 0.6B v3 | Live speech recognition | Used (local) |
| ASR (offline) | Qwen3-ASR 1.7B | Archival/recorded path | Configured, path not exercised |
| TTS | Qwen3-TTS 12Hz 0.6B | Interviewer speech | Used (local) |
| Embeddings | BGE-M3 (oMLX) | Semantic representation (1024-d) | Used (local) |
| Reranking | Qwen3-Reranker-0.6B (oMLX) | Retrieval precision | Used (local) |
| Runtime | oMLX | Local model serving (:8000, serialized) | Used |
| Database | PostgreSQL 17 + pgvector | Persistent state + vector search | Used |
| ORM/migrations | SQLAlchemy 2.0 async · Alembic | Data access + schema | Used |
| Observability | Structured JSON logs + request IDs | Correlation | Used (Langfuse: not integrated) |
| Evaluation suite | — | AI-system quality | Planned |
| MCP | — | External AI interoperability | Planned |
| Testing | pytest · pytest-asyncio · Playwright scripts | Unit/contract/integration + visual QA | Used |
| Packaging | uv · pnpm | Dependencies | Used |
| Deployment | Docker Compose · GitHub Actions | Local dev + CI | Used (fresh-clone unverified) |

---

## Quick start

Requires: Docker, Python 3.12+, Node 20+, `uv`, `pnpm`, and a running oMLX
runtime with the voice/retrieval models (see
[docs/operations/DEPLOYMENT.md](docs/operations/DEPLOYMENT.md) and
[docs/MODEL_CATALOG.md](docs/MODEL_CATALOG.md)).

```bash
git clone https://github.com/areddy1805/pramya.git
cd pramya
cp .env.example .env          # then set DEEPSEEK_API_KEY (required for all text inference)

make up                       # postgres+pgvector, backend, frontend (Docker)
make migrate                  # alembic upgrade head
make backend-install          # uv sync
make frontend-install         # pnpm install
make dev-backend              # uvicorn :8001 (oMLX owns :8000)
make dev-frontend             # vite :3000
```

- Frontend → http://localhost:3000
- Backend → http://localhost:8001
- API docs → http://localhost:8001/docs
- Health → `curl http://127.0.0.1:8001/api/v1/health`

> A fresh clone has **no data**: the dashboard shows empty states until a
> profile, role, and practice session exist. `scripts/seed_demo.py` exercises
> the full HTTP pipeline (create → upload → index → extract → JD → readiness →
> prep → interview) for development:
> `cd backend && uv run python ../scripts/seed_demo.py`

## Command reference

| Command | Purpose | Exists |
|---|---|---|
| `make up` / `make down` | Start / stop Docker infrastructure | ✅ |
| `make migrate` | Apply Alembic migrations | ✅ |
| `make test` | Unit + contract tests | ✅ |
| `make test-integration` | Integration suite (isolated `pramya_test` DB) | ✅ |
| `make evals` | AI evaluation suite (golden-data, DeepSeek judge) | ✅ |
| `make lint` | Backend ruff + frontend oxlint | ✅ |
| `make typecheck` | Backend mypy + frontend tsc | ✅ |
| `make dev-backend` / `make dev-frontend` | Dev servers | ✅ |
| `make demo-setup` | Seed the 4-role demo dataset (idempotent) | ✅ |
| `make backend-install` / `make frontend-install` | Install dependencies | ✅ |

`make e2e` runs the Playwright browser suite (real backend + vite, `frontend/e2e/`):
`cd frontend && pnpm exec playwright test`.

---

## Configuration

Copy `.env.example` → `.env`. **Never commit `.env`** (gitignored).

| Variable | Required | Purpose | Default |
|---|---|---|---|
| `DEEPSEEK_API_KEY` | ✅ | All text/LLM inference (sole text provider) | — |
| `DATABASE_URL` | ✅ | PostgreSQL async URL | `postgresql+asyncpg://pramya:pramya@localhost:5432/pramya` |
| `APP_PORT` | — | Backend port (oMLX owns 8000) | `8001` |
| `CORS_ORIGINS` | — | Comma-separated origins. **Config only — middleware not yet wired** | `http://localhost:3000` |
| `OMLX_BASE_URL` | — | Local model runtime | `http://127.0.0.1:8000/v1` |
| `OMLX_EMBEDDING_MODEL` | — | Embedding model | `bge-m3-mlx-4bit` |
| `OMLX_RERANK_MODEL` | — | Rerank model | `Qwen3-Reranker-0.6B-4bit` |
| `VOICE_LIVE_ASR_MODEL` | — | Live ASR (H.4: Parakeet must stay the live path) | `parakeet-tdt-0.6b-v3-int8` |
| `VOICE_OFFLINE_ASR_MODEL` | — | Offline/archival ASR | `Qwen3-ASR-1.7B-4bit` |
| `VOICE_TTS_MODEL` | — | Interviewer TTS | `Qwen3-TTS-12Hz-0.6B-Base-MLX-4bit` |
| `VOICE_SILENCE_SECONDS` | — | Auto end-of-turn silence | `1.5` |
| `VOICE_SPEECH_RMS` | — | Speech energy threshold (0–32767) | `400` |
| `VOICE_RETENTION_DAYS` | — | Retention window (unused until audio storage exists) | `30` |
| `AUDIO_STORAGE_DIR` | — | Audio path (unused) | `.runtime/audio` |
| `UPLOAD_MAX_MB` | — | Upload size cap | `5` |
| `DOCUMENT_MAX_PAGES` | — | PDF page cap | `50` |
| `KNOWLEDGE_CHUNK_SIZE` / `_OVERLAP` | — | Chunking parameters | `1200` / `200` |
| `LANGFUSE_*` | — | **Config only — not integrated** | — |
| `VITE_API_URL` | — | Frontend API base | `http://localhost:8001` |

---

## API / WebSocket

### REST (`/api/v1`)

| Area | Endpoints |
|---|---|
| Health / runtime | `GET /health`, `GET /models/status` |
| Candidates | `GET/POST/PATCH/DELETE /candidates…` |
| Documents | `GET/POST/DELETE /documents…`, `POST /documents/{id}/index` |
| Evidence | `GET/PATCH /candidates/{uid}/evidence…` |
| Roles | `POST /roles/analyze`, `GET /roles…` |
| Extraction | `POST /candidates/{uid}/extract` |
| Interviews | `POST /interviews`, `GET /interviews…`, `POST …/begin·questions·answers·hint·pause·resume·stop·cancel`, `GET …/report`, `GET …/events` (SSE) |
| Analytics | `POST /readiness`, `GET /readiness/latest`, `POST /preparation/regenerate`, `GET /preparation`, `GET /progress` |
| Stories | `GET/POST/PATCH/DELETE /stories…`, `GET/POST /debriefs`, `POST /transcripts/analyze`, `POST /debriefs/analyze` |

Errors use a uniform envelope: `{code, message, request_id, details}`. Answer
submission is idempotency-keyed. OpenAPI at `/docs`.

### Voice WebSocket

`ws://{host}/api/v1/ws/voice/{interview_id}?user_id=N`

- **Client → server:** binary PCM16 mono 16 kHz mic frames (while `listening`);
  JSON controls `start_turn`, `end_turn`, `interrupt`, `pause`, `resume`,
  `stop`, `cancel`.
- **Server → client:** JSON events `state`, `question`, `tts_start{generation}`,
  `tts_stop{generation}`, `partial_transcript`, `final_transcript`,
  `turn_ended`, `answer_submitted`, `evaluation`, `error`; binary PCM16 mono
  24 kHz playback chunks (200 ms).
- **Turn flow:** speaking → listening → (auto silence 1.5 s or `end_turn`) →
  processing → final transcript → evaluation → next question.
- **Interruption:** `interrupt` bumps the generation; chunks from older
  generations are dropped by both sides. `pause` during speaking cancels TTS;
  `resume` returns to listening. No reconnect/heartbeat yet.

---

## Testing

Verified 2026-08-12 (local run, clean tree):

| Suite | Command | Result |
|---|---|---|
| Unit + contract | `cd backend && uv run pytest ../tests/unit ../tests/contract -p no:warnings -q` | ✅ 182 passing |
| Integration | `cd backend && PYTHONPATH=.. uv run pytest ../tests/integration -p no:warnings -q` | ✅ 36 passing (isolated `pramya_test`, created/dropped per run) |
| Migration drift | `cd backend && uv run alembic check` | ✅ no new operations |
| Frontend typecheck | `cd frontend && pnpm exec tsc -b --noEmit` | ✅ 0 errors |
| Frontend lint | `cd frontend && pnpm exec oxlint` | ✅ |
| Frontend build | `cd frontend && pnpm build` | ✅ |
| E2E (Playwright) | `cd frontend && pnpm exec playwright test` | ✅ 2 tests: dashboard readiness + typed interview journey (real backend) |
| Evals | `make evals` | ✅ golden-data harness (DeepSeek judge; variance recorded as WARNING) |

Voice coverage: 10 unit tests (hot-loop interrupt mid-TTS, generation bump, no
stale chunks, auto + manual end-of-turn, pause/resume/stop/cancel, transcript
persistence) against injected stubs — they verify the state machine, not audio
hardware.

No coverage percentage is claimed: no coverage measurement is configured.

---

## Repository structure

```
pramya/
├── backend/
│   ├── app/
│   │   ├── ai/            # InferenceRouter, task policy, DeepSeek/oMLX providers, structured output
│   │   ├── api/v1/        # REST routers, SSE, voice WebSocket
│   │   ├── core/          # config, DB engine, JSON logging, request-id middleware
│   │   ├── domain/        # Pydantic schemas, enums (interview/voice/evidence), errors
│   │   ├── interview/     # deterministic interview state machine, generation, evaluation
│   │   ├── knowledge/     # parsing, chunking, ingestion, hybrid retrieval
│   │   ├── models/        # SQLAlchemy models (22 tables)
│   │   ├── repositories/  # typed async data access
│   │   ├── services/      # extraction, role, readiness, preparation, progress, analytics
│   │   └── voice/         # VoiceEngine, ASR client, TTS client
│   ├── alembic/           # migrations (1 initial; alembic check clean)
│   └── pyproject.toml     # uv-managed deps + test config
├── frontend/
│   ├── src/
│   │   ├── pages/         # 10 product screens
│   │   ├── components/    # UI primitives + AppShell
│   │   ├── hooks/         # TanStack Query hooks, SSE hook
│   │   ├── lib/           # api client, types, voice client, theme
│   │   └── stores/        # zustand theme store
│   └── scripts/           # visual QA + real-model voice E2E (Playwright)
├── tests/
│   ├── unit/              # 135 tests
│   ├── contract/          # API surface + error-envelope contracts
│   ├── integration/       # 29 tests on isolated pramya_test
│   ├── e2e/               # browser suite (Playwright, frontend/e2e)
│   └── evals/             # golden-data AI eval harness (DeepSeek judge)
├── prompts/               # versioned prompt files (question, eval, hints, reports…)
├── scripts/               # seed_demo.py (full HTTP pipeline exercise)
├── docs/                  # plan, ADRs, architecture, model catalog, operations
├── assets/
│   ├── branding/          # pramya-logo.svg, pramya-mark.svg
│   └── screenshots/       # product captures
├── docker-compose.yml     # postgres+pgvector, backend, frontend
├── Makefile               # dev/test/lint/typecheck targets
└── .env.example           # canonical env template
```

---

## Performance / resource notes

Observed facts (16 GB M4 MacBook; not a benchmark):

- oMLX runs all local models in one process with a memory guard and serialized
  inference (`max_concurrent_requests: 1`). ASR and TTS share one
  `_speech_lock` in the voice engine — no parallel audio inference.
- Model load/unload churn under memory pressure caused system-wide lag in
  early development. Operational rule: do not fire heavy local inference while
  models are cold and memory is tight.
- No caching layer exists beyond idempotency records; DeepSeek prompt-cache
  tokens are surfaced in usage telemetry for cost visibility.
- Frontend production bundle ≈ 335 KB (≈ 101 KB gzip).
- **No latency/TTFA numbers are published** — they are not instrumented.

---

## Security

**What exists:**

- `.env` gitignored; `.env.example` contains no real secrets.
- Upload validation: size ≤ 5 MB, MIME allowlist (PDF/DOCX/TXT/MD), PDF page
  cap, parse timeout, DOCX uncompressed cap. Documents treated as untrusted.
- Pydantic request validation with uniform error envelopes.
- Structured-output validation: LLM output that fails the schema never mutates
  state.
- Candidate content is logged as counts/IDs, not raw text; audio is not stored
  anywhere (feature not implemented).

**What does not exist yet (V1 boundaries):**

- **Authentication / authorization** — single-user; all APIs take `user_id`
  as a query parameter. No login, tokens, or per-user isolation.
- **CORS enforcement** — `CORS_ORIGINS` is configurable but the middleware is
  not wired into the app; the dev frontend relies on the Vite proxy.
- **Rate limiting** — none.
- **Prompt-injection test suite** — prompt structure separates system/user
  data, but no adversarial-document tests exist.
- **Secret scanning / dependency audits in CI** — not configured.

See [docs/operations/SECURITY.md](docs/operations/SECURITY.md) for the full
posture.

---

## Known limitations

**Implemented limitations**

- Parakeet live ASR is chunked/buffered, not true streaming (native streaming
  needs vLLM, not MLX). Partials are emitted on a ~2 s cadence over the
  accumulated buffer.
- Live ASR is pinned to Parakeet by config and provider-layer responsibilities
  (H.4); Qwen3-ASR is the offline/archival path.

**Incomplete features**

- Voice: no audio persistence, replay, reconnect, heartbeat; no real-mic
  automated test; no communication analysis.
- Interview memory (longitudinal adaptation) — not implemented.
- Debrief workflow: backend endpoints only, no UI.
- Demo mode is implemented (`demo/` fixtures + `POST /demo/setup` + `make demo-setup`);
  MCP and Langfuse are not implemented.
- RAG: pipeline implemented and tested, but the reference runtime holds
  **0 indexed chunks** — retrieval is starved until indexing runs on real data.
- Resume extraction: endpoint and service exist and are integration-tested,
  but no extraction output was observed landing in the reference database.
- Eval suite and browser E2E are implemented; MCP and Langfuse remain not implemented.

**Architectural debt**

- Framework substitutions (ADR-021/022) are documented but the older README
  text and some operation docs still describe the intended stack; docs lag.
- Interview reports are generated on demand, not stored.
- Evaluation version registry exists in code but no rows were observed
  persisted at runtime.

**Operational limitations**

- Requires DeepSeek API access and a local oMLX runtime; no pure-local text
  mode (text reasoning is cloud-only by ADR-023).
- Fresh-clone quickstart is not verified end-to-end.
- Single-user, no auth — not suitable for multi-tenant deployment as-is.

**Hardware requirements**

- 16 GB RAM is the practical floor for voice: Parakeet (~720 MB), Qwen3-TTS
  (~1.6 GB), BGE-M3 (~320 MB), reranker (~330 MB) plus the oMLX process; model
  churn under pressure can lag the whole machine.

---

## Roadmap

**Completed**

- Core domain + persistence (22 tables, pgvector, Alembic-clean)
- Hybrid retrieval pipeline (vector + FTS + RRF + rerank) with degradation
- Adaptive text interviews with structured evaluation + evidence extraction
- Deterministic readiness / preparation / progress engines
- React product UI (dark-first semantic-token design system)
- Live voice interview engine (concurrent, interruption-safe)
- DeepSeek-only text routing with observable decisions (ADR-023)

**In progress**

- Voice: audio persistence, replay, reconnect, real-mic coverage
- RAG: index real documents so retrieval has runtime content
- Report persistence, runtime eval-version persistence
- Early README/docs sections still describe the intended (pre-ADR) stack in places.

**Implemented since**

- Security hardening (CORS applied, bearer tokens, rate limit, security headers)
- Communication analysis, voice audio persistence + replay + reconnect
- Interview memory (record endpoint), history, debriefs, transcript views
- Demo mode (4 roles), browser E2E suite, fresh-clone verification

**Planned**

- MCP server, Langfuse integration, release packaging

---

## Development

```bash
make lint && make typecheck && make test && make test-integration
cd frontend && pnpm build
```

**Backend feature flow:** model → `backend/app/models/` + Alembic migration →
repository (`repositories/`) → service (`services/`) → router (`api/v1/`) →
tests in `tests/unit` + `tests/integration`.

**Frontend feature flow:** hook in `hooks/queries.ts` (typed, TanStack Query)
→ screen in `pages/` → primitive in `components/ui.tsx` (semantic tokens only)
→ route in `components/AppShell.tsx`.

**AI providers:** text models live in `backend/app/ai/policy.py` + `providers/`
(ADR-023: text tasks have no fallback chain — preserve that). Speech lives in
`backend/app/voice/` and talks to oMLX directly.

**Voice engine rules:** keep the receive loop hot in `voice/engine.py`; long
work belongs in background tasks; bump `_generation` before cancelling TTS.
Client rules in `frontend/src/lib/voice.ts`: generation-gated playback; never
play stale audio after an interrupt.

---

## Documentation

| Document | Purpose |
|---|---|
| [Master implementation plan](docs/MASTER_IMPLEMENTATION_PLAN.md) | Authoritative V1 plan (phases, acceptance, tracker) |
| [Decisions & ADRs](docs/DECISIONS.md) | Decision log incl. ADR-021/022/023 |
| [Model catalog](docs/MODEL_CATALOG.md) | Model stack + acquisition (ADR-023 topology) |
| [AI architecture](docs/ai/AI_ARCHITECTURE.md) | Inference architecture |
| [Voice architecture](docs/ai/VOICE_ARCHITECTURE.md) | Voice protocol + implementation status |
| [Retrieval architecture](docs/ai/RETRIEVAL_ARCHITECTURE.md) | Hybrid retrieval design |
| [Evaluation strategy](docs/ai/EVALUATION.md) | Evaluation plan (not yet implemented) |
| [Deployment](docs/operations/DEPLOYMENT.md) | oMLX/DeepSeek setup + deployment |
| [Troubleshooting](docs/operations/TROUBLESHOOTING.md) | Operational issues |
| [Security](docs/operations/SECURITY.md) | Security posture |
| [Observability](docs/operations/OBSERVABILITY.md) | Observability intent (Langfuse wiring not yet live) |
| ADRs | [ADR-001…014](docs/architecture/) · [ADR-023](docs/architecture/ADR-023-deepseek-only-text-omlx-audio-retrieval.md) |

**Not yet written:** `CONTRIBUTING.md`, `PRIVACY.md`, `CHANGELOG.md` (a root
`CHANGELOG.md` exists with an Unreleased section).

---

## License

**No license is currently declared.** The repository contains a placeholder
`LICENSE` template (`Copyright (c) {{ year }} {{ organization }}`), not a real
license grant. Until a license is chosen, treat the code as all-rights-reserved.
