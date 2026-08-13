"""LlamaIndex integration (Phase D realignment, ADR-003).

LlamaIndex owns the knowledge/retrieval layer:
- IngestionPipeline (chunk -> metadata -> embeddings -> vector store)
- VectorStoreIndex retriever + rerank postprocessor at query time.

Two constraints from the existing architecture:
- Every model call still goes through the InferenceRouter (ADR-004):
  RouterEmbeddings delegates to router.embed (BGE-M3 via oMLX).
- Storage stays on the existing PostgreSQL/pgvector schema
  (DocumentChunk table) — no second database. PramyaVectorStore is a
  thin BaseVectorStore adapter over DocumentChunk.

The deterministic ingestion/retrieval services (app.knowledge.*) remain
the reference/fallback layer; production paths execute these adapters.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from llama_index.core.embeddings import BaseEmbedding
from llama_index.core.node_parser import NodeParser
from llama_index.core.schema import (
    BaseNode,
    Document,
    TextNode,
)

from app.ai.router import InferenceRouter
from app.knowledge.chunking import Chunk, chunk_text

DEFAULT_CHUNK_SIZE = 1200
DEFAULT_CHUNK_OVERLAP = 200


class RouterEmbeddings(BaseEmbedding):
    """LlamaIndex embedding model backed by the InferenceRouter.

    Keeps ADR-004 (router-only model access): the router decides the
    embedding provider/model (BGE-M3 via oMLX) — never a direct call.
    """

    router: InferenceRouter  # pydantic field (arbitrary types allowed)

    def __init__(self, router: InferenceRouter, **kwargs: Any) -> None:
        super().__init__(router=router, **kwargs)  # type: ignore[call-arg]

    def _get_text_embedding(self, text: str) -> list[float]:
        import asyncio

        return asyncio.run(self._aget_text_embedding(text))

    async def _aget_text_embedding(self, text: str) -> list[float]:
        response = await self.router.embed([text])
        return list(response.embeddings[0])

    def _get_query_embedding(self, query: str) -> list[float]:
        import asyncio

        return asyncio.run(self._aget_query_embedding(query))

    async def _aget_query_embedding(self, query: str) -> list[float]:
        response = await self.router.embed([query])
        return list(response.embeddings[0])

    def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        import asyncio

        return asyncio.run(self._aget_text_embeddings(texts))

    async def _aget_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        response = await self.router.embed(texts)
        return [list(e) for e in response.embeddings]


class DeterministicChunker(NodeParser):
    """LlamaIndex NodeParser wrapping the deterministic chunker.

    The deterministic greedy paragraph-packing chunker (app.knowledge
    .chunking) stays the canonical algorithm (reference layer); this
    TransformComponent feeds its output into the LlamaIndex pipeline as
    TextNodes so the pipeline genuinely executes while chunk boundaries
    stay identical.
    """

    chunk_size: int = DEFAULT_CHUNK_SIZE
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP

    def __init__(
        self,
        *,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
        **kwargs: Any,
    ) -> None:
        super().__init__(  # type: ignore[call-arg]
            chunk_size=chunk_size,  # pyright: ignore[reportCallIssue]
            chunk_overlap=chunk_overlap,  # pyright: ignore[reportCallIssue]
            **kwargs,
        )

    def _parse_nodes(
        self, nodes: Sequence[BaseNode], show_progress: bool = False, **kwargs: Any
    ) -> list[BaseNode]:
        out: list[BaseNode] = []
        for node in nodes:
            text = node.get_content()
            metadata = dict(node.metadata or {})
            for chunk in chunk_text(
                text, chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap
            ):
                out.append(
                    TextNode(
                        text=chunk.content,
                        metadata={
                            **metadata,
                            "chunk_index": chunk.index,
                            "char_start": chunk.char_start,
                            "char_end": chunk.char_end,
                        },
                    )
                )
        return out


def to_llamaindex_documents(
    content: str, *, document_id: int, kind: str, filename: str
) -> list[Document]:
    """Wrap parsed document text + metadata as LlamaIndex Documents."""
    return [
        Document(
            text=content,
            metadata={
                "document_id": str(document_id),
                "kind": kind,
                "filename": filename,
            },
        )
    ]


def chunks_to_nodes(chunks: Sequence[Chunk]) -> list[TextNode]:
    """Convert deterministic chunks to TextNodes (no re-chunking)."""
    return [
        TextNode(
            text=c.content,
            metadata={
                "chunk_index": c.index,
                "char_start": c.char_start,
                "char_end": c.char_end,
            },
        )
        for c in chunks
    ]


__all__ = [
    "BaseNode",
    "Document",
    "RouterEmbeddings",
    "DeterministicChunker",
    "to_llamaindex_documents",
    "chunks_to_nodes",
]
