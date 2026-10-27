import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.modules.assignments.models import LatePolicy, SubmissionStatus


class AssignmentCreateIn(BaseModel):
    course_offering_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    instructions: str = Field(default="", max_length=20_000)
    available_from: AwareDatetime | None = None
    deadline: AwareDatetime | None = None
    max_points: Decimal = Field(default=Decimal("100"), gt=0, le=100_000)
    late_policy: LatePolicy = LatePolicy.REJECT
    late_penalty_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)

    @model_validator(mode="after")
    def dates_are_ordered(self) -> "AssignmentCreateIn":
        if self.available_from and self.deadline and self.deadline <= self.available_from:
            raise ValueError("deadline must be after available_from")
        if self.late_policy != LatePolicy.PENALIZE and self.late_penalty_percent:
            raise ValueError("late_penalty_percent requires the penalize policy")
        return self


class AssignmentSubmissionIn(BaseModel):
    object_key: str = Field(min_length=1, max_length=300)
    filename: str = Field(min_length=1, max_length=255)
    mime: str = Field(min_length=1, max_length=127)
    size_bytes: int = Field(ge=1)


class AssignmentGradeIn(BaseModel):
    points: Decimal = Field(ge=0, le=100_000)
    feedback: str = Field(default="", max_length=20_000)


class AssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_offering_id: uuid.UUID
    title: str
    instructions: str
    available_from: datetime | None
    deadline: datetime | None
    max_points: Decimal
    late_policy: LatePolicy
    late_penalty_percent: Decimal


class SubmissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    assignment_id: uuid.UUID
    student_id: uuid.UUID
    status: SubmissionStatus
    filename: str | None
    mime: str | None
    size_bytes: int | None
    submitted_at: datetime | None
    is_late: bool


class GradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    points: Decimal
    feedback: str
    graded_by: uuid.UUID | None
    graded_at: datetime
