"""Ingestion integration tests (Phase 2.2): real pgvector persistence.

Uses the shared pgvector fixtures (tests/integration/conftest.py). The
embedding router is faked with the schema-locked 1024 dimension so tests
run without oMLX in CI; real-runtime embedding smoke is covered separately.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contracts import EmbedResponse
from app.domain.enums import DocumentKind
from app.knowledge.ingestion import IngestionService
from app.models.document import Document
from app.repositories.document import DocumentChunkRepository
from app.services.document import DocumentService


class FakeEmbedRouter1024:
    """1024-dim fake embedding router (schema-locked dimension)."""

    def __init__(self) -> None:
        self.calls = 0

    async def embed(self, texts: list[str]) -> EmbedResponse:
        self.calls += 1
        return EmbedResponse(
            embeddings=[[float(i % 7) / 7 for i in range(1024)] for _ in texts],
            model="fake-embed",
            dimension=1024,
        )


@pytest.fixture
async def uploaded_doc(db_session: AsyncSession, tmp_path: Path) -> AsyncIterator[Document]:
    svc = DocumentService(db_session, storage_dir=tmp_path)
    text = "Senior Software Engineer with 6 years of backend experience.\n\n" + (
        "Built distributed systems using Python, FastAPI, and PostgreSQL.\n\n" * 20
    )
    doc, _parsed = await svc.upload(
        user_id=1,
        kind=DocumentKind.RESUME,
        filename="resume.txt",
        mime="text/plain",
        data=text.encode(),
    )
    yield doc


async def test_index_persists_chunks_with_embeddings(
    db_session: AsyncSession, uploaded_doc: Document, tmp_path: Path
) -> None:
    router = FakeEmbedRouter1024()
    svc = DocumentService(db_session, storage_dir=tmp_path)
    doc = await svc.get_document(1, uploaded_doc.id)
    data = await svc.read_stored_bytes(1, uploaded_doc.id)

    ingestion = IngestionService(
        db_session, router, chunk_size=300, chunk_overlap=50, embed_batch_size=2
    )
    parsed = await _parse(data, doc)
    rows = await ingestion.index_document(doc, parsed.content)
    await db_session.commit()

    assert len(rows) >= 2
    repo = DocumentChunkRepository(db_session)
    persisted = list(await repo.list_for_document(doc.id))
    assert len(persisted) == len(rows)
    for row in persisted:
        assert row.embedding is not None
        assert len(row.embedding) == 1024
        assert row.meta is not None
        assert row.meta["kind"] == "resume"

    # Re-index is idempotent: same chunk set size, no duplicates.
    rows2 = await ingestion.index_document(doc, parsed.content)
    await db_session.commit()
    persisted2 = list(await repo.list_for_document(doc.id))
    assert len(persisted2) == len(rows2)
    assert (await repo.count_for_document(doc.id)) == len(persisted2)


async def _parse(data: bytes, doc: Document) -> object:
    from app.knowledge.parsing import parse_document_with_timeout

    return await parse_document_with_timeout(
        data=data,
        kind=doc.kind,
        mime=doc.mime,
        filename=doc.filename,
        content_hash=doc.content_hash,
        max_pages=50,
        timeout_seconds=30,
    )
