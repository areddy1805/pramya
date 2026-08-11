"""Role model (analyzed JD) + competency graph + candidate competency state.

`role` is the analyzed JD; `competency` rows are the graph nodes derived
from it; `candidate_competency` holds the candidate's derived state per
node (deterministic aggregation + LLM inputs).
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import CompetencyCategory, CompetencyImportance
from app.models.base import Base, TimestampMixin


class Role(Base, TimestampMixin):
    """Analyzed target role (from a JD document)."""

    __tablename__ = "role"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("document.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    seniority: Mapped[str | None] = mapped_column(String(100), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    competencies: Mapped[list[Competency]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
        order_by="Competency.importance_rank",
    )


class Competency(Base, TimestampMixin):
    """Competency graph node for a role."""

    __tablename__ = "competency"
    __table_args__ = (
        UniqueConstraint("role_id", "name", name="uq_competency_role_name"),
        CheckConstraint("level >= 1 AND level <= 5", name="ck_competency_level"),
        CheckConstraint("weight >= 0 AND weight <= 1", name="ck_competency_weight"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    role_id: Mapped[int] = mapped_column(
        ForeignKey("role.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[CompetencyCategory] = mapped_column(String(32), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)  # 1..5 required level
    importance: Mapped[CompetencyImportance] = mapped_column(String(32), nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    importance_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    role: Mapped[Role] = relationship(back_populates="competencies")


class CandidateCompetency(Base, TimestampMixin):
    """Derived candidate state per competency (deterministic + LLM inputs)."""

    __tablename__ = "candidate_competency"
    __table_args__ = (
        UniqueConstraint(
            "candidate_profile_id", "competency_id", name="uq_candidate_comp_profile_comp"
        ),
        CheckConstraint("score >= 0 AND score <= 10", name="ck_candidate_comp_score"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_candidate_comp_confidence"),
        CheckConstraint(
            "evidence_coverage >= 0 AND evidence_coverage <= 1",
            name="ck_candidate_comp_coverage",
        ),
        CheckConstraint(
            "demonstrated_level >= 1 AND demonstrated_level <= 5",
            name="ck_candidate_comp_level",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_profile_id: Mapped[int] = mapped_column(
        ForeignKey("candidate_profile.id", ondelete="CASCADE"), nullable=False, index=True
    )
    competency_id: Mapped[int] = mapped_column(
        ForeignKey("competency.id", ondelete="CASCADE"), nullable=False, index=True
    )
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence_coverage: Mapped[float | None] = mapped_column(Float, nullable=True)
    demonstrated_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
