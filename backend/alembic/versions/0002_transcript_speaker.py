"""add speaker column to transcript_segment (speaker-integrity guarantee)

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-13
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "transcript_segment",
        sa.Column(
            "speaker",
            sa.String(length=16),
            nullable=False,
            server_default="unknown",
        ),
    )
    # Backfill from the legacy JSONB role (old voice sessions): interviewer
    # and candidate rows get explicit speaker identity; anything else stays
    # 'unknown' (never guessed).
    op.execute(
        """
        UPDATE transcript_segment
        SET speaker = timestamps ->> 'role'
        WHERE timestamps ->> 'role' IN ('interviewer', 'candidate')
        """
    )
    # Keep the DB default for rows written without an explicit speaker.
    op.alter_column("transcript_segment", "speaker", server_default=None)


def downgrade() -> None:
    op.drop_column("transcript_segment", "speaker")
