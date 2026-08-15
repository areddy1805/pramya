# Changelog

All notable changes to Pramya are recorded here.
Format based on [Keep a Changelog](https://keepachangelog.com/); versions follow [SemVer](https://semver.org/).

## [Unreleased]

Reserved for post-v1.0.0 work (auth/multi-user, MCP surface, OTel
instrumentation, distribution). No in-progress v1.0 items remain.

## [1.0.0] — 2026-08-16

### Added

- **Persistent multi-profile career workspace (ADR-026):** `candidate_profile`
  as a multi-instance profile container (unique `(user_id, name)`); profile
  CRUD + header switcher; profile-scoped documents, roles, evidence,
  readiness snapshots, preparation items, practice sessions; interview
  sessions record their profile at creation; active profile is a persisted
  UX preference (SET NULL), never an authorization boundary.
- **Explicit preferred resume/JD per profile** (migration 0006): persisted
  document selection; stale pointers are SET NULL on delete; immutable
  per-session grounding snapshots retain historical references.
- **Interview productization (ADR-028):** profile-scoped grounding snapshot
  (resume/JD/role/evidence/prior feedback) injected into the question prompt;
  question provenance columns (category/source/source_ref) with a 20-category
  taxonomy; interviewer-reasoning follow-up engine in the answer lane;
  deterministic coverage rotation (seeded per session id) + JD gap detection;
  preparation memory (`interview_feedback`) written at session stop and read
  by the next session; report v2 deterministic scorecard + per-question
  feedback; anti-hallucination entity guard; 7 interviewer styles + duration
  presets.
- **Pocket TTS default (ADR-027):** Kyutai Pocket TTS (CPU, in-process,
  English single voice "alba") becomes the default TTS provider; Qwen3-TTS
  retained as `TTS_PROVIDER=qwen3` fallback with the streaming pipeline
  (segmenter, generation guards, voice profile) intact.
- **Long-run + playback quality (live voice):** bounded SSE event bus (no
  per-session queue growth), gapless client playback (pre-scheduled
  `AudioBufferSourceNode`s), interrupt/pause stop in-flight sources,
  40-turn engine endurance test.
- **Physical-mic speaker integrity:** playback-completion gating —
  `tts_stop` no longer opens candidate listening; server stays SPEAKING
  until `playback_complete{generation}` (bounded by
  `VOICE_PLAYBACK_TIMEOUT_SECONDS`); server-authoritative mic gating;
  `speaker` column on `transcript_segment` (migration 0002); opt-in
  voice-triggered barge-in (`VOICE_BARGE_IN_ENABLED`, default off).
- **Frontend visual canon (ADR-029):** all 14 routes (9 primary + 5
  secondary) in the frozen Drawing Sheet language; `More ▾` secondary
  navigation; density refinement; `DESIGN.md` as the permanent design
  contract.
- **Phase H — voice persistence & communication:** opt-in candidate audio
  (WAV + `audio_segment`, retention, replay endpoints); WS heartbeat +
  reconnect `resume`; deterministic communication analysis (measured only,
  never fabricated).
- **Phase I — security hardening:** CORS applied; optional bearer tokens
  (`API_TOKENS`, HTTP + voice WS); per-IP rate limit; security headers;
  digest-keyed upload storage; prompt-injection boundary tests.
- **Phase J — demo mode:** 4-role idempotent demo dataset (`make demo-setup`,
  API, Settings button).
- **Phase K/L — memory + E2E:** interview record endpoint + History/Debrief/
  Transcript surfaces; Playwright suite (dashboard readiness + typed
  interview journey) exposing and fixing two real SSE defects.
- **Phase M — fresh-clone verification:** fresh-DB migration (23 tables),
  example-env boot, documented quickstart.

### Changed

- **TTS default:** Qwen3-TTS (oMLX) → Pocket TTS (CPU), per measured
  benchmark (see Performance); Qwen3 kept as fallback.
- **Audio persistence default:** OFF (`VOICE_STORE_AUDIO=false`) — candidate
  audio is only persisted on explicit opt-in (release-audit fix).
- **Observability:** `LANGFUSE_ENABLED` is the single authoritative switch,
  default `false` (no client/worker/network); keys alone never enable
  Langfuse.
- **Profile isolation hardening (release audit):** role ownership enforced in
  interview grounding + readiness; `GET /interviews/{id}` ownership-checked;
  `candidate_profile.status` NOT NULL + user_id index (migration 0007).
- **Static checks:** ruff/mypy/pyright drift on main fixed (CI gate green).

### Performance

Measured on the Pramya development machine (Apple Silicon M4, 16 GB),
same warm state, `scripts/tts_bench.py` (ADR-027):

| Metric | Qwen3 (oMLX) | Pocket (CPU) |
|---|---:|---:|
| Warm first PCM (SHORT / MEDIUM / LONG) | 634 / 2 152 / 4 333 ms | 30 / 31 / 31 ms |
| Total generation (LONG ~12 s audio) | 4 333 ms | 1 281 ms |
| RTF | 2.9–3.0× | 8.3–9.0× |
| Model RSS | ~1.71 GB | ~0.84–0.96 GB (−44%) |
| Real voice path Q1 first audio | 7.35 s | 1.62 s |
| Real voice path Q2 final → audible | 9.13 s | 5.67 s |

10-turn sustained first-audio median (Pocket): 3.34 s (3.06–3.81, no drift);
stale frames after interrupt: 0 for both providers.

### Validation

- 233 unit + contract tests PASS, 89 integration tests PASS (real pgvector,
  migrations from zero) — 0 failures.
- ruff, mypy, pyright, tsc clean; `alembic check` clean (migrations 0001–0007).
- Controlled browser probe: 14/14 routes HTTP 200, 0 console errors.
- Recorded real-E2E evidence: typed-interview journey (Playwright, real
  backend) and physical-mic voice E2E (real microphone + speakers,
  2026-08-13) — not re-run in the release audit.
- Eval suite recorded run: 95 checks, 0 FAIL, 3 WARNING (DeepSeek judge
  variance recorded honestly).
- Release audit (2026-08-16): 6 P1 findings fixed, 0 P0 →
  **v1.0.0 RELEASE CANDIDATE** (see `docs/RELEASE_ACCEPTANCE.md`).

### Known limitations (v1.0.0 boundary)

- No per-user authentication — local/dev ownership model; bearer tokens
  opt-in; not a public multi-user deployment.
- Pocket TTS is English-only, single voice; adds ~1.1 GB RSS to the backend
  process once loaded.
- MCP server deferred from V1 (ADR-006 accepted); full OTel instrumentation
  not wired.
- Jobs/applications submission is out of v1.0 scope.

---

## [0.0.0] — 2026-08

### Added

- Initial repository: `AGENTS.md`, README, LICENSE, `.gitignore`,
  `.env.example`, docs stubs.
- Master implementation plan (`docs/MASTER_IMPLEMENTATION_PLAN.md`): product
  vision, architecture, domain model, framework boundaries, AI/voice/
  retrieval/evaluation architecture, 13 implementation phases, risk register,
  progress tracker.
- Decision records (`docs/DECISIONS.md` + `docs/architecture/ADR-001..014`):
  framework boundaries, LangGraph workflow, LlamaIndex knowledge layer,
  evidence-first evaluation, pgvector, observability, evaluation strategy,
  security/PII, model stack, oMLX runtime, speech stack, MCP boundary,
  persistence, modular monolith, deployment.
- Model catalog (`docs/MODEL_CATALOG.md`): 8-model definitive V1 stack with
  verified licenses, MLX weights, memory, fallbacks.
- Architecture companions (`docs/ai/`): AI, Voice, Retrieval, Evaluation.
- Operations docs (`docs/operations/`): Deployment, Troubleshooting.
- **Phase 0 scaffold (2026-08):** uv-managed backend (FastAPI 0.139, Pydantic
  2.13, SQLAlchemy 2.0 async, alembic, pgvector 0.5.x), domain enums/schemas/
  typed errors, request-id middleware, structured JSON logging; Vite 8 +
  React 19 + TS strict + Tailwind 4 frontend shell; docker-compose
  (pgvector:pg17), Dockerfiles, nginx, Makefile; CI (ruff, mypy, pytest,
  oxlint, frontend build); tests relocated to repo-root `tests/`; pgvector
  pin correction (client 0.5.x vs server extension 0.8.x).
