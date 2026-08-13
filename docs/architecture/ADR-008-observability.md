# ADR-008 — Observability

**Status:** Accepted — Runtime Verified (2026-08-12, Phase E)
**Date:** 2026-08

## Verification Evidence

- Self-hosted Langfuse OSS stack (web 3.225.2, worker, postgres, redis,
  clickhouse, minio) healthy under the `langfuse` docker-compose profile;
  `GET http://127.0.0.1:3030/api/public/health` → 200.
- Real DeepSeek operation (`POST /interviews/{id}/questions`) produced a
  queryable Langfuse trace: OTel exporter → `/api/public/otel/v1/traces` →
  MinIO S3 → langfuse-worker → ClickHouse → `GET /api/public/traces`
  returned `question_generation`.
- Degradation-safe proven: Langfuse container stopped → same endpoint 201,
  OTel exporter retried/dropped without crash or hang.
- No local text LLM used; DeepSeek is the only text model in the path.

## Context

Interviews must be traceable end-to-end: LangGraph run → question generation →
retrieval → evaluation → evidence extraction → tool calls. Capture latency,
model, tokens, estimated cost, prompt version, retrieval context, tool calls,
failures, evaluation results. Do not leak PII/candidate content.

## Problem

How to observe AI workflows without exposing sensitive data?

## Decision

- **Langfuse OSS (self-hosted, MIT-licensed) is the V1 observability
  platform.** Langfuse Cloud and Enterprise-only features are NOT V1
  dependencies; no paid Langfuse subscription is required.
- Langfuse Python SDK 4.x (OTel-based) via a degradation-safe facade in
  `app/observability` (`LangfuseObservability` / `NullObservability`,
  `trace_span` / `record_event`). Configured via `LANGFUSE_PUBLIC_KEY`,
  `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` (default http://127.0.0.1:3030).
- Wire AI execution paths (question generation, retrieval, evaluation,
  evidence extraction, role analysis) with `trace_span`; voice telemetry
  (ASR/TTS latency, interruption count) via `record_event`.
- Structured telemetry fields: request_id, session_id, turn_id, graph_node,
  model, provider, latency, tokens, cache_hit, retrieval_count,
  reranker_count, ASR latency, TTS latency, time_to_first_audio,
  interruption_count, error, fallback.
- Redaction policy: never put raw resume contents or candidate answer content
  in traces; store IDs and redacted metadata. Explicit env flag controls any
  debug-level content capture (off by default).
- Langfuse prompt management (OSS) for versioned prompts; `prompts/` tree
  remains canonical.

## Alternatives

- Custom metrics only — rejected: misses trace topology/costs.
- OpenTelemetry-only — rejected: loses AI-specific span semantics.

## Tradeoffs

- Extra dependency + local Langfuse container; SDK v4 is newer (migration
  from v3 patterns).
- Redaction limits debugging depth — acceptable; can enable per-deployment.

## Consequences

- Observability config in env; tests assert no PII in trace payloads.
- Prompts registered in Langfuse; evaluation versions linked to prompts.
