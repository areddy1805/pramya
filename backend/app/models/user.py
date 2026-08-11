"""User + candidate profile models.

Single-user default in V1; `user_id` is the ownership root for all
candidate data. Deleting a user cascades to everything they own.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """Application user. Auth is deployment-dependent; email is optional."""

    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    candidate_profile: Mapped[CandidateProfile | None] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )


class CandidateProfile(Base, TimestampMixin):
    """Candidate profile. One per user in V1."""

    __tablename__ = "candidate_profile"
    __table_args__ = (UniqueConstraint("user_id", name="uq_candidate_profile_user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    seniority_target: Mapped[str | None] = mapped_column(String(100), nullable=True)
    headline: Mapped[str | None] = mapped_column(String(300), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)

    user: Mapped[User] = relationship(back_populates="candidate_profile")
