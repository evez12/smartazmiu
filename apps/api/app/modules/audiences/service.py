"""Target audiences of announcements and events (§6): who belongs to them, resolved inside SQL."""

import uuid
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import ColumnElement, Select, and_, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.errors import AppError
from app.core.text import like_pattern, normalize_az
from app.core.time import baku_today
from app.modules.academics.models import (
    AcademicGroup,
    CourseOffering,
    CourseOfferingTeacher,
    Enrollment,
    EnrollmentStatus,
    Faculty,
    Semester,
    SemesterTerm,
    Specialty,
    Subject,
)
from app.modules.users.models import PersonType, User, UserStatus

TERM_NAMES = {SemesterTerm.FALL: "Payız", SemesterTerm.SPRING: "Yaz", SemesterTerm.SUMMER: "Yay"}
OPTIONS_LIMIT = 50


class AudienceType(StrEnum):
    UNIVERSITY = "university"
    FACULTY = "faculty"
    SPECIALTY = "specialty"
    GROUP = "group"
    COURSE_OFFERING = "course_offering"


@dataclass(frozen=True, slots=True)
class Audience:
    type: AudienceType
    target_id: uuid.UUID | None
    """NULL for the whole university."""


@dataclass(frozen=True, slots=True)
class AudienceOption:
    id: uuid.UUID
    label: str
    detail: str


def members(audience: Audience) -> Select[uuid.UUID]:
    """Active accounts in the audience, as a ``SELECT user_id``.

    University: every active account. Faculty, specialty, group: the registry students of the groups below it and
    those groups' curators. Course offering: its students (unless dropped) and its teachers.
    """
    active = User.status == UserStatus.ACTIVE
    if audience.type is AudienceType.UNIVERSITY:
        return select(User.id).where(active)
    if audience.type is AudienceType.COURSE_OFFERING:
        students = select(Enrollment.user_id).where(
            Enrollment.course_offering_id == audience.target_id,
            Enrollment.status != EnrollmentStatus.DROPPED,
        )
        teachers = select(CourseOfferingTeacher.teacher_id).where(
            CourseOfferingTeacher.course_offering_id == audience.target_id
        )
        return select(User.id).where(active, User.id.in_(students.union(teachers)))
    groups = _groups(audience)
    return select(User.id).where(
        active,
        or_(
            and_(User.person_type == PersonType.STUDENT, User.academic_group_id.in_(groups)),
            User.id.in_(select(AcademicGroup.curator_id).where(AcademicGroup.id.in_(groups))),
        ),
    )


def is_member(audience: Audience, user_id: uuid.UUID) -> Select[bool]:
    return select(members(audience).where(User.id == user_id).exists())


def _groups(audience: Audience) -> Select[uuid.UUID]:
    if audience.type is AudienceType.GROUP:
        return select(AcademicGroup.id).where(AcademicGroup.id == audience.target_id)
    if audience.type is AudienceType.SPECIALTY:
        return select(AcademicGroup.id).where(AcademicGroup.specialty_id == audience.target_id)
    return (
        select(AcademicGroup.id)
        .join(Specialty, Specialty.id == AcademicGroup.specialty_id)
        .where(Specialty.faculty_id == audience.target_id)
    )


def _folded(column: InstrumentedAttribute[str]) -> ColumnElement[str]:
    # Same folding as normalize_az, in SQL: typed without Azerbaijani letters still matches (§13.1).
    return func.lower(func.translate(column, "ƏİIÖÜÇŞĞəıöüçşğ", "eiiouscgeiouscg"))


class Audiences:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def validate(self, audience: Audience) -> None:
        """The target exists and fits the type; the university needs none."""
        if audience.type is AudienceType.UNIVERSITY:
            if audience.target_id is not None:
                raise AppError("audience.invalid", 422)
            return
        if audience.target_id is None or not await self.labels([audience]):
            raise AppError("audience.invalid", 422)

    async def labels(self, audiences: list[Audience]) -> dict[Audience, AudienceOption]:
        """Names of the targets, for lists and detail pages (the university has no target)."""
        found: dict[Audience, AudienceOption] = {}
        by_type: dict[AudienceType, set[uuid.UUID]] = {}
        for audience in audiences:
            if audience.target_id is not None:
                by_type.setdefault(audience.type, set()).add(audience.target_id)
        for kind, ids in by_type.items():
            for option in await self._options(kind, ids=ids):
                found[Audience(kind, option.id)] = option
        return found

    async def options(self, kind: AudienceType, query: str = "") -> list[AudienceOption]:
        return await self._options(kind, query=query)

    async def _options(
        self, kind: AudienceType, *, ids: set[uuid.UUID] | None = None, query: str = ""
    ) -> list[AudienceOption]:
        pattern = like_pattern(normalize_az(query).folded) if query.strip() else None
        if kind is AudienceType.FACULTY:
            rows = select(Faculty.id, Faculty.name_az, literal(""), Faculty.code).order_by(
                Faculty.name_az
            )
            searched: list[InstrumentedAttribute[str]] = [Faculty.name_az, Faculty.code]
            id_column = Faculty.id
        elif kind is AudienceType.SPECIALTY:
            rows = (
                select(Specialty.id, Specialty.name_az, Faculty.name_az, Specialty.code)
                .join(Faculty, Faculty.id == Specialty.faculty_id)
                .order_by(Specialty.name_az)
            )
            searched = [Specialty.name_az, Specialty.code]
            id_column = Specialty.id
        elif kind is AudienceType.GROUP:
            rows = (
                select(AcademicGroup.id, AcademicGroup.code, Specialty.name_az, literal(""))
                .join(Specialty, Specialty.id == AcademicGroup.specialty_id)
                .order_by(AcademicGroup.code)
            )
            searched = [AcademicGroup.code, Specialty.name_az]
            id_column = AcademicGroup.id
        elif kind is AudienceType.COURSE_OFFERING:
            rows = (
                select(
                    CourseOffering.id,
                    Subject.name_az,
                    CourseOffering.code,
                    func.concat(Semester.year, " ", Semester.term),
                )
                .join(Subject, Subject.id == CourseOffering.subject_id)
                .join(Semester, Semester.id == CourseOffering.semester_id)
                .order_by(Semester.starts_on.desc(), Subject.name_az, CourseOffering.code)
            )
            searched = [Subject.name_az, Subject.code, CourseOffering.code]
            id_column = CourseOffering.id
            if ids is None:
                # The picker offers offerings that are running or still to come.
                rows = rows.where(Semester.ends_on >= baku_today())
        else:
            return []
        if ids is not None:
            rows = rows.where(id_column.in_(ids))
        if pattern is not None:
            rows = rows.where(
                or_(*(_folded(column).like(pattern, escape="\\") for column in searched))
            )
        result = await self.session.execute(rows.limit(None if ids is not None else OPTIONS_LIMIT))
        return [_option(kind, *row) for row in result]


def _option(kind: AudienceType, id_: uuid.UUID, name: str, extra: str, code: str) -> AudienceOption:
    if kind is AudienceType.SPECIALTY:
        return AudienceOption(id_, f"{name} ({code})", extra)
    if kind is AudienceType.COURSE_OFFERING:
        year, _, term = code.partition(" ")
        return AudienceOption(id_, f"{name} · {extra}", f"{year} {TERM_NAMES[SemesterTerm(term)]}")
    return AudienceOption(id_, name, extra)
