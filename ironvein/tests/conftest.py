"""Интеграционные тесты на настоящем PostgreSQL. Схема создаётся миграциями Alembic.

TEST_DATABASE_URL по умолчанию указывает на локальную БД ironvein_test (её содержимое уничтожается).
"""

import os

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from alembic import command
from ironvein.config import get_settings
from ironvein.services import clock, users
from ironvein.services.world import ensure_world

TEST_DB = os.environ.get("TEST_DATABASE_URL", "postgresql+asyncpg://postgres@127.0.0.1:5432/ironvein_test")
HERE = os.path.dirname(os.path.dirname(__file__))


def _migrate():
    cfg = Config(os.path.join(HERE, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(HERE, "alembic"))
    cfg.attributes["url"] = TEST_DB
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
async def engine():
    import asyncio
    eng = create_async_engine(TEST_DB, pool_size=20, max_overflow=20)
    async with eng.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    await asyncio.to_thread(_migrate)
    yield eng
    await eng.dispose()


@pytest.fixture
async def sm(engine):
    """Чистый мир для каждого теста."""
    clock.reset()
    get_settings.cache_clear()
    os.environ.setdefault("ENVIRONMENT", "development")
    async with engine.begin() as conn:
        tables = (await conn.execute(text(
            "select string_agg(quote_ident(tablename), ',') from pg_tables "
            "where schemaname='public' and tablename <> 'alembic_version'"))).scalar()
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s, s.begin():
        await ensure_world(s)
    yield maker
    clock.reset()


async def make_user(sm, tg_id: int, name: str = "Игрок"):
    async with sm() as s, s.begin():
        u, _ = await users.get_or_register(s, tg_id, name, f"user{tg_id}")
        return u.id
