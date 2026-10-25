"""Telling people about timetable changes (§13.4): imported changes for today or later notify everyone who
attends or teaches that class; changes to past days are stored for history only."""

import hashlib
import uuid
from datetime import date

from sqlalchemy import Select, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import baku_today
from app.modules.academics.models import (
    CourseOffering,
    CourseOfferingTeacher,
    Enrollment,
    EnrollmentStatus,
    Subject,
)
from app.modules.notifications.models import NotificationCategory, NotificationKind
from app.modules.notifications.service import NotificationSpec, Notifier
from app.modules.schedule.models import ScheduleChange, ScheduleEntry, ScheduleEntryGroup
from app.modules.users.models import User, UserStatus

SUBJECT_TYPE = "schedule_change"
MONTHS = (
    "Yanvar",
    "Fevral",
    "Mart",
    "Aprel",
    "May",
    "İyun",
    "İyul",
    "Avqust",
    "Sentyabr",
    "Oktyabr",
    "Noyabr",
    "Dekabr",
)


def _day(value: date) -> str:
    return f"{value.day} {MONTHS[value.month - 1]}"


def affected(entry: ScheduleEntry, substitute_id: uuid.UUID | None) -> Select[uuid.UUID]:
    """Active accounts that attend or teach the class: the same rule as the timetable view."""
    restricted = exists().where(ScheduleEntryGroup.schedule_entry_id == entry.id)
    own_group = exists().where(
        ScheduleEntryGroup.schedule_entry_id == entry.id,
        ScheduleEntryGroup.academic_group_id == User.academic_group_id,
    )
    attends = exists().where(
        Enrollment.user_id == User.id,
        Enrollment.course_offering_id == entry.course_offering_id,
        Enrollment.status != EnrollmentStatus.DROPPED,
    ) & or_(~restricted, own_group)
    if entry.teacher_id is not None:
        teaches = User.id == entry.teacher_id
    else:
        teaches = exists().where(
            CourseOfferingTeacher.course_offering_id == entry.course_offering_id,
            CourseOfferingTeacher.teacher_id == User.id,
        )
    reasons = [attends, teaches]
    if substitute_id is not None:
        reasons.append(User.id == substitute_id)
    return select(User.id).where(User.status == UserStatus.ACTIVE, or_(*reasons))


def _fingerprint(change: ScheduleChange) -> str:
    """Identifies this version of the change, so an edited change notifies again and a re-import does not."""
    parts = (
        change.cancelled,
        change.new_date,
        change.new_starts_at,
        change.new_ends_at,
        change.room_id,
        change.teacher_id,
        change.note,
    )
    return hashlib.sha256(repr(parts).encode()).hexdigest()[:16]


async def notify_changes(
    session: AsyncSession, changes: list[tuple[ScheduleChange, ScheduleEntry]]
) -> None:
    """Notifies about each change that concerns today or a later day (in Baku time)."""
    today = baku_today()
    notifier = Notifier(session)
    for change, entry in changes:
        if change.occurs_on < today and (change.new_date is None or change.new_date < today):
            continue
        subject = await session.scalar(
            select(Subject.name_az)
            .join(CourseOffering, CourseOffering.subject_id == Subject.id)
            .where(CourseOffering.id == entry.course_offering_id)
        )
        await notifier.notify(
            affected(entry, change.teacher_id),
            NotificationSpec(
                category=NotificationCategory.SCHEDULE,
                kind=NotificationKind.SCHEDULE_CHANGED,
                subject_type=SUBJECT_TYPE,
                subject_id=change.id,
                dedupe_key=f"schedule_change:{change.id}:{_fingerprint(change)}",
                title=f"{subject}, {_day(change.occurs_on)}",
                link=f"/schedule?view=day&date={change.occurs_on.isoformat()}",
            ),
        )


async def still_affected(session: AsyncSession, change_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """Delivery-time check (§5.6): the change still exists, is not past, and the user still has the class."""
    change = await session.get(ScheduleChange, change_id)
    if change is None:
        return False
    today = baku_today()
    if change.occurs_on < today and (change.new_date is None or change.new_date < today):
        return False
    entry = await session.get(ScheduleEntry, change.schedule_entry_id)
    if entry is None:
        return False
    query = affected(entry, change.teacher_id).where(User.id == user_id)
    return bool(await session.scalar(select(query.exists())))
