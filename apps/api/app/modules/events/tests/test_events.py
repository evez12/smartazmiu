import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academics.models import AcademicGroup, Faculty, ImportKind
from app.modules.academics.tests.conftest import SEED_DIR, Upload
from app.modules.audit.models import AuditLog
from app.modules.events import tickets
from app.modules.events.models import Event
from app.modules.events.service import EventService, still_relevant
from app.modules.notifications.models import (
    DeliveryChannel,
    Notification,
    NotificationDelivery,
    NotificationKind,
)
from app.modules.users.models import User
from tests.support import FakeJobs, TokenFactory

Seed = Callable[..., Awaitable[None]]
Headers = dict[str, str]
SECRET = "test-ticket-secret"


def person(tokens: TokenFactory, email: str, roles: list[str], given: str, family: str) -> Headers:
    token = tokens.issue(
        str(uuid.uuid4()), roles, given_name=given, family_name=family, email=email
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def aysel(tokens: TokenFactory) -> Headers:
    return person(tokens, "aysel.mammadova@smartazmiu.test", ["student"], "Aysel", "Məmmədova")


@pytest.fixture
def ramin(tokens: TokenFactory) -> Headers:
    return person(tokens, "ramin.aliyev@smartazmiu.test", ["student"], "Ramin", "Əliyev")


@pytest.fixture
def nigar(tokens: TokenFactory) -> Headers:
    return person(tokens, "nigar.ismayilova@smartazmiu.test", ["student"], "Nigar", "İsmayılova")


def soon(hours: float) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


async def group_audience(db: AsyncSession, code: str = "765a2") -> dict[str, Any]:
    group = await db.scalar(select(AcademicGroup.id).where(AcademicGroup.code == code))
    return {"type": "group", "target_id": str(group)}


async def publish(
    client: AsyncClient,
    headers: Headers,
    audience: dict[str, Any],
    *,
    expected: int = 201,
    key: str | None = None,
    **fields: Any,
) -> dict[str, Any]:
    body = {
        "title": "Memarlıq sərgisi: tələbə layihələri",
        "description": "Birinci kurs tələbələrinin layihələri nümayiş olunur.",
        "starts_at": soon(1),
        "ends_at": soon(3),
        "room_code": "1-305",
        "audience": audience,
        **fields,
    }
    response = await client.post(
        "/api/v1/events",
        json=body,
        headers={**headers, **({"Idempotency-Key": key} if key else {})},
    )
    assert response.status_code == expected, response.text
    result: dict[str, Any] = response.json()
    return result


async def rsvp(
    client: AsyncClient, headers: Headers, event_id: str, expected: int = 200
) -> dict[str, Any]:
    response = await client.put(f"/api/v1/events/{event_id}/registration", headers=headers)
    assert response.status_code == expected, response.text
    result: dict[str, Any] = response.json()
    return result


async def check_in(
    client: AsyncClient, headers: Headers, event_id: str, expected: int = 200, **body: str
) -> dict[str, Any]:
    response = await client.post(f"/api/v1/events/{event_id}/check-ins", json=body, headers=headers)
    assert response.status_code == expected, response.text
    result: dict[str, Any] = response.json()
    return result


async def kinds_for(db: AsyncSession, email: str) -> list[NotificationKind]:
    rows = await db.scalars(
        select(Notification.kind)
        .join(User, User.id == Notification.user_id)
        .where(User.email == email)
        .order_by(Notification.id)
    )
    return list(rows)


async def test_faculty_event_notifies_its_students_and_rsvp_gives_a_ticket(
    client: AsyncClient,
    db: AsyncSession,
    seed: Seed,
    staff_headers: Headers,
    aysel: Headers,
    jobs: FakeJobs,
) -> None:
    """Sprint 4 acceptance at the API: an event for faculty X reaches the students of X; RSVP gives a QR ticket."""
    await seed(ImportKind.ROOMS)
    faculty = str(await db.scalar(select(Faculty.id).where(Faculty.code == "TIQ")))
    event = await publish(
        client, staff_headers, {"type": "faculty", "target_id": faculty}, key="e-1"
    )
    assert event["room"] == {"code": "1-305", "name": event["room"]["name"]}
    assert event["audience"]["label"] == "Tikinti iqtisadiyyatı fakültəsi"
    assert jobs.dispatches == 1

    assert await kinds_for(db, "aysel.mammadova@smartazmiu.test") == [
        NotificationKind.EVENT_PUBLISHED
    ]
    assert await kinds_for(db, "leyla.hasanova@smartazmiu.test") == [
        NotificationKind.EVENT_PUBLISHED
    ]
    # Events notify by push; e-mail is off by default for this category (D-049).
    channels = set(await db.scalars(select(NotificationDelivery.channel).distinct()))
    assert channels == {DeliveryChannel.PUSH}
    # A student outside the faculty: the seed's other faculties have no students, so every student is in.
    students = await db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.academic_group_id.is_not(None), User.status == "active")
    )
    assert await db.scalar(select(func.count()).select_from(Notification)) == (students or 0) + 3

    again = await publish(
        client, staff_headers, {"type": "faculty", "target_id": faculty}, key="e-1"
    )
    assert again["id"] == event["id"]
    assert jobs.dispatches == 1

    registered = await rsvp(client, aysel, event["id"])
    mine = registered["my_registration"]
    assert mine["status"] == "going"
    assert tickets.read_ticket(SECRET, mine["ticket_code"]) is not None
    assert registered["going"] == 1
    # Idempotent: a second RSVP keeps the same ticket.
    assert (await rsvp(client, aysel, event["id"]))["my_registration"]["ticket_code"] == mine[
        "ticket_code"
    ]
    listed = (await client.get("/api/v1/me/tickets", headers=aysel)).json()["items"]
    assert [item["id"] for item in listed] == [event["id"]]


async def test_capacity_is_enforced_even_for_simultaneous_registrations(
    client: AsyncClient,
    db: AsyncSession,
    seed: Seed,
    staff_headers: Headers,
    aysel: Headers,
    ramin: Headers,
) -> None:
    await seed()
    event = await publish(
        client,
        staff_headers,
        await group_audience(db),
        capacity=1,
        room_code=None,
        location="Akt zalı",
    )
    first, second = await asyncio.gather(
        client.put(f"/api/v1/events/{event['id']}/registration", headers=aysel),
        client.put(f"/api/v1/events/{event['id']}/registration", headers=ramin),
    )
    assert sorted([first.status_code, second.status_code]) == [200, 409]
    loser = first if first.status_code == 409 else second
    assert loser.json()["error"]["code"] == "events.full"
    detail = (await client.get(f"/api/v1/events/{event['id']}", headers=staff_headers)).json()
    assert (detail["going"], detail["spots_left"]) == (1, 0)

    # A withdrawn place can be taken again; the capacity cannot drop below the registrations.
    winner = aysel if first.status_code == 200 else ramin
    other = ramin if winner is aysel else aysel
    withdrawn = await client.delete(f"/api/v1/events/{event['id']}/registration", headers=winner)
    assert withdrawn.json()["my_registration"] == {
        "status": "cancelled",
        "ticket_code": None,
        "checked_in_at": None,
    }
    await rsvp(client, other, event["id"])
    edit = {
        "version": detail["version"],
        "title": detail["title"],
        "description": detail["description"],
        "starts_at": detail["starts_at"],
        "ends_at": detail["ends_at"],
        "location": "Akt zalı",
        "capacity": 1,
    }
    assert (
        await client.patch(f"/api/v1/events/{event['id']}", json=edit, headers=staff_headers)
    ).status_code == 200
    await db.execute(update(Event).where(Event.id == uuid.UUID(event["id"])).values(capacity=None))
    await db.commit()
    await rsvp(client, winner, event["id"])
    shrink = {**edit, "version": edit["version"] + 1, "capacity": 1}
    response = await client.patch(
        f"/api/v1/events/{event['id']}", json=shrink, headers=staff_headers
    )
    assert response.json()["error"]["code"] == "events.capacity_below_registrations"


async def test_check_in_at_the_door(
    client: AsyncClient,
    db: AsyncSession,
    seed: Seed,
    staff_headers: Headers,
    aysel: Headers,
    ramin: Headers,
) -> None:
    await seed(ImportKind.ROOMS)
    event = await publish(client, staff_headers, await group_audience(db))
    other = await publish(client, staff_headers, await group_audience(db), title="Başqa tədbir")
    code = (await rsvp(client, aysel, event["id"]))["my_registration"]["ticket_code"]
    other_code = (await rsvp(client, aysel, other["id"]))["my_registration"]["ticket_code"]

    # Students cannot admit anyone; forged, foreign or mistyped codes are refused.
    await check_in(client, aysel, event["id"], 403, code=code)
    forged = code[:-4] + ("AAAA" if not code.endswith("AAAA") else "BBBB")
    assert (await check_in(client, staff_headers, event["id"], 422, code=forged))["error"][
        "code"
    ] == "events.ticket_invalid"
    assert (await check_in(client, staff_headers, event["id"], 422, code="765a2"))["error"][
        "code"
    ] == "events.ticket_invalid"
    assert (await check_in(client, staff_headers, event["id"], 409, code=other_code))["error"][
        "code"
    ] == "events.ticket_other_event"

    admitted = await check_in(client, staff_headers, event["id"], code=f" {code}\n")
    assert (admitted["name"], admitted["group"], admitted["check_in_method"]) == (
        "Aysel Məmmədova",
        "765a2",
        "scan",
    )
    twice = await check_in(client, staff_headers, event["id"], 409, code=code)
    assert twice["error"]["code"] == "events.already_checked_in"
    assert twice["error"]["details"]["name"] == "Aysel Məmmədova"
    # Checked in: the RSVP can no longer be withdrawn.
    locked = await client.delete(f"/api/v1/events/{event['id']}/registration", headers=aysel)
    assert locked.json()["error"]["code"] == "events.already_checked_in"

    # Manual check-in from the list (phone left at home) is audited.
    await rsvp(client, ramin, event["id"])
    attendees = (
        await client.get(f"/api/v1/events/{event['id']}/attendees", headers=staff_headers)
    ).json()
    assert (attendees["going"], attendees["checked_in"]) == (2, 1)
    ramin_row = next(item for item in attendees["items"] if item["name"] == "Ramin Əliyev")
    manual = await check_in(
        client, staff_headers, event["id"], registration_id=ramin_row["registration_id"]
    )
    assert manual["check_in_method"] == "manual"
    audit = await db.scalar(select(AuditLog).where(AuditLog.action == "event.manual_check_in"))
    assert audit is not None
    assert audit.details == {"event_id": event["id"]}
    assert (
        await client.get(f"/api/v1/events/{event['id']}/attendees", headers=aysel)
    ).status_code == 403

    # A cancelled registration's ticket no longer works.
    await client.delete(f"/api/v1/events/{other['id']}/registration", headers=aysel)
    refused = await check_in(client, staff_headers, other["id"], 409, code=other_code)
    assert refused["error"]["code"] == "events.ticket_cancelled"


async def test_check_in_window_and_registration_close_at_the_start(
    client: AsyncClient,
    db: AsyncSession,
    seed: Seed,
    staff_headers: Headers,
    aysel: Headers,
    ramin: Headers,
) -> None:
    await seed(ImportKind.ROOMS)
    later = await publish(
        client, staff_headers, await group_audience(db), starts_at=soon(5), ends_at=soon(6)
    )
    code = (await rsvp(client, aysel, later["id"]))["my_registration"]["ticket_code"]
    closed = await check_in(client, staff_headers, later["id"], 409, code=code)
    assert closed["error"]["code"] == "events.check_in_closed"

    # Once the event has started, RSVPs neither open nor close.
    now = datetime.now(UTC)
    await db.execute(
        update(Event)
        .where(Event.id == uuid.UUID(later["id"]))
        .values(starts_at=now - timedelta(minutes=10), ends_at=now + timedelta(hours=1))
    )
    await db.commit()
    assert (await rsvp(client, ramin, later["id"], 409))["error"][
        "code"
    ] == "events.registration_closed"
    withdraw = await client.delete(f"/api/v1/events/{later['id']}/registration", headers=aysel)
    assert withdraw.json()["error"]["code"] == "events.registration_closed"
    assert (await check_in(client, staff_headers, later["id"], code=code))[
        "check_in_method"
    ] == "scan"


async def test_changes_and_cancellation_reach_registered_attendees_only(
    client: AsyncClient,
    db: AsyncSession,
    seed: Seed,
    staff_headers: Headers,
    aysel: Headers,
    ramin: Headers,
    jobs: FakeJobs,
) -> None:
    await seed(ImportKind.ROOMS)
    event = await publish(client, staff_headers, await group_audience(db))
    await rsvp(client, aysel, event["id"])
    edit = {
        "version": 1,
        "title": "Memarlıq sərgisi (yeni vaxt)",
        "description": event["description"],
        "starts_at": soon(2),
        "ends_at": soon(4),
        "room_code": "1-305",
    }
    changed = await client.patch(f"/api/v1/events/{event['id']}", json=edit, headers=staff_headers)
    assert changed.status_code == 200, changed.text
    assert await kinds_for(db, "aysel.mammadova@smartazmiu.test") == [
        NotificationKind.EVENT_PUBLISHED,
        NotificationKind.EVENT_CHANGED,
    ]
    assert await kinds_for(db, "ramin.aliyev@smartazmiu.test") == [NotificationKind.EVENT_PUBLISHED]
    # A title-only correction notifies nobody; a stale version is refused.
    retitled = {**edit, "version": 2, "title": "Memarlıq sərgisi"}
    await client.patch(f"/api/v1/events/{event['id']}", json=retitled, headers=staff_headers)
    assert len(await kinds_for(db, "aysel.mammadova@smartazmiu.test")) == 2
    stale = await client.patch(
        f"/api/v1/events/{event['id']}", json=retitled, headers=staff_headers
    )
    assert stale.json()["error"]["code"] == "events.version_conflict"

    cancelled = (
        await client.post(f"/api/v1/events/{event['id']}/cancel", headers=staff_headers)
    ).json()
    assert cancelled["status"] == "cancelled"
    assert (
        await client.post(f"/api/v1/events/{event['id']}/cancel", headers=staff_headers)
    ).json()["version"] == cancelled["version"]
    assert (await kinds_for(db, "aysel.mammadova@smartazmiu.test"))[
        -1
    ] == NotificationKind.EVENT_CANCELLED
    assert NotificationKind.EVENT_CANCELLED not in await kinds_for(
        db, "ramin.aliyev@smartazmiu.test"
    )
    # The worker is woken after publishing, the change and the cancellation.
    assert jobs.dispatches >= 3

    mine = (await client.get(f"/api/v1/events/{event['id']}", headers=aysel)).json()[
        "my_registration"
    ]
    assert mine["ticket_code"] is None
    # New RSVPs are refused; an existing one simply stays as it was.
    assert (await rsvp(client, ramin, event["id"], 409))["error"]["code"] == "events.cancelled"
    locked = await client.patch(
        f"/api/v1/events/{event['id']}",
        json={**retitled, "version": cancelled["version"]},
        headers=staff_headers,
    )
    assert locked.json()["error"]["code"] == "events.cancelled"

    aysel_id = await db.scalar(
        select(User.id).where(User.email == "aysel.mammadova@smartazmiu.test")
    )
    ramin_id = await db.scalar(select(User.id).where(User.email == "ramin.aliyev@smartazmiu.test"))
    assert aysel_id is not None
    assert ramin_id is not None
    # Delivery-time check: the cancellation still reaches people who registered, nothing else does.
    assert await still_relevant(db, uuid.UUID(event["id"]), aysel_id)
    assert not await still_relevant(db, uuid.UUID(event["id"]), ramin_id)
    assert not await still_relevant(db, uuid.uuid4(), ramin_id)


async def test_visibility_lists_filters_and_cursor(
    client: AsyncClient,
    db: AsyncSession,
    seed: Seed,
    staff_headers: Headers,
    aysel: Headers,
    nigar: Headers,
) -> None:
    await seed(ImportKind.ROOMS)
    audience = await group_audience(db)
    ids = []
    for hours in (1, 2, 3):
        created = await publish(
            client,
            staff_headers,
            audience,
            title=f"Seminar {hours}",
            starts_at=soon(hours),
            ends_at=soon(hours + 0.5),
        )
        ids.append(created["id"])
    first = (await client.get("/api/v1/events", params={"limit": 2}, headers=aysel)).json()
    assert [item["title"] for item in first["items"]] == ["Seminar 1", "Seminar 2"]
    rest = (
        await client.get(
            "/api/v1/events", params={"limit": 2, "cursor": first["next_cursor"]}, headers=aysel
        )
    ).json()
    assert [item["title"] for item in rest["items"]] == ["Seminar 3"]
    assert rest["next_cursor"] is None
    bad = await client.get("/api/v1/events", params={"cursor": "%%%"}, headers=aysel)
    assert bad.json()["error"]["code"] == "request.invalid_cursor"

    # Nigar's group (765a1) was not addressed: no list entry, no page, no RSVP.
    assert (await client.get("/api/v1/events", headers=nigar)).json()["items"] == []
    assert (await client.get(f"/api/v1/events/{ids[0]}", headers=nigar)).status_code == 404
    await rsvp(client, nigar, ids[0], 404)

    await rsvp(client, aysel, ids[1])
    mine = (await client.get("/api/v1/events", params={"registered": "true"}, headers=aysel)).json()
    assert [item["id"] for item in mine["items"]] == [ids[1]]

    await db.execute(
        update(Event)
        .where(Event.id == uuid.UUID(ids[0]))
        .values(
            starts_at=datetime.now(UTC) - timedelta(days=1, hours=1),
            ends_at=datetime.now(UTC) - timedelta(days=1),
        )
    )
    await db.commit()
    past = (await client.get("/api/v1/events", params={"period": "past"}, headers=aysel)).json()
    assert [item["id"] for item in past["items"]] == [ids[0]]
    # Staff who manage events see every event.
    assert len((await client.get("/api/v1/events", headers=staff_headers)).json()["items"]) == 2


async def test_people_who_join_later_hear_about_coming_events(
    client: AsyncClient,
    db: AsyncSession,
    seed: Seed,
    upload: Upload,
    staff_headers: Headers,
    nigar: Headers,
) -> None:
    await seed(ImportKind.ROOMS)
    event = await publish(client, staff_headers, await group_audience(db))
    students = (SEED_DIR / "students.csv").read_text(encoding="utf-8")
    header, *rows = students.splitlines()
    row = next(row for row in rows if row.startswith("25765101,"))
    await upload(
        ImportKind.STUDENTS, f"{header}\n{row.replace(',765a1,', ',765a2,')}\n", apply=True
    )

    service = EventService(db)
    assert await service.sync_recipients() == 1
    assert await service.sync_recipients() == 0
    assert await kinds_for(db, "nigar.ismayilova@smartazmiu.test") == [
        NotificationKind.EVENT_PUBLISHED
    ]
    assert (await client.get(f"/api/v1/events/{event['id']}", headers=nigar)).status_code == 200


async def test_input_is_validated_and_only_managers_publish(
    client: AsyncClient, db: AsyncSession, seed: Seed, staff_headers: Headers, aysel: Headers
) -> None:
    await seed(ImportKind.ROOMS)
    audience = await group_audience(db)
    await publish(client, aysel, audience, expected=403)
    cases: list[tuple[dict[str, Any], str]] = [
        ({"starts_at": soon(-1), "ends_at": soon(1)}, "events.starts_in_past"),
        ({"starts_at": soon(3), "ends_at": soon(2)}, "events.invalid_times"),
        ({"room_code": "9-999"}, "events.room_not_found"),
        ({"room_code": None, "location": "  "}, "events.location_required"),
        ({"starts_at": "2027-01-10T10:00"}, "request.validation_failed"),
        ({"capacity": 0}, "request.validation_failed"),
    ]
    for fields, code in cases:
        body = await publish(client, staff_headers, audience, expected=422, **fields)
        assert body["error"]["code"] == code, fields
    outside = await publish(
        client, staff_headers, audience, room_code=None, location="Bakı Konqres Mərkəzi"
    )
    assert (outside["room"], outside["location"]) == (None, "Bakı Konqres Mərkəzi")
    both = await check_in(client, staff_headers, outside["id"], 422, code="x", registration_id="y")
    assert both["error"]["code"] == "request.validation_failed"


def test_ticket_codes_cannot_be_forged() -> None:
    registration = uuid.uuid4()
    code = tickets.ticket_code(SECRET, registration)
    assert code.startswith("SA1.")
    assert tickets.read_ticket(SECRET, code) == registration
    assert tickets.read_ticket("another-secret", code) is None
    assert tickets.read_ticket(SECRET, code.replace(registration.hex, uuid.uuid4().hex)) is None
    for garbage in ("", "SA1", "SA1.nothex.sig", "SA2" + code[3:], code + ".extra"):
        assert tickets.read_ticket(SECRET, garbage) is None
