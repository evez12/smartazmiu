"""Telling people about exams (D-105): a new or moved exam goes to the offering's students and teachers, a decision
on a past paper goes to the person who uploaded it. Both use the ``schedule`` category (D-049)."""

import hashlib
import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import Select, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import BAKU, utc_now
from app.modules.academics.models import (
    CourseOffering,
    CourseOfferingTeacher,
    Enrollment,
    EnrollmentStatus,
    Subject,
)
from app.modules.exams.models import ExamSlot, PastPaper, PastPaperStatus
from app.modules.notifications.models import NotificationCategory, NotificationKind
from app.modules.notifications.service import NotificationSpec, Notifier
from app.modules.schedule.notifications import MONTHS
from app.modules.users.models import User, UserStatus

SLOT_SUBJECT_TYPE = "exam_slot"
PAPER_SUBJECT_TYPE = "past_paper"

# What a student or teacher notices about an exam: when it is and where.
SlotState = tuple[datetime, datetime, str | None]


def state_of(slot: ExamSlot) -> SlotState:
    return slot.starts_at, slot.ends_at, slot.room_code


def attendees(offering_id: uuid.UUID) -> Select[uuid.UUID]:
    """Active accounts that attend or teach the offering: the same people ``my_exams`` shows the exam to."""
    attends = exists().where(
        Enrollment.user_id == User.id,
        Enrollment.course_offering_id == offering_id,
        Enrollment.status == EnrollmentStatus.ACTIVE,
    )
    teaches = exists().where(
        CourseOfferingTeacher.course_offering_id == offering_id,
        CourseOfferingTeacher.teacher_id == User.id,
    )
    return select(User.id).where(User.status == UserStatus.ACTIVE, or_(attends, teaches))


def _utc(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat()


def _fingerprint(previous: SlotState | None, current: SlotState, stamp: datetime | None) -> str:
    """Identifies this version of the change: the same edit notifies once, a move back and forth notifies each
    time (the stamp tells two edits to the same values apart). Instants are written in UTC, because the same
    instant prints differently depending on where its time zone object came from."""

    def describe(state: SlotState) -> list[str | None]:
        return [_utc(state[0]), _utc(state[1]), state[2]]

    parts = [
        describe(previous) if previous else None,
        describe(current),
        _utc(stamp) if stamp else None,
    ]
    return hashlib.sha256(json.dumps(parts).encode()).hexdigest()[:16]


def _when(moment: datetime) -> str:
    local = moment.astimezone(BAKU)
    return f"{local.day} {MONTHS[local.month - 1]} {local:%H:%M}"


async def notify_slot(
    session: AsyncSession,
    slot: ExamSlot,
    previous: SlotState | None,
    stamp: datetime | None = None,
) -> None:
    """Notifies about a new exam (``previous`` is None) or a moved one; nothing for an exam that is over, and
    nothing when time and room are as before. Runs in the caller's transaction."""
    current = state_of(slot)
    if slot.ends_at <= utc_now() or current == previous:
        return
    subject = await session.scalar(
        select(Subject.name_az)
        .join(CourseOffering, CourseOffering.subject_id == Subject.id)
        .where(CourseOffering.id == slot.course_offering_id)
    )
    await Notifier(session).notify(
        attendees(slot.course_offering_id),
        NotificationSpec(
            category=NotificationCategory.SCHEDULE,
            kind=NotificationKind.EXAM_SCHEDULED
            if previous is None
            else NotificationKind.EXAM_MOVED,
            subject_type=SLOT_SUBJECT_TYPE,
            subject_id=slot.id,
            dedupe_key=f"exam_slot:{slot.id}:{_fingerprint(previous, current, stamp)}",
            title=f"{subject}, {_when(slot.starts_at)}",
            link="/exams",
        ),
    )


async def still_scheduled(session: AsyncSession, slot_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """Delivery-time check (§5.6): the exam still exists, is not over, and the user still attends or teaches it."""
    slot = await session.get(ExamSlot, slot_id)
    if slot is None or slot.ends_at <= utc_now():
        return False
    return bool(
        await session.scalar(
            select(attendees(slot.course_offering_id).where(User.id == user_id).exists())
        )
    )


async def notify_paper_decision(session: AsyncSession, paper: PastPaper) -> None:
    """Tells the uploader that a paper was approved or rejected. A reviewer cannot decide on their own paper, so
    the uploader is never the one who just acted."""
    approved = paper.status is PastPaperStatus.APPROVED
    fingerprint = hashlib.sha256(
        json.dumps([paper.status.value, paper.reviewed_at and _utc(paper.reviewed_at)]).encode()
    ).hexdigest()[:16]
    await Notifier(session).notify(
        select(User.id).where(User.id == paper.uploader_id),
        NotificationSpec(
            category=NotificationCategory.SCHEDULE,
            kind=(
                NotificationKind.PAST_PAPER_APPROVED
                if approved
                else NotificationKind.PAST_PAPER_REJECTED
            ),
            subject_type=PAPER_SUBJECT_TYPE,
            subject_id=paper.id,
            dedupe_key=f"past_paper:{paper.id}:{fingerprint}",
            title=paper.title or paper.filename,
            link="/exams/papers",
        ),
    )


async def still_decided(session: AsyncSession, paper_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """Delivery-time check: the paper still exists, is still decided, and belongs to the recipient."""
    paper = await session.get(PastPaper, paper_id)
    return (
        paper is not None
        and paper.uploader_id == user_id
        and paper.purged_at is None
        and paper.status is not PastPaperStatus.PENDING
    )
