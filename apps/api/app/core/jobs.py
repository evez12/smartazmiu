"""Waking the ARQ worker from the API. Work is persisted first; a lost wake-up only delays it to the next cron
tick, so enqueue failures (Redis outage, §13.5) are logged and swallowed."""

from typing import Protocol

import structlog
from arq.connections import ArqRedis
from redis.exceptions import RedisError

logger = structlog.get_logger(__name__)

DISPATCH_NOTIFICATIONS = "dispatch_notifications"
SYNC_AUDIENCES = "sync_audiences"
PROVISION_CHANNELS = "provision_channels"
SCAN_ATTACHMENTS = "scan_attachments"
SYNC_GUIDES = "sync_guides"
SYNC_CABINET = "sync_cabinet"


class JobQueue(Protocol):
    async def dispatch_notifications(self) -> None: ...

    async def sync_audiences(self) -> None: ...

    async def provision_channels(self) -> None: ...

    async def scan_attachments(self) -> None: ...

    async def sync_guides(self) -> None: ...

    async def sync_cabinet(self, triggered_by: str) -> None: ...


class ArqQueue:
    def __init__(self, redis_url: str) -> None:
        # Connects on first use, so the API starts even while Redis is down.
        self.redis = ArqRedis.from_url(redis_url)

    async def _enqueue(self, function: str, *args: str, job_id: str | None = None) -> None:
        try:
            await self.redis.enqueue_job(function, *args, _job_id=job_id)
        except (RedisError, OSError) as exc:
            logger.warning("job_enqueue_failed", function=function, error=type(exc).__name__)

    async def dispatch_notifications(self) -> None:
        await self._enqueue(DISPATCH_NOTIFICATIONS)

    async def sync_audiences(self) -> None:
        await self._enqueue(SYNC_AUDIENCES)

    async def provision_channels(self) -> None:
        await self._enqueue(PROVISION_CHANNELS)

    async def scan_attachments(self) -> None:
        await self._enqueue(SCAN_ATTACHMENTS)

    async def sync_guides(self) -> None:
        await self._enqueue(SYNC_GUIDES)

    async def sync_cabinet(self, triggered_by: str) -> None:
        # One manual run waits in the queue at a time, however often the button is pressed.
        await self._enqueue(SYNC_CABINET, triggered_by, job_id=f"{SYNC_CABINET}:manual")

    async def close(self) -> None:
        await self.redis.aclose()
