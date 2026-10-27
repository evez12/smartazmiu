"""Subject Guide cards (§5.2 flow 5, `course_tips`): structured advice from students who passed a subject."""

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


class WeeklyHours(StrEnum):
    UNDER_2 = "under_2"
    H2_4 = "2_4"
    H4_6 = "4_6"
    H6_10 = "6_10"
    OVER_10 = "over_10"


class TipStatus(StrEnum):
    PENDING = "pending"
    PUBLISHED = "published"
    REJECTED = "rejected"
    HIDDEN = "hidden"


class CourseTip(Base):
    """One per author, subject and semester taken; an edit sends it back to moderation."""

    __tablename__ = "course_tips"
    __table_args__ = (
        UniqueConstraint("author_id", "subject_id", "semester_taken_id"),
        CheckConstraint("difficulty BETWEEN 1 AND 5", name="difficulty_range"),
        Index("ix_course_tips_subject_id_status", "subject_id", "status"),
        Index("ix_course_tips_status_updated_at", "status", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"))
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    semester_taken_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("semesters.id"))
    difficulty: Mapped[int] = mapped_column(SmallInteger)
    weekly_hours: Mapped[WeeklyHours] = mapped_column(_enum(WeeklyHours, "tip_weekly_hours"))
    key_topics: Mapped[str] = mapped_column(Text)
    # [{"title": str, "url": str | None, "material_id": str | None}]
    resources: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    exam_advice: Mapped[str] = mapped_column(Text)
    retrospective: Mapped[str] = mapped_column(Text)
    status: Mapped[TipStatus] = mapped_column(
        _enum(TipStatus, "tip_status"),
        default=TipStatus.PENDING,
        server_default=TipStatus.PENDING.value,
    )
    upvotes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Staff only: why it was rejected or hidden. Never in a payload for students.
    moderation_note: Mapped[str] = mapped_column(String(500), default="", server_default="")
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TipUpvote(Base):
    __tablename__ = "tip_upvotes"

    tip_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course_tips.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
