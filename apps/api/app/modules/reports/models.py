"""Reports of messages and people (§5.4, §5.5, §5.7). The moderation console and auto-hiding arrive in Sprint 10;
Sprint 6 records reports and lets staff list and close them (D-070)."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import uuid7


def _enum(enum: type[StrEnum], name: str) -> Enum:
    return Enum(enum, name=name, values_callable=lambda members: [m.value for m in members])


class ReportTarget(StrEnum):
    MESSAGE = "message"
    USER = "user"
    TIP = "tip"


class ReportReason(StrEnum):
    SPAM = "spam"
    HARASSMENT = "harassment"
    HATE = "hate"
    EXAM_LEAK = "exam_leak"
    PRIVACY = "privacy"
    OTHER = "other"


class ReportStatus(StrEnum):
    OPEN = "open"
    ACTIONED = "actioned"
    DISMISSED = "dismissed"


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        # A person reports a target once; repeating it changes nothing (§5.5 "counted once").
        UniqueConstraint("reporter_id", "target_type", "target_id"),
        Index("ix_reports_status_created_at", "status", "created_at"),
        Index("ix_reports_target", "target_type", "target_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    # Kept when the reporter's account is deleted, so a handled report stays understandable.
    reporter_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    target_type: Mapped[ReportTarget] = mapped_column(_enum(ReportTarget, "report_target"))
    # A message's snowflake or a user's UUID, as text.
    target_id: Mapped[str] = mapped_column(String(64))
    # The message's channel, for scoping moderators later (§5.5); NULL for reports of people.
    channel_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("channels.id", ondelete="SET NULL")
    )
    reason: Mapped[ReportReason] = mapped_column(_enum(ReportReason, "report_reason"))
    note: Mapped[str] = mapped_column(String(500), default="", server_default="")
    status: Mapped[ReportStatus] = mapped_column(
        _enum(ReportStatus, "report_status"),
        default=ReportStatus.OPEN,
        server_default=ReportStatus.OPEN.value,
    )
    handled_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
