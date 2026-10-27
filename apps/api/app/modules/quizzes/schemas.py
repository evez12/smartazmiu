import uuid
from datetime import datetime
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.modules.quizzes.models import AttemptStatus, QuestionType


class QuizCreateIn(BaseModel):
    course_offering_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    instructions: str = Field(default="", max_length=20_000)
    available_from: AwareDatetime | None = None
    deadline: AwareDatetime | None = None
    time_limit_seconds: int | None = Field(default=None, gt=0)
    max_attempts: int = Field(default=1, gt=0, le=100)

    @model_validator(mode="after")
    def dates_are_ordered(self) -> "QuizCreateIn":
        if self.available_from and self.deadline and self.deadline <= self.available_from:
            raise ValueError("deadline must be after available_from")
        return self


class QuestionCreateIn(BaseModel):
    type: QuestionType
    prompt: str = Field(min_length=1, max_length=20_000)
    points: int = Field(default=1, gt=0, le=10_000)
    options: list[dict[str, Any]] = Field(default_factory=list)
    correct_answer: Any
    is_required: bool = True


class AnswersIn(BaseModel):
    answers: dict[uuid.UUID, Any] = Field(default_factory=dict)


class QuizOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_offering_id: uuid.UUID
    title: str
    instructions: str
    available_from: datetime | None
    deadline: datetime | None
    time_limit_seconds: int | None
    max_attempts: int
    published_at: datetime | None


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    position: int
    type: QuestionType
    prompt: str
    points: int
    options: list[dict[str, Any]]
    is_required: bool


class AttemptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    quiz_id: uuid.UUID
    student_id: uuid.UUID
    attempt_number: int
    status: AttemptStatus
    started_at: datetime
    expires_at: datetime | None
    submitted_at: datetime | None
    answers: dict[str, Any]
    score: int | None
    max_score: int | None
