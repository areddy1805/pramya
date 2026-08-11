"""Integration test fixtures: real pgvector Postgres + alembic migrations.

Requires a reachable PostgreSQL server with pgvector (docker compose `db`
or CI service). The test database is created/dropped per session; schema is
built by running the real Alembic migrations (never create_all) so migration
and model parity is exercised.

Alembic's env.py calls `asyncio.run`, so migration commands must run from a
context without a live event loop: DB prep lives in a sync fixture, and
async tests shell out via `asyncio.to_thread`.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from tests.integration.helpers import TEST_DATABASE_URL, create_database, drop_database, run_upgrade

from app.core.db import SessionFactory


@pytest.fixture(scope="session")
def prepared_database() -> Iterator[None]:
    """Create test DB + run alembic upgrade head (no live event loop)."""
    asyncio.run(create_database(TEST_DATABASE_URL))
    run_upgrade(TEST_DATABASE_URL)
    yield
    asyncio.run(drop_database(TEST_DATABASE_URL))


@pytest.fixture
def session_factory(db_engine: AsyncEngine) -> SessionFactory:
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def db_engine(prepared_database: None) -> AsyncIterator[AsyncEngine]:
    """Function-scoped async engine: pytest-asyncio loops are function-scoped,
    so a session-scoped async engine would be bound to a dead loop."""
    engine = create_async_engine(TEST_DATABASE_URL)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def db_session(session_factory: SessionFactory) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session
