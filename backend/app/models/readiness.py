"""Readiness snapshot model — immutable append-only history."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, Float, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ReadinessSnapshot(Base):
    """Deterministic readiness snapshot. Append-only; never edited."""

    __tablename__ = "readiness_snapshot"
    __table_args__ = (
        CheckConstraint("overall >= 0 AND overall <= 100", name="ck_readiness_overall"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_readiness_confidence"),
        CheckConstraint(
            "evidence_coverage >= 0 AND evidence_coverage <= 1", name="ck_readiness_coverage"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Profile-scoped: readiness snapshots belong to one career profile.
    profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("candidate_profile.id", ondelete="CASCADE"), nullable=True, index=True
    )
    role_id: Mapped[int | None] = mapped_column(
        ForeignKey("role.id", ondelete="SET NULL"), nullable=True
    )
    overall: Mapped[float] = mapped_column(Float, nullable=False)
    per_competency: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_coverage: Mapped[float] = mapped_column(Float, nullable=False)
    critical_gaps: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default="now()", nullable=False
    )
