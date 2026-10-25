import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academics.models import (
    AcademicGroup,
    CourseOffering,
    Faculty,
    ImportKind,
    Semester,
    SemesterTerm,
    Subject,
)
from app.modules.academics.tests.conftest import SEED_DIR, Upload
from app.modules.announcements.models import Announcement, AnnouncementRecipient
from app.modules.announcements.service import AnnouncementService, still_addressed
from app.modules.audit.models import AuditLog
from app.modules.notifications.models import Notification, NotificationDelivery
from app.modules.users.models import User
from tests.support import FakeJobs, TokenFactory

Seed = Callable[..., Awaitable[None]]
Headers = dict[str, str]


def person(tokens: TokenFactory, email: str, roles: list[str], given: str, family: str) -> Headers:
    token = tokens.issue(
        str(uuid.uuid4()), roles, given_name=given, family_name=family, email=email
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def aysel(tokens: TokenFactory) -> Headers:
    return person(tokens, "aysel.mammadova@smartazmiu.test", ["student"], "Aysel", "Məmmədova")


@pytest.fixture
def nigar(tokens: TokenFactory) -> Headers:
    return person(tokens, "nigar.ismayilova@smartazmiu.test", ["student"], "Nigar", "İsmayılova")


async def group_id(db: AsyncSession, code: str) -> str:
    return str(await db.scalar(select(AcademicGroup.id).where(AcademicGroup.code == code)))


async def publish(
    client: AsyncClient,
    headers: Headers,
    audience: dict[str, Any],
    *,
    title: str = "Qış imtahan sessiyasının cədvəli dərc olundu",
    key: str | None = None,
    expected: int = 201,
    **extra: Any,
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/announcements",
        json={
            "title": title,
            "body": "Cədvəl dekanlığın lövhəsində və saytda.",
            "audience": audience,
            **extra,
        },
        headers={**headers, **({"Idempotency-Key": key} if key else {})},
    )
    assert response.status_code == expected, response.text
    body: dict[str, Any] = response.json()
    return body


async def recipients(db: AsyncSession, announcement_id: str) -> set[str]:
    rows = await db.scalars(
        select(User.email)
        .join(AnnouncementRecipient, AnnouncementRecipient.user_id == User.id)
        .where(AnnouncementRecipient.announcement_id == uuid.UUID(announcement_id))
    )
    return {email for email in rows if email}


async def test_group_announcement_reaches_the_group_and_its_curator_once(
    client: AsyncClient,
    db: AsyncSession,
    seed: Seed,
    staff_headers: Headers,
    aysel: Headers,
    nigar: Headers,
    jobs: FakeJobs,
) -> None:
    await seed()
    target = await group_id(db, "765a2")
    first = await publish(client, staff_headers, {"type": "group", "target_id": target}, key="k-1")
    assert first["audience"] == {
        "type": "group",
        "target_id": target,
        "label": "765a2",
        "detail": "İqtisadiyyat",
    }
    reached = await recipients(db, first["id"])
    assert len(reached) == 22 + 1  # the group's students and its curator
    assert "leyla.hasanova@smartazmiu.test" in reached
    assert "nigar.ismayilova@smartazmiu.test" not in reached
    assert await db.scalar(select(func.count()).select_from(Notification)) == 23
    # Announcements default to push and e-mail: both are queued, and the worker is woken once.
    assert await db.scalar(select(func.count()).select_from(NotificationDelivery)) == 46
    assert jobs.dispatches == 1

    # A retried request (same Idempotency-Key) returns the first announcement and notifies nobody again.
    again = await publish(client, staff_headers, {"type": "group", "target_id": target}, key="k-1")
    assert again["id"] == first["id"]
    assert await db.scalar(select(func.count()).select_from(Notification)) == 23
    assert jobs.dispatches == 1
    audit = await db.scalar(select(AuditLog).where(AuditLog.action == "announcement.published"))
    assert audit is not None
    assert audit.details == {"audience": "group"}

    mine = (await client.get("/api/v1/announcements", headers=aysel)).json()
    assert [item["id"] for item in mine["items"]] == [first["id"]]
    assert (await client.get("/api/v1/announcements", headers=nigar)).json()["items"] == []
    hidden = await client.get(f"/api/v1/announcements/{first['id']}", headers=nigar)
    assert hidden.status_code == 404
    shown = await client.get(f"/api/v1/announcements/{first['id']}", headers=aysel)
    assert shown.json()["body"] == "Cədvəl dekanlığın lövhəsində və saytda."


async def test_faculty_specialty_university_and_offering_audiences(
    client: AsyncClient, db: AsyncSession, seed: Seed, staff_headers: Headers
) -> None:
    await seed()
    faculty = str(await db.scalar(select(Faculty.id).where(Faculty.code == "TIQ")))
    by_faculty = await publish(client, staff_headers, {"type": "faculty", "target_id": faculty})
    reached = await recipients(db, by_faculty["id"])
    # The three economics groups (8 + 18 + 22 students; one is inactive) and their curators.
    students = await db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.academic_group_id.is_not(None), User.status == "active")
    )
    assert len(reached) == (students or 0) + 3

    university = await publish(client, staff_headers, {"type": "university"})
    everyone = await db.scalar(
        select(func.count()).select_from(User).where(User.status == "active")
    )
    assert len(await recipients(db, university["id"])) == everyone

    offering = await db.scalar(
        select(CourseOffering.id)
        .join(Subject, Subject.id == CourseOffering.subject_id)
        .join(Semester, Semester.id == CourseOffering.semester_id)
        .where(
            Subject.code == "IQT-2101",
            Semester.year == 2026,
            Semester.term == SemesterTerm.FALL,
            CourseOffering.code == "765a2",
        )
    )
    course = await publish(
        client, staff_headers, {"type": "course_offering", "target_id": str(offering)}
    )
    assert course["audience"]["label"] == "Mikroiqtisadiyyat · 765a2"
    assert course["audience"]["detail"] == "2026 Payız"
    reached = await recipients(db, course["id"])
    # Enrolled students plus both teachers of the offering; the curator is not involved.
    assert {"shahla.agayeva@smartazmiu.test", "aysel.mammadova@smartazmiu.test"} <= reached
    assert "leyla.hasanova@smartazmiu.test" not in reached


async def test_people_who_join_the_audience_later_receive_active_announcements(
    client: AsyncClient,
    db: AsyncSession,
    seed: Seed,
    upload: Upload,
    staff_headers: Headers,
    nigar: Headers,
    jobs: FakeJobs,
) -> None:
    await seed()
    target = await group_id(db, "765a2")
    current = await publish(client, staff_headers, {"type": "group", "target_id": target})
    expired = await publish(
        client,
        staff_headers,
        {"type": "group", "target_id": target},
        title="Köhnə elan",
        expires_at=(datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
    )

    # Nigar transfers from 765a1 to 765a2 (§13.1); the import wakes the audience sync.
    students = (SEED_DIR / "students.csv").read_text(encoding="utf-8")
    header, *rows = students.splitlines()
    nigar_row = next(row for row in rows if row.startswith("25765101,"))
    syncs = jobs.syncs
    await upload(
        ImportKind.STUDENTS, f"{header}\n{nigar_row.replace(',765a1,', ',765a2,')}\n", apply=True
    )
    assert jobs.syncs == syncs + 1

    # The second announcement expires before the sync runs: it is no longer active, so nobody new gets it.
    stale = await db.get(Announcement, uuid.UUID(expired["id"]))
    assert stale is not None
    stale.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db.commit()

    service = AnnouncementService(db)
    assert await service.sync_recipients() == 1
    assert "nigar.ismayilova@smartazmiu.test" in await recipients(db, current["id"])
    assert "nigar.ismayilova@smartazmiu.test" not in await recipients(db, expired["id"])
    # Idempotent: a second run (cron tick, retried job) adds nobody and notifies nobody.
    assert await service.sync_recipients() == 0
    nigar_id = await db.scalar(
        select(User.id).where(User.email == "nigar.ismayilova@smartazmiu.test")
    )
    assert (
        await db.scalar(
            select(func.count()).select_from(Notification).where(Notification.user_id == nigar_id)
        )
        == 1
    )
    mine = (await client.get("/api/v1/announcements", headers=nigar)).json()
    assert [item["id"] for item in mine["items"]] == [current["id"]]


async def test_delivery_time_check_follows_membership_and_status(
    client: AsyncClient, db: AsyncSession, seed: Seed, upload: Upload, staff_headers: Headers
) -> None:
    await seed()
    target = await group_id(db, "765a2")
    item = await publish(client, staff_headers, {"type": "group", "target_id": target})
    announcement_id = uuid.UUID(item["id"])
    aysel_id = await db.scalar(
        select(User.id).where(User.email == "aysel.mammadova@smartazmiu.test")
    )
    assert aysel_id is not None
    assert await still_addressed(db, announcement_id, aysel_id)

    # Transferred out before the worker sent the push: not delivered any more (§5.6).
    students = (SEED_DIR / "students.csv").read_text(encoding="utf-8")
    header, *rows = students.splitlines()
    row = next(row for row in rows if row.startswith("25765201,"))
    await upload(
        ImportKind.STUDENTS, f"{header}\n{row.replace(',765a2,', ',765a1,')}\n", apply=True
    )
    db.expire_all()
    assert not await still_addressed(db, announcement_id, aysel_id)

    await client.post(f"/api/v1/announcements/{item['id']}/archive", headers=staff_headers)
    leyla = await db.scalar(select(User.id).where(User.email == "leyla.hasanova@smartazmiu.test"))
    assert leyla is not None
    assert not await still_addressed(db, announcement_id, leyla)
    assert not await still_addressed(db, uuid.uuid4(), leyla)


async def test_editing_archiving_and_versions(
    client: AsyncClient, db: AsyncSession, seed: Seed, staff_headers: Headers, aysel: Headers
) -> None:
    await seed()
    target = await group_id(db, "765a2")
    item = await publish(client, staff_headers, {"type": "group", "target_id": target})
    path = f"/api/v1/announcements/{item['id']}"
    notified = await db.scalar(select(func.count()).select_from(Notification))

    edit = {"version": 1, "title": "Qış sessiyasının cədvəli (yenilənib)", "body": "Yeni otaqlar."}
    updated = await client.patch(path, json=edit, headers=staff_headers)
    assert updated.status_code == 200
    assert (updated.json()["version"], updated.json()["title"]) == (2, edit["title"])
    stale = await client.patch(path, json=edit, headers=staff_headers)
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "announcements.version_conflict"
    # Corrections notify nobody again.
    assert await db.scalar(select(func.count()).select_from(Notification)) == notified

    archived = await client.post(f"{path}/archive", headers=staff_headers)
    assert archived.json()["status"] == "archived"
    again = await client.post(f"{path}/archive", headers=staff_headers)
    assert again.json()["version"] == archived.json()["version"]
    assert (await client.get(path, headers=aysel)).status_code == 404
    assert (await client.get("/api/v1/announcements", headers=aysel)).json()["items"] == []
    # Staff still see it in their table and on its page.
    assert (await client.get(path, headers=staff_headers)).json()["status"] == "archived"
    locked = await client.patch(path, json={**edit, "version": 3}, headers=staff_headers)
    assert locked.json()["error"]["code"] == "announcements.archived"

    managed = (await client.get("/api/v1/announcements/managed", headers=staff_headers)).json()
    assert managed["total"] == 1
    assert managed["items"][0]["recipients"] == 23


async def test_only_staff_publish_and_input_is_validated(
    client: AsyncClient, db: AsyncSession, seed: Seed, staff_headers: Headers, aysel: Headers
) -> None:
    await seed(ImportKind.GROUPS)
    target = await group_id(db, "765a2")
    denied = await client.post(
        "/api/v1/announcements",
        json={"title": "Elan", "body": "Mətn", "audience": {"type": "university"}},
        headers=aysel,
    )
    assert denied.status_code == 403
    for path in ("/api/v1/announcements/managed", "/api/v1/audiences/options?type=group"):
        assert (await client.get(path, headers=aysel)).status_code == 403

    for audience in (
        {"type": "group", "target_id": str(uuid.uuid4())},
        {"type": "group", "target_id": "765a2"},
        {"type": "group"},
        {"type": "university", "target_id": target},
        {"type": "faculty", "target_id": target},
    ):
        body = await publish(client, staff_headers, audience, expected=422)
        assert body["error"]["code"] == "audience.invalid", audience
    past = await publish(
        client,
        staff_headers,
        {"type": "university"},
        expected=422,
        expires_at="2026-01-01T10:00:00+04:00",
    )
    assert past["error"]["code"] == "announcements.expiry_in_past"
    blank = await publish(client, staff_headers, {"type": "university"}, title="   ", expected=422)
    assert blank["error"]["code"] == "request.validation_failed"
    naive = await publish(
        client, staff_headers, {"type": "university"}, expected=422, expires_at="2027-01-01T10:00"
    )
    assert naive["error"]["code"] == "request.validation_failed"


async def test_audience_options_for_the_picker(
    client: AsyncClient, seed: Seed, staff_headers: Headers
) -> None:
    await seed()

    async def options(kind: str, q: str = "") -> list[dict[str, str]]:
        response = await client.get(
            "/api/v1/audiences/options", params={"type": kind, "q": q}, headers=staff_headers
        )
        assert response.status_code == 200
        items: list[dict[str, str]] = response.json()["items"]
        return items

    # Typed without Azerbaijani letters, as staff often do (§13.1).
    assert [o["label"] for o in await options("faculty", "iqtisad")] == [
        "Tikinti iqtisadiyyatı fakültəsi"
    ]
    assert [o["label"] for o in await options("specialty", "6004004")] == ["İqtisadiyyat (6004004)"]
    assert [o["label"] for o in await options("group", "765")] == ["765a1", "765a2"]
    # Only offerings that are running or still to come; past semesters are not offered.
    offerings = await options("course_offering", "mikro")
    assert offerings
    assert {o["detail"] for o in offerings} <= {"2026 Payız", "2027 Yaz"}
    assert await options("group", "%") == []
