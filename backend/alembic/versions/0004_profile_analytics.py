"""profile-scoped analytics: readiness/preparation/practice attribution

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-14

What changes:
- readiness_snapshot, preparation_item, practice_session gain profile_id
  (FK -> candidate_profile.id) so derived analytics are attributable to a
  career profile and never mix evidence from another profile.
- Existing rows are backfilled to the owning user's first (legacy single)
  profile, mirroring the 0003 backfill for documents/roles/evidence.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("readiness_snapshot", "preparation_item", "practice_session"):
        op.add_column(
            table,
            sa.Column(
                "profile_id",
                sa.Integer(),
                sa.ForeignKey(
                    "candidate_profile.id",
                    ondelete="CASCADE",
                    name=f"{table}_profile_id_fkey",
                ),
                nullable=True,
            ),
        )
        op.execute(
            f"""
            UPDATE {table} t
            SET profile_id = (
                SELECT cp.id FROM candidate_profile cp
                WHERE cp.user_id = t.user_id
                ORDER BY cp.id LIMIT 1
            )
            WHERE t.profile_id IS NULL
            """
        )
        op.create_index(f"ix_{table}_profile_id", table, ["profile_id"], unique=False)


def downgrade() -> None:
    for table in ("practice_session", "preparation_item", "readiness_snapshot"):
        op.drop_index(f"ix_{table}_profile_id", table_name=table)
        op.drop_constraint(f"{table}_profile_id_fkey", table, type_="foreignkey")
        op.drop_column(table, "profile_id")
