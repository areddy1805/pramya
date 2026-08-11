"""Idempotency record — dedupe for answer submission / write endpoints.

Task 1.6: idempotency keys for answer submission. A (scope, key) pair is
unique; a second submission with the same key returns the stored payload
instead of re-executing.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class IdempotencyRecord(Base):
    """One processed idempotency key within a scope."""

    __tablename__ = "idempotency_record"
    __table_args__ = (
        UniqueConstraint("scope", "key", name="uq_idempotency_record_scope_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    scope: Mapped[str] = mapped_column(String(128), nullable=False)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default="now()", nullable=False
    )
