import json
import uuid
from typing import Any

import pytest
import sentry_sdk
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import openapi
from app.core import observability
from app.core.config import Settings, get_settings
from app.core.db import Database
from app.core.i18n import error_message, negotiate_language
from app.core.ids import uuid7
from app.core.logging import REDACTED, redact_sensitive
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


def test_uuid7_is_versioned_and_time_ordered() -> None:
    first, second = uuid7(), uuid7()
    assert first.version == 7
    assert first.variant == uuid.RFC_4122
    assert first.int >> 80 <= second.int >> 80


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, "az"),
        ("", "az"),
        ("en-US,en;q=0.9", "en"),
        ("ru-RU,ru;q=0.9", "az"),
        ("ru;q=1, en;q=0.4, az;q=0.8", "az"),
        ("en;q=0, az;q=0.1", "az"),
        ("en;q=abc", "az"),
        ("tr, en", "en"),
    ],
)
def test_negotiate_language(header: str | None, expected: str) -> None:
    assert negotiate_language(header) == expected


def test_unknown_error_code_falls_back_to_generic_message() -> None:
    assert error_message("chat.something_new", "az") == error_message("request.failed", "az")


def test_log_redaction_covers_credentials_and_contact_data() -> None:
    event = redact_sensitive(
        None, "info", {"event": "x", "Authorization": "Bearer abc", "email": "a@b.az", "path": "/"}
    )
    assert event == {"event": "x", "Authorization": REDACTED, "email": REDACTED, "path": "/"}


def test_sentry_events_are_scrubbed() -> None:
    event: Any = {
        "request": {
            "headers": {"Authorization": "Bearer abc", "Cookie": "sa_session=1", "Accept": "*/*"},
            "cookies": {"sa_session": "1"},
            "data": {"password": "x"},
            "query_string": "ticket=abc",
        },
        "user": {"id": "0190", "email": "a@b.az", "ip_address": "10.0.0.1"},
    }
    scrubbed: Any = observability.scrub_event(event, {})
    assert scrubbed["request"] == {"headers": {"Accept": "*/*"}}
    assert scrubbed["user"] == {"id": "0190"}
    assert observability.scrub_event({"user": {"email": "a@b.az"}}, {}) == {"user": {}}


def test_sentry_is_initialised_only_with_a_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: captured.update(kwargs))

    assert observability.init_sentry(Settings(sentry_dsn=None)) is False
    assert captured == {}
    assert observability.init_sentry(Settings(sentry_dsn="https://key@sentry.test/1")) is True
    assert captured["send_default_pii"] is False
    assert captured["before_send"] is observability.scrub_event


def test_openapi_export_lists_versioned_routes(capsys: pytest.CaptureFixture[str]) -> None:
    openapi.main()
    schema = json.loads(capsys.readouterr().out)
    assert "/api/v1/me" in schema["paths"]
    assert "/healthz" not in schema["paths"]


async def test_names_sort_with_azerbaijani_collation(db: AsyncSession) -> None:
    names = [
        "Çingiz",
        "Cavid",
        "İlkin",
        "Ismayıl",
        "Əli",
        "Elvin",
        "Xədicə",
        "Həsən",
        "Qəmər",
        "Orxan",
    ]
    rows = await db.execute(
        text('SELECT n FROM unnest(CAST(:names AS text[])) AS n ORDER BY n COLLATE "az-x-icu"'),
        {"names": names},
    )
    assert [row[0] for row in rows] == [
        "Cavid",
        "Çingiz",
        "Elvin",
        "Əli",
        "Həsən",
        "Xədicə",
        "Ismayıl",
        "İlkin",
        "Qəmər",
        "Orxan",
    ]
