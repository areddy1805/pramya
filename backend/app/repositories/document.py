"""Document + document_chunk repositories."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select

from app.domain.enums import DocumentKind
from app.models.document import Document, DocumentChunk
from app.repositories.base import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    model = Document

    async def list_for_user(
        self, user_id: int, *, kind: DocumentKind | None = None
    ) -> Sequence[Document]:
        stmt = select(Document).where(Document.user_id == user_id)
        if kind is not None:
            stmt = stmt.where(Document.kind == kind)
        return (await self.session.scalars(stmt.order_by(Document.id))).all()

    async def get_by_hash(self, user_id: int, content_hash: str) -> Document | None:
        stmt = select(Document).where(
            Document.user_id == user_id, Document.content_hash == content_hash
        )
        return (await self.session.scalars(stmt)).first()


class DocumentChunkRepository(BaseRepository[DocumentChunk]):
    model = DocumentChunk

    async def list_for_document(self, document_id: int) -> Sequence[DocumentChunk]:
        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
        return (await self.session.scalars(stmt)).all()
