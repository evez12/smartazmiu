"""ARQ worker: ``arq app.workers.main.WorkerSettings`` (Docker service ``worker``, ``make dev-worker``)."""

from datetime import timedelta
from typing import Any, ClassVar

import httpx
from arq import cron
from arq.connections import RedisSettings
from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.db import Database
from app.core.jobs import DISPATCH_NOTIFICATIONS, PROVISION_CHANNELS, SYNC_AUDIENCES
from app.core.logging import configure_logging
from app.core.observability import init_sentry
from app.modules.announcements import service as announcements
from app.modules.chat import partitions
from app.modules.chat.bus import ChatBus
from app.modules.chat.provisioning import ChannelProvisioner
from app.modules.events import service as events
from app.modules.notifications.delivery import Dispatcher, RelevanceCheck
from app.modules.notifications.mail import SmtpMailer
from app.modules.notifications.push import VapidKeys, WebPushSender
from app.modules.notifications.service import LateJoinBudget
from app.modules.schedule import notifications as schedule_changes

# Per subject type: whether a recipient should still hear about it when the worker sends (§5.6).
RELEVANCE: dict[str, RelevanceCheck] = {
    announcements.SUBJECT_TYPE: announcements.still_addressed,
    events.SUBJECT_TYPE: events.still_relevant,
    schedule_changes.SUBJECT_TYPE: schedule_changes.still_affected,
}


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    init_sentry(settings)
    database = Database(str(settings.database_url))
    http = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
    push = (
        WebPushSender(
            http,
            VapidKeys(settings.vapid_secret, settings.vapid_subject),
            settings.push_service_hosts,
        )
        if settings.vapid_secret
        else None
    )
    ctx["database"] = database
    ctx["http"] = http
    # Instance B: chat pub/sub (D-053).
    ctx["cache_redis"] = Redis.from_url(str(settings.redis_url), decode_responses=True)
    ctx["dispatcher"] = Dispatcher(
        database.sessionmaker,
        push=push,
        mailer=SmtpMailer(settings),
        relevance=RELEVANCE,
        public_url=settings.app_public_url,
        mail_batch=settings.mail_batch_size,
        mail_window=timedelta(seconds=settings.mail_batch_interval_seconds),
    )
    ctx["mail_interval"] = settings.mail_batch_interval_seconds
    # A worker started after a long outage must not wait for the nightly run to create this month.
    async with database.sessionmaker() as session:
        await partitions.ensure_partitions(session)


async def shutdown(ctx: dict[str, Any]) -> None:
    await ctx["http"].aclose()
    await ctx["cache_redis"].aclose()
    await ctx["database"].dispose()


async def dispatch_notifications(ctx: dict[str, Any]) -> int:
    dispatcher: Dispatcher = ctx["dispatcher"]
    result = await dispatcher.run()
    if result.mail_waiting:
        # The next e-mail batch; a fixed id keeps one continuation queued however many runs ask for it.
        await ctx["redis"].enqueue_job(
            DISPATCH_NOTIFICATIONS,
            _job_id=f"{DISPATCH_NOTIFICATIONS}:next_mail_batch",
            _defer_by=ctx["mail_interval"],
        )
    return result.handled


async def sync_audiences(ctx: dict[str, Any]) -> int:
    """Adds people who joined an audience to its active announcements and coming events. Their
    notifications are in-app only, so nothing is queued for sending (D-054)."""
    database: Database = ctx["database"]
    late = LateJoinBudget()
    async with database.sessionmaker() as session:
        added = await announcements.AnnouncementService(session).sync_recipients(late)
        added += await events.EventService(session).sync_recipients(late)
    return added


async def provision_channels(ctx: dict[str, Any]) -> int:
    """Syncs registry channels and memberships, then tells connected sockets about the changes (§5.9)."""
    database: Database = ctx["database"]
    async with database.sessionmaker() as session:
        result = await ChannelProvisioner(session).run()
    bus = ChatBus(ctx["cache_redis"])
    await bus.membership_changed(result.added, result.removed)
    await bus.channels_changed(result.state_changed)
    return len(result.added) + len(result.removed) + len(result.state_changed)


async def ensure_message_partitions(ctx: dict[str, Any]) -> int:
    """Keeps this month and the next three partitions of ``messages`` (ADR 0002)."""
    database: Database = ctx["database"]
    async with database.sessionmaker() as session:
        created = await partitions.ensure_partitions(session)
        await partitions.warn_if_running_out(session)
    return len(created)


async def purge_message_client_ids(ctx: dict[str, Any]) -> int:
    """Forgets duplicate-send keys older than seven days (D-058)."""
    database: Database = ctx["database"]
    async with database.sessionmaker() as session:
        return await partitions.purge_client_ids(session)


class WorkerSettings:
    functions: ClassVar = [dispatch_notifications, sync_audiences, provision_channels]
    # The safety net for wake-ups lost while Redis was unreachable, and for retries that come due.
    cron_jobs: ClassVar = [
        cron(dispatch_notifications, name=f"{DISPATCH_NOTIFICATIONS}_cron"),
        # Imports wake the sync directly; this catches people added any other way.
        cron(sync_audiences, name=f"{SYNC_AUDIENCES}_cron", minute=set(range(0, 60, 5))),
        # Every minute: picks up wake-ups lost in a Redis outage and changes made outside imports.
        cron(provision_channels, name=f"{PROVISION_CHANNELS}_cron"),
        # Daily, at night in Baku (UTC+4); both are idempotent, so a retried or doubled run is harmless.
        cron(ensure_message_partitions, hour={22}, minute={10}),
        cron(purge_message_client_ids, hour={22}, minute={20}),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(str(get_settings().queue_redis_url))
    keep_result = 0
    max_jobs = 4
