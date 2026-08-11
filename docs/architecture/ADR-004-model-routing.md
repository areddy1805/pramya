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
- **Canonical model roles (finalized 2026-08):**
  - Qwen3.5-4B (oMLX alias `pramya-4b`) = primary local workhorse. Default
    local model; handles the majority of workload (routine generation,
    extraction, classification, structured generation, semantic tasks,
    interview content generation, ordinary evaluation/support). Thinking off.
  - deepseek-v4-flash = escalation/cloud reasoning model. Used only when the
    workload materially benefits from stronger reasoning/capability/context.
    NOT the default; routine high-volume work never escalates merely because
    cloud is stronger.
  - Qwen3.5-9B = DEFERRED from V1 production stack: not required, not a
    fallback, not a routing target, not a setup dependency.
- Initial policy (task-class decision; 4B local first → escalate only when
  warranted):
  - Routine generation / extraction / classification / structured generation /
    semantic tasks / ordinary evaluation → Qwen3.5-4B (`pramya-4b`, OMLX)
  - Deep evaluation / complex reasoning / adaptive reasoning / system design /
    final synthesis / difficult follow-ups → deepseek-v4-flash (escalation)
  - Embeddings → BGE-M3 (OMLX `/v1/embeddings`)
  - Reranking → Qwen3-Reranker-0.6B (OMLX `/v1/rerank`)
  - Live ASR → Parakeet-TDT-0.6B-v3
  - Recorded/multilingual ASR → Qwen3-ASR-1.7B
  - TTS → Qwen3-TTS-0.6B
- Routing decision flow: 4B first → application-level task-class decision →
  can 4B handle this adequately? yes → 4B; no → deepseek-v4-flash. No
  arbitrary "complexity = cloud" heuristic beyond the task-class policy.
- Every routing decision observable: task, provider, model, reason, latency,
  tokens, cost estimate, fallback, cache hit/miss, errors.

Architecture principle: **the strongest model is not the default model.**
Local 4B handles the majority of workload; cloud escalation is reserved for
workloads where additional capability is justified.

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
