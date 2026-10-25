"""ARQ worker: ``arq app.workers.main.WorkerSettings`` (Docker service ``worker``, ``make dev-worker``)."""

from typing import Any, ClassVar

import httpx
from arq import cron
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.db import Database
from app.core.jobs import DISPATCH_NOTIFICATIONS
from app.core.logging import configure_logging
from app.core.observability import init_sentry
from app.modules.notifications.delivery import Dispatcher, RelevanceCheck
from app.modules.notifications.mail import SmtpMailer
from app.modules.notifications.push import VapidKeys, WebPushSender

# Per subject type: whether a recipient should still hear about it when the worker sends (§5.6).
RELEVANCE: dict[str, RelevanceCheck] = {}


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
    ctx["dispatcher"] = Dispatcher(
        database.sessionmaker,
        push=push,
        mailer=SmtpMailer(settings),
        relevance=RELEVANCE,
        public_url=settings.app_public_url,
    )


async def shutdown(ctx: dict[str, Any]) -> None:
    await ctx["http"].aclose()
    await ctx["database"].dispose()


async def dispatch_notifications(ctx: dict[str, Any]) -> int:
    dispatcher: Dispatcher = ctx["dispatcher"]
    return await dispatcher.run()


class WorkerSettings:
    functions: ClassVar = [dispatch_notifications]
    # The safety net for wake-ups lost while Redis was unreachable, and for retries that come due.
    cron_jobs: ClassVar = [cron(dispatch_notifications, name=f"{DISPATCH_NOTIFICATIONS}_cron")]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(str(get_settings().redis_url))
    keep_result = 0
    max_jobs = 4
