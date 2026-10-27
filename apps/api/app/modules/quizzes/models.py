import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import uuid7


def _enum(enum: type[StrEnum], name: str) -> Enum:
    return Enum(enum, name=name, values_callable=lambda members: [m.value for m in members])


class QuestionType(StrEnum):
    MCQ = "mcq"
    MULTI_SELECT = "multi_select"
    SHORT_ANSWER = "short_answer"


class AttemptStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    AUTO_SUBMITTED = "auto_submitted"


class Quiz(Base):
    __tablename__ = "quizzes"
    __table_args__ = (
        CheckConstraint(
            "time_limit_seconds IS NULL OR time_limit_seconds > 0", name="positive_time_limit"
        ),
        CheckConstraint("max_attempts > 0", name="positive_max_attempts"),
        Index("ix_quizzes_course_offering_published", "course_offering_id", "published_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    course_offering_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course_offerings.id", ondelete="CASCADE"), index=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(200))
    instructions: Mapped[str] = mapped_column(Text, default="", server_default="")
    available_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    time_limit_seconds: Mapped[int | None] = mapped_column(Integer)
    max_attempts: Mapped[int] = mapped_column(SmallInteger, default=1, server_default="1")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"
    __table_args__ = (
        UniqueConstraint("quiz_id", "position"),
        CheckConstraint("points > 0", name="positive_question_points"),
        Index("ix_quiz_questions_quiz_position", "quiz_id", "position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    quiz_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quizzes.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(SmallInteger)
    type: Mapped[QuestionType] = mapped_column(_enum(QuestionType, "question_type"))
    prompt: Mapped[str] = mapped_column(Text)
    points: Mapped[int] = mapped_column(SmallInteger, default=1, server_default="1")
    options: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, server_default="[]")
    # Kept server-side; never include this field in student-facing schemas.
    correct_answer: Mapped[Any] = mapped_column(JSONB)
    is_required: Mapped[bool] = mapped_column(default=True, server_default="true")


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"
    __table_args__ = (
        UniqueConstraint("quiz_id", "student_id", "attempt_number"),
        CheckConstraint("attempt_number > 0", name="positive_attempt_number"),
        Index("ix_quiz_attempts_quiz_status", "quiz_id", "status"),
        Index("ix_quiz_attempts_student", "student_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    quiz_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quizzes.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    attempt_number: Mapped[int] = mapped_column(SmallInteger)
    status: Mapped[AttemptStatus] = mapped_column(
        _enum(AttemptStatus, "attempt_status"),
        default=AttemptStatus.IN_PROGRESS,
        server_default=AttemptStatus.IN_PROGRESS.value,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    answers: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    score: Mapped[int | None] = mapped_column(Integer)
    max_score: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
