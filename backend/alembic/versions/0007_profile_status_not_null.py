"""align candidate_profile schema with models (NOT NULL status)

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-16

What changes:
- candidate_profile.status is enforced NOT NULL. The model declares a
  non-optional column; migration 0003 created it nullable with a
  server_default 'active' and backfilled every row, so the column already
  holds 'active' everywhere. This migration closes the model/migration
  drift (alembic check) without touching data.

The ix_candidate_profile_user_id index (created in 0003) is retained and
now declared on the model (index=True) — the index is the query path for
profile listing and must not be dropped by future autogenerate runs.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "candidate_profile",
        "status",
        existing_type=sa.String(length=32),
        nullable=False,
        existing_server_default="active",
    )


def downgrade() -> None:
    op.alter_column(
        "candidate_profile",
        "status",
        existing_type=sa.String(length=32),
        nullable=True,
        existing_server_default="active",
    )
