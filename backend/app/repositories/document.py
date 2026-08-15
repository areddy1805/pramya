"""Document + document_chunk repositories."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete, func, select

from app.domain.enums import DocumentKind
from app.models.document import Document, DocumentChunk
from app.repositories.base import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    model = Document

    async def list_for_user(
        self,
        user_id: int,
        *,
        kind: DocumentKind | None = None,
        profile_id: int | None = None,
        legacy_only: bool = False,
    ) -> Sequence[Document]:
        stmt = select(Document).where(Document.user_id == user_id)
        if legacy_only:
            # Explicit global/legacy rows only (profile_id IS NULL) — never
            # other profiles' documents.
            stmt = stmt.where(Document.profile_id.is_(None))
        elif profile_id is not None:
            stmt = stmt.where(Document.profile_id == profile_id)
        if kind is not None:
            stmt = stmt.where(Document.kind == kind)
        return (await self.session.scalars(stmt.order_by(Document.id))).all()

    async def get_by_hash(
        self, user_id: int, content_hash: str, *, profile_id: int | None = None
    ) -> Document | None:
        """Content-hash lookup. Dedup is scoped to (user, profile) so the
        same file in a different career profile is a distinct document.
        profile_id=None (legacy callers) scopes to the user only."""
        stmt = select(Document).where(Document.user_id == user_id)
        if profile_id is not None:
            stmt = stmt.where(Document.profile_id == profile_id)
        stmt = stmt.where(Document.content_hash == content_hash)
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

    async def count_for_document(self, document_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
        )
        return int((await self.session.scalar(stmt)) or 0)

    async def delete_for_document(self, document_id: int) -> None:
        stmt = delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        await self.session.execute(stmt)
