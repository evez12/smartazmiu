import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import uuid7
from app.modules.audiences.columns import AudienceColumns, audience_check


class AnnouncementStatus(StrEnum):
    PUBLISHED = "published"
    ARCHIVED = "archived"
    """Taken down by staff; recipients no longer see it."""


class Announcement(AudienceColumns, Base):
    """Published on creation (scheduled announcements are Sprint 20). The audience never changes afterwards."""

    __tablename__ = "announcements"
    __table_args__ = (
        audience_check(),
        UniqueConstraint("created_by", "idempotency_key"),
        Index("ix_announcements_published_at", "published_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[AnnouncementStatus] = mapped_column(
        Enum(
            AnnouncementStatus,
            name="announcement_status",
            values_callable=lambda members: [m.value for m in members],
        ),
        default=AnnouncementStatus.PUBLISHED,
    )
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # After this moment the announcement is no longer active: hidden from lists, no new recipients (§6.1).
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(100))
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AnnouncementRecipient(Base):
    """Who the announcement reached: resolved at publication and extended for people who join later (§6.1)."""

    __tablename__ = "announcement_recipients"

    announcement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("announcements.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
