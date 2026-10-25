"""Waking the ARQ worker from the API. Work is persisted first; a lost wake-up only delays it to the next cron
tick, so enqueue failures (Redis outage, §13.5) are logged and swallowed."""

from typing import Protocol

import structlog
from arq.connections import ArqRedis
from redis.exceptions import RedisError

logger = structlog.get_logger(__name__)

DISPATCH_NOTIFICATIONS = "dispatch_notifications"
SYNC_AUDIENCES = "sync_audiences"


class JobQueue(Protocol):
    async def dispatch_notifications(self) -> None: ...

    async def sync_audiences(self) -> None: ...


class ArqQueue:
    def __init__(self, redis_url: str) -> None:
        # Connects on first use, so the API starts even while Redis is down.
        self.redis = ArqRedis.from_url(redis_url)

    async def _enqueue(self, function: str) -> None:
        try:
            await self.redis.enqueue_job(function)
        except (RedisError, OSError) as exc:
            logger.warning("job_enqueue_failed", function=function, error=type(exc).__name__)

    async def dispatch_notifications(self) -> None:
        await self._enqueue(DISPATCH_NOTIFICATIONS)

    async def sync_audiences(self) -> None:
        await self._enqueue(SYNC_AUDIENCES)

    async def close(self) -> None:
        await self.redis.aclose()
