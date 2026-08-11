# Pramya — Deployment & Operations

> Companion to master plan §34. Proportional infra; fresh-clone quickstart is the bar.

---

## 1. Local Development (target: M4 16GB macOS)

Prerequisites: Python 3.12/3.13 (uv), Node 24, Docker 27, oMLX (host install), DeepSeek API key (optional for local-only).

```bash
git clone <repo> && cd pramya
cp .env.example .env        # edit: DATABASE_URL, DEEPSEEK_API_KEY, OMLX_BASE_URL
docker compose up -d        # postgres+pgvector (+ optional langfuse OSS profile)
make models-pull            # downloads pinned local models via oMLX (see MODEL_CATALOG)
make migrate
make dev-backend            # uvicorn on :8001 (oMLX owns :8000)
make dev-frontend           # vite on :5173
make demo-setup             # synthetic Senior Full Stack Engineer demo
```

Open http://localhost:5173 → onboarding → demo.

## 2. Environment Variables (`.env.example`)

| Var | Purpose |
|---|---|
| APP_ENV / APP_HOST / APP_PORT | app config |
| DATABASE_URL | `postgresql+asyncpg://pramya:pramya@localhost:5432/pramya` |
| DEEPSEEK_API_KEY | cloud reasoning |
| DEEPSEEK_BASE_URL | default `https://api.deepseek.com` |
| OMLX_BASE_URL | default `http://localhost:8000/v1` (oMLX default port; may differ) |
| OMLX_API_KEY | optional |
| LOCAL_AI_ENABLED | true |
| LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_HOST | optional observability (OSS self-hosted; Cloud/Enterprise not V1) |
| VOICE_RETENTION_DAYS | audio retention (default 0 = do not store audio) |
| UPLOAD_MAX_MB | default 5 |
| RATE_LIMIT_* | app-level token bucket |
| VITE_API_URL | frontend → backend |

Never commit `.env`. Secrets only via env.

## 3. Docker Compose

Services: `db` (pgvector/pgvector:pg17), `backend` (uvicorn, depends on db), `frontend` (vite dev or nginx serving build). Optional profiles: `langfuse` (OSS v4: web + worker + its own postgres/clickhouse/redis/s3 — heavy; skip on 16GB dev unless needed).

## 4. Local AI Runtime (oMLX)

- Runs on host (Metal access): brew (`brew services start omlx`) or DMG. Backend reaches via `OMLX_BASE_URL`.
- Models: per `docs/MODEL_CATALOG.md` — Qwen3.5-4B 4-bit (required, alias `pramya-4b`), BGE-M3, Qwen3-Reranker-0.6B, Parakeet-TDT-0.6B-v3 (int8), Qwen3-ASR-1.7B, Qwen3-TTS-0.6B. Qwen3.5-9B is NOT required (deferred — see catalog §2.3); a fresh environment must not download it.
- `make models-pull` downloads only the required V1 model set (no 9B).
- Resource control: model artifacts may coexist on disk; oMLX dynamically loads/manages models under its memory policy, with memory residency determined by demand, cache state, TTL/pinning, and the configured memory guard. The catalog §3 budget rules still apply (pinning/TTL/LRU + memory enforcement; not every model resident at once). Lifecycle managed by oMLX.
- Fallbacks if oMLX unavailable: app degrades (ASR→manual transcript, TTS→text, cloud→local, local→cloud per policy).

## 5. Production (documented path, proportional)

- Backend + frontend behind reverse proxy (Caddy/nginx); TLS.
- Managed PostgreSQL with pgvector (or same image on a small VM).
- oMLX on an Apple Silicon host (or swap MLXProvider for a cloud OpenAI-compatible endpoint).
- Env-driven; secrets via host secrets; no secrets in repo.
- Backup/recovery: pg_dump schedules; document in ops runbook.
- Observability: Langfuse OSS self-hosted (MIT) or structured logs to stdout; no Cloud dependency.

## 6. Performance Targets (recorded after measurement, not fabricated)

Record in TROUBLESHOOTING.md + this doc once measured (Phase 8/12): API latency, LLM latency (per provider/model), retrieval latency, DB latency, TTFA, TTF-transcript, token usage, model selection stats, cache effectiveness, cost per interview, memory peak under load.

## 7. Health / Monitoring

- `/api/v1/health` (app), `/api/v1/models/status` (providers + loaded models), DB connectivity check.
- Structured logs: request_id/session_id/turn_id/graph_node/model/provider/latency/tokens/errors (ADR-008).

## 8. Release Checklist (spec §57)

- [ ] all tests pass, eval suite passes
- [ ] Docker + fresh-clone setup verified
- [ ] demo works end-to-end (text + voice)
- [ ] README complete; screenshots current; architecture diagram current
- [ ] no secrets; license audit complete (incl. model licenses, CC-BY-4.0 attribution)
- [ ] dependency audit (pip/npm audit)
- [ ] security review checklist complete
- [ ] known limitations documented; changelog updated
- [ ] release tag + notes
