"""question provenance columns + interview_feedback prep-memory table

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-15

What changes:
- question gains category/source/source_ref so every generated question
  carries provenance (which taxonomy category, which grounding source,
  which specific entity) — the interviewer must never invent experience.
- interview_feedback is the per-profile preparation memory: one row per
  completed mock interview, capturing weaknesses/gaps/topics + avg overall.
  The context builder reads the latest 3 rows for the profile so the next
  session re-probes prior weak areas.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- question provenance ------------------------------------------------
    op.add_column("question", sa.Column("category", sa.String(length=64), nullable=True))
    op.add_column("question", sa.Column("source", sa.String(length=32), nullable=True))
    op.add_column("question", sa.Column("source_ref", sa.Text(), nullable=True))
    op.add_column(
        "question", sa.Column("target_competency", sa.String(length=200), nullable=True)
    )

    # --- interview_feedback (prep memory) -----------------------------------
    op.create_table(
        "interview_feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("candidate_profile.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("interview_session.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("weaknesses", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("gaps", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("topics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("avg_overall", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_interview_feedback_user_id", "interview_feedback", ["user_id"])
    op.create_index("ix_interview_feedback_profile_id", "interview_feedback", ["profile_id"])
    op.create_index("ix_interview_feedback_session_id", "interview_feedback", ["session_id"])


def downgrade() -> None:
    op.drop_table("interview_feedback")
    op.drop_column("question", "target_competency")
    op.drop_column("question", "source_ref")
    op.drop_column("question", "source")
    op.drop_column("question", "category")
