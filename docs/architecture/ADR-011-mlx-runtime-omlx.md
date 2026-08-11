# ADR-011 — MLX Local Runtime + OMLX Server

**Status:** Accepted
**Date:** 2026-08

## Context

Target hardware: MacBook Pro M4, 16 GB unified memory, 512 GB storage. Local
models are first-class. Resource-aware lifecycle required: lazy load, memory
limits, unload, concurrency bounds, cancellation, health checks, fallback.

## Problem

How to run LLM/embeddings/reranker locally without exhausting 16 GB and
without coupling business logic to MLX specifics?

## Decision

- **OMLX (Apache 2.0, ~0.2.7+) is the local inference server** for LLM,
  embeddings, reranker: OpenAI-compatible `/v1/chat/completions`,
  `/v1/embeddings`, `/v1/rerank`; multi-model serving with LRU eviction,
  model pinning, per-model TTL; continuous batching; SSD-tiered KV cache.
- OMLX owns model lifecycle (load/unload). Pramya owns routing policy,
  health checks, concurrency limits, fallback.
- **Speech models are NOT served by OMLX**: Parakeet v3 via `parakeet-mlx`
  (streaming API), Qwen3-ASR via `mlx-audio`, Qwen3-TTS via MLX TTS paths.
  They get dedicated lifecycle managers inside the voice service.
- Provider abstraction: `InferenceProvider` (generate/embed/rerank) →
  `DeepSeekProvider` / `MLXProvider` (OMLX client). No MLX imports in
  business logic.
- Model selection is configuration, not code: task → policy → provider/model.

## Alternatives

- Ollama — rejected (spec: do not introduce Ollama merely for convenience).
- Direct mlx-lm embedding calls — rejected: `mlx-embeddings` (Blaizzy) is
  GPL-3.0; OMLX serves the same MLX weights under Apache 2.0.
- VMLX / mlx-serve — noted; OMLX selected for Apache license, active
  maintenance, embeddings+rerank endpoints.

## Tradeoffs

- OMLX is younger than Ollama; pin versions, health-check before use.
- One more local process; mitigated by Docker/brew services.

## Consequences

- `packages/ai/providers/` (deepseek, omlx, speech), `runtime/` health +
  lifecycle managers.
- Degraded-mode matrix: OMLX down → local LLM tasks fall back to
  deepseek-v4-flash or fail gracefully; embeddings down → degraded retrieval.
- ADR-012 (voice models), ADR-013 (DeepSeek), ADR-014 (retrieval models).
