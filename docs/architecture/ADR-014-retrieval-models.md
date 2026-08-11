# ADR-014 — Retrieval Models: BGE-M3 + Qwen3-Reranker-0.6B

**Status:** Accepted
**Date:** 2026-08

## Context

Evidence retrieval across resumes, JDs, transcripts, competencies, historical
sessions. Spec mandates BGE-M3 embeddings + Qwen3-Reranker-0.6B. Verified:
BGE-M3 MIT, 1024-dim, 8192 seq, 100+ langs, MLX 8-bit ~592 MB; reranker
Apache 2.0, MLX 4-bit ~331 MB, yes/no logit scoring. Licensing trap: Python
`mlx-embeddings` (Blaizzy) is GPL-3.0 → serve via OMLX endpoints instead.

## Problem

How to build retrieval that is precise, multilingual, cheap, and license-clean?

## Decision

- Embeddings: BGE-M3 (8-bit) via OMLX `/v1/embeddings` — dense vectors into
  pgvector HNSW; batch indexing with deterministic IDs + upsert.
- Rerank: Qwen3-Reranker-0.6B (4-bit) via OMLX `/v1/rerank` on top-K (~20)
  from hybrid fusion; only then LLM synthesis. Never send whole profile to
  the LLM.
- Hybrid retrieval (ADR-007): BGE-M3 dense + tsvector full-text + RRF(k=60)
  → rerank → evidence selection.
- Evidence nodes carry provenance metadata (source doc, claim vs observed vs
  demonstrated, competency, session, timestamp) for filterable retrieval.

## Alternatives

- GPL `mlx-embeddings` direct — rejected (license conflict).
- Cloud embeddings (OpenAI) — rejected: cost + privacy.
- Skip reranker — rejected: precision loss on evidence matching.

## Tradeoffs

- Two retrieval hops (embed+rerank) add latency; rerank is tiny (~0.5 GB).
- OMLX rerank endpoint maturity — fallback: in-process rerank via mlx-lm
  (Apache-compatible path) if endpoint issues; documented in troubleshooting.

## Consequences

- `packages/ai/providers/omlx.py` embed+rerank clients; `packages/knowledge/`
  retrieval pipeline; retrieval golden tests (precision/recall on synthetic
  corpus); RAG evals via DeepEval (ADR-009).
