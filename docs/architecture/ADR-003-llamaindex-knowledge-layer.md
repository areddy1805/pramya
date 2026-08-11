# ADR-003 — LlamaIndex Knowledge Layer

**Status:** Accepted
**Date:** 2026-08

## Context

Resumes, JDs, interview transcripts, project evidence, and competency
descriptions must be ingested, chunked, embedded, indexed, and retrieved with
metadata. This is a document/retrieval concern, separate from workflow state.

## Problem

Where does document processing and RAG retrieval live? Duplicating ingestion
between LangChain and LlamaIndex is forbidden.

## Decision

LlamaIndex core 0.14.x owns the knowledge/retrieval layer, used narrowly:

- `IngestionPipeline` (SentenceSplitter chunks, metadata extractors,
  embedding stage) for resume/JD/evidence ingestion.
- `PGVectorStore` (llama-index-vector-stores-postgres 0.8.x) with
  `hybrid_search=True` (dense + full-text) and HNSW kwargs.
- `PostgresDocumentStore` for incremental ingestion/dedup.
- Query-time: `VectorStoreIndex.from_vector_store(...)` (never rebuild per
  request), retrieve top-K with metadata filters, hand candidates to the
  reranker (ADR-014), then to synthesis.

Domain workflow state, candidate model, evidence ledger: plain domain code —
LlamaIndex never owns application state.

## Alternatives

- LangChain retrievers — rejected: overlapping responsibility; spec assigns
  ingestion/retrieval to LlamaIndex.
- Raw pgvector SQL everywhere — rejected: lose ingestion pipeline, chunking,
  docstore dedup.

## Tradeoffs

- Third abstraction to learn; LlamaIndex release churn (0.14.x).
- Keep the adapter thin; retrieval service interface hides LlamaIndex.

## Consequences

- `packages/knowledge/` module wraps ingestion + retrieval.
- Observability via OpenInference instrumentation (Langfuse OSS v4 path —
  native llama-index callback deprecated).
- Tests: ingestion idempotency, hybrid retrieval, metadata filters, rerank.
