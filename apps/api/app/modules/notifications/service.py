"""Creating and reading notifications. Fan-out is set-based: one statement per recipient query, never a loop."""

import uuid
from dataclasses import dataclass

from sqlalchemy import Select, and_, func, literal, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.modules.notifications.models import (
    DeliveryChannel,
    Notification,
    NotificationCategory,
    NotificationDelivery,
    NotificationKind,
    NotificationPreference,
)

# Push and e-mail per category until the user changes them; in-app is always on (the bell is the record).
DEFAULT_CHANNELS: dict[NotificationCategory, tuple[bool, bool]] = {
    NotificationCategory.ANNOUNCEMENTS: (True, True),
    NotificationCategory.EVENTS: (True, False),
    NotificationCategory.SCHEDULE: (True, False),
}

MAX_PAGE = 100
# Someone who joins an audience late (a transfer, a late enrollment) is notified in-app about at most this many
# of the items they missed per sync; the rest appear in their lists without a notification (D-054).
LATE_JOIN_CAP = 5


@dataclass(frozen=True, slots=True)
class NotificationSpec:
    category: NotificationCategory
    kind: NotificationKind
    subject_type: str
    subject_id: uuid.UUID
    dedupe_key: str
    """Identifies the event: a user who already has a notification with this key gets no second one."""
    title: str
    link: str


class Notifier:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def notify(
        self, recipients: Select[uuid.UUID], spec: NotificationSpec, *, deliver: bool = True
    ) -> int:
        """Notifies every user ``recipients`` selects, once per ``dedupe_key``; returns how many are new.

        With ``deliver``, push and e-mail deliveries are queued for the channels the user has on now; the worker
        checks the preference, quiet hours and membership again when it sends (§5.6). Without it the
        notification is in-app only. Runs in the caller's transaction.
        """
        source = recipients.subquery()
        columns = Notification.__table__.c
        created = await self.session.scalars(
            insert(Notification)
            .from_select(
                [
                    "user_id",
                    "category",
                    "kind",
                    "dedupe_key",
                    "subject_type",
                    "subject_id",
                    "title",
                    "link",
                ],
                select(
                    source.c[0],
                    literal(spec.category, columns.category.type),
                    literal(spec.kind, columns.kind.type),
                    literal(spec.dedupe_key, columns.dedupe_key.type),
                    literal(spec.subject_type, columns.subject_type.type),
                    literal(spec.subject_id, columns.subject_id.type),
                    literal(spec.title[:300], columns.title.type),
                    literal(spec.link, columns.link.type),
                ).distinct(),
            )
            .on_conflict_do_nothing(index_elements=["user_id", "dedupe_key"])
            .returning(Notification.id)
        )
        ids = list(created)
        if ids and deliver:
            push_default, email_default = DEFAULT_CHANNELS[spec.category]
            for channel, column, default in (
                (DeliveryChannel.PUSH, NotificationPreference.push, push_default),
                (DeliveryChannel.EMAIL, NotificationPreference.email, email_default),
            ):
                await self.session.execute(
                    insert(NotificationDelivery).from_select(
                        ["notification_id", "channel"],
                        select(
                            Notification.id,
                            literal(channel, NotificationDelivery.__table__.c.channel.type),
                        )
                        .outerjoin(
                            NotificationPreference,
                            and_(
                                NotificationPreference.user_id == Notification.user_id,
                                NotificationPreference.category == spec.category,
                            ),
                        )
                        .where(Notification.id.in_(ids), func.coalesce(column, default)),
                    )
                )
        return len(ids)


class LateJoinBudget:
    """Counts backfilled in-app notifications per person across one audience sync (announcements and events)."""

    def __init__(self, cap: int = LATE_JOIN_CAP) -> None:
        self.cap = cap
        self.used: dict[uuid.UUID, int] = {}

    def take(self, user_ids: list[uuid.UUID]) -> list[uuid.UUID]:
        allowed = [user_id for user_id in user_ids if self.used.get(user_id, 0) < self.cap]
        for user_id in allowed:
            self.used[user_id] = self.used.get(user_id, 0) + 1
        return allowed


@dataclass(frozen=True, slots=True)
class InboxPage:
    items: list[Notification]
    next_before: uuid.UUID | None


class Inbox:
    """The signed-in user's own notifications; every query is filtered by ``user_id`` in SQL."""

    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        self.session = session
        self.user_id = user_id

    async def page(self, before: uuid.UUID | None, limit: int) -> InboxPage:
        query = select(Notification).where(Notification.user_id == self.user_id)
        if before is not None:
            # UUIDv7 ids are time-ordered, so the id is the cursor.
            query = query.where(Notification.id < before)
        rows = list(
            await self.session.scalars(query.order_by(Notification.id.desc()).limit(limit + 1))
        )
        more = len(rows) > limit
        items = rows[:limit]
        return InboxPage(items=items, next_before=items[-1].id if more else None)

    async def unread_count(self) -> int:
        count = await self.session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == self.user_id, Notification.read_at.is_(None))
        )
        return count or 0

    async def mark_read(self, notification_id: uuid.UUID) -> Notification | None:
        notification = await self.session.scalar(
            select(Notification).where(
                Notification.id == notification_id, Notification.user_id == self.user_id
            )
        )
        if notification is not None and notification.read_at is None:
            notification.read_at = utc_now()
            await self.session.commit()
        return notification

    async def mark_all_read(self) -> int:
        result = await self.session.execute(
            update(Notification)
            .where(Notification.user_id == self.user_id, Notification.read_at.is_(None))
            .values(read_at=utc_now())
        )
        await self.session.commit()
        return int(getattr(result, "rowcount", 0) or 0)
