import time
from dataclasses import dataclass

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.errors import AppError

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RateLimit:
    name: str
    limit: int
    window_seconds: int


async def enforce_rate_limit(redis: Redis, rule: RateLimit, subject: str) -> None:
    """Fixed-window counter; exceeding it returns 429 with ``Retry-After`` (§4.2)."""
    retry_after = await consume(redis, rule, subject)
    if retry_after is not None:
        raise AppError(
            "request.rate_limited",
            429,
            details={"retry_after_seconds": retry_after},
            headers={"Retry-After": str(retry_after)},
        )


async def consume(redis: Redis, rule: RateLimit, subject: str) -> int | None:
    """Counts one use; returns the seconds until the window resets once the limit is exceeded, else None."""
    now = int(time.time())
    window = now // rule.window_seconds
    key = f"ratelimit:{rule.name}:{subject}:{window}"
    try:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, rule.window_seconds, nx=True)
            count, _ = await pipe.execute()
    except RedisError as exc:
        # Uploads and exports keep working during a Redis outage; the limit is a safeguard, not a gate.
        logger.warning("rate_limit_unavailable", rule=rule.name, error=type(exc).__name__)
        return None
    if count > rule.limit:
        return (window + 1) * rule.window_seconds - now
    return None
