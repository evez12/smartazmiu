import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
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


def _enum(enum: type[StrEnum], name: str) -> Enum:
    return Enum(enum, name=name, values_callable=lambda members: [m.value for m in members])


class EventStatus(StrEnum):
    PUBLISHED = "published"
    CANCELLED = "cancelled"


class RegistrationStatus(StrEnum):
    GOING = "going"
    CANCELLED = "cancelled"
    """Withdrawn by the attendee, or void because the event was cancelled."""


class CheckInMethod(StrEnum):
    SCAN = "scan"
    """The ticket's QR code (or its text) at the door."""
    MANUAL = "manual"
    """Found by name in the attendee list; audited."""


class Event(AudienceColumns, Base):
    """An event for an audience (§6), published on creation; the audience never changes afterwards."""

    __tablename__ = "events"
    __table_args__ = (
        audience_check(),
        CheckConstraint("ends_at > starts_at", name="times_ordered"),
        CheckConstraint("capacity IS NULL OR capacity > 0", name="positive_capacity"),
        UniqueConstraint("created_by", "idempotency_key"),
        Index("ix_events_starts_at", "starts_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # A campus room links to the map; the free text covers places outside the room registry.
    room_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rooms.id", ondelete="SET NULL"))
    location: Mapped[str] = mapped_column(String(200), default="")
    capacity: Mapped[int | None] = mapped_column(Integer)
    """NULL: no limit."""
    status: Mapped[EventStatus] = mapped_column(
        _enum(EventStatus, "event_status"), default=EventStatus.PUBLISHED
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(100))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EventRecipient(Base):
    """Who the event was announced to: resolved at publication, extended for people who join later."""

    __tablename__ = "event_recipients"

    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EventRegistration(Base):
    """An RSVP and its ticket: the QR code carries this id and a signature (D-051)."""

    __tablename__ = "event_registrations"
    __table_args__ = (UniqueConstraint("event_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[RegistrationStatus] = mapped_column(
        _enum(RegistrationStatus, "registration_status"), default=RegistrationStatus.GOING
    )
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checked_in_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    check_in_method: Mapped[CheckInMethod | None] = mapped_column(
        _enum(CheckInMethod, "check_in_method")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
