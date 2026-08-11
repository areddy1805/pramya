"""Story bank model (Situation/Task/Action/Result + metrics)."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Story(Base, TimestampMixin):
    """One story from the candidate's story bank."""

    __tablename__ = "story"
    __table_args__ = (
        CheckConstraint("freshness >= 0 AND freshness <= 1", name="ck_story_freshness"),
        CheckConstraint("coverage >= 0 AND coverage <= 1", name="ck_story_coverage"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_story_confidence"),
        CheckConstraint("usage_count >= 0", name="ck_story_usage_count"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    situation: Mapped[str | None] = mapped_column(Text, nullable=True)
    task: Mapped[str | None] = mapped_column(Text, nullable=True)
    action: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics: Mapped[str | None] = mapped_column(Text, nullable=True)
    conflict: Mapped[str | None] = mapped_column(Text, nullable=True)
    learning: Mapped[str | None] = mapped_column(Text, nullable=True)
    strength: Mapped[str | None] = mapped_column(String(255), nullable=True)
    competency_ids: Mapped[list[int] | None] = mapped_column(JSONB, nullable=True)
    freshness: Mapped[float | None] = mapped_column(Float, nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    coverage: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
