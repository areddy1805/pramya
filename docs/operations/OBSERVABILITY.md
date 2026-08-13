# Pramya — Observability

> Langfuse OSS (self-hosted, MIT-licensed) tracing. ADR-008
> (docs/architecture/ADR-008-observability.md). Redaction is mandatory.
> Langfuse Cloud and Enterprise-only features are not V1 dependencies.

## Runtime Status (Phase E — verified 2026-08-12)

The self-hosted Langfuse stack is a **real execution path**, verified with a
real DeepSeek operation. Trace ingestion uses the **official Langfuse Python
SDK v4 directly** (native `/api/public/ingestion`); it is **not** an
OpenTelemetry/OpenInference pipeline — there is no OTel exporter or LangChain
callback handler in the codebase. The stack itself is the full Langfuse OSS
composition:

```
Pramya trace_span / record_event
  → langfuse SDK v4 (direct ingestion)
  → langfuse-web (3030) → worker → ClickHouse
  → S3/MinIO event staging (events/otel/pramya-v1/…)
  → queryable via GET /api/public/traces
```

> Honest limitation: spans are sent only when `LANGFUSE_PUBLIC_KEY` +
> `LANGFUSE_SECRET_KEY` are configured; otherwise the facade degrades to
> structured JSON logs. OTel instrumentation is deferred.

- `GET http://127.0.0.1:3030/api/public/health` → 200
- Trace query with project API key (Basic auth) returned the real trace.
- **Degradation-safe proven**: with the Langfuse container stopped, the same
  endpoint returned 201; the OTel exporter retried then dropped the batch
  without crashing or blocking the request.

## Stack (docker-compose.langfuse.yml, profile `langfuse`)

Start:

```sh
docker compose -f docker-compose.yml -f docker-compose.langfuse.yml \
  --profile langfuse up -d
```

| Service | Image | Role |
|---|---|---|
| langfuse | langfuse/langfuse:3 | Web UI + API (port 3030 host) |
| langfuse-worker | langfuse/langfuse-worker:3 | Drains S3 events → ClickHouse |
| langfuse-db | postgres:16 | Langfuse metadata |
| langfuse-redis | redis:7-alpine | BullMQ queues |
| langfuse-clickhouse | clickhouse-server:24.8 | Trace/observation storage |
| langfuse-minio | minio/minio:latest | S3 event staging (`langfuse` bucket) |

Port **3030** (not 3000): the Pramya frontend dev server owns `::1:3000`;
Docker publishes IPv4, so `localhost` may resolve to `::1` first. Use
`127.0.0.1:3030` for all checks and for `LANGFUSE_HOST`.

Non-obvious config (all in `docker-compose.langfuse.yml` +
`infra/langfuse/clickhouse-keeper.xml`):

- `CLICKHOUSE_MIGRATION_URL` must be `clickhouse://` (native, port 9000);
  `CLICKHOUSE_URL` is `http://` (port 8123). Both need explicit
  `CLICKHOUSE_USER` / `CLICKHOUSE_PASSWORD`.
- ClickHouse `ReplicatedMergeTree` tables require ZooKeeper → embedded
  **keeper** config + `{shard}`/`{replica}` macros (infra/langfuse/
  clickhouse-keeper.xml).
- S3 contract is `LANGFUSE_S3_EVENT_UPLOAD_*` (region, access/secret,
  endpoint, bucket, force-path-style=true, prefix `events/`); the MinIO
  bucket must exist (`mc mb local/langfuse`).
- The worker is a **separate image**; the web container alone cannot ingest
  traces into ClickHouse.
- Web container needs `REDIS_HOST`/`REDIS_PORT` (not only `REDIS_URL`) or
  queue instantiation fails.

## What We Trace

```
Interview
 └── LangGraph run
      ├── question generation   (task, competency, difficulty, seniority)
      ├── retrieval             (query_len, degraded flags)
      ├── evaluation            (task, hints_used)
      ├── evidence extraction   (document_id)
      └── role analysis         (task)
Voice: voice_tts (latency, bytes), voice_asr (latency, audio bytes),
voice_interrupt (interruption_count), voice_turn
```

Wired via `app/observability`:

- `trace_span("question_generation", ...)` — LangChain question/eval paths
- `trace_span("retrieval", ...)` — hybrid retrieval (vector+FTS+RRF+rerank)
- `trace_span("evidence_extraction" / "role_analysis", ...)`
- `record_event("voice_tts" / "voice_asr" / "voice_interrupt", ...)`

## Facade (degradation-safe)

`app/observability/__init__.py`:

- `get_observability()` singleton → `LangfuseObservability` when
  `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` are configured, else
  `NullObservability` (structured logs).
- `trace_span(name, **metadata)` async context manager: start → finish
  (error captured) → flush. Never raises into the caller path.
- `record_event(name, **metadata)` fire-and-forget telemetry (voice).
- `reset_observability()` test seam.

## Telemetry Fields

request_id · session_id · turn_id · graph_node · model · provider · task ·
latency · tokens (in/out) · retrieval_count · reranker_count · ASR/TTS
latency · time_to_first_audio · interruption_count · error · fallback.

## Redaction Policy

- **Never** put raw resume contents, answers, or transcript text in traces.
- Use IDs + redacted metadata (e.g., `document_id=…`, `competency=…`,
  `query_len=…`).
- Debug content capture behind explicit env flag, **off by default**.
- Tests (`tests/unit/test_observability.py`) assert trace payloads contain
  no candidate content.

## Prompt Management

Prompts versioned in `prompts/`; evaluation records store prompt_version +
evaluator_version. Langfuse prompt management (MIT, OSS) optional; versioned
prompts remain the source of truth regardless.

## Health / Degradation

- oMLX health, DeepSeek reachability, model status surfaced via
  `/api/v1/models/status`.
- Every degraded-mode decision (fallback used) logged with reason.
- Langfuse down → structured-log fallback; never breaks interview/voice.
