# ADR-008 — Observability

**Status:** Accepted
**Date:** 2026-08

## Context

Interviews must be traceable end-to-end: LangGraph run → question generation →
retrieval → evaluation → evidence extraction → tool calls. Capture latency,
model, tokens, estimated cost, prompt version, retrieval context, tool calls,
failures, evaluation results. Do not leak PII/candidate content.

## Problem

How to observe AI workflows without exposing sensitive data?

## Decision

- Langfuse Python SDK 4.x (OTel-based; `get_client()` singleton) as the
  observability backend, self-hosted/local by default.
- LangGraph traced via `langfuse.langchain.CallbackHandler` in graph config;
  one trace per interview invocation, `thread_id`/`session_id` propagation.
- LlamaIndex via `openinference-instrumentation-llama-index` (native callback
  deprecated in SDK v4).
- Structured telemetry fields: request_id, session_id, turn_id, graph_node,
  model, provider, latency, tokens, cache_hit, retrieval_count,
  reranker_count, ASR latency, TTS latency, time_to_first_audio,
  interruption_count, error, fallback.
- Redaction policy: never put raw resume contents or candidate answer content
  in traces; store IDs and redacted metadata. Explicit env flag controls any
  debug-level content capture (off by default).
- Langfuse prompts management for versioned prompts.

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
