"""Unit tests: model metadata matches plan §7 (no DB required)."""

from app.models import (
    Answer,
    CandidateCompetency,
    CandidateProfile,
    Competency,
    Document,
    DocumentChunk,
    Evaluation,
    EvaluationVersion,
    Evidence,
    IdempotencyRecord,
    InterviewDebrief,
    InterviewSession,
    InterviewTurn,
    PracticeSession,
    PreparationItem,
    Question,
    ReadinessSnapshot,
    Role,
    Story,
    User,
)
from app.models.base import Base

PLAN_TABLES = {
    "user",
    "candidate_profile",
    "document",
    "document_chunk",
    "role",
    "competency",
    "candidate_competency",
    "evidence",
    "interview_session",
    "interview_turn",
    "audio_segment",
    "transcript_segment",
    "question",
    "answer",
    "evaluation",
    "preparation_item",
    "practice_session",
    "story",
    "readiness_snapshot",
    "interview_debrief",
    "evaluation_version",
    "idempotency_record",
}

# §7 entities mapping model -> table name (idempotency_record is task 1.6 infra)
MODEL_TABLE_EXPECT = {
    User: "user",
    CandidateProfile: "candidate_profile",
    Document: "document",
    DocumentChunk: "document_chunk",
    Role: "role",
    Competency: "competency",
    CandidateCompetency: "candidate_competency",
    Evidence: "evidence",
    InterviewSession: "interview_session",
    InterviewTurn: "interview_turn",
    Question: "question",
    Answer: "answer",
    Evaluation: "evaluation",
    PreparationItem: "preparation_item",
    PracticeSession: "practice_session",
    Story: "story",
    ReadinessSnapshot: "readiness_snapshot",
    InterviewDebrief: "interview_debrief",
    EvaluationVersion: "evaluation_version",
    IdempotencyRecord: "idempotency_record",
}


def test_all_plan_tables_present() -> None:
    actual = set(Base.metadata.tables)
    missing = PLAN_TABLES - actual
    assert not missing, f"missing tables: {sorted(missing)}"


def test_table_names_match_plan() -> None:
    for model, table in MODEL_TABLE_EXPECT.items():
        assert model.__tablename__ == table, f"{model.__name__} -> {table}"


def test_document_chunk_embedding_is_1024_vector() -> None:
    col = DocumentChunk.__table__.c.embedding
    assert col.type.dim == 1024


def test_document_chunk_has_fts_computed_column() -> None:
    col = DocumentChunk.__table__.c.fts
    assert col.computed is not None
    assert "to_tsvector" in col.computed.sqltext.text


def test_ownership_columns_are_foreign_keys() -> None:
    # Every candidate-owned table has user_id -> user.id (except child tables
    # whose parent chain terminates at user).
    for model in [
        Document,
        Role,
        Evidence,
        InterviewSession,
        PreparationItem,
        PracticeSession,
        Story,
        ReadinessSnapshot,
        InterviewDebrief,
    ]:
        table = model.__tablename__
        fk = Base.metadata.tables[table].c.user_id.foreign_keys
        assert len(fk) == 1, table
        assert next(iter(fk)).target_fullname == "user.id", table


def test_evaluation_immutable_unique_answer() -> None:
    uq = {c.name for c in Evaluation.__table__.constraints if c.name == "uq_evaluation_answer_id"}
    assert uq, "evaluation must be unique per answer"


def test_interview_turn_unique_session_seq() -> None:
    uq = {
        c.name
        for c in InterviewTurn.__table__.constraints
        if c.name == "uq_interview_turn_session_seq"
    }
    assert uq
