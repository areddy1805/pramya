"""multi-profile career workspace: profile identity + profile-scoped entities

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-13

What changes:
- candidate_profile becomes the career-profile container: gains name/slug/
  positioning/status and drops the one-per-user uniqueness constraint in
  favor of unique (user_id, name). Existing rows are backfilled to a
  deterministic default ('Career Profile').
- document, role, evidence gain profile_id (FK -> candidate_profile.id,
  CASCADE) so every workspace entity has an unambiguous entity -> profile
  -> user ownership path. Existing rows are backfilled to the owning user's
  (single) profile.
- user gains active_profile_id (FK -> candidate_profile.id, SET NULL) — a
  persisted UX preference only; authorization never depends on it.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- candidate_profile: career profile identity -------------------------
    op.add_column("candidate_profile", sa.Column("name", sa.String(length=200), nullable=True))
    op.add_column("candidate_profile", sa.Column("slug", sa.String(length=200), nullable=True))
    op.add_column("candidate_profile", sa.Column("positioning", sa.Text(), nullable=True))
    op.add_column(
        "candidate_profile",
        sa.Column("status", sa.String(length=32), nullable=True, server_default="active"),
    )
    op.drop_constraint("uq_candidate_profile_user_id", "candidate_profile", type_="unique")
    # Backfill legacy single profile rows (one per user) with a stable name.
    op.execute("UPDATE candidate_profile SET name = 'Career Profile' WHERE name IS NULL")
    op.execute("UPDATE candidate_profile SET status = 'active' WHERE status IS NULL")
    op.alter_column("candidate_profile", "name", nullable=False)
    op.create_unique_constraint(
        "uq_candidate_profile_user_name", "candidate_profile", ["user_id", "name"]
    )
    op.create_index(
        "ix_candidate_profile_user_id", "candidate_profile", ["user_id"], unique=False
    )

    # --- document.profile_id -------------------------------------------------
    op.add_column(
        "document",
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("candidate_profile.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.execute(
        """
        UPDATE document d
        SET profile_id = (
            SELECT cp.id FROM candidate_profile cp
            WHERE cp.user_id = d.user_id
            ORDER BY cp.id LIMIT 1
        )
        WHERE d.profile_id IS NULL
        """
    )
    op.create_index("ix_document_profile_id", "document", ["profile_id"], unique=False)

    # --- role.profile_id -------------------------------------------------------
    op.add_column(
        "role",
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("candidate_profile.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.execute(
        """
        UPDATE role r
        SET profile_id = (
            SELECT cp.id FROM candidate_profile cp
            WHERE cp.user_id = r.user_id
            ORDER BY cp.id LIMIT 1
        )
        WHERE r.profile_id IS NULL
        """
    )
    op.create_index("ix_role_profile_id", "role", ["profile_id"], unique=False)

    # --- evidence.profile_id ----------------------------------------------------
    op.add_column(
        "evidence",
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("candidate_profile.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.execute(
        """
        UPDATE evidence e
        SET profile_id = (
            SELECT cp.id FROM candidate_profile cp
            WHERE cp.user_id = e.user_id
            ORDER BY cp.id LIMIT 1
        )
        WHERE e.profile_id IS NULL
        """
    )
    op.create_index("ix_evidence_profile_id", "evidence", ["profile_id"], unique=False)

    # --- user.active_profile_id (persisted UX preference) -----------------------
    op.add_column(
        "user",
        sa.Column(
            "active_profile_id",
            sa.Integer(),
            sa.ForeignKey("candidate_profile.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.execute(
        """
        UPDATE "user" u
        SET active_profile_id = (
            SELECT cp.id FROM candidate_profile cp
            WHERE cp.user_id = u.id ORDER BY cp.id LIMIT 1
        )
        """
    )


def downgrade() -> None:
    op.drop_column("user", "active_profile_id")
    op.drop_index("ix_evidence_profile_id", table_name="evidence")
    op.drop_constraint(
        "fk_evidence_profile_id_candidate_profile", "evidence", type_="foreignkey"
    )
    op.drop_column("evidence", "profile_id")
    op.drop_index("ix_role_profile_id", table_name="role")
    op.drop_constraint(
        "fk_role_profile_id_candidate_profile", "role", type_="foreignkey"
    )
    op.drop_column("role", "profile_id")
    op.drop_index("ix_document_profile_id", table_name="document")
    op.drop_constraint(
        "fk_document_profile_id_candidate_profile", "document", type_="foreignkey"
    )
    op.drop_column("document", "profile_id")
    op.drop_index("ix_candidate_profile_user_id", table_name="candidate_profile")
    op.drop_constraint("uq_candidate_profile_user_name", "candidate_profile", type_="unique")
    op.alter_column("candidate_profile", "name", nullable=True)
    op.drop_column("candidate_profile", "status")
    op.drop_column("candidate_profile", "positioning")
    op.drop_column("candidate_profile", "slug")
    op.drop_column("candidate_profile", "name")
    op.create_unique_constraint(
        "uq_candidate_profile_user_id", "candidate_profile", ["user_id"]
    )
