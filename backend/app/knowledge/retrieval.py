"""Hybrid retrieval service (Phase 2.3).

Query -> BGE-M3 embedding -> pgvector cosine search + PostgreSQL FTS
(plainto_tsquery) -> RRF fusion (k=60) -> Qwen3-Reranker-0.6B rerank ->
top-K evidence chunks. Degradation is explicit: embedding failure falls
back to FTS-only; rerank failure returns RRF order (caller can decide).
All model access goes through the InferenceRouter — never direct provider
calls (ADR-004, ADR-011).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from pgvector.sqlalchemy import Vector
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.errors import AIError, ProviderConnectionError
from app.ai.router import InferenceRouter
from app.core.logging import get_logger
from app.domain.enums import DocumentKind
from app.models.document import Document, DocumentChunk
from app.repositories.document import DocumentChunkRepository

RRF_K = 60
DEFAULT_TOP_K = 5
DEFAULT_FETCH_PER_SIDE = 20


@dataclass(frozen=True)
class RetrievedChunk:
    """One retrieved evidence chunk."""

    chunk_id: int
    document_id: int
    chunk_index: int
    content: str
    score: float
    kind: str
    metadata: dict[str, object]


@dataclass(frozen=True)
class RetrievalResult:
    """Retrieval outcome with degradation flags (observable)."""

    chunks: list[RetrievedChunk]
    degraded: bool
    degradation: str | None  # e.g. "embedding_unavailable" | "rerank_unavailable"
    vector_used: bool
    fts_used: bool
    rerank_used: bool


class RetrievalService:
    """Hybrid retrieval: vector + FTS + RRF + rerank over pgvector."""

    def __init__(
        self,
        session: AsyncSession,
        router: InferenceRouter,
        *,
        top_k: int = DEFAULT_TOP_K,
        fetch_per_side: int = DEFAULT_FETCH_PER_SIDE,
        logger: logging.Logger | None = None,
    ) -> None:
        self.session = session
        self.router = router
        self.top_k = top_k
        self.fetch_per_side = fetch_per_side
        self.chunks = DocumentChunkRepository(session)
        self._logger = logger or get_logger("app.knowledge.retrieval")

    async def search(
        self,
        user_id: int,
        query: str,
        *,
        kind: DocumentKind | None = None,
        top_k: int | None = None,
    ) -> RetrievalResult:
        """Search user-scoped chunks and rerank. Never raises on provider
        failure — degrades (FTS-only / no-rerank) and reports the flag."""
        k = top_k or self.top_k
        if not query.strip():
            return RetrievalResult(
                [],
                degraded=False,
                degradation=None,
                vector_used=False,
                fts_used=False,
                rerank_used=False,
            )

        vector_hits: list[RetrievedChunk] = []
        fts_hits: list[RetrievedChunk] = []
        vector_used = False
        fts_used = False

        # -- vector leg ------------------------------------------------------
        try:
            embed_resp = await self.router.embed([query])
            query_vec = embed_resp.embeddings[0]
            vector_hits = list(
                await self._vector_search(user_id, query_vec, kind=kind, limit=self.fetch_per_side)
            )
            vector_used = True
        except (ProviderConnectionError, AIError):
            self._logger.warning("embedding unavailable; FTS-only retrieval")

        # -- fts leg ---------------------------------------------------------
        fts_hits = list(
            await self._fts_search(user_id, query, kind=kind, limit=self.fetch_per_side)
        )
        fts_used = bool(fts_hits)

        if not vector_hits and not fts_hits:
            return RetrievalResult(
                [],
                degraded=not vector_used,
                degradation=None if vector_used else "embedding_unavailable",
                vector_used=vector_used,
                fts_used=fts_used,
                rerank_used=False,
            )

        fused = _rrf_fuse(vector_hits, fts_hits)
        fused = fused[: self.fetch_per_side * 3]

        # -- rerank leg ------------------------------------------------------
        rerank_used = False
        degradation: str | None = None if vector_used else "embedding_unavailable"
        try:
            if len(fused) > 1:
                reranked = await self.router.rerank(query, [c.content for c in fused], top_n=k)
                order = {item.index: item.score for item in reranked.results}
                fused = sorted(fused, key=lambda c: order.get(fused.index(c), 0.0), reverse=True)
                rerank_used = True
        except (ProviderConnectionError, AIError):
            degradation = "rerank_unavailable" if degradation is None else degradation
            self._logger.warning("rerank unavailable; RRF order used")

        chunks = fused[:k]
        return RetrievalResult(
            chunks=chunks,
            degraded=degradation is not None,
            degradation=degradation,
            vector_used=vector_used,
            fts_used=fts_used,
            rerank_used=rerank_used,
        )

    async def _vector_search(
        self,
        user_id: int,
        query_vec: list[float],
        *,
        kind: DocumentKind | None,
        limit: int,
    ) -> list[RetrievedChunk]:
        vec = cast(query_vec, Vector(1024))
        stmt = (
            select(
                DocumentChunk,
                Document.kind,
                (1 - DocumentChunk.embedding.cosine_distance(vec)).label("score"),
            )
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(Document.user_id == user_id, DocumentChunk.embedding.isnot(None))
            .order_by(DocumentChunk.embedding.cosine_distance(vec))
            .limit(limit)
        )
        if kind is not None:
            stmt = stmt.where(Document.kind == kind)
        rows = (await self.session.execute(stmt)).all()
        return [
            self._to_chunk(chunk, float(score), str(doc_kind)) for chunk, doc_kind, score in rows
        ]

    async def _fts_search(
        self,
        user_id: int,
        query: str,
        *,
        kind: DocumentKind | None,
        limit: int,
    ) -> list[RetrievedChunk]:
        tsq = func.plainto_tsquery("english", query)
        rank = func.ts_rank(DocumentChunk.fts, tsq).label("rank")
        stmt = (
            select(DocumentChunk, Document.kind, rank)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                Document.user_id == user_id,
                DocumentChunk.fts.op("@@")(tsq),
            )
            .order_by(rank.desc())
            .limit(limit)
        )
        if kind is not None:
            stmt = stmt.where(Document.kind == kind)
        rows = (await self.session.execute(stmt)).all()
        return [
            self._to_chunk(chunk, float(score), str(doc_kind)) for chunk, doc_kind, score in rows
        ]

    @staticmethod
    def _to_chunk(chunk: DocumentChunk, score: float, kind: str) -> RetrievedChunk:
        meta: dict[str, object] = dict(chunk.meta or {})
        return RetrievedChunk(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            score=score,
            kind=kind,
            metadata=meta,
        )


def _rrf_fuse(
    vector_hits: list[RetrievedChunk], fts_hits: list[RetrievedChunk]
) -> list[RetrievedChunk]:
    """Reciprocal-rank fusion: 1/(k + rank) per hit, summed across legs."""
    scores: dict[int, float] = {}
    by_id: dict[int, RetrievedChunk] = {}
    for hits in (vector_hits, fts_hits):
        for rank, hit in enumerate(hits, start=1):
            by_id.setdefault(hit.chunk_id, hit)
            scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1.0 / (RRF_K + rank)
    fused = sorted(by_id.values(), key=lambda c: scores[c.chunk_id], reverse=True)
    return fused
