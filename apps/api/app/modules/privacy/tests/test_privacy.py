import base64
import io
import uuid
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ratelimit import RateLimit
from app.modules.academics.models import Enrollment, EnrollmentStatus
from app.modules.academics.seed import seed
from app.modules.audit.models import AuditLog
from app.modules.privacy import router as privacy_router
from app.modules.privacy.service import PRIVACY_NOTICE_VERSION
from app.modules.users.models import User
from tests.support import MemoryStorage, TokenFactory

SEED_DIR = Path(__file__).resolve().parents[6] / "infra" / "seed" / "academics"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def aysel(tokens: TokenFactory) -> dict[str, str]:
    return bearer(tokens.issue(str(uuid.uuid4()), ["student"], family_name="Məmmədova"))


async def consents(client: AsyncClient, headers: dict[str, str]) -> dict[str, Any]:
    response = await client.get("/api/v1/me/consents", headers=headers)
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


async def test_privacy_notice_is_acknowledged_once_per_version(
    client: AsyncClient, aysel: dict[str, str], db: AsyncSession
) -> None:
    before = await consents(client, aysel)
    assert before == {
        "notice_version": PRIVACY_NOTICE_VERSION,
        "notice_acknowledged_at": None,
        "history": [],
    }

    url = "/api/v1/me/consents/privacy-notice"
    first = await client.post(url, headers=aysel, json={"version": PRIVACY_NOTICE_VERSION})
    second = await client.post(url, headers=aysel, json={"version": PRIVACY_NOTICE_VERSION})
    outdated = await client.post(url, headers=aysel, json={"version": "2025-01"})

    assert first.status_code == second.status_code == 200
    assert first.json()["notice_acknowledged_at"] == second.json()["notice_acknowledged_at"]
    assert [entry["purpose"] for entry in second.json()["history"]] == ["privacy_notice"]
    assert outdated.status_code == 409
    assert outdated.json()["error"]["code"] == "privacy.notice_outdated"
    assert outdated.json()["error"]["details"] == {"version": PRIVACY_NOTICE_VERSION}


async def test_consent_history_is_newest_first(client: AsyncClient, aysel: dict[str, str]) -> None:
    for version, visibility in ((1, "everyone"), (2, "hidden")):
        await client.patch(
            "/api/v1/me/profile",
            headers=aysel,
            json={"version": version, "contact_visibility": visibility},
        )
    history = (await consents(client, aysel))["history"]
    assert [(entry["purpose"], entry["granted"]) for entry in history] == [
        ("contact_sharing", False),
        ("contact_sharing", True),
    ]


async def test_export_contains_own_data_only(
    client: AsyncClient, tokens: TokenFactory, storage: MemoryStorage, db: AsyncSession
) -> None:
    assert await seed(SEED_DIR) == 0
    headers = bearer(
        tokens.issue(
            str(uuid.uuid4()),
            ["student"],
            given_name="Aysel",
            family_name="Məmmədova",
            email="aysel.mammadova@smartazmiu.test",
        )
    )
    aysel = (await client.get("/api/v1/me", headers=headers)).json()["id"]
    # A graded past result, to check the user's own grades are part of their export.
    await db.execute(
        update(Enrollment)
        .where(
            Enrollment.user_id == uuid.UUID(aysel), Enrollment.status == EnrollmentStatus.COMPLETED
        )
        .values(grade=87)
    )
    await db.commit()
    image = io.BytesIO()
    Image.new("RGB", (32, 32), (31, 58, 95)).save(image, "PNG")
    await client.put(
        "/api/v1/me/photo",
        headers=headers,
        files={"file": ("aysel.png", image.getvalue(), "image/png")},
    )

    response = await client.get("/api/v1/me/export", headers=headers)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json; charset=utf-8"
    assert response.headers["content-disposition"].startswith(
        'attachment; filename="smartazmiu-melumatlarim-'
    )
    assert response.headers["cache-control"] == "no-store"
    document = response.json()
    assert document["account"]["email"] == "aysel.mammadova@smartazmiu.test"
    assert document["account"]["university_id"] == "25765201"
    assert document["roles"] == ["student"]
    assert document["academic"]["group"]["code"] == "765a2"
    enrollments = document["academic"]["enrollments"]
    assert len(enrollments) == 15
    assert {e["grade"] for e in enrollments if e["status"] == "completed"} == {87}
    assert base64.b64decode(document["profile"]["photo"]["base64"])[:4] == b"RIFF"
    assert [c["purpose"] for c in document["consents"]] == ["profile_photo"]
    assert {entry["action"] for entry in document["audit"]} >= {
        "user.account_linked",
        "user.roles_synced",
    }
    # Classmates and teachers appear nowhere: not their e-mails, IDs or names.
    text = response.text
    for other in ("ramin.aliyev", "25765202", "Şəhla", "leyla.hasanova"):
        assert other not in text

    exported = await db.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.action == "user.data_exported", AuditLog.actor_id == uuid.UUID(aysel))
    )
    assert exported == 1


async def test_teacher_export_lists_teaching(
    client: AsyncClient, tokens: TokenFactory, db: AsyncSession
) -> None:
    assert await seed(SEED_DIR) == 0
    headers = bearer(
        tokens.issue(
            str(uuid.uuid4()),
            ["teacher"],
            given_name="Leyla",
            family_name="Həsənova",
            email="leyla.hasanova@smartazmiu.test",
        )
    )
    document = (await client.get("/api/v1/me/export", headers=headers)).json()
    assert document["academic"]["group"] is None
    assert document["academic"]["enrollments"] == []
    teaching = document["academic"]["teaching"]
    assert sorted(
        (t["subject"]["code"], t["semester"]["year"], t["offering_code"]) for t in teaching
    ) == [("IQT-2102", 2025, "764a1"), ("IQT-2102", 2026, "765a1"), ("IQT-2102", 2026, "765a2")]


async def test_export_is_rate_limited_and_needs_storage_for_photos(
    client: AsyncClient,
    aysel: dict[str, str],
    storage: MemoryStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert (await client.get("/api/v1/me/export")).status_code == 401

    image = io.BytesIO()
    Image.new("RGB", (8, 8)).save(image, "PNG")
    await client.put(
        "/api/v1/me/photo", headers=aysel, files={"file": ("a.png", image.getvalue(), "image/png")}
    )
    storage.available = False
    unavailable = await client.get("/api/v1/me/export", headers=aysel)
    assert unavailable.status_code == 503

    storage.available = True
    monkeypatch.setattr(privacy_router, "EXPORTS", RateLimit(f"t{uuid.uuid4()}", 1, 60))
    assert (await client.get("/api/v1/me/export", headers=aysel)).status_code == 200
    assert (await client.get("/api/v1/me/export", headers=aysel)).status_code == 429


async def test_export_of_a_missing_user_is_not_found(db: AsyncSession) -> None:
    from app.modules.privacy.export import DataExportService

    with pytest.raises(Exception, match=r"request\.not_found"):
        await DataExportService(db, MemoryStorage()).export(uuid.uuid4())
    assert await db.scalar(select(func.count()).select_from(User)) == 0
