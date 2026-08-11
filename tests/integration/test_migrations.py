"""Integration tests: alembic migration up/down + schema assertions."""

from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from tests.integration.helpers import (
    TEST_DATABASE_URL,
    alembic_config,
    create_database,
    drop_database,
)

from alembic import command

EXPECTED_TABLES = {
    "user",
    "candidate_profile",
    "document",
    "document_chunk",
    "role",
    "competency",
    "candidate_competency",
    "evidence",
    "interview_session",
    "interview_turn",
    "audio_segment",
    "transcript_segment",
    "question",
    "answer",
    "evaluation",
    "preparation_item",
    "practice_session",
    "story",
    "readiness_snapshot",
    "interview_debrief",
    "evaluation_version",
    "idempotency_record",
}


async def test_migration_up_creates_all_tables(db_engine: AsyncEngine) -> None:
    async with db_engine.connect() as conn:
        rows = (
            (await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'")))
            .scalars()
            .all()
        )
        assert set(rows) >= EXPECTED_TABLES, set(EXPECTED_TABLES) - set(rows)


async def test_vector_extension_installed(db_engine: AsyncEngine) -> None:
    async with db_engine.connect() as conn:
        ext = await conn.execute(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
        assert ext.scalar(), "pgvector extension missing"


async def test_document_chunk_indexes_exist(db_engine: AsyncEngine) -> None:
    async with db_engine.connect() as conn:
        rows = (
            (
                await conn.execute(
                    text("SELECT indexname FROM pg_indexes WHERE tablename='document_chunk'")
                )
            )
            .scalars()
            .all()
        )
    assert "ix_document_chunk_embedding_hnsw" in rows, rows
    assert "ix_document_chunk_fts_gin" in rows, rows


async def test_fts_generated_column(db_engine: AsyncEngine) -> None:
    async with db_engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT is_generated, generation_expression FROM information_schema.columns "
                    "WHERE table_name='document_chunk' AND column_name='fts'"
                )
            )
        ).first()
    assert row is not None and row[0] == "ALWAYS"
    assert "to_tsvector" in row[1]


async def test_migration_downgrade_removes_everything() -> None:
    """Downgrade base on a scratch DB, assert empty, re-upgrade."""
    scratch = TEST_DATABASE_URL.rsplit("/", 1)[0] + "/pramya_scratch"
    await create_database(scratch)
    cfg = alembic_config(scratch)
    # alembic env.py calls asyncio.run -> must run off the live loop
    await asyncio.to_thread(command.upgrade, cfg, "head")
    await asyncio.to_thread(command.downgrade, cfg, "base")

    engine2 = create_async_engine(scratch)
    async with engine2.connect() as conn:
        rows = (
            (await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'")))
            .scalars()
            .all()
        )
        assert rows == ["alembic_version"], rows
    await engine2.dispose()
    await drop_database(scratch)
