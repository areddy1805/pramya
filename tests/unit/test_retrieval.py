"""Hybrid retrieval unit tests (Phase 2.3): RRF fusion + degradation."""

from __future__ import annotations

from app.ai.contracts import EmbedResponse, RerankResponse
from app.ai.errors import ProviderConnectionError
from app.knowledge.retrieval import RetrievalService, RetrievedChunk, _rrf_fuse


def _chunk(cid: int) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=cid,
        document_id=1,
        chunk_index=cid,
        content=f"content {cid}",
        score=1.0,
        kind="resume",
        metadata={},
    )


def test_rrf_fusion_combines_rankings() -> None:
    vector = [_chunk(1), _chunk(2), _chunk(3)]
    fts = [_chunk(2), _chunk(4)]
    fused = _rrf_fuse(vector, fts)
    # chunk 2 appears in both -> highest fused score.
    assert fused[0].chunk_id == 2
    ids = [c.chunk_id for c in fused]
    # chunk1 (rank1 vector) and chunk4 (rank1 fts) tie at 1/61; stable
    # insertion order keeps chunk1 (vector leg first) before chunk4.
    assert ids == [2, 1, 4, 3]


def test_rrf_single_leg() -> None:
    fused = _rrf_fuse([_chunk(1), _chunk(2)], [])
    assert [c.chunk_id for c in fused] == [1, 2]


def test_rrf_dedup() -> None:
    fused = _rrf_fuse([_chunk(5)], [_chunk(5), _chunk(6)])
    assert [c.chunk_id for c in fused] == [5, 6]


class _FakeRouter:
    def __init__(self, *, embed_fails: bool = False, rerank_fails: bool = False) -> None:
        self.embed_fails = embed_fails
        self.rerank_fails = rerank_fails
        self.embed_calls = 0
        self.rerank_calls = 0

    async def embed(self, texts: list[str]) -> EmbedResponse:
        self.embed_calls += 1
        if self.embed_fails:
            raise ProviderConnectionError("embedding down")
        return EmbedResponse(
            embeddings=[[float(i) for i in range(1024)] for _ in texts],
            model="fake",
            dimension=1024,
        )

    async def rerank(
        self, query: str, documents: list[str], top_n: int | None = None
    ) -> RerankResponse:
        self.rerank_calls += 1
        if self.rerank_fails:
            raise ProviderConnectionError("rerank down")
        # Score by position ascending: LAST document gets the highest score,
        # proving rerank reorders the RRF order.
        return RerankResponse(
            model="fake",
            results=[{"index": i, "score": float(i)} for i in range(len(documents))],
        )


class _FakeRepo:
    def __init__(
        self, vector: list[RetrievedChunk] | None = None, fts: list[RetrievedChunk] | None = None
    ) -> None:
        self.vector = vector or []
        self.fts = fts or []

    async def _vector_search(self, *a, **kw):  # type: ignore[no-untyped-def]
        return self.vector

    async def _fts_search(self, *a, **kw):  # type: ignore[no-untyped-def]
        return self.fts


def _svc(
    router: _FakeRouter,
    vector: list[RetrievedChunk] | None = None,
    fts: list[RetrievedChunk] | None = None,
) -> RetrievalService:
    svc = RetrievalService(None, router)  # type: ignore[arg-type]
    svc._vector_search = _FakeRepo(vector=vector)._vector_search  # type: ignore[method-assign]
    svc._fts_search = _FakeRepo(fts=fts)._fts_search  # type: ignore[method-assign]
    return svc


async def test_search_reranks_and_orders() -> None:
    router = _FakeRouter()
    vector = [_chunk(1), _chunk(2), _chunk(3)]
    fts = [_chunk(2)]
    svc = _svc(router, vector, fts)
    result = await svc.search(1, "python")
    assert result.rerank_used
    assert not result.degraded
    # Rerank reversed: index 2 first -> chunk 3 top.
    assert result.chunks[0].chunk_id == 3


async def test_embed_failure_degrades_to_fts() -> None:
    router = _FakeRouter(embed_fails=True)
    svc = _svc(router, [_chunk(1)], [_chunk(2)])
    result = await svc.search(1, "python")
    assert result.degraded
    assert result.degradation == "embedding_unavailable"
    assert result.vector_used is False
    assert result.chunks and result.chunks[0].chunk_id == 2


async def test_rerank_failure_keeps_rrf_order() -> None:
    router = _FakeRouter(rerank_fails=True)
    vector = [_chunk(1), _chunk(2)]
    fts = [_chunk(2)]
    svc = _svc(router, vector, fts)
    result = await svc.search(1, "python")
    assert result.degraded
    assert result.degradation == "rerank_unavailable"
    assert result.rerank_used is False
    # RRF: chunk 2 in both legs -> first.
    assert result.chunks[0].chunk_id == 2


async def test_empty_query_returns_empty() -> None:
    router = _FakeRouter()
    svc = _svc(router, [_chunk(1)])
    result = await svc.search(1, "   ")
    assert result.chunks == []
    assert router.embed_calls == 0
