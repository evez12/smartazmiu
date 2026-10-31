import uuid
from datetime import datetime
from typing import Any

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from app.modules.academics.coursework import CourseOfferingOut
from app.modules.assignments.schemas import StudentOut
from app.modules.quizzes.models import AttemptStatus, QuestionType

MAX_TIME_LIMIT_SECONDS = 8 * 3600
MAX_OPTIONS = 10


class QuizCreateIn(BaseModel):
    course_offering_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    instructions: str = Field(default="", max_length=20_000)
    available_from: AwareDatetime | None = None
    deadline: AwareDatetime | None = None
    time_limit_seconds: int | None = Field(default=None, ge=60, le=MAX_TIME_LIMIT_SECONDS)
    max_attempts: int = Field(default=1, ge=1, le=10)

    @model_validator(mode="after")
    def dates_are_ordered(self) -> "QuizCreateIn":
        if self.available_from and self.deadline and self.deadline <= self.available_from:
            raise ValueError("deadline must be after available_from")
        return self


class OptionIn(BaseModel):
    id: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    text: str = Field(min_length=1, max_length=500)


class QuestionCreateIn(BaseModel):
    type: QuestionType
    prompt: str = Field(min_length=1, max_length=5_000)
    points: int = Field(default=1, ge=1, le=100)
    options: list[OptionIn] = Field(default_factory=list, max_length=MAX_OPTIONS)
    correct_answer: Any = None
    """An option id (mcq), a list of option ids (multi_select), or a model answer for the teacher (short_answer)."""
    is_required: bool = True

    @model_validator(mode="after")
    def answer_fits_the_type(self) -> "QuestionCreateIn":
        ids = [option.id for option in self.options]
        if self.type is QuestionType.SHORT_ANSWER:
            if self.options:
                raise ValueError("a short answer question has no options")
            if self.correct_answer is not None and not isinstance(self.correct_answer, str):
                raise ValueError("the model answer is text")
            return self
        if len(ids) < 2 or len(set(ids)) != len(ids):
            raise ValueError("at least two options with different ids")
        if self.type is QuestionType.MCQ:
            if self.correct_answer not in ids:
                raise ValueError("the correct answer is one of the options")
            return self
        chosen = self.correct_answer
        if (
            not isinstance(chosen, list)
            or not chosen
            or len(set(chosen)) != len(chosen)
            or not all(isinstance(item, str) and item in ids for item in chosen)
        ):
            raise ValueError("the correct answers are a non-empty list of options")
        return self


class OptionOut(BaseModel):
    id: str
    text: str


class QuestionOut(BaseModel):
    """What a student sees: never the correct answer."""

    id: str
    position: int
    type: QuestionType
    prompt: str
    points: int
    options: list[OptionOut]
    is_required: bool


class ManagerQuestionOut(QuestionOut):
    correct_answer: Any


class AttemptSummaryOut(BaseModel):
    id: str
    attempt_number: int
    status: AttemptStatus
    started_at: datetime
    submitted_at: datetime | None
    score: int | None
    max_score: int | None
    pending_review: bool
    """Open questions wait for a teacher's points, so the score is not final."""


class AttemptOut(AttemptSummaryOut):
    quiz_id: str
    expires_at: datetime | None
    answers: dict[str, Any]
    questions: list[QuestionOut] | None
    """Only while the attempt is in progress."""
    server_time: datetime
    """The server's clock, so the page counts down from it and not from the device's."""


class QuizSummaryOut(BaseModel):
    id: str
    offering: CourseOfferingOut
    title: str
    available_from: datetime | None
    deadline: datetime | None
    time_limit_seconds: int | None
    max_attempts: int
    published: bool
    question_count: int
    can_manage: bool
    attempts_used: int | None
    """For students."""
    best_percent: int | None
    """For students: their best submitted attempt, once graded."""
    students_attempted: int | None
    """For people who manage the offering."""


class QuizListOut(BaseModel):
    items: list[QuizSummaryOut]


class QuizDetailOut(QuizSummaryOut):
    instructions: str
    can_start: bool
    start_blocked: str | None
    """``not_available``, ``closed`` or ``attempt_limit_reached``."""
    my_attempts: list[AttemptSummaryOut]
    questions: list[ManagerQuestionOut] | None
    """Only for people who manage the offering."""


class AnswersIn(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)


class ManualScoresIn(BaseModel):
    scores: dict[str, int]
    """Points for open questions, keyed by question id."""


class AttemptRowOut(AttemptSummaryOut):
    student: StudentOut


class AttemptListOut(BaseModel):
    items: list[AttemptRowOut]


class AttemptReviewOut(AttemptRowOut):
    quiz_id: str
    answers: dict[str, Any]
    manual_scores: dict[str, int]
    questions: list[ManagerQuestionOut]


class DistributionBucket(BaseModel):
    label: str
    count: int


class QuestionStats(BaseModel):
    question_id: str
    position: int
    prompt: str
    type: QuestionType
    correct_percent: int | None
    """For questions graded automatically; ``None`` for open ones."""


class QuizStatsOut(BaseModel):
    submitted_attempts: int
    students: int
    average_percent: int | None
    distribution: list[DistributionBucket]
    questions: list[QuestionStats]
    pending_review: int
