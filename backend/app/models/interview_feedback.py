"""Interview feedback model — per-profile preparation memory.

One row per completed mock interview (written at stop()). The interview
context builder reads the latest rows for a profile so a subsequent session
re-probes prior weak areas (weaknesses/gaps/topics). Profile-scoped: prep
memory never leaks across career profiles.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class InterviewFeedback(Base):
    """Preparation memory for one completed mock interview."""

    __tablename__ = "interview_feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("candidate_profile.id", ondelete="CASCADE"), nullable=True, index=True
    )
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("interview_session.id", ondelete="CASCADE"), nullable=True, index=True
    )
    weaknesses: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    gaps: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    topics: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    avg_overall: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default="now()", nullable=False
    )
