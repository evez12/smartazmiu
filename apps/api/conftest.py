import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.db import create_engine
from app.core.security import TokenVerifier
from app.main import create_app
from tests.support import TEST_AUDIENCE, TEST_ISSUER, MemoryStorage, TokenFactory

API_ROOT = Path(__file__).parent


@pytest.fixture(scope="session")
def settings() -> Settings:
    settings = Settings(app_env="test", oidc_issuer=TEST_ISSUER, oidc_audience=TEST_AUDIENCE)
    database = settings.database_url.path or ""
    # The suite truncates tables; refuse to run against anything but a dedicated test database.
    if not database.endswith("_test"):
        pytest.exit(f"DATABASE_URL must point at a *_test database, got {database!r}", returncode=2)
    return settings


def alembic_config(settings: Settings) -> Config:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.attributes["database_url"] = str(settings.database_url)
    config.attributes["configure_logging"] = False
    return config


@pytest_asyncio.fixture(scope="session")
async def migrated(settings: Settings) -> None:
    config = alembic_config(settings)
    # Alembic's env.py runs its own event loop, so it is driven from a worker thread.
    await asyncio.to_thread(command.downgrade, config, "base")
    await asyncio.to_thread(command.upgrade, config, "head")


@pytest_asyncio.fixture(scope="session")
async def engine(settings: Settings, migrated: None) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(str(settings.database_url))
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def seeded_permissions(engine: AsyncEngine) -> frozenset[str]:
    """Permission codes created by migrations; tests may add their own, which are removed afterwards."""
    async with engine.connect() as connection:
        return frozenset(await connection.scalars(text("SELECT code FROM permissions")))


@pytest_asyncio.fixture
async def db(
    engine: AsyncEngine, seeded_permissions: frozenset[str]
) -> AsyncIterator[AsyncSession]:
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        yield session
    async with engine.begin() as connection:
        # CASCADE reaches every table that references these roots (academic data, imports, audit log).
        await connection.execute(text("TRUNCATE users, faculties, semesters CASCADE"))
        await connection.execute(
            text("DELETE FROM permissions WHERE code <> ALL(:seeded)"),
            {"seeded": list(seeded_permissions)},
        )


@pytest.fixture(scope="session")
def tokens() -> TokenFactory:
    return TokenFactory()


@pytest.fixture
def storage() -> MemoryStorage:
    return MemoryStorage()


@pytest_asyncio.fixture
async def app(
    settings: Settings, tokens: TokenFactory, db: AsyncSession, storage: MemoryStorage
) -> AsyncIterator[FastAPI]:
    """The API wired to the test database, with Keycloak and object storage replaced by doubles."""
    application = create_app(settings)
    async with LifespanManager(application):
        application.state.token_verifier = TokenVerifier(
            issuer=TEST_ISSUER, audience=TEST_AUDIENCE, keys=tokens.key_source()
        )
        application.state.storage = storage
        yield application


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
