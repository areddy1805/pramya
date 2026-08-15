"""User + candidate profile (career profile) models.

`user` is the ownership root; each user owns one or more career profiles
(candidate_profile). Every workspace entity (documents, roles, evidence,
interviews, readiness) is owned by a profile, giving an unambiguous
entity -> profile -> user path. Deleting a user cascades to everything
they own; deleting a profile cascades to everything the profile owns.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """Application user. Auth is deployment-dependent; email is optional."""

    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Persisted UX preference only; authorization always verifies an
    # explicit profile_id against the authenticated user.
    active_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("candidate_profile.id", ondelete="SET NULL"), nullable=True
    )

    profiles: Mapped[list[CandidateProfile]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="CandidateProfile.user_id",
    )


class CandidateProfile(Base, TimestampMixin):
    """Career profile. A user may own many; unique (user_id, name)."""

    __tablename__ = "candidate_profile"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_candidate_profile_user_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str | None] = mapped_column(String(200), nullable=True)
    positioning: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    seniority_target: Mapped[str | None] = mapped_column(String(100), nullable=True)
    headline: Mapped[str | None] = mapped_column(String(300), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Explicit preferred/current documents (persisted user choice). NULL =
    # unset (builder falls back to the latest parsed document). ON DELETE
    # SET NULL keeps the pointer valid when a document is removed while
    # historical interview snapshots stay intact.
    preferred_resume_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("document.id", ondelete="SET NULL"), nullable=True
    )
    preferred_jd_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("document.id", ondelete="SET NULL"), nullable=True
    )

    user: Mapped[User] = relationship(
        back_populates="profiles", foreign_keys="CandidateProfile.user_id"
    )
