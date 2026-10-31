"""Who may do what in a course offering: shared by assignments and quizzes (D-092).

A teacher manages the offerings they teach; staff and administrators with the module's permission manage any
offering; a student with an enrollment that is not dropped reads, and one with an active enrollment submits.
Everyone else gets the same 404 as for an offering that does not exist (§14).
"""

import uuid
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import Select, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academics.models import (
    AcademicGroup,
    CourseOffering,
    CourseOfferingGroup,
    CourseOfferingTeacher,
    Enrollment,
    EnrollmentStatus,
    Semester,
    Subject,
)
from app.modules.audiences.service import TERM_NAMES
from app.modules.users.service import CurrentUser

CourseRole = Literal["manager", "student", "reader"]
"""``reader`` has a completed enrollment: sees the work, cannot submit."""


def teaching(user: CurrentUser) -> Select[Any]:
    return select(CourseOfferingTeacher.course_offering_id).where(
        CourseOfferingTeacher.teacher_id == user.id
    )


def attending(user: CurrentUser, *, active_only: bool = False) -> Select[Any]:
    wanted = (
        [EnrollmentStatus.ACTIVE]
        if active_only
        else [
            EnrollmentStatus.ACTIVE,
            EnrollmentStatus.COMPLETED,
        ]
    )
    return select(Enrollment.course_offering_id).where(
        Enrollment.user_id == user.id, Enrollment.status.in_(wanted)
    )


async def course_role(
    session: AsyncSession, user: CurrentUser, offering_id: uuid.UUID, manage_permission: str
) -> CourseRole | None:
    """The user's role in the offering, or ``None`` for outsiders and for offerings that do not exist."""
    if not await session.scalar(select(exists().where(CourseOffering.id == offering_id))):
        return None
    if user.has_permission(manage_permission):
        return "manager"
    if await session.scalar(
        select(
            exists().where(
                CourseOfferingTeacher.course_offering_id == offering_id,
                CourseOfferingTeacher.teacher_id == user.id,
            )
        )
    ):
        return "manager"
    status = await session.scalar(
        select(Enrollment.status).where(
            Enrollment.user_id == user.id,
            Enrollment.course_offering_id == offering_id,
            Enrollment.status != EnrollmentStatus.DROPPED,
        )
    )
    if status is None:
        return None
    return "student" if status is EnrollmentStatus.ACTIVE else "reader"


class CourseOfferingOut(BaseModel):
    """An offering in a picker or a heading: subject, groups and semester."""

    id: str
    subject_name: str
    subject_code: str
    groups: list[str]
    semester: str


async def offering_labels(
    session: AsyncSession, ids: set[uuid.UUID]
) -> dict[uuid.UUID, CourseOfferingOut]:
    if not ids:
        return {}
    groups: dict[uuid.UUID, list[str]] = {offering: [] for offering in ids}
    for offering_id, code in await session.execute(
        select(CourseOfferingGroup.course_offering_id, AcademicGroup.code)
        .join(AcademicGroup, AcademicGroup.id == CourseOfferingGroup.academic_group_id)
        .where(CourseOfferingGroup.course_offering_id.in_(ids))
        .order_by(AcademicGroup.code)
    ):
        groups[offering_id].append(code)
    rows = await session.execute(
        select(CourseOffering.id, Subject.name_az, Subject.code, Semester)
        .join(Subject, Subject.id == CourseOffering.subject_id)
        .join(Semester, Semester.id == CourseOffering.semester_id)
        .where(CourseOffering.id.in_(ids))
    )
    return {
        offering_id: CourseOfferingOut(
            id=str(offering_id),
            subject_name=name,
            subject_code=code,
            groups=groups[offering_id],
            semester=f"{semester.year} {TERM_NAMES[semester.term]}",
        )
        for offering_id, name, code, semester in rows
    }
