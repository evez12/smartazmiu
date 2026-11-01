from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academics.models import (
    CourseOffering,
    Enrollment,
    EnrollmentStatus,
    Semester,
    Subject,
)
from app.modules.grades.schemas import FinishedCourseOut
from app.modules.users.service import CurrentUser


class GradeService:
    """A student's own results; there is no way to ask for anyone else's (§5.4)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def mine(self, user: CurrentUser) -> list[FinishedCourseOut]:
        rows = await self.session.execute(
            select(Enrollment, Subject, Semester)
            .join(CourseOffering, CourseOffering.id == Enrollment.course_offering_id)
            .join(Subject, Subject.id == CourseOffering.subject_id)
            .join(Semester, Semester.id == CourseOffering.semester_id)
            .where(
                Enrollment.user_id == user.id,
                Enrollment.status == EnrollmentStatus.COMPLETED,
                Enrollment.grade.is_not(None),
            )
            .order_by(Semester.year, Semester.starts_on, Subject.code)
        )
        return [
            FinishedCourseOut(
                enrollment_id=str(enrollment.id),
                subject_id=str(subject.id),
                subject_code=subject.code,
                subject_name=subject.name_az,
                credits=subject.credits,
                semester_year=semester.year,
                semester_term=semester.term,
                score=enrollment.grade,
                passed=bool(enrollment.passed),
            )
            for enrollment, subject, semester in rows.all()
        ]
