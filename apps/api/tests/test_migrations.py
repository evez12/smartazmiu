import asyncio

from alembic import command
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from conftest import alembic_config

APP_TABLES = {"users", "roles", "permissions", "role_permissions", "user_roles"}


async def table_names(engine: AsyncEngine) -> set[str]:
    async with engine.connect() as connection:
        return set(await connection.run_sync(lambda sync: inspect(sync).get_table_names()))


async def test_migrations_are_reversible(settings: Settings, engine: AsyncEngine) -> None:
    config = alembic_config(settings)

    await asyncio.to_thread(command.downgrade, config, "base")
    assert await table_names(engine) & APP_TABLES == set()
    async with engine.connect() as connection:
        enum_count = await connection.scalar(
            text("SELECT count(*) FROM pg_type WHERE typname = 'user_status'")
        )
    assert enum_count == 0

    await asyncio.to_thread(command.upgrade, config, "head")
    assert await table_names(engine) >= APP_TABLES
    async with engine.connect() as connection:
        roles = await connection.scalars(text("SELECT code FROM roles ORDER BY code"))
        assert list(roles) == ["admin", "guest", "moderator", "staff", "student", "teacher"]
