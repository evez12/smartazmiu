import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academics.models import (
    CourseOffering,
    Enrollment,
    EnrollmentStatus,
    Semester,
    SemesterTerm,
    Subject,
)
from app.modules.cabinet.models import (
    CabinetAppeal,
    CabinetConflict,
    CabinetGrade,
    CabinetSemester,
    CabinetStudent,
    CabinetSyncRun,
    SyncOutcome,
)
from app.modules.cabinet.schemas import (
    AppealListOut,
    AppealOut,
    CabinetStudentOut,
    ConflictOut,
    SourceOut,
    SourceState,
    SyncRunListOut,
    SyncRunOut,
    TranscriptCourseOut,
    TranscriptOut,
    TranscriptSemesterOut,
)
from app.modules.users.models import User

MANAGE = "cabinet.manage"
RUNS_SHOWN = 30
CONFLICTS_SHOWN = 500

# Calendar order inside the year a term starts in: the spring of 2026 comes before the fall of 2026.
_TERM_ORDER = {SemesterTerm.SPRING: 0, SemesterTerm.SUMMER: 1, SemesterTerm.FALL: 2}

type SemesterKey = tuple[int, SemesterTerm]
type CourseKey = tuple[str, int, SemesterTerm]


def _semester_order(key: SemesterKey) -> tuple[int, int]:
    return key[0], _TERM_ORDER[key[1]]


class CabinetReadService:
    """What a student may read about themselves, and what staff may read about the sync. Every student query is
    filtered by the requester's own id; no method takes the id of another person (§5.4)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def source(self) -> SourceOut:
        latest = await self.session.scalar(
            select(CabinetSyncRun.outcome).order_by(CabinetSyncRun.finished_at.desc()).limit(1)
        )
        last_success = await self.session.scalar(
            select(CabinetSyncRun.finished_at)
            .where(CabinetSyncRun.outcome == SyncOutcome.SUCCEEDED)
            .order_by(CabinetSyncRun.finished_at.desc())
            .limit(1)
        )
        if latest is SyncOutcome.FAILED:
            return SourceOut(state=SourceState.UNAVAILABLE, last_synced_at=last_success)
        if last_success is None:
            return SourceOut(state=SourceState.NEVER_SYNCED, last_synced_at=None)
        return SourceOut(state=SourceState.OK, last_synced_at=last_success)

    async def transcript(self, user_id: uuid.UUID) -> TranscriptOut:
        source = await self.source()
        student = await self.session.get(CabinetStudent, user_id)
        grades = list(
            await self.session.scalars(select(CabinetGrade).where(CabinetGrade.user_id == user_id))
        )
        summaries = {
            (row.semester_year, row.semester_term): row
            for row in await self.session.scalars(
                select(CabinetSemester).where(CabinetSemester.user_id == user_id)
            )
        }
        conflicts: set[CourseKey] = {
            (row.subject_code, row.semester_year, row.semester_term)
            for row in await self.session.scalars(
                select(CabinetConflict).where(CabinetConflict.user_id == user_id)
            )
        }
        registry = await self._registry_results(user_id, conflicts)

        courses: dict[SemesterKey, list[TranscriptCourseOut]] = {}
        for grade in grades:
            course_key = (grade.subject_code, grade.semester_year, grade.semester_term)
            differs = course_key in conflicts
            score, passed = registry.get(course_key, (grade.score, grade.passed))
            courses.setdefault((grade.semester_year, grade.semester_term), []).append(
                TranscriptCourseOut(
                    subject_code=grade.subject_code,
                    subject_name=grade.subject_name,
                    credits=grade.credits,
                    score=score,
                    passed=passed,
                    differs=differs,
                )
            )
        semesters = []
        for key in sorted(courses.keys() | summaries.keys(), key=_semester_order):
            summary = summaries.get(key)
            semesters.append(
                TranscriptSemesterOut(
                    semester_year=key[0],
                    semester_term=key[1],
                    credits_attempted=summary.credits_attempted if summary else None,
                    credits_earned=summary.credits_earned if summary else None,
                    average=float(summary.average)
                    if summary and summary.average is not None
                    else None,
                    courses=sorted(courses.get(key, []), key=lambda course: course.subject_code),
                )
            )
        return TranscriptOut(
            source=source,
            student=CabinetStudentOut(
                specialty_name=student.specialty_name,
                credits_earned=student.credits_earned,
                cumulative_average=float(student.cumulative_average)
                if student.cumulative_average is not None
                else None,
                synced_at=student.synced_at,
            )
            if student
            else None,
            semesters=semesters,
        )

    async def appeals(self, user_id: uuid.UUID) -> AppealListOut:
        names = {
            row.subject_code: row.subject_name
            for row in await self.session.scalars(
                select(CabinetGrade).where(CabinetGrade.user_id == user_id)
            )
        }
        rows = await self.session.scalars(
            select(CabinetAppeal)
            .where(CabinetAppeal.user_id == user_id)
            .order_by(CabinetAppeal.submitted_on.desc(), CabinetAppeal.reference)
        )
        return AppealListOut(
            source=await self.source(),
            items=[
                AppealOut(
                    reference=row.reference,
                    subject_code=row.subject_code,
                    subject_name=names.get(row.subject_code),
                    semester_year=row.semester_year,
                    semester_term=row.semester_term,
                    status=row.status,
                    submitted_on=row.submitted_on,
                    decided_on=row.decided_on,
                )
                for row in rows
            ],
        )

    async def _registry_results(
        self, user_id: uuid.UUID, conflicts: set[CourseKey]
    ) -> dict[CourseKey, tuple[int, bool]]:
        """The registry result for the courses in conflict, which is what the student is shown."""
        if not conflicts:
            return {}
        rows = await self.session.execute(
            select(Subject.code, Semester.year, Semester.term, Enrollment.grade, Enrollment.passed)
            .join(CourseOffering, CourseOffering.subject_id == Subject.id)
            .join(Semester, Semester.id == CourseOffering.semester_id)
            .join(Enrollment, Enrollment.course_offering_id == CourseOffering.id)
            .where(
                Enrollment.user_id == user_id,
                Enrollment.status == EnrollmentStatus.COMPLETED,
                Enrollment.grade.is_not(None),
            )
        )
        return {
            (code, year, term): (grade, bool(passed))
            for code, year, term, grade, passed in rows
            if grade is not None and (code, year, term) in conflicts
        }

    async def runs(self) -> SyncRunListOut:
        rows = await self.session.scalars(
            select(CabinetSyncRun).order_by(CabinetSyncRun.finished_at.desc()).limit(RUNS_SHOWN)
        )
        return SyncRunListOut(
            source=await self.source(),
            items=[
                SyncRunOut(
                    id=str(run.id),
                    trigger=run.trigger,
                    outcome=run.outcome,
                    started_at=run.started_at,
                    finished_at=run.finished_at,
                    students_synced=run.students_synced,
                    students_not_found=run.students_not_found,
                    students_mismatched=run.students_mismatched,
                    conflicts=run.conflicts,
                    error_code=run.error_code,
                )
                for run in rows
            ],
        )

    async def conflicts(self) -> list[ConflictOut]:
        """Who and which course, never a grade."""
        rows = await self.session.execute(
            select(User.university_id, CabinetConflict)
            .join(User, User.id == CabinetConflict.user_id)
            .order_by(User.university_id, CabinetConflict.subject_code)
            .limit(CONFLICTS_SHOWN)
        )
        return [
            ConflictOut(
                university_id=university_id or "",
                subject_code=conflict.subject_code,
                semester_year=conflict.semester_year,
                semester_term=conflict.semester_term,
                detected_at=conflict.detected_at,
            )
            for university_id, conflict in rows
        ]
