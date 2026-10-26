"""Per-user notification settings: channels per category, quiet hours, and the user's push subscriptions."""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, time

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.ids import uuid7
from app.core.time import BAKU
from app.modules.notifications.models import (
    NotificationCategory,
    NotificationPreference,
    PushSubscription,
    QuietHours,
)
from app.modules.notifications.push import allowed_endpoint
from app.modules.notifications.service import DEFAULT_CHANNELS, WITHOUT_EMAIL

DEFAULT_QUIET_START = time(23, 0)
DEFAULT_QUIET_END = time(8, 0)
# Older devices are dropped first; a person rarely has more browsers than this.
MAX_SUBSCRIPTIONS = 10


@dataclass(frozen=True, slots=True)
class Channels:
    push: bool
    email: bool


@dataclass(frozen=True, slots=True)
class QuietWindow:
    enabled: bool
    starts_at: time
    ends_at: time

    def covers(self, moment: datetime) -> bool:
        """Whether ``moment`` falls inside the window in Baku time; a window may span midnight."""
        if not self.enabled or self.starts_at == self.ends_at:
            return False
        local = moment.astimezone(BAKU).time()
        if self.starts_at < self.ends_at:
            return self.starts_at <= local < self.ends_at
        return local >= self.starts_at or local < self.ends_at


DEFAULT_QUIET_WINDOW = QuietWindow(True, DEFAULT_QUIET_START, DEFAULT_QUIET_END)


@dataclass(frozen=True, slots=True)
class NotificationSettings:
    channels: dict[NotificationCategory, Channels]
    quiet_hours: QuietWindow
    devices: int
    """Push subscriptions on record."""


class Preferences:
    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        self.session = session
        self.user_id = user_id

    async def channels(self, category: NotificationCategory) -> Channels:
        row = await self.session.get(NotificationPreference, (self.user_id, category))
        if row is None:
            return Channels(*DEFAULT_CHANNELS[category])
        return Channels(row.push, row.email)

    async def quiet_window(self) -> QuietWindow:
        row = await self.session.get(QuietHours, self.user_id)
        if row is None:
            return DEFAULT_QUIET_WINDOW
        return QuietWindow(row.enabled, row.starts_at, row.ends_at)

    async def read(self) -> NotificationSettings:
        stored = {
            row.category: Channels(row.push, row.email)
            for row in await self.session.scalars(
                select(NotificationPreference).where(NotificationPreference.user_id == self.user_id)
            )
        }
        devices = await self.session.scalars(
            select(PushSubscription.id).where(PushSubscription.user_id == self.user_id)
        )
        return NotificationSettings(
            channels={
                category: stored.get(category, Channels(*DEFAULT_CHANNELS[category]))
                for category in NotificationCategory
            },
            quiet_hours=await self.quiet_window(),
            devices=len(list(devices)),
        )

    async def update(
        self, channels: dict[NotificationCategory, Channels], quiet_hours: QuietWindow
    ) -> NotificationSettings:
        if quiet_hours.enabled and quiet_hours.starts_at == quiet_hours.ends_at:
            raise AppError("notifications.quiet_hours_empty", 422)
        for category, value in channels.items():
            email = value.email and category not in WITHOUT_EMAIL
            await self.session.execute(
                insert(NotificationPreference)
                .values(user_id=self.user_id, category=category, push=value.push, email=email)
                .on_conflict_do_update(
                    index_elements=["user_id", "category"],
                    set_={"push": value.push, "email": email},
                )
            )
        values = {
            "enabled": quiet_hours.enabled,
            "starts_at": quiet_hours.starts_at,
            "ends_at": quiet_hours.ends_at,
        }
        await self.session.execute(
            insert(QuietHours)
            .values(user_id=self.user_id, **values)
            .on_conflict_do_update(index_elements=["user_id"], set_=values)
        )
        await self.session.commit()
        return await self.read()

    async def subscribe(self, endpoint: str, p256dh: str, auth: str, hosts: Iterable[str]) -> None:
        """Registers this browser; an endpoint seen before moves to the user now signed in on it."""
        if not allowed_endpoint(endpoint, list(hosts)):
            raise AppError("notifications.push_endpoint_rejected", 422)
        await self.session.execute(
            insert(PushSubscription)
            .values(id=uuid7(), user_id=self.user_id, endpoint=endpoint, p256dh=p256dh, auth=auth)
            .on_conflict_do_update(
                index_elements=["endpoint"],
                set_={"user_id": self.user_id, "p256dh": p256dh, "auth": auth},
            )
        )
        stale = list(
            await self.session.scalars(
                select(PushSubscription.id)
                .where(PushSubscription.user_id == self.user_id)
                .order_by(PushSubscription.created_at.desc(), PushSubscription.id.desc())
                .offset(MAX_SUBSCRIPTIONS)
            )
        )
        if stale:
            await self.session.execute(
                delete(PushSubscription).where(PushSubscription.id.in_(stale))
            )
        await self.session.commit()

    async def unsubscribe(self, endpoint: str) -> None:
        await self.session.execute(
            delete(PushSubscription).where(
                PushSubscription.endpoint == endpoint, PushSubscription.user_id == self.user_id
            )
        )
        await self.session.commit()
