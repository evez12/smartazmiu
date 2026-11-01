"""Exam slots: management, exam mode from the real table, the import with overlap warnings, my exams (D-097)."""

import uuid
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.modules.academics.models import CourseOffering, ImportKind, Subject
from app.modules.audit.models import AuditLog
from app.modules.campus.models import Room
from app.modules.chat.access import ChannelAccess
from app.modules.chat.bus import ChatBus
from app.modules.chat.models import Channel, ChannelType
from app.modules.chat.provisioning import ChannelProvisioner
from app.modules.chat.tests.conftest import MakePerson, Person
from app.modules.chat.tests.test_messages import current
from app.modules.exams.models import ExamSlot
from app.modules.exams.windows import DatabaseExamWindows
from app.modules.materials.tests.test_materials import sign_in
from app.modules.users.service import CurrentUser
from tests.support import TokenFactory

API = "/api/v1/exams"
Seed = Callable[..., Awaitable[None]]


@pytest.fixture
async def people(
    client: AsyncClient, tokens: TokenFactory, seed: Seed, person: MakePerson, db: AsyncSession
) -> dict[str, Person]:
    await seed(ImportKind.ROOMS)
    await ChannelProvisioner(db).run()
    return {
        "leyla": await sign_in(
            client, tokens, "leyla.hasanova@smartazmiu.test", ["teacher"], "Leyla", "Həsənova"
        ),
        "aysel": await sign_in(
            client, tokens, "aysel.mammadova@smartazmiu.test", ["student"], "Aysel", "Məmmədova"
        ),
        "outsider": await person("Orxan", "Rzayev"),
        "staff": await person("Günel", "Səfərova", roles=["staff"]),
    }


async def offering(db: AsyncSession, subject_code: str, groups: int = 1) -> CourseOffering:
    """The 2026 Payız offering of a subject; the joint ones have two groups."""
    found = await db.scalars(
        select(CourseOffering)
        .join(Subject, Subject.id == CourseOffering.subject_id)
        .where(Subject.code == subject_code, CourseOffering.code.like("%765a2%"))
    )
    result = list(found)
    assert result, subject_code
    return result[0]


def body(
    offering_id: uuid.UUID, start: timedelta, length: timedelta, room: str | None = None
) -> dict[str, Any]:
    starts = utc_now() + start
    return {
        "course_offering_id": str(offering_id),
        "starts_at": starts.isoformat(),
        "ends_at": (starts + length).isoformat(),
        "room_code": room,
    }


async def channels(db: AsyncSession, found: CourseOffering) -> tuple[uuid.UUID, uuid.UUID]:
    course = await db.scalar(
        select(Channel.id).where(
            Channel.type == ChannelType.COURSE_OFFERING, Channel.course_offering_id == found.id
        )
    )
    community = await db.scalar(
        select(Channel.id).where(
            Channel.type == ChannelType.SUBJECT_COMMUNITY, Channel.subject_id == found.subject_id
        )
    )
    assert course is not None
    assert community is not None
    return course, community


async def exam_until(db: AsyncSession, app: FastAPI, user: CurrentUser, channel: uuid.UUID) -> Any:
    access = ChannelAccess(db, app.state.redis, DatabaseExamWindows(db))
    return (await access.state(user, channel)).exam_until


async def test_only_staff_manage_slots(
    client: AsyncClient, db: AsyncSession, people: dict[str, Person]
) -> None:
    found = await offering(db, "IQT-2102")
    payload = body(found.id, timedelta(days=30), timedelta(hours=2))
    for denied in ("leyla", "aysel", "outsider"):
        for call in (
            client.get(f"{API}/slots", headers=people[denied].headers),
            client.post(f"{API}/slots", headers=people[denied].headers, json=payload),
        ):
            assert (await call).status_code == 403
    assert (await client.get(f"{API}/slots")).status_code == 401
    created = await client.post(f"{API}/slots", headers=people["staff"].headers, json=payload)
    assert created.status_code == 201, created.text
    listed = (await client.get(f"{API}/slots", headers=people["staff"].headers)).json()["items"]
    assert created.json()["id"] in [slot["id"] for slot in listed]


async def test_exam_mode_follows_the_real_slots_in_the_course_channel_and_the_subject_community(
    client: AsyncClient,
    app: FastAPI,
    db: AsyncSession,
    people: dict[str, Person],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Sprint 10 acceptance, run against the table instead of a fake provider (D-097)."""
    announced: list[list[uuid.UUID]] = []

    async def record(self: ChatBus, channel_ids: list[uuid.UUID]) -> None:
        announced.append(list(channel_ids))

    monkeypatch.setattr(ChatBus, "channels_changed", record)
    found = await offering(db, "IQT-2102")
    course, community = await channels(db, found)
    aysel = await current(db, people["aysel"])
    staff = people["staff"].headers

    # An exam that starts in an hour is not exam mode yet: the lead is 15 minutes.
    later = await client.post(
        f"{API}/slots", headers=staff, json=body(found.id, timedelta(hours=1), timedelta(hours=2))
    )
    assert later.status_code == 201, later.text
    assert announced[-1]
    assert {course, community} <= set(announced[-1])
    assert await exam_until(db, app, aysel, course) is None
    assert await exam_until(db, app, aysel, community) is None

    # Moved to start in 10 minutes it is inside the lead: both channels turn read-only until its end.
    slot_id = later.json()["id"]
    moved_body = body(found.id, timedelta(minutes=10), timedelta(hours=2))
    moved = await client.put(
        f"{API}/slots/{slot_id}",
        headers=staff,
        json={k: moved_body[k] for k in ("starts_at", "ends_at", "room_code")},
    )
    assert moved.status_code == 200, moved.text
    assert {course, community} <= set(announced[-1])
    ends = await db.get(ExamSlot, uuid.UUID(slot_id))
    assert ends is not None
    await db.refresh(ends)
    assert await exam_until(db, app, aysel, course) == ends.ends_at
    assert await exam_until(db, app, aysel, community) == ends.ends_at

    # A channel of another subject is untouched.
    other = await offering(db, "XDL-2103")
    other_course, other_community = await channels(db, other)
    assert await exam_until(db, app, aysel, other_course) is None
    assert await exam_until(db, app, aysel, other_community) is None

    # Deleting the slot ends exam mode at once and tells the open screens.
    assert (await client.delete(f"{API}/slots/{slot_id}", headers=staff)).status_code == 204
    assert {course, community} <= set(announced[-1])
    assert await exam_until(db, app, aysel, course) is None
    assert len(announced) == 3
    actions = list(
        await db.scalars(select(AuditLog.action).where(AuditLog.action.like("exam_slot.%")))
    )
    assert sorted(actions) == ["exam_slot.created", "exam_slot.deleted", "exam_slot.edited"]


async def test_overlapping_slots_overlap_in_the_community_and_merge_into_one_window(
    client: AsyncClient, app: FastAPI, db: AsyncSession, people: dict[str, Person]
) -> None:
    """Two offerings of one subject: the community follows the union of their windows (D-003)."""
    first = await offering(db, "IQT-2102")
    siblings = list(
        await db.scalars(
            select(CourseOffering).where(
                CourseOffering.subject_id == first.subject_id, CourseOffering.id != first.id
            )
        )
    )
    if not siblings:
        pytest.skip("the sample data has one offering of this subject in the semester")
    _, community = await channels(db, first)
    aysel = await current(db, people["aysel"])
    staff = people["staff"].headers
    await client.post(
        f"{API}/slots",
        headers=staff,
        json=body(first.id, timedelta(minutes=-10), timedelta(hours=1)),
    )
    await client.post(
        f"{API}/slots",
        headers=staff,
        json=body(siblings[0].id, timedelta(minutes=-5), timedelta(hours=3)),
    )
    until = await exam_until(db, app, aysel, community)
    assert until is not None
    assert until > utc_now() + timedelta(hours=2)


async def test_creating_a_colliding_slot_warns_staff(
    client: AsyncClient, db: AsyncSession, people: dict[str, Person]
) -> None:
    statistika = await offering(db, "IQT-2102")
    mikro = await offering(db, "IQT-2101")
    rooms = list(await db.scalars(select(Room.code).limit(2)))
    staff = people["staff"].headers
    first = await client.post(
        f"{API}/slots",
        headers=staff,
        json=body(statistika.id, timedelta(days=40), timedelta(hours=2), rooms[0]),
    )
    assert first.status_code == 201
    assert first.json()["overlaps"] == []
    start = first.json()["starts_at"]

    # Another offering of the same group, at the same time: the students would sit two exams at once.
    group = await client.post(
        f"{API}/slots",
        headers=staff,
        json={
            "course_offering_id": str(mikro.id),
            "starts_at": start,
            "ends_at": first.json()["ends_at"],
            "room_code": rooms[1],
        },
    )
    assert group.status_code == 201, group.text
    assert [o["kind"] for o in group.json()["overlaps"]] == ["group"]

    # The same room for an offering of other students is a room collision.
    other = await offering(db, "SOS-2103")
    room = await client.post(
        f"{API}/slots",
        headers=staff,
        json={
            "course_offering_id": str(other.id),
            "starts_at": start,
            "ends_at": first.json()["ends_at"],
            "room_code": rooms[0],
        },
    )
    kinds = {o["kind"] for o in room.json()["overlaps"]}
    assert "room" in kinds or "group" in kinds
    listed = (await client.get(f"{API}/slots", headers=staff)).json()["items"]
    assert any(slot["overlaps"] for slot in listed)


async def test_slot_input_is_checked(
    client: AsyncClient, db: AsyncSession, people: dict[str, Person]
) -> None:
    found = await offering(db, "IQT-2102")
    staff = people["staff"].headers
    good = body(found.id, timedelta(days=50), timedelta(hours=2))
    assert (await client.post(f"{API}/slots", headers=staff, json=good)).status_code == 201
    duplicate = await client.post(f"{API}/slots", headers=staff, json=good)
    assert (duplicate.status_code, duplicate.json()["error"]["code"]) == (409, "exams.duplicate")
    backwards = {**good, "ends_at": good["starts_at"]}
    assert (await client.post(f"{API}/slots", headers=staff, json=backwards)).status_code == 422
    marathon = body(found.id, timedelta(days=51), timedelta(hours=13))
    long = await client.post(f"{API}/slots", headers=staff, json=marathon)
    assert (long.status_code, long.json()["error"]["code"]) == (422, "exams.window_too_long")
    room = await client.post(
        f"{API}/slots",
        headers=staff,
        json=body(found.id, timedelta(days=52), timedelta(hours=2), "Z-999"),
    )
    assert (room.status_code, room.json()["error"]["code"]) == (422, "exams.unknown_room")
    ghost = body(uuid.uuid4(), timedelta(days=52), timedelta(hours=2))
    missing = await client.post(f"{API}/slots", headers=staff, json=ghost)
    assert (missing.status_code, missing.json()["error"]["code"]) == (
        404,
        "exams.offering_not_found",
    )
    gone = await client.delete(f"{API}/slots/{uuid.uuid4()}", headers=staff)
    assert gone.status_code == 404


async def test_students_and_teachers_see_their_own_upcoming_exams_and_a_calendar(
    client: AsyncClient, db: AsyncSession, people: dict[str, Person]
) -> None:
    found = await offering(db, "IQT-2102")
    staff = people["staff"].headers
    room = await db.scalar(select(Room.code).limit(1))
    soon = await client.post(
        f"{API}/slots",
        headers=staff,
        json=body(found.id, timedelta(days=3), timedelta(hours=2), room),
    )
    await client.post(
        f"{API}/slots", headers=staff, json=body(found.id, timedelta(days=-3), timedelta(hours=2))
    )
    for who in ("aysel", "leyla"):
        mine = (await client.get(f"{API}/mine", headers=people[who].headers)).json()["items"]
        assert soon.json()["id"] in [slot["id"] for slot in mine], who
        assert all(slot["overlaps"] == [] for slot in mine)
        # Exams that already ended are not "upcoming".
        assert all(slot["ends_at"] > utc_now().isoformat() for slot in mine)
    assert (await client.get(f"{API}/mine", headers=people["outsider"].headers)).json() == {
        "items": []
    }

    calendar = await client.get(f"{API}/mine.ics", headers=people["aysel"].headers)
    assert calendar.headers["content-type"].startswith("text/calendar")
    text = calendar.text
    assert f"UID:exam-{soon.json()['id']}@smartazmiu" in text
    assert "DTSTART;TZID=Asia/Baku:" in text
    assert f"LOCATION:Otaq {room}" in text
    assert text.startswith("BEGIN:VCALENDAR")
    assert text.rstrip().endswith("END:VCALENDAR")
    empty = await client.get(f"{API}/mine.ics", headers=people["outsider"].headers)
    assert "BEGIN:VEVENT" not in empty.text
