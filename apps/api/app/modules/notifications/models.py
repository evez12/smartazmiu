import uuid
from datetime import datetime, time
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import uuid7


def _enum(enum: type[StrEnum], name: str) -> Enum:
    return Enum(enum, name=name, values_callable=lambda members: [m.value for m in members])


class NotificationCategory(StrEnum):
    """What a user switches push and e-mail on or off for; chat and mentorship add theirs later."""

    ANNOUNCEMENTS = "announcements"
    EVENTS = "events"
    SCHEDULE = "schedule"
    CHAT = "chat"
    """Mentions and replies to one's messages (§5.6)."""


class NotificationKind(StrEnum):
    ANNOUNCEMENT_PUBLISHED = "announcement.published"
    EVENT_PUBLISHED = "event.published"
    EVENT_CHANGED = "event.changed"
    EVENT_CANCELLED = "event.cancelled"
    SCHEDULE_CHANGED = "schedule.changed"
    CHAT_MENTION = "chat.mention"
    CHAT_REPLY = "chat.reply"


class DeliveryChannel(StrEnum):
    PUSH = "push"
    EMAIL = "email"


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    SUPPRESSED = "suppressed"
    """Not sent on purpose; ``reason`` says why (quiet hours, preference, membership)."""
    FAILED = "failed"
    """Gave up after the last attempt."""


class Notification(Base):
    """One in-app notification; ``dedupe_key`` makes the same event notify a user only once (§5.6)."""

    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("user_id", "dedupe_key"),
        Index("ix_notifications_user_id_id", "user_id", "id"),
        Index("ix_notifications_unread", "user_id", postgresql_where=text("read_at IS NULL")),
    )

    # Set-based fan-out inserts many rows in one statement, so the database generates the id.
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuid7()"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    category: Mapped[NotificationCategory] = mapped_column(
        _enum(NotificationCategory, "notification_category")
    )
    kind: Mapped[NotificationKind] = mapped_column(_enum(NotificationKind, "notification_kind"))
    dedupe_key: Mapped[str] = mapped_column(String(200))
    # What the notification is about: checked again at delivery time and removed with its subject.
    subject_type: Mapped[str] = mapped_column(String(32))
    subject_id: Mapped[uuid.UUID] = mapped_column(index=True)
    title: Mapped[str] = mapped_column(String(300))
    """The subject's own title (user content); the UI adds the localized kind."""
    link: Mapped[str] = mapped_column(String(300))
    """Path inside the app, e.g. ``/announcements/<id>``."""
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationDelivery(Base):
    """A push or e-mail copy of a notification, sent by the worker; at most one per channel."""

    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint("notification_id", "channel"),
        Index(
            "ix_notification_deliveries_pending",
            "not_before",
            postgresql_where=text("status = 'pending'"),
        ),
        Index(
            "ix_notification_deliveries_mail_sent",
            "updated_at",
            postgresql_where=text("channel = 'email' AND status = 'sent'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuid7()"))
    notification_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("notifications.id", ondelete="CASCADE")
    )
    channel: Mapped[DeliveryChannel] = mapped_column(_enum(DeliveryChannel, "delivery_channel"))
    status: Mapped[DeliveryStatus] = mapped_column(
        _enum(DeliveryStatus, "delivery_status"),
        default=DeliveryStatus.PENDING,
        server_default=DeliveryStatus.PENDING.value,
    )
    reason: Mapped[str | None] = mapped_column(String(40))
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    not_before: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PushSubscription(Base):
    """A browser's Web Push endpoint (one per device and browser profile)."""

    __tablename__ = "push_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str] = mapped_column(String(100))
    auth: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NotificationPreference(Base):
    """Channel switches per category; without a row the category's defaults apply."""

    __tablename__ = "notification_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    category: Mapped[NotificationCategory] = mapped_column(
        _enum(NotificationCategory, "notification_category"), primary_key=True
    )
    push: Mapped[bool] = mapped_column(Boolean)
    email: Mapped[bool] = mapped_column(Boolean)


class QuietHours(Base):
    """Push is suppressed inside the window, in Baku time (§5.6); without a row: 23:00–08:00, on."""

    __tablename__ = "notification_quiet_hours"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean)
    starts_at: Mapped[time] = mapped_column(Time)
    ends_at: Mapped[time] = mapped_column(Time)
