"""explicit preferred resume/JD per profile (document selection)

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-16

What changes:
- candidate_profile gains preferred_resume_document_id and
  preferred_jd_document_id (FK document.id, ON DELETE SET NULL): the
  user's explicit persisted choice of current resume / JD for interviews.
  NULL means unset -> the context builder falls back to the latest parsed
  document. Historical interview sessions are unaffected: they keep the
  immutable grounding snapshot in session.config.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidate_profile",
        sa.Column(
            "preferred_resume_document_id",
            sa.Integer(),
            sa.ForeignKey("document.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "candidate_profile",
        sa.Column(
            "preferred_jd_document_id",
            sa.Integer(),
            sa.ForeignKey("document.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("candidate_profile", "preferred_jd_document_id")
    op.drop_column("candidate_profile", "preferred_resume_document_id")
