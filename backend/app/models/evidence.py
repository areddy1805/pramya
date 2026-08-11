"""Evidence ledger model.

Append-only ledger with provenance statuses
(claimed/observed/demonstrated/inferred/unknown). Status transitions are
enforced by the evidence service, never invented by an LLM.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import EvidenceSourceKind, EvidenceStatus
from app.models.base import Base, TimestampMixin


class Evidence(Base, TimestampMixin):
    """One piece of evidence about the candidate."""

    __tablename__ = "evidence"
    __table_args__ = (
        CheckConstraint("strength >= 0 AND strength <= 1", name="ck_evidence_strength"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_kind: Mapped[EvidenceSourceKind] = mapped_column(String(32), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[EvidenceStatus] = mapped_column(
        String(32), nullable=False, default=EvidenceStatus.CLAIMED
    )
    competency_id: Mapped[int | None] = mapped_column(
        ForeignKey("competency.id", ondelete="SET NULL"), nullable=True, index=True
    )
    strength: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
