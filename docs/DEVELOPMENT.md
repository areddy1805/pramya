# Pramya — Developer Guide

## How do I start Pramya locally?

```bash
make dev
```

That is the canonical entry point. From the repository root it:

1. checks tooling (docker, uv, pnpm, node, curl),
2. starts PostgreSQL via Docker and waits for it to be **healthy**,
3. starts the Langfuse OSS stack (`docker-compose.langfuse.yml`) ONLY when
   opted in with `PRAMYA_DEV_LANGFUSE=1 make dev` (off by default),
4. applies database migrations (`alembic upgrade head`),
5. starts the backend and waits for its health endpoint,
6. starts the frontend and waits for it to serve,
7. verifies the frontend→backend proxy,
8. prints the URLs and status.

When it prints **`Status READY`** the environment is usable.

> First run: `cp .env.example .env` and add your `DEEPSEEK_API_KEY`
> (and Langfuse keys if you want Langfuse). Backend settings are read from
> the repo-root `.env` at process start.

---

## Command reference

| Command | What it does |
|---|---|
| `make dev` | Start the full dev environment (docker db → migrations → backend → frontend). Langfuse is optional and off by default: `PRAMYA_DEV_LANGFUSE=1 make dev` to include it. |
| `make dev-down` | Stop backend + frontend **and** stop the docker dev containers (db + Langfuse; containers preserved, restart with `make dev`). |
| `make dev-status` | Readiness + process state of every dev service. |
| `make dev-logs` | Tail the aggregated backend/frontend launcher logs. |
| `make dev-verify` | Probe-only verification (deps, db, backend, frontend, proxy). No starting. |
| `make dev-reset` | Stop launcher processes **and** `docker compose down` for both compose files (containers removed; volumes preserved — `pgdata` + Langfuse volumes). Full wipe is printed by the command. |
| `make up / down / logs / ps` | Docker compose control for the containerized stack (db, containerized backend/frontend). |
| `make dev-backend` | Backend only (uvicorn `--reload`, port 8001) — manual alternative. |
| `make dev-frontend` | Frontend only (vite, port 3000) — manual alternative. |
| `make migrate` | Apply migrations only. |
| `make test` / `test-unit` / `test-contract` / `test-integration` | Test suites. |
| `make lint` / `typecheck` | ruff + oxlint / mypy + tsc. |
| `make demo-setup` | Seed the demo candidate/role via `scripts/seed_demo.py` (needs backend running). |

The launcher itself is `scripts/dev` (bash); the Makefile targets are thin
wrappers. `scripts/dev check` is the standalone verification command.

## Services and ports

| Service | URL | Notes |
|---|---|---|
| Backend API | http://127.0.0.1:8001 | FastAPI; health at `/api/v1/health` |
| API docs | http://127.0.0.1:8001/docs | OpenAPI |
| Frontend | http://localhost:3000 | Vite dev server; `/api` proxied to backend (incl. voice WebSocket) |
| PostgreSQL | localhost:5432 | Docker `pgvector/pgvector:pg17`, volume `pgdata` |
| Langfuse | http://127.0.0.1:3030 | optional, OFF by default: `PRAMYA_DEV_LANGFUSE=1 make dev` to start (self-hosted OSS stack: postgres/clickhouse/redis/minio + web/worker) |
| oMLX (local AI) | http://127.0.0.1:8000 | External runtime for voice/embeddings/rerank; see `docs/MODEL_CATALOG.md` |

Launcher logs: `.runtime/dev/backend.log`, `.runtime/dev/frontend.log`
(gitignored). PIDs: `.runtime/dev/*.pid`.

## Process management

- `make dev` twice: if the backend or frontend ports are already in use it
  prints `make dev-status` / `make dev-down` and exits — no duplicate
  processes. Docker commands are idempotent (already-running containers are
  left as-is).
- **Ctrl-C** on `make dev` stops the backend + frontend it started; Docker
  containers keep running (restart them with `make dev` or stop with
  `make dev-down`).
- `make dev-down` stops launcher-started processes (PID-file based — it
  never kills unrelated processes) and stops the dev docker containers.

## Troubleshooting

- **`ERROR: 'docker' not found` / daemon not running** → install/start
  Docker Desktop, then `make dev` again.
- **Backend never becomes ready** → `make dev-logs`; typical causes:
  missing `.env`, wrong `DATABASE_URL`, DeepSeek key absent (backend still
  starts), port 8001 already in use.
- **Frontend never becomes ready** → port 3000 conflict; `make dev-down`
  then free the port, retry.
- **Migrations fail** → fix and re-run `make dev` (migrations are
  idempotent; safe to re-run).
- **Voice interview won't connect** → the vite proxy needs `ws: true`
  (it is); ensure oMLX is running on 8000 (`brew services start omlx`) and
  the model weights are present (see `docs/MODEL_CATALOG.md`).

## Architecture notes

- Dev runtime: **local uvicorn (8001) + local vite (3000)** over the
  Dockerized PostgreSQL — this is the primary developer loop.
- The containerized stack (`make up`) is for deployment-shaped validation;
  the launcher only starts the `db` service from it.
- Langfuse runs from a **separate compose file**
  (`docker-compose.langfuse.yml`) and is started by `make dev` by default;
  on memory-constrained machines use `PRAMYA_DEV_LANGFUSE=0 make dev`.

See `README.md` for product/architecture overview, `docs/MASTER_IMPLEMENTATION_PLAN.md`
for roadmap state, and `docs/ai/VOICE_ARCHITECTURE.md` for the voice system.
