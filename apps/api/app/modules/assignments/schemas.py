import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, Field, PlainSerializer, model_validator

from app.modules.academics.coursework import CourseOfferingOut
from app.modules.assignments.models import LatePolicy
from app.modules.chat.models import ScanStatus


class CourseOfferingListOut(BaseModel):
    items: list[CourseOfferingOut]


# Points and percentages always travel with two decimals, whether just written or read back.
Points = Annotated[
    Decimal, PlainSerializer(lambda value: f"{value:.2f}", return_type=str, when_used="json")
]


class AssignmentCreateIn(BaseModel):
    course_offering_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    instructions: str = Field(default="", max_length=20_000)
    available_from: AwareDatetime | None = None
    deadline: AwareDatetime | None = None
    max_points: Decimal = Field(default=Decimal("100"), gt=0, le=100_000, decimal_places=2)
    late_policy: LatePolicy = LatePolicy.REJECT
    late_penalty_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100, decimal_places=2)

    @model_validator(mode="after")
    def dates_are_ordered(self) -> "AssignmentCreateIn":
        if self.available_from and self.deadline and self.deadline <= self.available_from:
            raise ValueError("deadline must be after available_from")
        if self.late_policy != LatePolicy.PENALIZE and self.late_penalty_percent:
            raise ValueError("late_penalty_percent requires the penalize policy")
        return self


class SubmissionFileOut(BaseModel):
    id: str
    version: int
    filename: str
    mime: str
    size_bytes: int
    status: ScanStatus
    previewable: bool
    created_at: datetime


class GradeOut(BaseModel):
    points: Points
    raw_points: Points
    """What the teacher entered, before the late penalty."""
    feedback: str
    graded_at: datetime


class MySubmissionOut(BaseModel):
    id: str
    submitted_at: datetime
    is_late: bool
    files: list[SubmissionFileOut]
    grade: GradeOut | None


class AssignmentSummaryOut(BaseModel):
    id: str
    offering: CourseOfferingOut
    title: str
    available_from: datetime | None
    deadline: datetime | None
    max_points: Points
    late_policy: LatePolicy
    late_penalty_percent: Points
    can_manage: bool
    my_status: Literal["not_submitted", "submitted", "graded"] | None
    """For students; ``None`` for people who manage the offering."""
    enrolled_count: int | None
    submitted_count: int | None
    graded_count: int | None
    """The three counts are for people who manage the offering."""


class AssignmentListOut(BaseModel):
    items: list[AssignmentSummaryOut]


class AssignmentDetailOut(AssignmentSummaryOut):
    instructions: str
    can_submit: bool
    submit_blocked: str | None
    """Why a student cannot submit now: ``not_available``, ``closed`` or ``graded``."""
    my_submission: MySubmissionOut | None


class AssignmentPresignIn(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    mime: str = Field(min_length=1, max_length=127)
    size: int = Field(ge=1)


class AssignmentPresignOut(BaseModel):
    upload_id: str
    url: str
    """PUT the file here with the given headers before the link expires."""
    expires_at: datetime
    headers: dict[str, str]


class AssignmentSubmissionIn(BaseModel):
    upload_id: uuid.UUID


class AssignmentGradeIn(BaseModel):
    points: Decimal = Field(ge=0, le=100_000, decimal_places=2)
    feedback: str = Field(default="", max_length=20_000)


class StudentOut(BaseModel):
    id: str
    display_name: str
    group_code: str | None


class SubmissionRowOut(BaseModel):
    student: StudentOut
    submission_id: str | None
    submitted_at: datetime | None
    is_late: bool
    file_status: ScanStatus | None
    """The status of the newest file."""
    points: Points | None
    graded: bool


class SubmissionListOut(BaseModel):
    items: list[SubmissionRowOut]


class SubmissionDetailOut(BaseModel):
    id: str
    assignment_id: str
    assignment_title: str
    max_points: Points
    late_policy: LatePolicy
    late_penalty_percent: Points
    student: StudentOut
    submitted_at: datetime
    is_late: bool
    files: list[SubmissionFileOut]
    grade: GradeOut | None


class FileDownloadOut(BaseModel):
    url: str
    expires_at: datetime
