"""Sending pending push and e-mail deliveries (ARQ worker).

Each delivery is sent in its own transaction with the row locked (``SKIP LOCKED``), so several workers and
retried jobs never send one twice while it is in flight. Everything that may have changed since the notification
was created (account status, audience membership, the preference, quiet hours) is checked again here (§5.6).
A crash between sending and committing can repeat one message; ARQ jobs are at-least-once (§13.5).

E-mail is throttled for mass announcements: at most ``mail_batch`` messages per ``mail_window`` across all
workers, counted in the database under an advisory lock. When the budget is spent, push keeps flowing and the
remaining e-mail waits for the next batch (D-055).
"""

import json
import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta

import structlog
from sqlalchemy import ColumnElement, delete, func, select, text
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
# Serialises the e-mail budget check and send across workers (any constant unique to this purpose).
MAIL_BUDGET_LOCK = 7_310_255_001


@dataclass(frozen=True, slots=True)
class DispatchRun:
    handled: int
    mail_waiting: bool
    """The e-mail budget is spent and e-mail is due: schedule the next batch."""


@dataclass(frozen=True, slots=True)
class Result:
    status: DeliveryStatus
    reason: str | None = None

    @classmethod
    def suppressed(cls, reason: str) -> "Result":
        return cls(DeliveryStatus.SUPPRESSED, reason)


SENT = Result(DeliveryStatus.SENT)
RETRY = Result(DeliveryStatus.PENDING, "retry")
THROTTLED = Result(DeliveryStatus.PENDING, "throttled")


class Dispatcher:
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        *,
        push: PushSender | None,
        mailer: Mailer,
        relevance: Mapping[str, RelevanceCheck],
        public_url: str,
        mail_batch: int = 200,
        mail_window: timedelta = timedelta(seconds=60),
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.sessionmaker = sessionmaker
        self.push = push
        self.mailer = mailer
        self.relevance = relevance
        self.public_url = public_url.rstrip("/")
        self.clock = clock
        self.mail_batch = mail_batch
        self.mail_window = mail_window
        self._mail_spent = False

    async def run(self) -> DispatchRun:
        """Sends what is due, e-mail within its budget."""
        self._mail_spent = False
        handled = 0
        while handled < MAX_PER_RUN and (outcome := await self._deliver_next()) is not None:
            handled += outcome
        return DispatchRun(handled, self._mail_spent and await self._mail_due())

    def _due(self, now: datetime) -> list[ColumnElement[bool]]:
        conditions = [
            NotificationDelivery.status == DeliveryStatus.PENDING,
            NotificationDelivery.not_before <= now,
        ]
        if self._mail_spent:
            conditions.append(NotificationDelivery.channel != DeliveryChannel.EMAIL)
        return conditions

    async def _mail_due(self) -> bool:
        async with self.sessionmaker() as session:
            due = await session.scalar(
                select(NotificationDelivery.id)
                .where(
                    NotificationDelivery.status == DeliveryStatus.PENDING,
                    NotificationDelivery.not_before <= self.clock(),
                    NotificationDelivery.channel == DeliveryChannel.EMAIL,
                )
                .limit(1)
            )
            return due is not None

    async def _mail_slot(self, session: AsyncSession) -> bool:
        """Whether another e-mail fits the budget; holds the lock until this delivery commits."""
        await session.execute(select(func.pg_advisory_xact_lock(MAIL_BUDGET_LOCK)))
        sent = await session.scalar(
            select(func.count())
            .select_from(NotificationDelivery)
            .where(
                NotificationDelivery.channel == DeliveryChannel.EMAIL,
                NotificationDelivery.status == DeliveryStatus.SENT,
                NotificationDelivery.updated_at
                > func.now() - text(f"interval '{int(self.mail_window.total_seconds())} seconds'"),
            )
        )
        return (sent or 0) < self.mail_batch

    async def _deliver_next(self) -> int | None:
        """1 when a delivery was handled, 0 when e-mail was held back by the budget, None when nothing is due."""
        async with self.sessionmaker() as session:
            now = self.clock()
            row = (
                await session.execute(
                    select(NotificationDelivery, Notification)
                    .join(Notification, Notification.id == NotificationDelivery.notification_id)
                    .where(*self._due(now))
                    .order_by(NotificationDelivery.not_before)
                    .limit(1)
                    .with_for_update(of=NotificationDelivery, skip_locked=True)
                )
            ).first()
            if row is None:
                return None
            delivery, notification = row
            result = await self._attempt(session, delivery, notification, now)
            if result is THROTTLED:
                # Left untouched for the next batch; this run continues with push only.
                await session.rollback()
                self._mail_spent = True
                return 0
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
            return 1

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
        if not await self._mail_slot(session):
            return THROTTLED
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
