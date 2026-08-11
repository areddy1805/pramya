"""phase 1: core domain schema

Revision ID: 0001
Revises:
Create Date: 2026-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # pgvector extension (server ext 0.8.x lives in the pg17 image)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- user ---
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("display_name", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.UniqueConstraint("email", name="uq_user_email"),
    )

    # --- candidate_profile ---
    op.create_table(
        "candidate_profile",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seniority_target", sa.String(length=100), nullable=True),
        sa.Column("headline", sa.String(length=300), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.UniqueConstraint("user_id", name="uq_candidate_profile_user_id"),
    )

    # --- document ---
    op.create_table(
        "document",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime", sa.String(length=127), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
    )
    op.create_index("ix_document_user_id", "document", ["user_id"])
    op.create_index("ix_document_content_hash", "document", ["content_hash"])

    # --- document_chunk (pgvector + FTS) ---
    op.create_table(
        "document_chunk",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("document.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "fts",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', content)", persisted=True),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk_doc_index"),
    )
    op.create_index("ix_document_chunk_document_id", "document_chunk", ["document_id"])
    op.create_index(
        "ix_document_chunk_embedding_hnsw",
        "document_chunk",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_document_chunk_fts_gin", "document_chunk", ["fts"], postgresql_using="gin"
    )

    # --- role ---
    op.create_table(
        "role",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_document_id", sa.Integer(), sa.ForeignKey("document.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("seniority", sa.String(length=100), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
    )
    op.create_index("ix_role_user_id", "role", ["user_id"])

    # --- competency ---
    op.create_table(
        "competency",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("role.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("importance", sa.String(length=32), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("importance_rank", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.CheckConstraint("level >= 1 AND level <= 5", name="ck_competency_level"),
        sa.CheckConstraint("weight >= 0 AND weight <= 1", name="ck_competency_weight"),
        sa.UniqueConstraint("role_id", "name", name="uq_competency_role_name"),
    )
    op.create_index("ix_competency_role_id", "competency", ["role_id"])

    # --- candidate_competency ---
    op.create_table(
        "candidate_competency",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("candidate_profile_id", sa.Integer(), sa.ForeignKey("candidate_profile.id", ondelete="CASCADE"), nullable=False),
        sa.Column("competency_id", sa.Integer(), sa.ForeignKey("competency.id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evidence_coverage", sa.Float(), nullable=True),
        sa.Column("demonstrated_level", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.CheckConstraint("score >= 0 AND score <= 10", name="ck_candidate_comp_score"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_candidate_comp_confidence"),
        sa.CheckConstraint("evidence_coverage >= 0 AND evidence_coverage <= 1", name="ck_candidate_comp_coverage"),
        sa.CheckConstraint("demonstrated_level >= 1 AND demonstrated_level <= 5", name="ck_candidate_comp_level"),
        sa.UniqueConstraint("candidate_profile_id", "competency_id", name="uq_candidate_comp_profile_comp"),
    )
    op.create_index("ix_candidate_competency_candidate_profile_id", "candidate_competency", ["candidate_profile_id"])
    op.create_index("ix_candidate_competency_competency_id", "candidate_competency", ["competency_id"])

    # --- evidence ---
    op.create_table(
        "evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("source_ref", sa.String(length=255), nullable=True),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("competency_id", sa.Integer(), sa.ForeignKey("competency.id", ondelete="SET NULL"), nullable=True),
        sa.Column("strength", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.CheckConstraint("strength >= 0 AND strength <= 1", name="ck_evidence_strength"),
    )
    op.create_index("ix_evidence_user_id", "evidence", ["user_id"])
    op.create_index("ix_evidence_competency_id", "evidence", ["competency_id"])

    # --- interview_session ---
    op.create_table(
        "interview_session",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("candidate_profile_id", sa.Integer(), sa.ForeignKey("candidate_profile.id", ondelete="SET NULL"), nullable=True),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("role.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("graph_thread_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.UniqueConstraint("graph_thread_id", name="uq_interview_session_graph_thread_id"),
    )
    op.create_index("ix_interview_session_user_id", "interview_session", ["user_id"])

    # --- interview_turn ---
    op.create_table(
        "interview_turn",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("interview_session_id", sa.Integer(), sa.ForeignKey("interview_session.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("hints_used", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.UniqueConstraint("interview_session_id", "seq", name="uq_interview_turn_session_seq"),
    )
    op.create_index("ix_interview_turn_interview_session_id", "interview_turn", ["interview_session_id"])

    # --- audio_segment ---
    op.create_table(
        "audio_segment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("interview_session_id", sa.Integer(), sa.ForeignKey("interview_session.id", ondelete="CASCADE"), nullable=False),
        sa.Column("turn_id", sa.Integer(), sa.ForeignKey("interview_turn.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
    )
    op.create_index("ix_audio_segment_interview_session_id", "audio_segment", ["interview_session_id"])

    # --- transcript_segment ---
    op.create_table(
        "transcript_segment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("interview_session_id", sa.Integer(), sa.ForeignKey("interview_session.id", ondelete="CASCADE"), nullable=False),
        sa.Column("turn_id", sa.Integer(), sa.ForeignKey("interview_turn.id", ondelete="SET NULL"), nullable=True),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("partial", sa.Boolean(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("timestamps", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.UniqueConstraint("interview_session_id", "turn_id", "seq", name="uq_transcript_segment_session_turn_seq"),
    )
    op.create_index("ix_transcript_segment_interview_session_id", "transcript_segment", ["interview_session_id"])

    # --- question ---
    op.create_table(
        "question",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("interview_session_id", sa.Integer(), sa.ForeignKey("interview_session.id", ondelete="CASCADE"), nullable=False),
        sa.Column("turn_id", sa.Integer(), sa.ForeignKey("interview_turn.id", ondelete="SET NULL"), nullable=True),
        sa.Column("competency_id", sa.Integer(), sa.ForeignKey("competency.id", ondelete="SET NULL"), nullable=True),
        sa.Column("difficulty", sa.String(length=32), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("hint_levels", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
    )
    op.create_index("ix_question_interview_session_id", "question", ["interview_session_id"])
    op.create_index("ix_question_competency_id", "question", ["competency_id"])

    # --- answer ---
    op.create_table(
        "answer",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("question.id", ondelete="CASCADE"), nullable=False),
        sa.Column("interview_turn_id", sa.Integer(), sa.ForeignKey("interview_turn.id", ondelete="SET NULL"), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("raw_audio_ref", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
    )
    op.create_index("ix_answer_question_id", "answer", ["question_id"])

    # --- evaluation (immutable) ---
    op.create_table(
        "evaluation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("answer_id", sa.Integer(), sa.ForeignKey("answer.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dimensions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("overall", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("strengths", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("weaknesses", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("missing_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("hints_used", sa.Integer(), nullable=False),
        sa.Column("follow_ups", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evaluator_version", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("overall >= 0 AND overall <= 10", name="ck_evaluation_overall"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_evaluation_confidence"),
        sa.UniqueConstraint("answer_id", name="uq_evaluation_answer_id"),
    )
    op.create_index("ix_evaluation_answer_id", "evaluation", ["answer_id"])

    # --- preparation_item ---
    op.create_table(
        "preparation_item",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("competency_id", sa.Integer(), sa.ForeignKey("competency.id", ondelete="SET NULL"), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("assessment_type", sa.String(length=64), nullable=True),
        sa.Column("expected_improvement", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.CheckConstraint("priority >= 0", name="ck_preparation_item_priority"),
        sa.CheckConstraint("expected_improvement >= 0 AND expected_improvement <= 1", name="ck_preparation_item_improvement"),
    )
    op.create_index("ix_preparation_item_user_id", "preparation_item", ["user_id"])

    # --- practice_session ---
    op.create_table(
        "practice_session",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("preparation_item_id", sa.Integer(), sa.ForeignKey("preparation_item.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
    )
    op.create_index("ix_practice_session_user_id", "practice_session", ["user_id"])

    # --- story ---
    op.create_table(
        "story",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("situation", sa.Text(), nullable=True),
        sa.Column("task", sa.Text(), nullable=True),
        sa.Column("action", sa.Text(), nullable=True),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("metrics", sa.Text(), nullable=True),
        sa.Column("conflict", sa.Text(), nullable=True),
        sa.Column("learning", sa.Text(), nullable=True),
        sa.Column("strength", sa.String(length=255), nullable=True),
        sa.Column("competency_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("freshness", sa.Float(), nullable=True),
        sa.Column("usage_count", sa.Integer(), nullable=False),
        sa.Column("coverage", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.CheckConstraint("freshness >= 0 AND freshness <= 1", name="ck_story_freshness"),
        sa.CheckConstraint("coverage >= 0 AND coverage <= 1", name="ck_story_coverage"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_story_confidence"),
        sa.CheckConstraint("usage_count >= 0", name="ck_story_usage_count"),
    )
    op.create_index("ix_story_user_id", "story", ["user_id"])

    # --- readiness_snapshot (append-only) ---
    op.create_table(
        "readiness_snapshot",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("role.id", ondelete="SET NULL"), nullable=True),
        sa.Column("overall", sa.Float(), nullable=False),
        sa.Column("per_competency", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_coverage", sa.Float(), nullable=False),
        sa.Column("critical_gaps", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("overall >= 0 AND overall <= 100", name="ck_readiness_overall"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_readiness_confidence"),
        sa.CheckConstraint("evidence_coverage >= 0 AND evidence_coverage <= 1", name="ck_readiness_coverage"),
    )
    op.create_index("ix_readiness_snapshot_user_id", "readiness_snapshot", ["user_id"])

    # --- interview_debrief ---
    op.create_table(
        "interview_debrief",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=200), nullable=True),
        sa.Column("round", sa.String(length=100), nullable=True),
        sa.Column("questions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("result", sa.String(length=64), nullable=True),
        sa.Column("analysis", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
    )
    op.create_index("ix_interview_debrief_user_id", "interview_debrief", ["user_id"])

    # --- evaluation_version ---
    op.create_table(
        "evaluation_version",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("prompt_hash", sa.String(length=64), nullable=False),
        sa.Column("model_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.UniqueConstraint("name", name="uq_evaluation_version_name"),
    )

    # --- idempotency_record ---
    op.create_table(
        "idempotency_record",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scope", sa.String(length=128), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("scope", "key", name="uq_idempotency_record_scope_key"),
    )


def downgrade() -> None:
    op.drop_table("idempotency_record")
    op.drop_table("evaluation_version")
    op.drop_table("interview_debrief")
    op.drop_table("readiness_snapshot")
    op.drop_table("story")
    op.drop_table("practice_session")
    op.drop_table("preparation_item")
    op.drop_table("evaluation")
    op.drop_table("answer")
    op.drop_table("question")
    op.drop_table("transcript_segment")
    op.drop_table("audio_segment")
    op.drop_table("interview_turn")
    op.drop_table("interview_session")
    op.drop_table("evidence")
    op.drop_table("candidate_competency")
    op.drop_table("competency")
    op.drop_table("role")
    op.drop_table("document_chunk")
    op.drop_table("document")
    op.drop_table("candidate_profile")
    op.drop_table("user")
    op.execute("DROP EXTENSION IF EXISTS vector")
