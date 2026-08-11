# Pramya — Retrieval Architecture

> Companion to master plan §12 and ADR-008/010.
> LlamaIndex ingestion + pgvector hybrid retrieval + reranking.

---

## 1. Purpose

Retrieve the right evidence for: question generation, answer evaluation, follow-up selection, report generation, transcript/debrief analysis, practice recommendation. Never dump whole documents into prompts.

## 2. Ingestion Pipeline (LlamaIndex 0.14)

```
document (pdf/docx/txt/md, validated) 
  → parse (pypdf / python-docx / markdown; timeouts; untrusted-input guards)
  → chunk (text-splitters; size tuned ~512–768 tokens w/ overlap)
  → metadata (document_id, kind, section, page, hash, user_id)
  → embed (BGE-M3 via oMLX, 1024-dim, batch)
  → write document_chunk rows (pgvector) + docstore tracking
```

- **Dedup**: `IngestionPipeline` does NOT dedupe against the vector store (verified 0.12–0.14 behavior). Explicit docstore (document hash → chunks) ensures idempotent re-ingestion: skip unchanged, replace changed, delete removed.
- Re-upload = new document id; previous document retained or marked superseded per privacy policy.

## 3. Collections (namespace by document_kind / metadata)

| Collection | Contains |
|---|---|
| resume-evidence | resume chunks + extracted claims |
| jd-requirements | JD chunks + role requirements |
| interview-history | turns, evaluations, transcripts |
| competency-library | competency definitions |
| story-library | candidate stories |

## 4. Hybrid Search

```
query → embed (BGE-M3)
  → vector search (cosine, HNSW, top-k×3)
  → + FTS (plainto_tsquery + ts_rank_cd, GIN)
  → RRF fusion (k=60)
  → Qwen3-Reranker-0.6B (top ~20 → top-K)
  → evidence selection
```

- Fetch top-k×3 before fusion; RRF k=60; final rerank picks top-K (K configurable, default 5–8).
- Metadata filters (user_id, document_kind, competency_id, time range) applied before ANN where supported.
- FTS handles exact tokens (IDs, acronyms, tech names) that semantic search misses.

## 5. Retrieval Service Interface

```python
class KnowledgeService:
    async def ingest_document(doc) -> IngestResult
    async def search_evidence(query, filters, top_k) -> list[EvidenceHit]
    async def get_competency_context(competency_id) -> list[Chunk]
    async def get_candidate_summary(candidate_id) -> str  # bounded, redacted
```

Used by interview graph nodes and analysis pipelines; testable with fixtures; providers swappable.

## 6. Evaluation of Retrieval

- Golden queries per collection with expected hits (deterministic recall checks).
- DeepEval RAG metrics where semantic: ContextualPrecision/Recall/Relevancy, Faithfulness (ADR-012).
- Rerank ordering asserted in fixtures.

## 7. Known Gotchas (verified)

- LlamaIndex node hash excludes metadata (issue #17871) → explicit docstore comparison by content hash, not node hash alone.
- Ingestion dedup only within batch → our docstore handles cross-run.
- Vector dimension changes require full re-embed + migration → locked at 1024.
