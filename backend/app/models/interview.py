"""Interview session models: session, turns, audio, transcript, question, answer, evaluation.

State transitions for `interview_session.status` are enforced by the
interview service (mirrored in the LangGraph thread in Phase 3).
`evaluation` is append-only and immutable once written.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import (
    AssessmentMode,
    InterviewKind,
    InterviewSessionStatus,
    InterviewTurnKind,
    QuestionDifficulty,
    QuestionType,
    TurnDirection,
)
from app.models.base import Base, TimestampMixin


class InterviewSession(Base, TimestampMixin):
    """A durable interview session (thread_id == LangGraph thread)."""

    __tablename__ = "interview_session"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("candidate_profile.id", ondelete="SET NULL"), nullable=True
    )
    role_id: Mapped[int | None] = mapped_column(
        ForeignKey("role.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[InterviewKind] = mapped_column(String(32), nullable=False)
    status: Mapped[InterviewSessionStatus] = mapped_column(
        String(32), nullable=False, default=InterviewSessionStatus.CREATED
    )
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    graph_thread_id: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)

    turns: Mapped[list[InterviewTurn]] = relationship(
        back_populates="interview_session",
        cascade="all, delete-orphan",
        order_by="InterviewTurn.seq",
    )


class InterviewTurn(Base, TimestampMixin):
    """One turn in an interview (question / answer / feedback)."""

    __tablename__ = "interview_turn"
    __table_args__ = (
        UniqueConstraint("interview_session_id", "seq", name="uq_interview_turn_session_seq"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    interview_session_id: Mapped[int] = mapped_column(
        ForeignKey("interview_session.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[InterviewTurnKind] = mapped_column(String(32), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    hints_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    interview_session: Mapped[InterviewSession] = relationship(back_populates="turns")


class AudioSegment(Base, TimestampMixin):
    """Audio clip for a turn. Stored only if the user opts in (retention)."""

    __tablename__ = "audio_segment"

    id: Mapped[int] = mapped_column(primary_key=True)
    interview_session_id: Mapped[int] = mapped_column(
        ForeignKey("interview_session.id", ondelete="CASCADE"), nullable=False, index=True
    )
    turn_id: Mapped[int | None] = mapped_column(
        ForeignKey("interview_turn.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[TurnDirection] = mapped_column(String(32), nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retention_until: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )


class TranscriptSegment(Base, TimestampMixin):
    """ASR transcript segment (partial or final)."""

    __tablename__ = "transcript_segment"
    __table_args__ = (
        UniqueConstraint(
            "interview_session_id", "turn_id", "seq", name="uq_transcript_segment_session_turn_seq"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    interview_session_id: Mapped[int] = mapped_column(
        ForeignKey("interview_session.id", ondelete="CASCADE"), nullable=False, index=True
    )
    turn_id: Mapped[int | None] = mapped_column(
        ForeignKey("interview_turn.id", ondelete="SET NULL"), nullable=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    partial: Mapped[bool] = mapped_column(nullable=False, default=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Unambiguous speaker identity (speaker-integrity guarantee).
    speaker: Mapped[str] = mapped_column(
        String(16), nullable=False, default="unknown", server_default="unknown"
    )
    timestamps: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class Question(Base, TimestampMixin):
    """An interview question, optionally tied to a turn + competency."""

    __tablename__ = "question"

    id: Mapped[int] = mapped_column(primary_key=True)
    interview_session_id: Mapped[int] = mapped_column(
        ForeignKey("interview_session.id", ondelete="CASCADE"), nullable=False, index=True
    )
    turn_id: Mapped[int | None] = mapped_column(
        ForeignKey("interview_turn.id", ondelete="SET NULL"), nullable=True
    )
    competency_id: Mapped[int | None] = mapped_column(
        ForeignKey("competency.id", ondelete="SET NULL"), nullable=True, index=True
    )
    difficulty: Mapped[QuestionDifficulty] = mapped_column(String(32), nullable=False)
    type: Mapped[QuestionType] = mapped_column(String(32), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    hint_levels: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Provenance (productization): taxonomy category + grounding source and
    # the specific entity the question targets. The interviewer must never
    # invent candidate experience — these columns make every question
    # attributable to resume / JD / profile / evidence / follow-up / generic.
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_competency: Mapped[str | None] = mapped_column(String(200), nullable=True)

    answers: Mapped[list[Answer]] = relationship(
        back_populates="question", cascade="all, delete-orphan"
    )


class Answer(Base, TimestampMixin):
    """Candidate answer to a question (text mode in V1; voice later)."""

    __tablename__ = "answer"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("question.id", ondelete="CASCADE"), nullable=False, index=True
    )
    interview_turn_id: Mapped[int | None] = mapped_column(
        ForeignKey("interview_turn.id", ondelete="SET NULL"), nullable=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[AssessmentMode] = mapped_column(
        String(32), nullable=False, default=AssessmentMode.TEXT
    )
    raw_audio_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)

    question: Mapped[Question] = relationship(back_populates="answers")
    evaluation: Mapped[Evaluation | None] = relationship(
        back_populates="answer", cascade="all, delete-orphan", uselist=False
    )


class Evaluation(Base):
    """Immutable evaluation of one answer. Append-only; never edited."""

    __tablename__ = "evaluation"
    __table_args__ = (
        UniqueConstraint("answer_id", name="uq_evaluation_answer_id"),
        CheckConstraint("overall >= 0 AND overall <= 10", name="ck_evaluation_overall"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_evaluation_confidence"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    answer_id: Mapped[int] = mapped_column(
        ForeignKey("answer.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dimensions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    overall: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    strengths: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    weaknesses: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    evidence_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    missing_evidence: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    hints_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    follow_ups: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    evaluator_version: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default="now()", nullable=False
    )

    answer: Mapped[Answer] = relationship(back_populates="evaluation")
