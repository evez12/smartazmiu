from sqlalchemy import text

from app.core.config import Settings, get_settings
from app.core.db import Database
from app.modules import load_models


def test_production_flag_follows_app_env() -> None:
    assert Settings(app_env="production").is_production
    assert not Settings(app_env="development").is_production


async def test_database_session_executes_queries() -> None:
    database = Database(str(get_settings().database_url))
    try:
        async for session in database.session():
            assert (await session.execute(text("SELECT 1"))).scalar_one() == 1
    finally:
        await database.dispose()


def test_load_models_is_idempotent() -> None:
    load_models()
    load_models()
