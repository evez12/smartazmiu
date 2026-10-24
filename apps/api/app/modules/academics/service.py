import uuid
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import baku_today
from app.modules.academics.models import (
    AcademicGroup,
    CourseOffering,
    CourseOfferingGroup,
    CourseOfferingTeacher,
    Enrollment,
    EnrollmentStatus,
    Faculty,
    Semester,
    Specialty,
    Subject,
)
from app.modules.users.models import User


@dataclass(frozen=True, slots=True)
class GroupPlacement:
    group: AcademicGroup
    specialty: Specialty
    faculty: Faculty


@dataclass(slots=True)
class Course:
    offering: CourseOffering
    subject: Subject
    semester: Semester
    group_codes: list[str] = field(default_factory=list)
    teacher_names: list[str] = field(default_factory=list)
    student_count: int = 0


@dataclass(frozen=True, slots=True)
class AcademicOverview:
    placement: GroupPlacement | None
    courses: list[Course]
    """Subjects the user currently takes (active enrollments)."""
    teaching: list[Course]
    """Offerings the user teaches in semesters that have not ended."""


CourseQuery = Select[CourseOffering, Subject, Semester]


def _course_query() -> CourseQuery:
    return (
        select(CourseOffering, Subject, Semester)
        .join(Subject, Subject.id == CourseOffering.subject_id)
        .join(Semester, Semester.id == CourseOffering.semester_id)
    )


class AcademicsService:
    """Read models of the academic registry. Every query is filtered by the requesting user in SQL."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def overview(self, user_id: uuid.UUID) -> AcademicOverview:
        return AcademicOverview(
            placement=await self._placement(user_id),
            courses=await self._courses(
                _course_query()
                .join(Enrollment, Enrollment.course_offering_id == CourseOffering.id)
                .where(Enrollment.user_id == user_id, Enrollment.status == EnrollmentStatus.ACTIVE)
            ),
            teaching=await self._courses(
                _course_query()
                .join(
                    CourseOfferingTeacher,
                    CourseOfferingTeacher.course_offering_id == CourseOffering.id,
                )
                .where(
                    CourseOfferingTeacher.teacher_id == user_id,
                    Semester.ends_on >= baku_today(),
                ),
                with_student_counts=True,
            ),
        )

    async def _placement(self, user_id: uuid.UUID) -> GroupPlacement | None:
        row = (
            await self.session.execute(
                select(AcademicGroup, Specialty, Faculty)
                .join(User, User.academic_group_id == AcademicGroup.id)
                .join(Specialty, Specialty.id == AcademicGroup.specialty_id)
                .join(Faculty, Faculty.id == Specialty.faculty_id)
                .where(User.id == user_id)
            )
        ).one_or_none()
        return GroupPlacement(*row) if row else None

    async def _courses(
        self, query: CourseQuery, *, with_student_counts: bool = False
    ) -> list[Course]:
        rows = await self.session.execute(
            query.order_by(Semester.starts_on.desc(), Subject.name_az, CourseOffering.code)
        )
        courses = [Course(offering, subject, semester) for offering, subject, semester in rows]
        by_id = {course.offering.id: course for course in courses}
        if not by_id:
            return []

        groups = await self.session.execute(
            select(CourseOfferingGroup.course_offering_id, AcademicGroup.code)
            .join(AcademicGroup, AcademicGroup.id == CourseOfferingGroup.academic_group_id)
            .where(CourseOfferingGroup.course_offering_id.in_(by_id))
            .order_by(AcademicGroup.code)
        )
        for offering_id, code in groups:
            by_id[offering_id].group_codes.append(code)

        teachers = await self.session.execute(
            select(CourseOfferingTeacher.course_offering_id, User.display_name)
            .join(User, User.id == CourseOfferingTeacher.teacher_id)
            .where(CourseOfferingTeacher.course_offering_id.in_(by_id))
            .order_by(User.family_name, User.given_name)
        )
        for offering_id, name in teachers:
            by_id[offering_id].teacher_names.append(name)

        if with_student_counts:
            counts: defaultdict[uuid.UUID, int] = defaultdict(int)
            enrolled = await self.session.execute(
                select(Enrollment.course_offering_id, func.count())
                .where(
                    Enrollment.course_offering_id.in_(by_id),
                    Enrollment.status == EnrollmentStatus.ACTIVE,
                )
                .group_by(Enrollment.course_offering_id)
            )
            counts.update({offering_id: count for offering_id, count in enrolled})
            for course in courses:
                course.student_count = counts[course.offering.id]
        return courses
