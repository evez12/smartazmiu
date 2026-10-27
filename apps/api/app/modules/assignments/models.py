import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import uuid7


def _enum(enum: type[StrEnum], name: str) -> Enum:
    return Enum(enum, name=name, values_callable=lambda members: [m.value for m in members])


class LatePolicy(StrEnum):
    ACCEPT = "accept"
    PENALIZE = "penalize"
    REJECT = "reject"


class SubmissionStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    RETURNED = "returned"


class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = (
        CheckConstraint("max_points > 0", name="positive_max_points"),
        CheckConstraint(
            "late_penalty_percent >= 0 AND late_penalty_percent <= 100",
            name="late_penalty_percent_range",
        ),
        CheckConstraint(
            "available_from IS NULL OR deadline IS NULL OR deadline > available_from",
            name="assignment_dates_ordered",
        ),
        Index("ix_assignments_course_offering_deadline", "course_offering_id", "deadline"),
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
    max_points: Mapped[Decimal] = mapped_column(
        Numeric(7, 2), default=Decimal("100"), server_default="100"
    )
    late_policy: Mapped[LatePolicy] = mapped_column(
        _enum(LatePolicy, "late_policy"),
        default=LatePolicy.REJECT,
        server_default=LatePolicy.REJECT.value,
    )
    late_penalty_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0"), server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AssignmentSubmission(Base):
    __tablename__ = "assignment_submissions"
    __table_args__ = (
        UniqueConstraint("assignment_id", "student_id"),
        CheckConstraint("size_bytes >= 0", name="non_negative_size_bytes"),
        Index("ix_assignment_submissions_student_status", "student_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[SubmissionStatus] = mapped_column(
        _enum(SubmissionStatus, "submission_status"),
        default=SubmissionStatus.DRAFT,
        server_default=SubmissionStatus.DRAFT.value,
    )
    object_key: Mapped[str | None] = mapped_column(String(300))
    filename: Mapped[str | None] = mapped_column(String(255))
    mime: Mapped[str | None] = mapped_column(String(127))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_late: Mapped[bool] = mapped_column(default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AssignmentGrade(Base):
    __tablename__ = "assignment_grades"
    __table_args__ = (
        UniqueConstraint("submission_id"),
        CheckConstraint("points >= 0", name="non_negative_points"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assignment_submissions.id", ondelete="CASCADE"), index=True
    )
    graded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    points: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    feedback: Mapped[str] = mapped_column(Text, default="", server_default="")
    graded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
