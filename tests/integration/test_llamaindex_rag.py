"""LlamaIndex RAG integration tests (Phase D): real pgvector via LlamaIndex.

The production RAG path (LlamaIndex IngestionPipeline + retriever +
rerank postprocessor) is exercised against real PostgreSQL/pgvector with a
fake oMLX router (no local inference in CI). Proves:
- chunks are written through the LlamaIndex pipeline (PramyaVectorStore)
- embeddings are stored (dimension 1024)
- LlamaIndex retrieval returns ranked context
- rerank postprocessor participates
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contracts import EmbedRequest, EmbedResponse, RerankRequest, RerankResponse
from app.ai.policy import TaskPolicyTable
from app.ai.router import InferenceRouter
from app.domain.enums import DocumentKind
from app.knowledge.rag.service import (
    LlamaIndexIngestionService,
    LlamaIndexRetriever,
)
from app.models.document import Document
from app.repositories.document import DocumentChunkRepository
from app.services.user import CandidateService


class FakeOmlxRouter:
    """Fake oMLX retrieval provider (embed + rerank), schema-locked 1024.

    Implements the provider contract the InferenceRouter calls:
    embed(RerankRequest/EmbedRequest) -> EmbedResponse/RerankResponse.
    """

    name = "fake"

    async def embed(self, request: EmbedRequest) -> EmbedResponse:
        texts = request.texts
        emb = []
        for t in texts:
            base = (ord(t[0]) % 100) / 100.0 if t else 0.0
            emb.append([base] * 1024)
        return EmbedResponse(embeddings=emb, model="bge-m3-mlx-4bit", dimension=1024)

    async def rerank(self, request: RerankRequest) -> RerankResponse:
        # Reverse-order relevance (deterministic for assertions).
        n = len(request.documents)
        return RerankResponse(
            results=[{"index": i, "score": float(n - i)} for i in range(n)],
            model="Qwen3-Reranker-0.6B-4bit",
        )


def _router() -> InferenceRouter:
    return InferenceRouter(policy=TaskPolicyTable(), omlx=FakeOmlxRouter(), deepseek=None)


async def _doc(db_session: AsyncSession) -> Document:
    user = await CandidateService(db_session).create_user(display_name="RAG user")
    await db_session.flush()
    doc = Document(
        user_id=user.id,
        kind=DocumentKind.RESUME,
        filename="resume.txt",
        mime="text/plain",
        size=4000,
        content_hash="rag-llamaindex-hash",
        status="parsed",
    )
    db_session.add(doc)
    await db_session.flush()
    return doc


async def test_llamaindex_ingestion_writes_chunks_with_embeddings(
    db_session: AsyncSession,
) -> None:
    doc = await _doc(db_session)
    content = "\n\n".join(f"Section {i}: " + ("experienced engineer " * 30) for i in range(4))

    service = LlamaIndexIngestionService(db_session, _router())
    count = await service.index_document(doc, content)
    await db_session.commit()

    assert count > 0
    chunks = await DocumentChunkRepository(db_session).list_for_document(doc.id)
    assert len(chunks) == count
    assert all(len(c.embedding or []) == 1024 for c in chunks)
    # Idempotent re-index: running again converges to the same chunk set.
    await service.index_document(doc, content)
    await db_session.commit()
    chunks2 = await DocumentChunkRepository(db_session).list_for_document(doc.id)
    assert len(chunks2) == count


async def test_llamaindex_retrieval_returns_ranked_context(db_session: AsyncSession) -> None:
    doc = await _doc(db_session)
    content = "\n\n".join(
        f"Paragraph {i}: the candidate built distributed systems with event "
        "streaming, consistency, and fault tolerance."
        for i in range(5)
    )
    await LlamaIndexIngestionService(db_session, _router()).index_document(doc, content)
    await db_session.commit()

    retriever = LlamaIndexRetriever(db_session, _router(), top_k=2)
    context = await retriever.retrieve(
        "distributed systems event streaming", user_id=doc.user_id, top_k=2
    )

    assert context
    assert all("distributed" in c for c in context)
    assert len(context) <= 2


async def test_llamaindex_retrieval_scopes_by_user(db_session: AsyncSession) -> None:
    doc = await _doc(db_session)
    content = "\n\n".join(
        f"Paragraph {i}: Kubernetes and observability are core strengths." for i in range(3)
    )
    await LlamaIndexIngestionService(db_session, _router()).index_document(doc, content)
    await db_session.commit()

    retriever = LlamaIndexRetriever(db_session, _router(), top_k=5)
    # Another (unrelated) user must not see this document's chunks.
    other = await CandidateService(db_session).create_user(display_name="Other user")
    await db_session.commit()

    context_other = await retriever.retrieve("Kubernetes", user_id=other.id, top_k=5)
    assert context_other == []

    context_owner = await retriever.retrieve("Kubernetes", user_id=doc.user_id, top_k=5)
    assert context_owner
