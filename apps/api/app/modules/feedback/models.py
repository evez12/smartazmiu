"""Feedback from the pilot form (D-074): what people tell the team, seen only by staff."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import uuid7


def _enum(enum: type[StrEnum], name: str) -> Enum:
    return Enum(enum, name=name, values_callable=lambda members: [m.value for m in members])


class FeedbackCategory(StrEnum):
    PROBLEM = "problem"
    SUGGESTION = "suggestion"
    QUESTION = "question"
    OTHER = "other"


class FeedbackStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (Index("ix_feedback_status_created_at", "status", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    category: Mapped[FeedbackCategory] = mapped_column(_enum(FeedbackCategory, "feedback_category"))
    message: Mapped[str] = mapped_column(String(2000))
    # The app path the form was opened from, so a problem can be reproduced; never a full URL with a query.
    page: Mapped[str] = mapped_column(String(300), default="", server_default="")
    contact_ok: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    status: Mapped[FeedbackStatus] = mapped_column(
        _enum(FeedbackStatus, "feedback_status"),
        default=FeedbackStatus.OPEN,
        server_default=FeedbackStatus.OPEN.value,
    )
    handled_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
