# ADR-007 — pgvector

**Status:** Accepted
**Date:** 2026-08

## Context

Vector persistence/retrieval for candidate evidence, resume/JD chunks,
interview context, competencies, historical sessions. Spec: pgvector owns
vector persistence; hybrid retrieval (dense + full-text) required; no second
mandatory database.

## Problem

How to store and query vectors without introducing a new database?

## Decision

- PostgreSQL 18 + pgvector 0.8.6 (HNSW indexes, cosine distance).
- Hybrid retrieval: BGE-M3 dense vectors (HNSW) + PostgreSQL full-text search
  (precomputed `tsvector` generated column + GIN index) + Reciprocal Rank
  Fusion (k=60), then Qwen3-Reranker-0.6B on top-K (~20), then LLM synthesis.
- `sparsevec` (0.7.0+) considered but not required in V1: HNSW-only indexing;
  BGE-M3 sparse output optional later.
- Metadata stored in JSONB columns for filterable retrieval (candidate_id,
  document_type, competency, source, timestamps).
- LlamaIndex `PGVectorStore` (hybrid_search=True) is the integration adapter.

## Alternatives

- Qdrant/Weaviate/Chroma — rejected: extra infra; pgvector in same DB keeps
  operations simple.
- pgvectorscale — rejected unless benchmark shows need (V1 scale small).

## Tradeoffs

- HNSW build/vacuum maintenance (use pgvector ≥0.8.4 fixes); RRF tuning.
- Vector search in OLTP DB is fine at V1 scale.

## Consequences

- Schema: `knowledge_nodes` table with `embedding vector(1024)`, `tsvector`,
  `metadata jsonb`; HNSW + GIN indexes.
- Migration + ingest idempotency tests; retrieval golden tests.
