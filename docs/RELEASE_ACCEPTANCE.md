# Pramya V1 — Release Acceptance Matrix

> Status as of 2026-08-12, branch `work/runtime-integration`. Each criterion
> from the Release Standard (plan §66 / §38) is mapped to evidence: code,
> tests, and runtime verification. Nothing here is asserted without evidence.

Legend: ✅ verified · ⚠️ partial / known variance · ❌ not met · ⏸ deferred

## Release Standard criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Complete text journey (profile → resume → role → readiness → prep → interview → evaluation → report) with no dev intervention | ✅ | Browser E2E (`frontend/e2e/text-journey.spec.ts`) drives dashboard + full typed interview through the real UI against the real backend; `make e2e` green 2/2, 3 consecutive runs |
| 2 | Voice journey (question TTS → candidate speech → ASR → evaluation → adaptive follow-up) | ✅ | Real-model E2E passed 2026-08-12 (sessions 39/40/41): 20 ASR partials, 9 TTS syntheses, interrupt concedes zero stale chunks; engine unit coverage 14 tests |
| 3 | Interruption correctness: no stale TTS after interrupt/cancel | ✅ | H.7 generation-gated TTS server+client; interrupt-mid-TTS unit tests; real-model E2E interrupt assertion |
| 4 | Deterministic, evidence-backed readiness | ✅ | `app/services/readiness.py` pure functions; 9 golden unit tests; evidence provenance ladder (claimed/observed/demonstrated/inferred/unknown); live `/readiness/latest` returns real per-competency math |
| 5 | Second interview adapts to first-interview weaknesses | ⚠️ | Adaptive generation passes `session_history` + evidence summary into the prompt (verified in logs/E2E: follow-up referenced the prior answer). Full cross-session weakness-driven adaptation not yet E2E-asserted |
| 6 | Framework boundaries removable / honest | ✅ | Deterministic engines (chunking, retrieval, readiness, interview state machine) replace planned frameworks per ADR-021/022/023; LangChain layer routes through the InferenceRouter; framework posture documented in README |
| 7 | Fresh-clone quickstart works | ✅ | Phase M: fresh-DB `alembic upgrade head` (23 tables), backend boots with example-only env, `make test/lint/typecheck` from repo root, seed idempotent |
| 8 | No secrets committed | ✅ | `.env` gitignored; secret-pattern scan of tracked files clean; `pip-audit` no known vulnerabilities |
| 9 | Model stack per MODEL_CATALOG, routing observable | ✅ | ADR-023 topology (DeepSeek sole text LLM; oMLX voice+retrieval); routing decisions logged with provider/model/latency/tokens; `/models/status` reflects reality |

## Product-capability matrix (FR traceability, headline items)

| FR | Status | Evidence |
|---|---|---|
| FR-1..4 candidate profile, resume, JD analysis, evidence profile | ✅ | CRUD + extraction/role-analysis services; integration tests; live demo data |
| FR-5..6 competency graph, gap analysis → prep plan | ✅ | Role competency graph persisted; readiness + preparation engines with golden tests; live prep queue after demo |
| FR-7..9 interview modes, adaptive questioning, progressive hints | ✅ | 8 modes; adaptive prompt with history; 4-level hints (hints_used persisted) |
| FR-10..11 evaluation dimensions, deterministic readiness | ✅ | 13 evaluation dimensions; readiness calculator |
| FR-12..14 prep queue, story bank, progress tracking | ✅ | `/preparation`, stories CRUD UI, `/progress` aggregation |
| FR-15..17 interview memory, debrief, transcript analysis | ✅ | Interview record endpoint + transcript page; debrief create/analyze UI; transcript analyze endpoint |
| FR-18..19 voice interviewing, communication analysis | ✅ | WS voice engine (H.1–H.12); deterministic communication analysis endpoint |
| FR-20 demo mode | ✅ | 4-role idempotent demo setup (API + `make demo-setup` + UI) |
| FR-21..22 model/runtime status, history | ✅ | `/models/status` + Runtime page; History page |
| FR-23 local-first/hybrid/cloud modes | ⚠️ | Local + DeepSeek routing exists; explicit mode switching not a UI feature |
| FR-24 MCP read-oriented surface | ❌ | ADR-006 accepted; `app/mcp_server/` stub only |

## Known gaps / honest status

- **MCP server** — not implemented (stub). ADR-006 accepted.
- **Langfuse** — config fields + self-hosted compose profile exist; SDK
  integration not wired (observability = structured JSON logs + routing
  telemetry). Docs state this plainly.
- **Eval suite** — COMPLETE WITH KNOWN WARNINGS: golden-data harness under
  `tests/evals` (95 checks, 0 FAIL, 3 WARNING in the recorded run); borderline
  DeepSeek judge variance is classified WARNING, never gamed to PASS.
- **Auth** — API bearer tokens implemented (opt-in via `API_TOKENS`); no
  per-user accounts/sessions (single-user local model, plan §19).
- **Real voice E2E on this machine** — previously passed; not re-run this
  session per Mac memory policy (would need one controlled run to re-verify).
- **Release packaging** (Docker image polish, CI release job, PyPI/Homebrew
  distribution) — deferred.

## Release verdict

**V1 FUNCTIONALLY COMPLETE BUT NOT RELEASE READY** — all core product loops
are integrated and runtime-tested (text E2E green this session, voice E2E
passed, 182 unit+contract + 36 integration tests green, clean static checks),
but the Release Standard additionally requires MCP + Langfuse presence for
the planned interop/observability surface (FR-24, observability section) and
release packaging — those remain not implemented, so the V1 label is
withheld until they land or are explicitly descoped.
