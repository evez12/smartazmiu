import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.time import utc_now
from app.modules.assignments.models import (
    Assignment,
    AssignmentGrade,
    AssignmentSubmission,
    LatePolicy,
    SubmissionStatus,
)
from app.modules.assignments.schemas import (
    AssignmentCreateIn,
    AssignmentGradeIn,
    AssignmentSubmissionIn,
)


def submission_is_late(assignment: Assignment, submitted_at: datetime) -> bool:
    return assignment.deadline is not None and submitted_at > assignment.deadline


def effective_points(assignment: Assignment, points: Decimal, *, is_late: bool) -> Decimal:
    if not is_late or assignment.late_policy == LatePolicy.ACCEPT:
        return points
    if assignment.late_policy == LatePolicy.REJECT:
        raise AppError("assignments.late_submission_rejected", 409)
    return points * (Decimal("100") - assignment.late_penalty_percent) / Decimal("100")


class AssignmentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: AssignmentCreateIn, teacher_id: uuid.UUID) -> Assignment:
        assignment = Assignment(**data.model_dump(), created_by=teacher_id)
        self.session.add(assignment)
        await self.session.flush()
        return assignment

    async def submit(
        self, assignment_id: uuid.UUID, student_id: uuid.UUID, data: AssignmentSubmissionIn
    ) -> AssignmentSubmission:
        assignment = await self.session.get(Assignment, assignment_id)
        if assignment is None:
            raise AppError("assignments.not_found", 404)
        now = utc_now()
        if assignment.available_from and now < assignment.available_from:
            raise AppError("assignments.not_available", 409)
        late = submission_is_late(assignment, now)
        if late and assignment.late_policy == LatePolicy.REJECT:
            raise AppError("assignments.late_submission_rejected", 409)
        submission = await self.session.scalar(
            select(AssignmentSubmission).where(
                AssignmentSubmission.assignment_id == assignment_id,
                AssignmentSubmission.student_id == student_id,
            )
        )
        if submission is None:
            submission = AssignmentSubmission(assignment_id=assignment_id, student_id=student_id)
            self.session.add(submission)
        for key, value in data.model_dump().items():
            setattr(submission, key, value)
        submission.status = SubmissionStatus.SUBMITTED
        submission.submitted_at = now
        submission.is_late = late
        await self.session.flush()
        return submission

    async def grade(
        self, submission_id: uuid.UUID, grader_id: uuid.UUID, data: AssignmentGradeIn
    ) -> AssignmentGrade:
        submission = await self.session.get(AssignmentSubmission, submission_id)
        if submission is None:
            raise AppError("assignments.submission_not_found", 404)
        assignment = await self.session.get(Assignment, submission.assignment_id)
        assert assignment is not None
        points = effective_points(assignment, data.points, is_late=submission.is_late)
        if points > assignment.max_points:
            raise AppError("assignments.grade_exceeds_maximum", 422)
        grade = await self.session.scalar(
            select(AssignmentGrade).where(AssignmentGrade.submission_id == submission_id)
        )
        if grade is None:
            grade = AssignmentGrade(submission_id=submission_id)
            self.session.add(grade)
        grade.points = points
        grade.feedback = data.feedback
        grade.graded_by = grader_id
        await self.session.flush()
        return grade
