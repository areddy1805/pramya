"""Debrief + evaluation version registry models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class InterviewDebrief(Base, TimestampMixin):
    """Real-interview debrief recorded by the candidate."""

    __tablename__ = "interview_debrief"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str | None] = mapped_column(String(200), nullable=True)
    round: Mapped[str | None] = mapped_column(String(100), nullable=True)
    questions: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str | None] = mapped_column(String(64), nullable=True)
    analysis: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class EvaluationVersion(Base, TimestampMixin):
    """Prompt/evaluator registry — every evaluation references a version."""

    __tablename__ = "evaluation_version"
    __table_args__ = (UniqueConstraint("name", name="uq_evaluation_version_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    model_policy: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default="now()", nullable=False
    )
