"""Document + document_chunk models (immutable uploads + vector store).

`document` content is immutable: re-uploading the same file creates a new
document (content-hash comparison is handled by the document service).
`document_chunk.embedding` is a pgvector vector(1024) (BGE-M3, locked from
day one); `fts` is a generated tsvector column for hybrid search.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import DocumentKind, DocumentStatus
from app.models.base import Base, TimestampMixin


class Document(Base, TimestampMixin):
    """One uploaded/ingested document. Immutable content; re-upload = new row."""

    __tablename__ = "document"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Profile-scoped: every document belongs to exactly one career profile
    # (legacy rows backfilled; new uploads always carry profile_id).
    profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("candidate_profile.id", ondelete="CASCADE"), nullable=True, index=True
    )
    kind: Mapped[DocumentKind] = mapped_column(
        String(32), nullable=False
    )  # validated as DocumentKind by domain/service layer
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime: Mapped[str] = mapped_column(String(127), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[DocumentStatus] = mapped_column(
        String(32), nullable=False, default=DocumentStatus.PENDING
    )
    parsed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index",
    )


class DocumentChunk(Base):
    """Chunk of a document with vector embedding + full-text tsvector.

    Append-only: chunks are rewritten with the document (no in-place edits).
    """

    __tablename__ = "document_chunk"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk_doc_index"),
        Index(
            "ix_document_chunk_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_document_chunk_fts_gin", "fts", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("document.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
    meta: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)
    fts: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', content)", persisted=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default="now()", nullable=False
    )

    document: Mapped[Document] = relationship(back_populates="chunks")
