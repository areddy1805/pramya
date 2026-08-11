"""Declarative base + shared column helpers for all ORM models.

Uses SQLAlchemy 2.0 typed mappings (`Mapped` / `mapped_column`).
A shared naming convention keeps constraint/index names stable across
Alembic migrations.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import MetaData, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Root declarative base. All ORM models inherit from this."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """created_at / updated_at columns, server-side defaults."""

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )
