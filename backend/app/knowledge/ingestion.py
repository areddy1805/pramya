"""Knowledge ingestion service (Phase 2.2).

Pipeline: parsed document text -> deterministic chunking -> BGE-M3
embeddings (via InferenceRouter, never direct provider calls) -> pgvector
persistence. Dedup is explicit: indexing replaces the document's existing
chunks (content-hash identity lives on the immutable ``document`` row), so
re-indexing is idempotent — calling it twice converges to the same chunk
set. Application code depends on this service + the router; no LlamaIndex
dependency (see DECISIONS.md deviation note).
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.router import InferenceRouter
from app.domain.enums import DocumentStatus
from app.domain.errors import ValidationFailedError
from app.knowledge.chunking import chunk_text
from app.models.document import Document, DocumentChunk
from app.repositories.document import DocumentChunkRepository

DEFAULT_CHUNK_SIZE = 1200
DEFAULT_CHUNK_OVERLAP = 200
DEFAULT_EMBED_BATCH_SIZE = 8


class IngestionService:
    """Chunk + embed + persist one document's parsed text."""

    def __init__(
        self,
        session: AsyncSession,
        router: InferenceRouter,
        *,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
        embed_batch_size: int = DEFAULT_EMBED_BATCH_SIZE,
    ) -> None:
        self.session = session
        self.router = router
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.embed_batch_size = embed_batch_size
        self.chunks_repo = DocumentChunkRepository(session)

    async def index_document(self, document: Document, content: str) -> list[DocumentChunk]:
        """Index (or re-index) a document's text into the vector store.

        Idempotent: existing chunks for the document are removed first, then
        fresh chunks are embedded and persisted. Returns the new chunk rows.
        """
        if document.status != DocumentStatus.PARSED:
            raise ValidationFailedError(
                "document must be parsed before indexing",
                details={"document_id": document.id, "status": document.status.value},
            )
        if not content.strip():
            raise ValidationFailedError(
                "cannot index empty document text",
                details={"document_id": document.id},
            )

        await self.chunks_repo.delete_for_document(document.id)
        await self.chunks_repo.flush()

        chunks = chunk_text(content, chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap)
        if not chunks:
            raise ValidationFailedError(
                "document text produced no chunks",
                details={"document_id": document.id},
            )

        rows: list[DocumentChunk] = []
        for batch in _batches(chunks, self.embed_batch_size):
            texts = [c.content for c in batch]
            response = await self.router.embed(texts)
            embeddings = response.embeddings
            if len(embeddings) != len(batch):
                raise ValidationFailedError(
                    "embedding count mismatch",
                    details={"expected": len(batch), "got": len(embeddings)},
                )
            for chunk, embedding in zip(batch, embeddings, strict=True):
                rows.append(
                    DocumentChunk(
                        document_id=document.id,
                        chunk_index=chunk.index,
                        content=chunk.content,
                        embedding=embedding,
                        meta={
                            "document_id": document.id,
                            "kind": str(document.kind),
                            "filename": document.filename,
                            "chunk_index": chunk.index,
                            "char_start": chunk.char_start,
                            "char_end": chunk.char_end,
                        },
                    )
                )
        await self.chunks_repo.add_all(rows)
        return rows


def _batches[T](items: Sequence[T], size: int) -> list[list[T]]:
    return [list(items[i : i + size]) for i in range(0, len(items), size)]
