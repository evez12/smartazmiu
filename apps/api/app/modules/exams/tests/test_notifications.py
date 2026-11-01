"""Notifications about exams: a new or moved slot reaches the offering's students and teachers, once per change,
never for an exam that is over, and is checked again at delivery time (D-105)."""

import uuid
from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.modules.academics.models import Enrollment, EnrollmentStatus, ImportKind
from app.modules.academics.tests.conftest import Upload
from app.modules.chat.tests.conftest import Person
from app.modules.exams import notifications
from app.modules.exams.models import ExamSlot
from app.modules.exams.tests import test_exams
from app.modules.exams.tests.test_exams import API, body, offering
from app.modules.exams.tests.test_import import HEADER
from app.modules.notifications.models import (
    DeliveryChannel,
    Notification,
    NotificationCategory,
    NotificationDelivery,
    NotificationKind,
)

people = test_exams.people


async def inbox(db: AsyncSession, who: Person) -> list[Notification]:
    return list(
        await db.scalars(
            select(Notification)
            .where(Notification.user_id == who.id, Notification.subject_type == "exam_slot")
            .order_by(Notification.id)
            .execution_options(populate_existing=True)
        )
    )


async def test_a_new_exam_notifies_students_and_teachers_of_the_offering_only(
    client: AsyncClient, db: AsyncSession, people: dict[str, Person]
) -> None:
    found = await offering(db, "IQT-2102")
    created = await client.post(
        f"{API}/slots",
        headers=people["staff"].headers,
        json=body(found.id, timedelta(days=20), timedelta(hours=2)),
    )
    assert created.status_code == 201, created.text
    for who in ("aysel", "leyla"):
        [note] = await inbox(db, people[who])
        assert note.kind is NotificationKind.EXAM_SCHEDULED
        assert note.category is NotificationCategory.SCHEDULE
        assert note.subject_id == uuid.UUID(created.json()["id"])
        assert note.title.startswith("Statistika, ")
        assert note.link == "/exams"
    assert await inbox(db, people["outsider"]) == []
    assert await inbox(db, people["staff"]) == []

    # Push is on for the schedule category by default; e-mail is not (D-049).
    channels = set(
        await db.scalars(
            select(NotificationDelivery.channel)
            .join(Notification, Notification.id == NotificationDelivery.notification_id)
            .where(Notification.subject_type == "exam_slot")
        )
    )
    assert channels == {DeliveryChannel.PUSH}


async def test_an_exam_that_is_already_over_notifies_nobody(
    client: AsyncClient, db: AsyncSession, people: dict[str, Person]
) -> None:
    found = await offering(db, "IQT-2102")
    staff = people["staff"].headers
    past = await client.post(
        f"{API}/slots", headers=staff, json=body(found.id, timedelta(days=-3), timedelta(hours=2))
    )
    assert past.status_code == 201
    # Moved to another day in the past: still nothing.
    moved = body(found.id, timedelta(days=-2), timedelta(hours=2))
    changed = await client.put(
        f"{API}/slots/{past.json()['id']}",
        headers=staff,
        json={k: moved[k] for k in ("starts_at", "ends_at", "room_code")},
    )
    assert changed.status_code == 200
    assert await inbox(db, people["aysel"]) == []
    assert await inbox(db, people["leyla"]) == []


async def test_a_move_notifies_once_per_change_and_a_save_without_change_says_nothing(
    client: AsyncClient, db: AsyncSession, people: dict[str, Person]
) -> None:
    found = await offering(db, "IQT-2102")
    staff = people["staff"].headers
    first = body(found.id, timedelta(days=20), timedelta(hours=2))
    created = await client.post(f"{API}/slots", headers=staff, json=first)
    slot_url = f"{API}/slots/{created.json()['id']}"
    keys = ("starts_at", "ends_at", "room_code")
    same = {k: created.json()[k] for k in keys}

    assert (await client.put(slot_url, headers=staff, json=same)).status_code == 200
    assert len(await inbox(db, people["aysel"])) == 1

    later = body(found.id, timedelta(days=21), timedelta(hours=2))
    assert (
        await client.put(slot_url, headers=staff, json={k: later[k] for k in keys})
    ).status_code == 200
    # A move back to the first time is a change again, so students hear about it as well.
    assert (await client.put(slot_url, headers=staff, json=same)).status_code == 200

    notes = await inbox(db, people["aysel"])
    assert [note.kind for note in notes] == [
        NotificationKind.EXAM_SCHEDULED,
        NotificationKind.EXAM_MOVED,
        NotificationKind.EXAM_MOVED,
    ]
    assert len({note.dedupe_key for note in notes}) == 3


async def test_the_same_change_is_never_delivered_twice(
    client: AsyncClient, db: AsyncSession, people: dict[str, Person]
) -> None:
    found = await offering(db, "IQT-2102")
    created = await client.post(
        f"{API}/slots",
        headers=people["staff"].headers,
        json=body(found.id, timedelta(days=20), timedelta(hours=2)),
    )
    slot = await db.get(ExamSlot, uuid.UUID(created.json()["id"]))
    assert slot is not None
    await notifications.notify_slot(db, slot, None)
    await db.commit()
    assert len(await inbox(db, people["aysel"])) == 1


async def test_delivery_time_check_follows_the_exam_and_the_enrollment(
    client: AsyncClient, db: AsyncSession, people: dict[str, Person]
) -> None:
    found = await offering(db, "IQT-2102")
    staff = people["staff"].headers
    created = await client.post(
        f"{API}/slots", headers=staff, json=body(found.id, timedelta(days=20), timedelta(hours=2))
    )
    slot_id = uuid.UUID(created.json()["id"])
    aysel, leyla, outsider = (people[n].id for n in ("aysel", "leyla", "outsider"))
    assert await notifications.still_scheduled(db, slot_id, aysel)
    assert await notifications.still_scheduled(db, slot_id, leyla)
    assert not await notifications.still_scheduled(db, slot_id, outsider)

    # The student drops the course before the push goes out.
    enrollment = await db.scalar(
        select(Enrollment).where(
            Enrollment.user_id == aysel, Enrollment.course_offering_id == found.id
        )
    )
    assert enrollment is not None
    enrollment.status = EnrollmentStatus.DROPPED
    await db.commit()
    assert not await notifications.still_scheduled(db, slot_id, aysel)
    enrollment.status = EnrollmentStatus.ACTIVE
    await db.commit()
    assert await notifications.still_scheduled(db, slot_id, aysel)

    # The exam is over by the time the worker runs, then it is deleted.
    slot = await db.get(ExamSlot, slot_id)
    assert slot is not None
    slot.starts_at, slot.ends_at = utc_now() - timedelta(hours=3), utc_now() - timedelta(hours=1)
    await db.commit()
    assert not await notifications.still_scheduled(db, slot_id, aysel)
    assert (await client.delete(f"{API}/slots/{slot_id}", headers=staff)).status_code == 204
    assert not await notifications.still_scheduled(db, slot_id, leyla)


async def test_the_import_notifies_new_and_changed_exams_but_not_a_repeat(
    upload: Upload, db: AsyncSession, people: dict[str, Person]
) -> None:
    content = (
        HEADER
        + "IQT-2102,2026,Payız,765a2,,2027-01-14,10:00,11:30,2-204\n"
        + "XDL-2103,2026,Payız,765a2,,2027-01-18,10:00,11:30,1-206\n"
        # An exam from the previous session is stored for history and tells nobody.
        + "IQT-2101,2026,Payız,765a2,,2026-10-01,10:00,11:30,1-301\n"
    )
    await upload(ImportKind.EXAM_SLOTS, content, apply=True)
    kinds = [n.kind for n in await inbox(db, people["aysel"])]
    assert kinds == [NotificationKind.EXAM_SCHEDULED] * 2

    await upload(ImportKind.EXAM_SLOTS, content, apply=True)
    assert len(await inbox(db, people["aysel"])) == 2

    later = content.replace("11:30,2-204", "12:00,2-204")
    await upload(ImportKind.EXAM_SLOTS, later, apply=True)
    kinds = [n.kind for n in await inbox(db, people["aysel"])]
    assert kinds.count(NotificationKind.EXAM_MOVED) == 1
    assert await db.scalar(select(func.count()).select_from(ExamSlot)) == 3
