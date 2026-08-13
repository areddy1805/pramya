"""Ingestion service unit tests (Phase 2.2): batching + persistence calls.

Persistence-side behavior (real pgvector writes, idempotent re-index) is
covered by integration tests; here the repository is faked so tests run
without a database.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from app.ai.contracts import EmbedResponse
from app.domain.enums import DocumentStatus
from app.domain.errors import ValidationFailedError
from app.knowledge.ingestion import IngestionService
from app.models.document import Document, DocumentChunk


class FakeEmbedRouter:
    """Minimal router stub implementing embed() with record-keeping."""

    def __init__(self, dimension: int = 8) -> None:
        self.dimension = dimension
        self.batches: list[list[str]] = []

    async def embed(self, texts: list[str]) -> EmbedResponse:
        self.batches.append(texts)
        return EmbedResponse(
            embeddings=[[float(i % self.dimension) for i in range(self.dimension)] for _ in texts],
            model="fake-embed",
            dimension=self.dimension,
        )


class FakeChunkRepo:
    """Records calls instead of touching a database."""

    def __init__(self) -> None:
        self.deleted: list[int] = []
        self.added: list[list[DocumentChunk]] = []
        self.flushes = 0

    async def delete_for_document(self, document_id: int) -> None:
        self.deleted.append(document_id)

    async def flush(self) -> None:
        self.flushes += 1

    async def add_all(self, objs: Sequence[DocumentChunk]) -> None:
        self.added.append(list(objs))


@pytest.fixture
def router() -> FakeEmbedRouter:
    return FakeEmbedRouter(dimension=8)


def _doc(status: DocumentStatus = DocumentStatus.PARSED) -> Document:
    d = Document(
        user_id=1,
        kind="resume",
        filename="resume.txt",
        mime="text/plain",
        size=10,
        content_hash="abc",
        status=status,
    )
    d.id = 42
    return d


def _svc(router: FakeEmbedRouter, repo: FakeChunkRepo) -> IngestionService:
    svc = IngestionService(None, router, chunk_size=200, chunk_overlap=40, embed_batch_size=2)  # type: ignore[arg-type]
    svc.chunks_repo = repo  # type: ignore[assignment]
    return svc


async def test_index_embeds_in_batches_and_persists(router: FakeEmbedRouter) -> None:
    repo = FakeChunkRepo()
    svc = _svc(router, repo)
    text = "\n\n".join(f"paragraph {i} " + "z" * 120 for i in range(5))

    rows = await svc.index_document(_doc(), text)

    assert repo.deleted == [42]  # idempotent: old chunks removed first
    assert router.batches, "embedding called with batches"
    assert all(len(b) <= 2 for b in router.batches)
    assert len(rows) >= 2
    for row in rows:
        assert row.document_id == 42
        assert row.embedding is not None
        assert len(row.embedding) == 8  # fake dimension
        assert row.meta is not None
        assert row.meta["document_id"] == 42
        assert row.meta["kind"] == "resume"


async def test_reindex_replaces_chunks(router: FakeEmbedRouter) -> None:
    repo = FakeChunkRepo()
    svc = _svc(router, repo)
    text = "\n\n".join(f"p {i} " + "q" * 100 for i in range(4))

    await svc.index_document(_doc(), text)
    await svc.index_document(_doc(), text)

    assert repo.deleted == [42, 42]
    assert len(repo.added) == 2


async def test_unparsed_document_rejected(router: FakeEmbedRouter) -> None:
    repo = FakeChunkRepo()
    svc = _svc(router, repo)
    with pytest.raises(ValidationFailedError):
        await svc.index_document(_doc(DocumentStatus.PENDING), "some text")
    assert repo.deleted == []


async def test_empty_content_rejected(router: FakeEmbedRouter) -> None:
    repo = FakeChunkRepo()
    svc = _svc(router, repo)
    with pytest.raises(ValidationFailedError):
        await svc.index_document(_doc(), "   ")
    assert repo.deleted == []
