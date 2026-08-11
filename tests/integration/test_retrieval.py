"""Hybrid retrieval integration tests (Phase 2.3): real pgvector SQL paths.

Fake embedding/rerank router keeps CI free of oMLX; the SQL (vector cosine,
FTS @@, ts_rank, joins, user scoping) runs against real PostgreSQL.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contracts import EmbedResponse, RerankResponse
from app.domain.enums import DocumentKind
from app.knowledge.ingestion import IngestionService
from app.knowledge.retrieval import RetrievalService
from app.models.document import Document
from app.services.document import DocumentService
from app.services.user import CandidateService


class StubRouter:
    def __init__(self, dimension: int = 1024) -> None:
        self.dimension = dimension

    async def embed(self, texts: list[str]) -> EmbedResponse:
        # Deterministic pseudo-embedding: index of first char.
        emb = []
        for t in texts:
            v = [0.0] * self.dimension
            if t:
                v[ord(t[0]) % self.dimension] = 1.0
            emb.append(v)
        return EmbedResponse(embeddings=emb, model="stub", dimension=self.dimension)

    async def rerank(
        self, query: str, documents: list[str], top_n: int | None = None
    ) -> RerankResponse:
        # Keep input order (identity rerank).
        return RerankResponse(
            model="stub",
            results=[
                {"index": i, "score": float(len(documents) - i)} for i in range(len(documents))
            ],
        )


async def _ingest(
    db_session: AsyncSession,
    tmp_path: Path,
    *,
    user_id: int,
    text: str,
    kind: DocumentKind,
    filename: str,
) -> Document:
    svc = DocumentService(db_session, storage_dir=tmp_path)
    doc, parsed = await svc.upload(
        user_id=user_id, kind=kind, filename=filename, mime="text/plain", data=text.encode()
    )
    router = StubRouter()
    ingestion = IngestionService(db_session, router, chunk_size=200, chunk_overlap=40)
    await ingestion.index_document(doc, parsed.content)
    await db_session.commit()
    return doc


@pytest.fixture
async def indexed_docs(db_session: AsyncSession, tmp_path: Path) -> AsyncIterator[dict[str, int]]:

    user = await CandidateService(db_session).create_user(display_name="Alex")
    await db_session.commit()
    resume = await _ingest(
        db_session,
        tmp_path,
        user_id=user.id,
        text=(
            "Senior backend engineer focused on Python and FastAPI.\n\n" * 5
            + "Built distributed systems with PostgreSQL and Kafka.\n\n" * 5
        ),
        kind=DocumentKind.RESUME,
        filename="resume.txt",
    )
    jd = await _ingest(
        db_session,
        tmp_path,
        user_id=user.id,
        text=(
            "We need a frontend engineer with React and TypeScript.\n\n" * 5
            + "Strong understanding of accessibility and testing.\n\n" * 5
        ),
        kind=DocumentKind.JD,
        filename="jd.txt",
    )
    yield {"resume": resume.id, "jd": jd.id, "user_id": user.id}


async def test_retrieval_finds_relevant_resume_chunks(
    db_session: AsyncSession, indexed_docs: dict[str, int]
) -> None:
    svc = RetrievalService(db_session, StubRouter(), top_k=3, fetch_per_side=10)
    result = await svc.search(indexed_docs["user_id"], "python fastapi backend")
    assert result.chunks, "expected at least one chunk"
    assert all(c.kind == "resume" for c in result.chunks)
    assert all(c.document_id == indexed_docs["resume"] for c in result.chunks)
    assert result.vector_used
    assert result.fts_used


async def test_retrieval_scopes_by_user(
    db_session: AsyncSession, indexed_docs: dict[str, int]
) -> None:
    svc = RetrievalService(db_session, StubRouter(), top_k=5, fetch_per_side=10)
    result = await svc.search(99999, "python fastapi backend")
    assert result.chunks == []


async def test_retrieval_kind_filter(
    db_session: AsyncSession, indexed_docs: dict[str, int]
) -> None:
    svc = RetrievalService(db_session, StubRouter(), top_k=3, fetch_per_side=10)
    result = await svc.search(
        indexed_docs["user_id"], "react typescript frontend", kind=DocumentKind.JD
    )
    assert result.chunks
    assert all(c.kind == "jd" for c in result.chunks)


async def test_retrieval_rerank_preserves_top_chunks(
    db_session: AsyncSession, indexed_docs: dict[str, int]
) -> None:
    svc = RetrievalService(db_session, StubRouter(), top_k=2, fetch_per_side=10)
    result = await svc.search(indexed_docs["user_id"], "python backend")
    assert result.rerank_used
    assert len(result.chunks) <= 2
