"""LlamaIndex ingestion + retrieval (Phase D realignment, ADR-003).

Production RAG path executes a real LlamaIndex IngestionPipeline
(documents -> nodes -> metadata -> embeddings -> vector store) and a real
VectorStoreIndex retriever with a rerank postprocessor. Storage stays on
the existing DocumentChunk pgvector table (PramyaVectorStore adapter);
every model call goes through the InferenceRouter (RouterEmbeddings).

The deterministic IngestionService/RetrievalService remain the reference/
fallback layer — they are not removed.
"""

from __future__ import annotations

import logging

from llama_index.core.embeddings import BaseEmbedding
from llama_index.core.indices.vector_store import VectorStoreIndex
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.schema import NodeWithScore, QueryBundle
from llama_index.core.vector_stores.types import VectorStoreQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.router import InferenceRouter
from app.core.logging import get_logger
from app.knowledge.rag import (
    DeterministicChunker,
    RouterEmbeddings,
    to_llamaindex_documents,
)
from app.knowledge.rag.store import PramyaVectorStore
from app.models.document import Document as DocumentRow

DEFAULT_CHUNK_SIZE = 1200
DEFAULT_CHUNK_OVERLAP = 200
DEFAULT_TOP_K = 5


class LlamaIndexIngestionService:
    """Chunk + embed + persist via a real LlamaIndex IngestionPipeline."""

    def __init__(
        self,
        session: AsyncSession,
        router: InferenceRouter,
        *,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
        logger: logging.Logger | None = None,
    ) -> None:
        self.session = session
        self.router = router
        self._logger = logger or get_logger("app.knowledge.rag.ingest")
        self._embeddings: BaseEmbedding = RouterEmbeddings(router)
        self._chunker = DeterministicChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self._store = PramyaVectorStore(session)

    async def index_document(self, document: DocumentRow, content: str) -> int:
        """Run the LlamaIndex pipeline for one document; returns chunk count."""
        if not content.strip():
            return 0
        docs = to_llamaindex_documents(
            content,
            document_id=document.id,
            kind=str(document.kind),
            filename=document.filename,
        )
        pipeline = IngestionPipeline(
            transformations=[self._chunker, self._embeddings],
            vector_store=self._store,
        )
        nodes = await pipeline.arun(documents=docs, show_progress=False)
        # aadd already inserted + flushed; commit so the outer session sees rows.
        await self.session.flush()
        return len(nodes)


class RouterRerankPostprocessor(BaseNodePostprocessor):
    """LlamaIndex postprocessor that reranks nodes via the InferenceRouter."""

    router: InferenceRouter  # pydantic field (arbitrary types allowed)
    top_n: int | None = None

    def __init__(self, router: InferenceRouter, *, top_n: int | None = None) -> None:
        super().__init__(router=router, top_n=top_n)  # type: ignore[call-arg]

    def _postprocess_nodes(
        self, nodes: list[NodeWithScore], query_bundle: QueryBundle | None = None
    ) -> list[NodeWithScore]:
        import asyncio

        return asyncio.run(self._apostprocess_nodes(nodes, query_bundle))

    async def _apostprocess_nodes(
        self, nodes: list[NodeWithScore], query_bundle: QueryBundle | None = None
    ) -> list[NodeWithScore]:
        if not nodes:
            return nodes
        query = query_bundle.query_str if query_bundle else ""
        docs = [n.get_content() for n in nodes]
        try:
            response = await self.router.rerank(query, docs, top_n=self.top_n or len(docs))
            order = {item.index: item.score for item in response.results}
            ranked = sorted(nodes, key=lambda n: order.get(nodes.index(n), 0.0), reverse=True)
            return ranked
        except Exception:  # rerank failure -> keep original order (caller degrades)
            return nodes


class LlamaIndexRetriever:
    """LlamaIndex VectorStoreIndex retriever + rerank postprocessor."""

    def __init__(
        self,
        session: AsyncSession,
        router: InferenceRouter,
        *,
        top_k: int = DEFAULT_TOP_K,
        logger: logging.Logger | None = None,
    ) -> None:
        self.session = session
        self.router = router
        self.top_k = top_k
        self._logger = logger or get_logger("app.knowledge.rag.retriever")
        self._embeddings: BaseEmbedding = RouterEmbeddings(router)
        self._store = PramyaVectorStore(session)
        self._rerank = RouterRerankPostprocessor(router, top_n=top_k)

    async def retrieve(self, query: str, *, user_id: int, top_k: int | None = None) -> list[str]:
        """Vector retrieval via LlamaIndex + rerank; returns chunk contents."""
        if not query.strip():
            return []
        k = top_k or self.top_k
        query_embedding = await self._embeddings.aget_query_embedding(query)
        result = await self._store.aquery_with_user(
            VectorStoreQuery(query_embedding=query_embedding, similarity_top_k=k * 3),
            user_id=user_id,
        )
        nodes = result.nodes or []
        similarities = result.similarities or []
        scored = [NodeWithScore(node=n, score=s) for n, s in zip(nodes, similarities, strict=False)]
        reranked = await self._rerank.apostprocess_nodes(scored, QueryBundle(query_str=query))
        return [n.get_content() for n in reranked[:k]]


__all__ = [
    "LlamaIndexIngestionService",
    "LlamaIndexRetriever",
    "RouterRerankPostprocessor",
    "VectorStoreIndex",
]
