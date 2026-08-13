# Pramya — Project Memory

> Persistent engineering memory. Maintained across sessions. Not a transcript.
> Read at session start. Verify before relying on stale notes.

---

## Current State

- Project status: **Phase 1 (Core Domain + Persistence) COMPLETE** (2026-08).
- Master plan: `docs/MASTER_IMPLEMENTATION_PLAN.md` — authoritative. Phase 2 (Knowledge Layer) is next.
- Last verified commit: see `git log`; Phase 1 committed.
- Local `.env` exists (copied from `.env.example`, gitignored).
- DB: docker compose `db` (pgvector/pgvector:pg17) running locally; `alembic upgrade head` applied; `alembic check` clean.

## Verified Environment Facts (2026-08)

- Dev machine: MacBook Pro M4, 16GB unified, 512GB. Node v24.11.1, Python 3.14.6 (project pinned to 3.12/3.13 via uv — `.venv` created with 3.13), Docker 27.5.1, uv 0.12, pnpm 10.
- Frontend reality (verified via template probe + registry): React 19.2.x, Vite 8.2.x, TypeScript ~6.0.x (7.0.2 latest available), plugin-react 6.x, oxlint (replaced eslint in Vite template), Tailwind 4.3.x, TanStack Query 5.101.x, Zustand 5.0.x, react-router-dom 7.18.x. Template ships `tsc -b` builds + oxlint; strict mode enabled explicitly.
- **pgvector pin correction**: PyPI Python client latest = **0.5.0** (server extension 0.8.x lives in the Docker image `pgvector/pgvector:pg17`). Plan §33 conflated them; pyproject pins `pgvector>=0.5,<0.6`.

## Verified Environment Facts (2026-08)

- Dev machine: MacBook Pro M4, 16GB unified, 512GB. Node v24.11.1, Python 3.14.6 (pin project to 3.12/3.13 in pyproject), Docker 27.5.1.
- DeepSeek API: model `deepseek-v4-flash` (V4-Flash-0731 public beta 2026-07-31). 1M ctx, thinking via `reasoning_effort`. Legacy IDs `deepseek-chat`/`deepseek-reasoner` DISCONTINUED 2026-07-24 — never use. `frequency_penalty`/`presence_penalty` unsupported. OpenAI-compatible at `https://api.deepseek.com`. Pricing: $0.14/M in (miss), $0.0028/M (hit), $0.28/M out.
- Framework versions (verified): LangChain 1.3.x, langchain-core 1.4.x, LangGraph 1.2.x (create_react_agent deprecated → `langchain.agents.create_agent`; `StateGraph(state_schema=...)` mandatory; `interrupt()`+`Command(resume=...)`; `langgraph.types`), LlamaIndex 0.14.x (QueryPipeline removed in 0.13), MCP Python SDK 2.0 (`MCPServer`, FastMCP renamed; v1 pinned `mcp>=1.28,<2` alternative), DeepEval 4.1.x (judge default gpt-5.4 → override to deepseek), Langfuse OSS v4 server / Python SDK 4.14.x (OTel-based, `@observe`; MIT self-hosted; Cloud/Enterprise not V1 deps), FastAPI 0.139.x, Pydantic 2.13.x, SQLAlchemy 2.0.51 async, pgvector 0.8.x (HNSW, sparsevec), PostgreSQL 17, React 19.x, Vite 8, TS 5.7+ strict.
- oMLX v0.5.x = local inference server (Apache-2.0). OpenAI-compatible: chat/embeddings/rerank/audio endpoints. SSD KV-cache, model pinning/TTL. Audio endpoint support for Parakeet/Qwen3-ASR/Qwen3-TTS must be VERIFIED at Phase 7; direct `parakeet-mlx` + `mlx-audio` are the fallback.

## Verified Model Facts (see docs/MODEL_CATALOG.md)

- All 8 definitive models exist; no concrete incompatibility found. Do NOT reopen selection.
- **Canonical roles (finalized 2026-08):** Qwen3.5-4B (oMLX alias `pramya-4b`) = PRIMARY local workhorse (default, thinking off, local-first, majority of workload); deepseek-v4-flash = ESCALATION model (only when workload materially benefits from stronger reasoning/capability/context; never default); Qwen3.5-9B = DEFERRED from V1 production (not required, not a fallback, not a routing target, not a setup dependency; historical entry preserved in catalog §2.3). Principle: strongest ≠ default.
- Licenses: Qwen3.5-4B Apache-2.0 (production); Qwen3.5-9B Apache-2.0 (deferred/experimental); BGE-M3 MIT (mlx-embeddings library is GPLv3 — use oMLX /v1/embeddings instead); Qwen3-Reranker-0.6B Apache-2.0; Parakeet-TDT-0.6B-v3 CC-BY-4.0 (attribution); Qwen3-ASR-1.7B Apache-2.0; Qwen3-TTS-0.6B Apache-2.0; oMLX Apache-2.0.
- Parakeet v3 = chunked pseudo-streaming only (offline model; no cache-aware streaming; sherpa-onnx no true streaming either). VAD-gated pseudo-streaming + local-agreement commit; Qwen3-ASR-1.7B on MLX is offline/chunked only (native streaming requires vLLM backend, not part of MLX deployment). Nemotron-3.5 ASR Streaming = upgrade candidate.
- MLX weights: mlx-community/Qwen3.5-4B-MLX-4bit (~2.4–3.1GB) [alias `pramya-4b`; REQUIRED], bge-m3-mlx-8bit (~592MB)/4bit (~321MB), Qwen3-TTS-12Hz-0.6B-Base-bf16 (~1.2GB)/CustomVoice-4bit (~960MB), parakeet-tdt-0.6b-v3 int8 (~1.3GB), Qwen3-ASR-1.7B-8bit (~2.35GB)/4bit (~1.5GB via mlx-audio). Qwen3.5-9B-MLX-4bit (~5.6GB) exists but is NOT required/downloaded in V1.
- Qwen3.5 checkpoints are VLM; need recent mlx-lm for `qwen3_5` arch (ml-explore/mlx-lm issue #1136) — text-only inference needs correct chat template check.
- MLX models cannot run concurrently from multiple threads → single serialized speech inference worker.

## Framework Gotchas (learned from research — avoid re-learning)

- LlamaIndex `IngestionPipeline` does NOT dedupe against the vector store; node hash excludes metadata (run-llama#17871). Implement explicit docstore dedup by content hash.
- DeepEval: `retrieval_context` must be list[str]; empty retrieval_context makes Faithfulness silently return 1.0; pin judge at temp 0.
- LangGraph v2 streaming returns unified StreamPart/GraphOutput; agent event node renamed "agent"→"model"; durability modes sync/async/exit.
- MCP SDK v2 (2026-07-28 protocol revision) = stateless request/response, `server/discover`; decide v2 vs pinned v1 at Phase 11.
- Langfuse (OSS): metadata now dict[str,str] ≤200 chars; `start_span`/`start_generation` unified to `start_observation`; real-time ingestion needs Python SDK ≥4.7.
- SSE vs WS: text events SSE; voice = WS (bidirectional + interrupt). AudioWorklet for low-latency playback; AbortController everywhere; rAF batching for token streams.

## Phase 1 Facts (verified 2026-08)

- SQLAlchemy 2.0.51 async + asyncpg 0.31 + alembic 1.19.1; pgvector Python client 0.5.x (`from pgvector.sqlalchemy import Vector`; type renders as `VECTOR(n)`, `.dim` holds dimension).
- **Alembic gotcha**: env.py resolves URL from app Settings (DATABASE_URL) unless a test override injects `sqlalchemy.url`; `alembic check` needs model types to match migration exactly — use `postgresql.TIMESTAMP(timezone=True)` in models (not `DateTime(timezone=True)`) or autogenerate flags type drift; name indexes with the naming-convention labels (`ix_<table>_<column>`) or drift is reported.
- `metadata` is a reserved attribute name in SQLAlchemy Declarative API — DocumentChunk stores metadata JSONB under attribute `meta` with explicit column name `"metadata"`.
- pytest-asyncio event loops are function-scoped: session-scoped async fixtures (engine) must be avoided; create the engine in a function-scoped async fixture (integration conftest pattern). Alembic's env.py calls `asyncio.run`, so migration commands must run outside a live loop (sync fixture / `asyncio.to_thread`).
- Pytest runs with `-c pyproject.toml` from `backend/` (asyncio_mode=auto, pythonpath includes repo root for `tests/` imports); running `pytest ../tests/unit` without `-c` misses the config and fails async tests.
- 22 tables + `idempotency_record` (task 1.6 infra, not in §7 list) = 23 tables; document_chunk has HNSW (`vector_cosine_ops`, m=16, ef_construction=64) + GIN (fts) + unique (document_id, chunk_index); fts is a stored generated column `to_tsvector('english', content)`.
- Integration tests: `TEST_DATABASE_URL` (default pramya_test on localhost); DB created/dropped per session; scratch DB `pramya_scratch` used for downgrade test; CI runs integration against pgvector service container.

## Architecture Decisions (durable)

- Modular monolith, FastAPI + React 19; LangGraph owns interview orchestration (Postgres checkpointer, thread_id=session); LlamaIndex owns ingestion/retrieval; InferenceRouter (deepseek + oMLX providers) owns model access; MCP = read-only external surface only; readiness/priority/progress = deterministic pure functions; evaluation append-only + versioned.
- 1024-dim BGE-M3 locked into schema from day one (dimension changes painful).
- DeepEval judge = deepseek-v4-flash (not gpt default): cost + privacy.
- Voice: Parakeet live / Qwen3-ASR recorded / Qwen3-TTS; explicit state machine server-side; stale-TTS prohibition (<150 ms flush target); audio not stored by default.

## Known Problems / Blockers

- None. Phase 0 acceptance criteria verified (make test/lint/typecheck green, CI config valid, compose config valid).

## Deferred Decisions

- Redis: only if Phase 10/11 measurement justifies (rate limiting/coordination/cache).
- Auth: deployment-dependent; single-user local default; must not threaten deadline.
- Langfuse self-host (OSS, MIT): optional Compose profile (heavy: pg+clickhouse+redis+s3); dev fallback = structured logs. Cloud/Enterprise not V1 deps.
- MCP SDK v2 vs pinned v1: decide at Phase 11.

## Important Lessons

- Research forks returned empty results in one planning session, but wrote files asynchronously → verify file state after parallel forks; do decision-critical research directly in parent context.
- Plan docs must be verified against framework reality (2026 versions differ wildly from 2024-era tutorials: chains removed, agents renamed, SDK renamed).

## Operational Notes

- Makefile targets planned: up/down/migrate/dev-backend/dev-frontend/test/evals/lint/typecheck/models-pull/demo-setup.
- Local AI runs on host (oMLX), not in Docker (Metal access).
- Never commit `.env`; never log candidate content; observability = IDs + redacted metadata.

## Voice engine concurrency lesson (2026-08-12, H.1–H.9)

- **Bug class:** the original VoiceEngine awaited `_speak_next_question()` inline in `run()`, so the WS receive loop was deaf during TTS streaming — Interrupt/Pause did nothing mid-speech. `_tts_task` was never assigned, so `_cancel_tts` cancelled nothing.
- **Fix pattern:** `run()` is a permanently hot receive loop; long work (`_start_session`, `_speak_next_question` TTS stream, `_process_answer` ASR→DeepSeek) runs in `asyncio.create_task` background tasks. Every cancellation path (interrupt/pause/stop/cancel) cancels tasks + bumps `_generation` before any state transition.
- **Turn finalization needs a watchdog, not inline-only logic:** checking `_speech_ended_at` only on subsequent audio frames fails when the client stops sending audio. The engine now runs a `_silence_task` loop (100ms tick) that auto-finalizes when silence exceeds `voice_silence_seconds` — plus manual `end_turn` from a Done-speaking button.
- **Stale-audio correctness:** every TTS stream has a `generation` id (`tts_start{generation}` / `tts_stop{generation}`); server skips chunks whose generation no longer matches; client drops binary frames unless `state==='speaking'` AND generation is current; interrupt invalidates both.
- **Model roles (H.4):** live ASR = Parakeet-TDT (`voice_live_asr_model`), offline/archival ASR = Qwen3-ASR (`voice_offline_asr_model`), TTS = Qwen3-TTS (`voice_tts_model`). Do not let config churn flip Qwen3-ASR back into the live path.
- **Mic permission errors** map to typed codes (`permission_denied` / `device_unavailable` / `mic_unavailable`) surfaced as actionable UI text, not generic "something went wrong".
- **Real-model voice E2E passed 2026-08-12** (sessions 39/40/41, fake-mic via Playwright): 20 ASR partials, 9 TTS syntheses, interrupt conceded no stale chunks. Voice engine unit coverage: 14 tests.

## Phases H–M completion record (2026-08-12)

- **H (voice persistence):** candidate audio → WAV under `audio_storage_path`
  + `audio_segment` row (`VOICE_STORE_AUDIO` opt-in, `voice_retention_days`);
  replay endpoints `GET /interviews/{id}/voice/audio[/{segment_id}]`;
  WS `heartbeat`→`heartbeat_ack`; reconnect emits `resume` (state + last
  question, never re-begins an active session); communication analysis is
  pure arithmetic over persisted transcript timestamps (`GET
  /interviews/{id}/communication`) — absent data → `None` + explanatory
  notes, never fabricated. PCM16 duration bug fixed: bytes/2 = samples
  (`_pcm16_duration_ms`).
- **I (security):** CORSMiddleware finally applied (config parsed it but the
  app never added it). **Starlette middleware order: LAST added = OUTERMOST**
  (verified by resolved-stack inspection) — CORS must be added last. Bearer
  tokens via `API_TOKENS` (HTTP + voice WS `?token=`), per-IP fixed-window
  rate limit `RATE_LIMIT_RPM`, security headers, digest-keyed upload storage
  with suffix whitelist. `pip-audit`: no known vulnerabilities.
- **J (demo):** `demo/roles/{4 keys}/resume.md+jd.md` fixtures; `POST
  /api/v1/demo/setup` idempotent (docs dedup by content hash, roles by title,
  evidence by source_ref); `make demo-setup` = seed script; Settings "Demo
  data" button. Runtime-verified: real bge-m3 embeddings + deepseek extraction.
- **K (memory/history/debrief):** `GET /interviews/{id}/transcript` builds the
  durable record (question turns + answer turns with `turn.content`, scores
  via Answer.interview_turn_id); History / Debriefs / Transcript pages wired;
  debriefs create+analyze (DeepSeek ANALYSIS). Transcript mapping pitfall:
  `turn.kind` from DB is a plain str — compare with `str(...) ==
  InterviewTurnKind.X.value`, never `is`.
- **L (E2E):** Playwright suite `frontend/e2e/` (`make e2e`) — dashboard +
  full typed-interview journey against live stack. **Race exposed:** the
  "Current question" heading + caption render immediately; the question text
  arrives via SSE after DeepSeek generation. Selectors must wait on the
  question paragraph (`main p.text-xl`), never the heading/caption (caption
  matched `/what/` → typed+clicked before question existed → silent no-op).
  **Real product bugs fixed:** text-mode UI never handled SSE `evaluation`
  events, and the score display lived only in the voice branch — evaluation
  now renders for both modes.
- **M (fresh clone):** verified fresh-DB `alembic upgrade head` (23 tables
  from zero), backend boot with example-only env (deepseek configured=false,
  honest), `make test/lint/typecheck/e2e` all green from repo root.

**Pending / not implemented:** MCP server, Langfuse SDK integration
(config fields only), real-model voice E2E re-run on this machine, release
packaging. Eval suite (Phase F) = COMPLETE WITH KNOWN WARNINGS (DeepSeek
judge variance recorded as WARNING; never gamed).

## V1.1 REALTIME VOICE — CHECKPOINT (2026-08-13, mid-implementation)

STATUS: R1 measured, R2-R11 implemented + unit/integration-tested, LIVE E2E VERIFICATION PENDING (one known fix applied, not yet live re-run).

V1 BASELINE (measured, session 83, client timestamps): TURN_TO_FIRST_AUDIO ≈ 22-55s. turn_end→tts_start median ~12.5s (includes 1.5s silence watchdog + full-buffer ASR + submit_answer blocking on COMPLETE DeepSeek evaluation + full question gen); tts_start→first_chunk 10.5-40s (full-utterance Qwen3-TTS synthesis; memory thrash on turn 2). Bottlenecks by contribution: (1) full-utterance TTS, (2) evaluation blocking submit_answer, (3) full DeepSeek gen, (4) silence+ASR.

V1.1 ARCHITECTURE (implemented, tests green):
- R2 VOICE IDENTITY: config interviewer_voice_id/name/style (PRAMYA_INTERVIEWER_VOICE_ID, default professional_female_01); app/voice/profile.py resolve_interviewer_voice() deterministic per session; Qwen3-TTS single speaker maps provider_voice='default'; no random selection anywhere; regression test test_tts_client_uses_same_voice_for_every_call.
- R3 PROVIDER BOUNDARY: TTSClient = single real provider (synthesize / synthesize_stream / warmup / voice_id); StreamingTextGenerationProvider optional protocol (contracts.py) — runtime_checkable base protocol stays minimal so fakes don't break.
- R4 WARMUP: TTSClient.warmup() tiny synthesis at session start (engine _warmup_tts task); model kept resident by oMLX.
- R5 DEEPSEEK STREAM: ChatStreamChunk + stream_chat SSE parser (_http.py) + DeepSeekProvider.stream + InferenceRouter.stream (fallback to single-chunk generate for non-streaming providers) + RouterChatModel._astream (on_llm_new_token → LangGraph stream_mode='messages').
- R6 SEGMENTER: app/voice/segmenter.py TextSegmenter (min 60/max 200 chars, sentence boundaries .!?…， mid-word-safe hard flush). Question prompt rewritten to streaming format prompts/question_generation/adaptive_question_stream.txt (QUESTION: first, then TYPE/DIFFICULTY/RATIONALE/TARGET/HINTS lines); parse_question_output() in generation.py; single code path for text+voice.
- R7 STREAMING TTS: oMLX /v1/audio/speech supports {"stream": true, "streaming_interval": s} — NATIVE streaming (Qwen3-TTS generate() has stream/streaming_interval params, verified in oMLX 0.5.7 source); 44-byte WAV header then PCM chunks; TTSClient.synthesize_stream; engine _speech_worker serializes segments on _speech_lock, relays 200ms frames.
- R9 STATES: VoiceState.THINKING added; engine: THINKING (LLM stream) → SPEAKING (first audio) → playback-gated LISTENING. Silence watchdog default 1.0s (was 1.5).
- R10 BARGE-IN: voice_barge_in_enabled default True (config 900 RMS / 250ms); _on_audio treats THINKING+SPEAKING as interviewer-owned (mic discarded, never ASR'd, barge-in checked).
- R11 TWO-LANE: submit_answer(await_evaluation=False) commits answer fast; evaluation DEFERRED to LISTENING window (_maybe_start_evaluation in _start_listening) — avoids concurrent use of shared async DB session (SQLAlchemy AsyncSession not concurrency-safe); next question streams immediately after submit.
- LANGGRAPH AUTHORITATIVE: InterviewService.next_question_streaming() = async generator over workflow.astream(stream_mode='messages') tokens + final ("question", (q, turn)) from workflow.aget_state(); generate_question node accumulates + parses.
- OBSERVABILITY: record_event now ALWAYS logs structured telemetry (event field) even when Langfuse down (Langfuse host 3030 currently NOT running); voice_question_waterfall carries question_gen_ms/llm_first_token_ms/tts_first_audio_ms/voice_id; voice_answer_waterfall asr_ms/submit_ms.

KNOWN DEFECT FIXED: LangGraph aget_state returns StateSnapshot (has .values, not .get) — fixed in service.py next_question_streaming. Live run before fix: 'StateSnapshot' object has no attribute 'get' (question pipeline degraded). After fix: 194 unit + 9 contract + 38 integration green, mypy/pyright/ruff clean, frontend tsc/lint/build green.

NEXT (resume point): restart backend on 8001, run frontend/scripts/voice_e2e_5turns.mjs (volume 50%) — verify streaming loop + TURN_TO_FIRST_AUDIO per turn; then R13 TTS benchmark (Pocket TTS research time-boxed), R10 barge-in live check, R14 reconnect, R18 V1-vs-V1.1 benchmark, R19 docs (ADR-025, VOICE_ARCHITECTURE, OBSERVABILITY, MODEL_CATALOG, README, CHANGELOG), R20 final validation + report. Uncommitted V1.1 work sits in the working tree (checkpoint commit to follow).
