"""Cross-cohort mentorship (§5.2): guide profiles per subject and advice requests."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
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
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import uuid7


def _enum(enum: type[StrEnum], name: str) -> Enum:
    return Enum(enum, name=name, values_callable=lambda members: [m.value for m in members])


class GradeVisibility(StrEnum):
    HIDDEN = "hidden"
    RANGE = "range"
    EXACT = "exact"


class Availability(StrEnum):
    AVAILABLE = "available"
    BUSY = "busy"
    PAUSED = "paused"


class RequestTopic(StrEnum):
    EXAM = "exam"
    WORKLOAD = "workload"
    MATERIALS = "materials"
    TEACHER_EXPECTATIONS = "teacher_expectations"
    PROJECT = "project"
    OTHER = "other"


class RequestStatus(StrEnum):
    OPEN = "open"
    ACCEPTED = "accepted"
    RESOLVED = "resolved"
    DECLINED = "declined"
    EXPIRED = "expired"


class RequestFeedback(StrEnum):
    HELPFUL = "helpful"
    NOT_HELPFUL = "not_helpful"


class MentorProfile(Base):
    """One per person and subject. ``revoked_at`` is set when a results import makes the person ineligible; the
    row stays so the history of requests keeps its guide (no hard delete)."""

    __tablename__ = "mentor_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", "subject_id"),
        Index("ix_mentor_profiles_subject_id_availability", "subject_id", "availability"),
        CheckConstraint("max_open_requests BETWEEN 1 AND 10", name="max_open_requests_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"))
    semester_taken_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("semesters.id"))
    teacher_taken_with_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    grade_visibility: Mapped[GradeVisibility] = mapped_column(
        _enum(GradeVisibility, "grade_visibility"),
        default=GradeVisibility.HIDDEN,
        server_default=GradeVisibility.HIDDEN.value,
    )
    show_teacher: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    bio: Mapped[str] = mapped_column(String(300), default="", server_default="")
    availability: Mapped[Availability] = mapped_column(
        _enum(Availability, "mentor_availability"),
        default=Availability.AVAILABLE,
        server_default=Availability.AVAILABLE.value,
    )
    max_open_requests: Mapped[int] = mapped_column(SmallInteger, default=3, server_default="3")
    helped_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    helpful_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    unhelpful_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    avg_response_minutes: Mapped[int | None] = mapped_column(Integer)
    consented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MentorRequest(Base):
    __tablename__ = "mentor_requests"
    __table_args__ = (
        # One open request per requester, guide and subject (§5.2); "any guide" counts as its own target.
        Index(
            "uq_mentor_requests_open_addressed",
            "requester_id",
            "mentor_id",
            "subject_id",
            unique=True,
            postgresql_where=text("status = 'open' AND mentor_id IS NOT NULL"),
        ),
        Index(
            "uq_mentor_requests_open_unaddressed",
            "requester_id",
            "subject_id",
            unique=True,
            postgresql_where=text("status = 'open' AND mentor_id IS NULL"),
        ),
        Index("ix_mentor_requests_status_created_at", "status", "created_at"),
        Index("ix_mentor_requests_mentor_id_status", "mentor_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"))
    requester_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    mentor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    topic: Mapped[RequestTopic] = mapped_column(_enum(RequestTopic, "mentor_request_topic"))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[RequestStatus] = mapped_column(
        _enum(RequestStatus, "mentor_request_status"),
        default=RequestStatus.OPEN,
        server_default=RequestStatus.OPEN.value,
    )
    dm_channel_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("channels.id", ondelete="SET NULL")
    )
    feedback: Mapped[RequestFeedback | None] = mapped_column(
        _enum(RequestFeedback, "mentor_request_feedback")
    )
    # Private to staff (§5.2); never in a payload for the guide or the requester.
    feedback_note: Mapped[str] = mapped_column(String(1000), default="", server_default="")
    feedback_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
