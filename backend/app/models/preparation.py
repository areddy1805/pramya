"""Preparation queue + practice session models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import PracticeItemStatus, PracticeKind
from app.models.base import Base, TimestampMixin


class PreparationItem(Base, TimestampMixin):
    """One item in the preparation queue (today's practice)."""

    __tablename__ = "preparation_item"
    __table_args__ = (
        CheckConstraint("priority >= 0", name="ck_preparation_item_priority"),
        CheckConstraint(
            "expected_improvement >= 0 AND expected_improvement <= 1",
            name="ck_preparation_item_improvement",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    competency_id: Mapped[int | None] = mapped_column(
        ForeignKey("competency.id", ondelete="SET NULL"), nullable=True
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    assessment_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expected_improvement: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[PracticeItemStatus] = mapped_column(
        String(32), nullable=False, default=PracticeItemStatus.OPEN
    )


class PracticeSession(Base, TimestampMixin):
    """A completed/attempted practice session tied to a prep item."""

    __tablename__ = "practice_session"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    preparation_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("preparation_item.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[PracticeKind] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(255), nullable=True)
