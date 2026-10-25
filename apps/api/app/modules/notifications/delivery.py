"""Sending pending push and e-mail deliveries (ARQ worker).

Each delivery is sent in its own transaction with the row locked (``SKIP LOCKED``), so several workers and
retried jobs never send one twice while it is in flight. Everything that may have changed since the notification
was created (account status, audience membership, the preference, quiet hours) is checked again here (§5.6).
A crash between sending and committing can repeat one message; ARQ jobs are at-least-once (§13.5).
"""

import json
import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.time import utc_now
from app.modules.notifications import messages
from app.modules.notifications.mail import Mailer, MailUnavailableError
from app.modules.notifications.models import (
    DeliveryChannel,
    DeliveryStatus,
    Notification,
    NotificationDelivery,
    PushSubscription,
)
from app.modules.notifications.preferences import Preferences
from app.modules.notifications.push import PushOutcome, PushSender, PushTarget
from app.modules.users.models import User, UserStatus

logger = structlog.get_logger(__name__)

RelevanceCheck = Callable[[AsyncSession, uuid.UUID, uuid.UUID], Awaitable[bool]]
"""``(session, subject_id, user_id)``: whether the user should still hear about the subject."""

MAX_ATTEMPTS = 5
PUSH_TTL_SECONDS = 24 * 3600
# One run handles at most this many deliveries; the next run (or cron tick) continues.
MAX_PER_RUN = 1000


@dataclass(frozen=True, slots=True)
class Result:
    status: DeliveryStatus
    reason: str | None = None

    @classmethod
    def suppressed(cls, reason: str) -> "Result":
        return cls(DeliveryStatus.SUPPRESSED, reason)


SENT = Result(DeliveryStatus.SENT)
RETRY = Result(DeliveryStatus.PENDING, "retry")


class Dispatcher:
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        *,
        push: PushSender | None,
        mailer: Mailer,
        relevance: Mapping[str, RelevanceCheck],
        public_url: str,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.sessionmaker = sessionmaker
        self.push = push
        self.mailer = mailer
        self.relevance = relevance
        self.public_url = public_url.rstrip("/")
        self.clock = clock

    async def run(self) -> int:
        """Sends what is due; returns how many deliveries were handled."""
        handled = 0
        while handled < MAX_PER_RUN and await self._deliver_next():
            handled += 1
        return handled

    async def _deliver_next(self) -> bool:
        async with self.sessionmaker() as session:
            now = self.clock()
            row = (
                await session.execute(
                    select(NotificationDelivery, Notification)
                    .join(Notification, Notification.id == NotificationDelivery.notification_id)
                    .where(
                        NotificationDelivery.status == DeliveryStatus.PENDING,
                        NotificationDelivery.not_before <= now,
                    )
                    .order_by(NotificationDelivery.not_before)
                    .limit(1)
                    .with_for_update(of=NotificationDelivery, skip_locked=True)
                )
            ).first()
            if row is None:
                return False
            delivery, notification = row
            result = await self._attempt(session, delivery, notification, now)
            delivery.attempts += 1
            if result is RETRY and delivery.attempts < MAX_ATTEMPTS:
                delivery.not_before = now + timedelta(minutes=2**delivery.attempts)
            elif result is RETRY:
                delivery.status, delivery.reason = DeliveryStatus.FAILED, "gave_up"
            else:
                delivery.status, delivery.reason = result.status, result.reason
            await session.commit()
            logger.info(
                "notification_delivery",
                channel=delivery.channel.value,
                status=delivery.status.value,
                reason=delivery.reason,
                attempts=delivery.attempts,
            )
            return True

    async def _attempt(
        self,
        session: AsyncSession,
        delivery: NotificationDelivery,
        notification: Notification,
        now: datetime,
    ) -> Result:
        user = await session.get(User, notification.user_id)
        if user is None or user.status is not UserStatus.ACTIVE:
            return Result.suppressed("inactive")
        check = self.relevance[notification.subject_type]
        if not await check(session, notification.subject_id, user.id):
            return Result.suppressed("not_relevant")
        preferences = Preferences(session, user.id)
        channels = await preferences.channels(notification.category)
        url = f"{self.public_url}{notification.link}"
        if delivery.channel is DeliveryChannel.PUSH:
            if not channels.push:
                return Result.suppressed("preference_off")
            if (await preferences.quiet_window()).covers(now):
                return Result.suppressed("quiet_hours")
            return await self._push(session, user.id, notification, url)
        if not channels.email:
            return Result.suppressed("preference_off")
        if not user.email:
            return Result.suppressed("no_address")
        mail = messages.email(
            notification, user.display_name, url, f"{self.public_url}/notifications/settings"
        )
        try:
            await self.mailer.send(user.email, mail.subject, mail.text)
        except MailUnavailableError:
            return RETRY
        return SENT

    async def _push(
        self, session: AsyncSession, user_id: uuid.UUID, notification: Notification, url: str
    ) -> Result:
        if self.push is None:
            return Result.suppressed("push_unavailable")
        subscriptions = list(
            await session.scalars(
                select(PushSubscription).where(PushSubscription.user_id == user_id)
            )
        )
        payload = json.dumps(messages.push_payload(notification, url), ensure_ascii=False).encode()
        outcomes: list[PushOutcome] = []
        for subscription in subscriptions:
            outcome = await self.push.send(
                PushTarget(subscription.endpoint, subscription.p256dh, subscription.auth),
                payload,
                PUSH_TTL_SECONDS,
            )
            if outcome is PushOutcome.GONE:
                await session.execute(
                    delete(PushSubscription).where(PushSubscription.id == subscription.id)
                )
            outcomes.append(outcome)
        if PushOutcome.SENT in outcomes:
            return SENT
        if PushOutcome.RETRY in outcomes:
            return RETRY
        return Result.suppressed("no_device")
