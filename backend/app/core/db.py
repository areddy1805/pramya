"""Async database engine, session factory, and FastAPI dependency."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings, get_settings
from app.models.base import Base


def create_engine(settings: Settings | None = None) -> AsyncEngine:
    """Create the async engine from settings (tests can inject a URL)."""
    if settings is None:
        settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=settings.db_echo,
        pool_pre_ping=True,
    )


engine: AsyncEngine = create_engine()

SessionFactory = async_sessionmaker[AsyncSession]
session_factory: SessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a scoped async session."""
    async with session_factory() as session:
        yield session


async def init_models(settings: Settings | None = None) -> None:
    """Create all tables (used by tests / demo; migrations are authoritative)."""
    eng = create_engine(settings)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await eng.dispose()
