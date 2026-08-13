"""PramyaVectorStore — LlamaIndex BasePydanticVectorStore over DocumentChunk.

Keeps LlamaIndex genuinely executing in the production RAG path while the
storage stays on the existing PostgreSQL/pgvector schema (no second
database, ADR-003/ADR-007). Implements the llama-index-core 0.14 vector
store interface (client / add / delete / query + async variants) against
the DocumentChunk table.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from llama_index.core.schema import BaseNode, TextNode
from llama_index.core.vector_stores.types import (
    BasePydanticVectorStore,
    VectorStoreQuery,
    VectorStoreQueryMode,
    VectorStoreQueryResult,
)
from pgvector.sqlalchemy import Vector
from sqlalchemy import cast, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk

EMBEDDING_DIM = 1024


class PramyaVectorStore(BasePydanticVectorStore):
    """LlamaIndex vector store backed by the DocumentChunk pgvector table."""

    stores_text: bool = True
    # pydantic field: the async SQLAlchemy session is allowed by the base
    # ConfigDict(arbitrary_types_allowed=True).
    session: AsyncSession

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session=session)  # type: ignore[call-arg]

    # -- required abstract surface -------------------------------------------

    @property
    def client(self) -> Any:
        return self.session

    def add(self, nodes: Sequence[BaseNode], **add_kwargs: Any) -> list[str]:
        raise NotImplementedError("use async_add (async app path)")

    async def async_add(self, nodes: Sequence[BaseNode], **add_kwargs: Any) -> list[str]:
        """Insert nodes as DocumentChunk rows (LlamaIndex ingestion writes)."""
        document_id = _document_id_from_nodes(list(nodes))
        if document_id is None:
            raise ValueError("nodes must carry document_id metadata")
        # Idempotent re-index: drop existing chunks for the document first.
        await self.session.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        rows: list[DocumentChunk] = []
        for idx, node in enumerate(nodes):
            meta = dict(node.metadata or {})
            chunk_index = int(meta.get("chunk_index", idx))
            rows.append(
                DocumentChunk(
                    document_id=document_id,
                    chunk_index=chunk_index,
                    content=node.get_content(),
                    embedding=list(node.embedding or []),
                    meta={
                        "document_id": document_id,
                        "kind": meta.get("kind", ""),
                        "filename": meta.get("filename", ""),
                        "chunk_index": chunk_index,
                        "char_start": meta.get("char_start"),
                        "char_end": meta.get("char_end"),
                    },
                )
            )
        self.session.add_all(rows)
        await self.session.flush()
        return [str(n.node_id) for n in nodes]

    def delete(self, ref_doc_id: str, **delete_kwargs: Any) -> None:
        raise NotImplementedError("use adelete (async app path)")

    async def adelete(self, ref_doc_id: str, **delete_kwargs: Any) -> None:
        await self.session.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == int(ref_doc_id))
        )
        await self.session.flush()

    def query(self, query: VectorStoreQuery, **kwargs: Any) -> VectorStoreQueryResult:
        raise NotImplementedError("use aquery (async app path)")

    async def aquery(self, query: VectorStoreQuery, **kwargs: Any) -> VectorStoreQueryResult:
        """Cosine similarity search over DocumentChunk (async pgvector)."""
        return await self._search(query, user_id=None)

    async def aquery_with_user(
        self, query: VectorStoreQuery, *, user_id: int, **kwargs: Any
    ) -> VectorStoreQueryResult:
        """User-scoped variant: joins Document to enforce ownership."""
        return await self._search(query, user_id=user_id)

    # -- internals -----------------------------------------------------------

    async def _search(
        self, query: VectorStoreQuery, *, user_id: int | None
    ) -> VectorStoreQueryResult:
        if query.mode not in (
            VectorStoreQueryMode.DEFAULT,
            VectorStoreQueryMode.HYBRID,
        ):
            raise ValueError(f"unsupported vector store query mode: {query.mode}")
        embedding = list(query.query_embedding or [])
        if not embedding:
            return VectorStoreQueryResult(nodes=[], similarities=[], ids=[])
        vec = cast(embedding, Vector(EMBEDDING_DIM))
        top_k = query.similarity_top_k or 10

        stmt = (
            select(
                DocumentChunk.id,
                DocumentChunk.content,
                DocumentChunk.meta,
                DocumentChunk.document_id,
                (1 - DocumentChunk.embedding.cosine_distance(vec)).label("score"),
            )
            .where(DocumentChunk.embedding.isnot(None))
            .order_by(DocumentChunk.embedding.cosine_distance(vec))
            .limit(top_k)
        )
        if user_id is not None:
            stmt = stmt.join(Document, Document.id == DocumentChunk.document_id).where(
                Document.user_id == user_id
            )
        if query.doc_ids:
            stmt = stmt.where(DocumentChunk.document_id.in_([int(d) for d in query.doc_ids]))
        rows = (await self.session.execute(stmt)).all()

        nodes: list[BaseNode] = []
        similarities: list[float] = []
        ids: list[str] = []
        for row in rows:
            nodes.append(
                TextNode(
                    text=row.content,
                    id_=str(row.id),
                    metadata={**dict(row.meta or {}), "document_id": str(row.document_id)},
                )
            )
            similarities.append(float(row.score))
            ids.append(str(row.id))
        return VectorStoreQueryResult(nodes=nodes, similarities=similarities, ids=ids)


def _document_id_from_nodes(nodes: list[BaseNode]) -> int | None:
    for node in nodes:
        meta = dict(node.metadata or {})
        raw = meta.get("document_id")
        if raw is not None:
            try:
                return int(raw)
            except (TypeError, ValueError):
                return None
    return None


__all__ = ["PramyaVectorStore", "VectorStoreQuery", "VectorStoreQueryResult"]
