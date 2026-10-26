"""Who may be a guide for a subject (§5.2), decided in SQL so the same rule serves opt-in, accept and the
results-import re-check.

Eligible: a completed and passed enrollment in a past semester of the subject, no active enrollment in it now
(a retake), an active account, and no moderator posting mute in the subject community. The mute stands in for a
chat ban until bans exist (Sprint 10, D-083).
"""

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import ColumnElement, Select, and_, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import baku_today
from app.modules.academics.models import (
    CourseOffering,
    CourseOfferingTeacher,
    Enrollment,
    EnrollmentStatus,
    Semester,
)
from app.modules.chat.models import Channel, ChannelMember, ChannelType
from app.modules.users.models import User, UserStatus


@dataclass(frozen=True, slots=True)
class Qualification:
    """The passed enrollment that makes someone a guide: the most recent one."""

    semester_id: uuid.UUID
    teacher_id: uuid.UUID | None
    grade: int | None


def _passed(user_id: Any, subject_id: Any, on: date) -> list[ColumnElement[bool]]:
    return [
        Enrollment.user_id == user_id,
        CourseOffering.subject_id == subject_id,
        Enrollment.status == EnrollmentStatus.COMPLETED,
        Enrollment.passed.is_(True),
        Semester.ends_on < on,
    ]


def retaking(user_id: Any, subject_id: Any) -> ColumnElement[bool]:
    active = select(Enrollment.id).join(
        CourseOffering, CourseOffering.id == Enrollment.course_offering_id
    )
    return exists(
        active.where(
            Enrollment.user_id == user_id,
            CourseOffering.subject_id == subject_id,
            Enrollment.status == EnrollmentStatus.ACTIVE,
        )
    )


def banned(user_id: Any, subject_id: Any) -> ColumnElement[bool]:
    return exists(
        select(ChannelMember.user_id)
        .join(Channel, Channel.id == ChannelMember.channel_id)
        .where(
            Channel.type == ChannelType.SUBJECT_COMMUNITY,
            Channel.subject_id == subject_id,
            ChannelMember.user_id == user_id,
            ChannelMember.posting_muted_until > func.now(),
        )
    )


def eligible_pairs(on: date | None = None) -> Select[uuid.UUID, uuid.UUID]:
    """(user_id, subject_id) of everyone eligible today."""
    on = on or baku_today()
    pairs = (
        select(Enrollment.user_id, CourseOffering.subject_id)
        .join(CourseOffering, CourseOffering.id == Enrollment.course_offering_id)
        .join(Semester, Semester.id == CourseOffering.semester_id)
        .join(User, User.id == Enrollment.user_id)
        .where(
            Enrollment.status == EnrollmentStatus.COMPLETED,
            Enrollment.passed.is_(True),
            Semester.ends_on < on,
            User.status == UserStatus.ACTIVE,
        )
        .distinct()
        .subquery()
    )
    return select(pairs.c.user_id, pairs.c.subject_id).where(
        ~retaking(pairs.c.user_id, pairs.c.subject_id),
        ~banned(pairs.c.user_id, pairs.c.subject_id),
    )


async def qualification(
    session: AsyncSession, user_id: uuid.UUID, subject_id: uuid.UUID
) -> Qualification | None:
    """The qualifying enrollment, or None when the person is not eligible for the subject today."""
    on = baku_today()
    ok = await session.scalar(
        select(
            and_(
                exists().where(User.id == user_id, User.status == UserStatus.ACTIVE),
                ~retaking(user_id, subject_id),
                ~banned(user_id, subject_id),
            )
        )
    )
    if not ok:
        return None
    teacher = (
        select(CourseOfferingTeacher.teacher_id)
        .where(CourseOfferingTeacher.course_offering_id == CourseOffering.id)
        .order_by(CourseOfferingTeacher.teacher_id)
        .limit(1)
        .scalar_subquery()
    )
    row = (
        await session.execute(
            select(Semester.id, teacher, Enrollment.grade)
            .join(CourseOffering, CourseOffering.id == Enrollment.course_offering_id)
            .join(Semester, Semester.id == CourseOffering.semester_id)
            .where(*_passed(user_id, subject_id, on))
            .order_by(Semester.ends_on.desc())
            .limit(1)
        )
    ).first()
    if row is None:
        return None
    return Qualification(semester_id=row[0], teacher_id=row[1], grade=row[2])
