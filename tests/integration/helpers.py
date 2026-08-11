"""Shared integration helpers (imported from test modules in same dir)."""

from __future__ import annotations

import os

from alembic.config import Config as AlembicConfig
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://pramya:pramya@localhost:5432/pramya_test"
)
SERVER_URL = TEST_DATABASE_URL.rsplit("/", 1)[0] + "/postgres"
TEST_DB_NAME = TEST_DATABASE_URL.rsplit("/", 1)[1]


def alembic_config(database_url: str) -> AlembicConfig:
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    cfg.set_main_option("script_location", "alembic")
    return cfg


def run_upgrade(database_url: str) -> None:
    command.upgrade(alembic_config(database_url), "head")


async def create_database(database_url: str) -> None:
    name = database_url.rsplit("/", 1)[1]
    server_url = database_url.rsplit("/", 1)[0] + "/postgres"
    engine = create_async_engine(server_url, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
        await conn.execute(text(f'CREATE DATABASE "{name}"'))
    await engine.dispose()


async def drop_database(database_url: str) -> None:
    name = database_url.rsplit("/", 1)[1]
    server_url = database_url.rsplit("/", 1)[0] + "/postgres"
    engine = create_async_engine(server_url, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
    await engine.dispose()
