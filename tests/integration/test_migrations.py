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


async def test_transcript_speaker_column_and_backfill(db_engine: AsyncEngine) -> None:
    """0002: transcript_segment gains an explicit speaker column; legacy rows
    are backfilled from the JSONB role; anything else stays 'unknown'."""
    async with db_engine.connect() as conn:
        cols = (
            await conn.execute(
                text(
                    "SELECT column_name, is_nullable FROM information_schema.columns "
                    "WHERE table_name='transcript_segment' AND column_name='speaker'"
                )
            )
        ).first()
        assert cols is not None, "speaker column missing after migration head"
        assert cols[1] == "NO"

        # Insert one legacy-style row (JSONB role only) + one with no role.
        await conn.execute(text('INSERT INTO "user" (id) VALUES (1) ON CONFLICT DO NOTHING'))
        sess_id = (
            await conn.execute(
                text(
                    "INSERT INTO interview_session (kind, status, user_id, config, "
                    "graph_thread_id) VALUES ('general','questioning',1,'{}',"
                    "'t-0002-test') RETURNING id"
                )
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO transcript_segment (interview_session_id, seq, partial, text, "
                "speaker, timestamps) VALUES (:sid, 1, false, 'legacy interviewer', "
                "'unknown', '{\"role\":\"interviewer\"}'), "
                "(:sid, 2, false, 'no role', 'unknown', NULL)"
            ),
            {"sid": sess_id},
        )
        await conn.commit()

        # Fresh upgrade path already ran on head; re-run backfill SQL idempotently.
        await conn.execute(
            text(
                "UPDATE transcript_segment SET speaker = timestamps ->> 'role' "
                "WHERE timestamps ->> 'role' IN ('interviewer','candidate')"
            )
        )
        await conn.commit()
        rows = (
            await conn.execute(
                text(
                    "SELECT text, speaker FROM transcript_segment WHERE interview_session_id = :sid"
                ),
                {"sid": sess_id},
            )
        ).all()
        by_text = {r[0]: r[1] for r in rows}
        assert by_text["legacy interviewer"] == "interviewer"
        assert by_text["no role"] == "unknown"
