"""Assignments: offering-scoped creation, scanned file submissions, late policy and grading (§6, D-092)."""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import ColumnElement, and_, exists, func, or_, select, true
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.jobs import JobQueue
from app.core.ratelimit import RateLimit, enforce_rate_limit
from app.core.storage import ObjectStorage, StorageUnavailableError
from app.core.time import baku_today, utc_now
from app.core.uploads import (
    PREVIEWABLE,
    allowed_extensions,
    allowed_type,
    content_disposition,
    safe_filename,
)
from app.modules.academics.coursework import (
    CourseOfferingOut,
    CourseRole,
    attending,
    course_role,
    offering_labels,
    teaching,
)
from app.modules.academics.models import (
    AcademicGroup,
    CourseOffering,
    Enrollment,
    EnrollmentStatus,
    Semester,
)
from app.modules.assignments.models import (
    Assignment,
    AssignmentFile,
    AssignmentGrade,
    AssignmentSubmission,
    LatePolicy,
    SubmissionStatus,
)
from app.modules.assignments.schemas import (
    AssignmentCreateIn,
    AssignmentDetailOut,
    AssignmentGradeIn,
    AssignmentPresignOut,
    AssignmentSummaryOut,
    FileDownloadOut,
    GradeOut,
    MySubmissionOut,
    StudentOut,
    SubmissionDetailOut,
    SubmissionFileOut,
    SubmissionRowOut,
)
from app.modules.audit.models import AuditAction
from app.modules.audit.service import record_audit
from app.modules.chat.models import ScanStatus
from app.modules.users.models import User
from app.modules.users.service import CurrentUser

MANAGE = "assignments.manage"
MAX_FILE_SIZE = 25 * 1024 * 1024
UPLOAD_TTL = timedelta(minutes=10)
DOWNLOAD_TTL = timedelta(minutes=1)
UPLOAD_LIMIT = RateLimit("assignment_upload", limit=30, window_seconds=3600)
LIST_LIMIT = 200


def effective_points(assignment: Assignment, raw: Decimal, *, is_late: bool) -> Decimal:
    """The points that count: the teacher's number, reduced by the late penalty of a late submission."""
    if not is_late or assignment.late_policy is not LatePolicy.PENALIZE:
        return raw
    return (raw * (Decimal("100") - assignment.late_penalty_percent) / Decimal("100")).quantize(
        Decimal("0.01")
    )


def submission_blocker(
    assignment: Assignment, now: datetime, *, graded: bool, role: CourseRole
) -> str | None:
    """Why this person cannot submit now, or ``None`` (D-092)."""
    if role != "student":
        return "not_student"
    if assignment.available_from and now < assignment.available_from:
        return "not_available"
    if graded:
        return "graded"
    if (
        assignment.deadline
        and now > assignment.deadline
        and assignment.late_policy is LatePolicy.REJECT
    ):
        return "closed"
    return None


class AssignmentService:
    def __init__(
        self, session: AsyncSession, storage: ObjectStorage, cache: Redis, jobs: JobQueue
    ) -> None:
        self.session = session
        self.storage = storage
        self.cache = cache
        self.jobs = jobs

    # --- who sees what -----------------------------------------------------------------------

    def _managed(self, user: CurrentUser) -> ColumnElement[bool]:
        if user.has_permission(MANAGE):
            return true()
        return Assignment.course_offering_id.in_(teaching(user))

    def _visible(self, user: CurrentUser) -> ColumnElement[bool]:
        """Managers see every assignment of their offerings; students see those that have opened."""
        opened = and_(
            Assignment.course_offering_id.in_(attending(user)),
            or_(Assignment.available_from.is_(None), Assignment.available_from <= utc_now()),
        )
        return or_(self._managed(user), opened)

    async def offerings_for_creation(self, user: CurrentUser) -> list[CourseOfferingOut]:
        """Offerings the user may add work to: those they teach, or any for staff, while their semester runs
        or has not started (a finished semester takes no new work)."""
        scope = true() if user.has_permission(MANAGE) else CourseOffering.id.in_(teaching(user))
        today = baku_today()
        ids = set(
            await self.session.scalars(
                select(CourseOffering.id)
                .join(Semester, Semester.id == CourseOffering.semester_id)
                .where(scope, Semester.ends_on >= today)
            )
        )
        found = await offering_labels(self.session, ids)
        return sorted(found.values(), key=lambda o: (o.subject_name, o.semester, o.groups))

    # --- reading -----------------------------------------------------------------------------

    def _summary_query(self, user: CurrentUser) -> Any:
        enrolled = (
            select(func.count())
            .where(
                Enrollment.course_offering_id == Assignment.course_offering_id,
                Enrollment.status != EnrollmentStatus.DROPPED,
            )
            .correlate(Assignment)
            .scalar_subquery()
        )
        submitted = (
            select(func.count())
            .where(AssignmentSubmission.assignment_id == Assignment.id)
            .correlate(Assignment)
            .scalar_subquery()
        )
        graded = (
            select(func.count())
            .select_from(AssignmentGrade)
            .join(AssignmentSubmission, AssignmentSubmission.id == AssignmentGrade.submission_id)
            .where(AssignmentSubmission.assignment_id == Assignment.id)
            .correlate(Assignment)
            .scalar_subquery()
        )
        mine = (
            select(AssignmentSubmission.id)
            .where(
                AssignmentSubmission.assignment_id == Assignment.id,
                AssignmentSubmission.student_id == user.id,
            )
            .correlate(Assignment)
            .scalar_subquery()
        )
        my_grade = exists().where(AssignmentGrade.submission_id == mine)
        managed = Assignment.course_offering_id.in_(teaching(user))
        return select(
            Assignment,
            (true() if user.has_permission(MANAGE) else managed).label("manages"),
            enrolled,
            submitted,
            graded,
            mine.label("mine"),
            my_grade.label("my_graded"),
        ).where(self._visible(user))

    def _summary(
        self, row: Any, offerings: dict[uuid.UUID, CourseOfferingOut]
    ) -> AssignmentSummaryOut:
        assignment, manages, enrolled, submitted, graded, mine, my_graded = row
        return AssignmentSummaryOut(
            id=str(assignment.id),
            offering=offerings[assignment.course_offering_id],
            title=assignment.title,
            available_from=assignment.available_from,
            deadline=assignment.deadline,
            max_points=assignment.max_points,
            late_policy=assignment.late_policy,
            late_penalty_percent=assignment.late_penalty_percent,
            can_manage=bool(manages),
            my_status=None
            if manages
            else ("graded" if my_graded else "submitted" if mine else "not_submitted"),
            enrolled_count=enrolled if manages else None,
            submitted_count=submitted if manages else None,
            graded_count=graded if manages else None,
        )

    async def assignments(
        self, user: CurrentUser, offering_id: uuid.UUID | None
    ) -> list[AssignmentSummaryOut]:
        query = self._summary_query(user)
        if offering_id is not None:
            query = query.where(Assignment.course_offering_id == offering_id)
        rows = list(
            await self.session.execute(
                query.order_by(Assignment.created_at.desc(), Assignment.id.desc()).limit(LIST_LIMIT)
            )
        )
        offerings = await offering_labels(self.session, {row[0].course_offering_id for row in rows})
        return [self._summary(row, offerings) for row in rows]

    async def _readable(
        self, user: CurrentUser, assignment_id: uuid.UUID
    ) -> tuple[Any, CourseRole]:
        row = (
            await self.session.execute(
                self._summary_query(user).where(Assignment.id == assignment_id)
            )
        ).first()
        if row is None:
            raise AppError("assignments.not_found", 404)
        role = await course_role(self.session, user, row[0].course_offering_id, MANAGE)
        assert role is not None
        return row, role

    async def detail(self, user: CurrentUser, assignment_id: uuid.UUID) -> AssignmentDetailOut:
        row, role = await self._readable(user, assignment_id)
        assignment: Assignment = row[0]
        offerings = await offering_labels(self.session, {assignment.course_offering_id})
        summary = self._summary(row, offerings)
        mine = None
        submission = None
        if role != "manager":
            submission = await self.session.scalar(
                select(AssignmentSubmission).where(
                    AssignmentSubmission.assignment_id == assignment_id,
                    AssignmentSubmission.student_id == user.id,
                )
            )
            if submission is not None:
                mine = await self._mine(submission)
        blocker = submission_blocker(
            assignment, utc_now(), graded=bool(mine and mine.grade), role=role
        )
        return AssignmentDetailOut(
            **summary.model_dump(),
            instructions=assignment.instructions,
            can_submit=blocker is None,
            submit_blocked=None if blocker in (None, "not_student") else blocker,
            my_submission=mine,
        )

    async def _files(self, submission_id: uuid.UUID) -> list[SubmissionFileOut]:
        files = await self.session.scalars(
            select(AssignmentFile)
            .where(AssignmentFile.submission_id == submission_id)
            .order_by(AssignmentFile.version.desc())
        )
        return [
            SubmissionFileOut(
                id=str(file.id),
                version=file.version or 0,
                filename=file.filename,
                mime=file.mime,
                size_bytes=file.size_bytes,
                status=file.scan_status,
                previewable=file.mime in PREVIEWABLE,
                created_at=file.created_at,
            )
            for file in files
        ]

    async def _grade(self, submission_id: uuid.UUID) -> GradeOut | None:
        grade = await self.session.scalar(
            select(AssignmentGrade).where(AssignmentGrade.submission_id == submission_id)
        )
        if grade is None:
            return None
        return GradeOut(
            points=grade.points,
            raw_points=grade.raw_points,
            feedback=grade.feedback,
            graded_at=grade.graded_at,
        )

    async def _mine(self, submission: AssignmentSubmission) -> MySubmissionOut:
        assert submission.submitted_at is not None
        return MySubmissionOut(
            id=str(submission.id),
            submitted_at=submission.submitted_at,
            is_late=submission.is_late,
            files=await self._files(submission.id),
            grade=await self._grade(submission.id),
        )

    # --- creating ----------------------------------------------------------------------------

    async def create(self, user: CurrentUser, data: AssignmentCreateIn) -> AssignmentDetailOut:
        role = await course_role(self.session, user, data.course_offering_id, MANAGE)
        if role != "manager":
            raise AppError("assignments.offering_not_found", 404)
        assignment = Assignment(**data.model_dump(), created_by=user.id)
        self.session.add(assignment)
        await self.session.flush()
        record_audit(
            self.session,
            AuditAction.ASSIGNMENT_CREATED,
            actor_id=user.id,
            target_type="assignment",
            target_id=assignment.id,
            details={"course_offering_id": str(data.course_offering_id)},
        )
        await self.session.commit()
        return await self.detail(user, assignment.id)

    # --- submitting --------------------------------------------------------------------------

    async def _student_context(
        self, user: CurrentUser, assignment_id: uuid.UUID
    ) -> tuple[Assignment, bool]:
        """The assignment and whether it is graded for this student; only active students may submit."""
        row, role = await self._readable(user, assignment_id)
        assignment: Assignment = row[0]
        if role != "student":
            raise AppError("assignments.not_a_student", 403)
        graded = bool(row[6])
        blocker = submission_blocker(assignment, utc_now(), graded=graded, role=role)
        if blocker is not None:
            raise AppError(f"assignments.{blocker}", 409)
        return assignment, graded

    async def presign(
        self, user: CurrentUser, assignment_id: uuid.UUID, filename: str, mime: str, size: int
    ) -> AssignmentPresignOut:
        await self._student_context(user, assignment_id)
        kind = allowed_type(filename, mime)
        if kind is None:
            raise AppError(
                "assignments.type_not_allowed", 422, details={"allowed": allowed_extensions()}
            )
        if not 0 < size <= MAX_FILE_SIZE:
            raise AppError("assignments.too_large", 422, details={"max_bytes": MAX_FILE_SIZE})
        await enforce_rate_limit(self.cache, UPLOAD_LIMIT, str(user.id))
        key = f"assignments/{assignment_id}/{uuid.uuid4().hex}"
        try:
            url = await self.storage.presign_put(key, kind, UPLOAD_TTL)
        except StorageUnavailableError as exc:
            raise AppError("assignments.storage_unavailable", 503) from exc
        file = AssignmentFile(
            assignment_id=assignment_id,
            student_id=user.id,
            object_key=key,
            filename=safe_filename(filename),
            mime=kind,
            size_bytes=size,
        )
        self.session.add(file)
        await self.session.commit()
        return AssignmentPresignOut(
            upload_id=str(file.id),
            url=url,
            expires_at=utc_now() + UPLOAD_TTL,
            headers={"Content-Type": kind},
        )

    async def submit(
        self, user: CurrentUser, assignment_id: uuid.UUID, upload_id: uuid.UUID
    ) -> AssignmentDetailOut:
        file = await self.session.get(AssignmentFile, upload_id, with_for_update=True)
        if file is None or file.student_id != user.id or file.assignment_id != assignment_id:
            raise AppError("assignments.upload_not_found", 422)
        if file.submission_id is not None:
            # The same upload sent twice (double click, retry) returns the same result.
            return await self.detail(user, assignment_id)
        assignment, _ = await self._student_context(user, assignment_id)
        try:
            stored = await self.storage.head(file.object_key)
        except StorageUnavailableError as exc:
            raise AppError("assignments.storage_unavailable", 503) from exc
        if stored is None:
            raise AppError("assignments.upload_missing", 422)
        if stored != file.size_bytes:
            raise AppError("assignments.upload_size_mismatch", 422)

        now = utc_now()
        await self.session.execute(
            insert(AssignmentSubmission)
            .values(assignment_id=assignment_id, student_id=user.id)
            .on_conflict_do_nothing(index_elements=["assignment_id", "student_id"])
        )
        submission = await self.session.scalar(
            select(AssignmentSubmission)
            .where(
                AssignmentSubmission.assignment_id == assignment_id,
                AssignmentSubmission.student_id == user.id,
            )
            .with_for_update()
        )
        assert submission is not None
        newest = await self.session.scalar(
            select(func.coalesce(func.max(AssignmentFile.version), 0)).where(
                AssignmentFile.submission_id == submission.id
            )
        )
        file.submission_id = submission.id
        file.version = (newest or 0) + 1
        file.scan_after = now
        submission.status = SubmissionStatus.SUBMITTED
        submission.submitted_at = now
        submission.is_late = bool(assignment.deadline and now > assignment.deadline)
        await self.session.commit()
        await self.jobs.scan_attachments()
        return await self.detail(user, assignment_id)

    async def download(
        self, user: CurrentUser, file_id: uuid.UUID, *, inline: bool
    ) -> FileDownloadOut:
        file = await self.session.get(AssignmentFile, file_id)
        if file is None or file.submission_id is None or file.assignment_id is None:
            raise AppError("assignments.not_found", 404)
        assignment = await self.session.get(Assignment, file.assignment_id)
        assert assignment is not None
        role = await course_role(self.session, user, assignment.course_offering_id, MANAGE)
        if role != "manager" and file.student_id != user.id:
            raise AppError("assignments.not_found", 404)
        if file.scan_status is not ScanStatus.CLEAN:
            raise AppError("assignments.file_not_available", 409)
        try:
            url = await self.storage.presign_get(
                file.object_key,
                content_type=file.mime,
                disposition=content_disposition(file.filename, inline and file.mime in PREVIEWABLE),
                expires=DOWNLOAD_TTL,
            )
        except StorageUnavailableError as exc:
            raise AppError("assignments.storage_unavailable", 503) from exc
        return FileDownloadOut(url=url, expires_at=utc_now() + DOWNLOAD_TTL)

    # --- the teacher's side ------------------------------------------------------------------

    async def _managed_assignment(self, user: CurrentUser, assignment_id: uuid.UUID) -> Assignment:
        row, role = await self._readable(user, assignment_id)
        if role != "manager":
            raise AppError("auth.forbidden", 403)
        assignment: Assignment = row[0]
        return assignment

    async def submissions(
        self, user: CurrentUser, assignment_id: uuid.UUID
    ) -> list[SubmissionRowOut]:
        assignment = await self._managed_assignment(user, assignment_id)
        newest = (
            select(AssignmentFile.scan_status)
            .where(AssignmentFile.submission_id == AssignmentSubmission.id)
            .order_by(AssignmentFile.version.desc())
            .limit(1)
            .correlate(AssignmentSubmission)
            .scalar_subquery()
        )
        rows = await self.session.execute(
            select(User, AcademicGroup.code, AssignmentSubmission, AssignmentGrade.points, newest)
            .join(Enrollment, Enrollment.user_id == User.id)
            .outerjoin(AcademicGroup, AcademicGroup.id == User.academic_group_id)
            .outerjoin(
                AssignmentSubmission,
                and_(
                    AssignmentSubmission.student_id == User.id,
                    AssignmentSubmission.assignment_id == assignment_id,
                ),
            )
            .outerjoin(AssignmentGrade, AssignmentGrade.submission_id == AssignmentSubmission.id)
            .where(
                Enrollment.course_offering_id == assignment.course_offering_id,
                Enrollment.status != EnrollmentStatus.DROPPED,
            )
            .order_by(User.display_name)
        )
        return [
            SubmissionRowOut(
                student=StudentOut(
                    id=str(person.id), display_name=person.display_name, group_code=group
                ),
                submission_id=str(submission.id) if submission else None,
                submitted_at=submission.submitted_at if submission else None,
                is_late=bool(submission and submission.is_late),
                file_status=status,
                points=points,
                graded=points is not None,
            )
            for person, group, submission, points, status in rows
        ]

    async def submission(self, user: CurrentUser, submission_id: uuid.UUID) -> SubmissionDetailOut:
        submission = await self.session.get(AssignmentSubmission, submission_id)
        if submission is None:
            raise AppError("assignments.submission_not_found", 404)
        assignment = await self._managed_assignment(user, submission.assignment_id)
        student = await self.session.get(User, submission.student_id)
        assert student is not None
        assert submission.submitted_at is not None
        group = (
            await self.session.scalar(
                select(AcademicGroup.code).where(AcademicGroup.id == student.academic_group_id)
            )
            if student.academic_group_id
            else None
        )
        return SubmissionDetailOut(
            id=str(submission.id),
            assignment_id=str(assignment.id),
            assignment_title=assignment.title,
            max_points=assignment.max_points,
            late_policy=assignment.late_policy,
            late_penalty_percent=assignment.late_penalty_percent,
            student=StudentOut(
                id=str(student.id), display_name=student.display_name, group_code=group
            ),
            submitted_at=submission.submitted_at,
            is_late=submission.is_late,
            files=await self._files(submission.id),
            grade=await self._grade(submission.id),
        )

    async def grade(
        self, user: CurrentUser, submission_id: uuid.UUID, data: AssignmentGradeIn
    ) -> SubmissionDetailOut:
        submission = await self.session.get(
            AssignmentSubmission, submission_id, with_for_update=True
        )
        if submission is None:
            raise AppError("assignments.submission_not_found", 404)
        assignment = await self._managed_assignment(user, submission.assignment_id)
        # The limit applies to what the teacher enters, not to the points left after a late penalty.
        if data.points > assignment.max_points:
            raise AppError("assignments.grade_exceeds_maximum", 422)
        grade = await self.session.scalar(
            select(AssignmentGrade).where(AssignmentGrade.submission_id == submission_id)
        )
        regraded = grade is not None
        if grade is None:
            grade = AssignmentGrade(submission_id=submission_id)
            self.session.add(grade)
        grade.raw_points = data.points
        grade.points = effective_points(assignment, data.points, is_late=submission.is_late)
        grade.feedback = data.feedback.strip()
        grade.graded_by = user.id
        submission.status = SubmissionStatus.RETURNED
        # Grades are personal data (§5.4): the audit entry says that a submission was graded, not what it got.
        record_audit(
            self.session,
            AuditAction.ASSIGNMENT_GRADED,
            actor_id=user.id,
            target_type="assignment_submission",
            target_id=submission_id,
            details={"assignment_id": str(assignment.id), "regraded": regraded},
        )
        await self.session.commit()
        return await self.submission(user, submission_id)
