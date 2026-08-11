"""Unit-of-work helper: one session, explicit commit/rollback boundary."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionFactory, session_factory


class UnitOfWork:
    """Wraps one AsyncSession with explicit commit/rollback.

    Repositories are created against the same session; the caller commits
    explicitly (or uses `run()` for the commit-on-success pattern).
    """

    def __init__(self, factory: SessionFactory | None = None) -> None:
        self._factory = factory or session_factory
        self.session: AsyncSession | None = None

    async def __aenter__(self) -> UnitOfWork:
        self.session = self._factory()
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        assert self.session is not None
        if exc is None:
            await self.session.commit()
        else:
            await self.session.rollback()
        await self.session.close()
        self.session = None

    async def commit(self) -> None:
        assert self.session is not None
        await self.session.commit()

    async def rollback(self) -> None:
        assert self.session is not None
        await self.session.rollback()


@asynccontextmanager
async def unit_of_work(factory: SessionFactory | None = None) -> AsyncGenerator[UnitOfWork]:
    """Commit-on-success / rollback-on-error context manager."""
    async with UnitOfWork(factory) as uow:
        yield uow
