# ADR-004 — Model Routing

**Status:** Accepted
**Date:** 2026-08

## Context

Multiple models (cloud + local + speech) exist with different cost, latency,
quality. The architecture must route by task, keep routing observable, and
avoid a model-coupled application.

## Problem

`InterviewService → DeepSeek` or `VoiceService → Parakeet` hard-wires models
into business logic. Cost control and fallback require a routing layer.

## Decision

Layered inference architecture:

```
Application → InferenceRouter → TaskPolicy → Provider → Model → Runtime
```

- `InferenceProvider` abstraction with capabilities: `generate()`, `embed()`,
  `rerank()`, `transcribe()`, `synthesize()`.
- `DeepSeekProvider` (OpenAI-compatible, `deepseek-v4-flash` only; thinking
  mode per task policy) and `MLXProvider` (OMLX) behind one interface.
- Initial policy:
  - Extraction / classification / simple summary → Qwen3.5-4B (OMLX)
  - Local reasoning / candidate analysis / local eval → Qwen3.5-9B (OMLX)
  - Question generation / deep evaluation / complex reasoning / synthesis →
    deepseek-v4-flash
  - Embeddings → BGE-M3 (OMLX `/v1/embeddings`)
  - Reranking → Qwen3-Reranker-0.6B (OMLX `/v1/rerank`)
  - Live ASR → Parakeet-TDT-0.6B-v3
  - Recorded/multilingual ASR → Qwen3-ASR-1.7B
  - TTS → Qwen3-TTS-0.6B
- Every routing decision observable: task, provider, model, reason, latency,
  tokens, cost estimate, fallback, cache hit/miss, errors.

## Alternatives

- Single frontier model for everything — rejected: cost/latency.
- Hard-coded model constants in services — rejected: replaceability.

## Tradeoffs

- Router adds indirection; needs a task registry and health checks.
- Policy is config (env/DB), not code, so operators can tune.

## Consequences

- `packages/ai/router/` + provider adapters; task policies in config.
- Telemetry includes routing fields; tests cover policy selection, fallback,
  unavailable-OMLX degradation.
