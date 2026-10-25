"""Snowflake message ids (ADR 0002): 41 bits of milliseconds since 2026-01-01, 10 bits of worker id leased
from Redis instance A, 12 bits of sequence. Ids sort by creation time and carry their partition key."""

import asyncio
import contextlib
import random
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = structlog.get_logger(__name__)

EPOCH = datetime(2026, 1, 1, tzinfo=UTC)
EPOCH_MS = int(EPOCH.timestamp() * 1000)
WORKER_BITS = 10
SEQUENCE_BITS = 12
MAX_WORKERS = 1 << WORKER_BITS
MAX_SEQUENCE = (1 << SEQUENCE_BITS) - 1
TIMESTAMP_SHIFT = WORKER_BITS + SEQUENCE_BITS

LEASE_TTL_SECONDS = 60
RENEW_INTERVAL_SECONDS = 20
# Ids stop before the TTL could have run out: 10 s of margin for a renewal in flight.
LEASE_TRUST_SECONDS = 50
MAX_CLOCK_WAIT_MS = 10

# Renews only while the key still holds this process's token, so a lease taken over is never extended.
_RENEW = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('expire', KEYS[1], ARGV[2])
end
return 0
"""


class SnowflakeUnavailableError(Exception):
    """No id can be issued safely right now: no confirmed lease, or the clock went backwards."""


def created_at_of(message_id: int) -> datetime:
    return EPOCH + timedelta(milliseconds=message_id >> TIMESTAMP_SHIFT)


def floor_id(moment: datetime) -> int:
    """The smallest id that could have been issued at ``moment``: a cursor for "everything since"."""
    milliseconds = max(0, int((moment - EPOCH).total_seconds() * 1000))
    return milliseconds << TIMESTAMP_SHIFT


class WorkerLease:
    """Holds ``snowflake:worker:<n>`` in Redis A for this process, renewed every 20 s with a 60 s TTL."""

    def __init__(
        self,
        redis: Redis,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        renew_interval: float = RENEW_INTERVAL_SECONDS,
    ) -> None:
        self.redis = redis
        self.token = uuid.uuid4().hex
        self.worker_id: int | None = None
        self.confirmed_at = float("-inf")
        self.monotonic = monotonic
        self.renew_interval = renew_interval
        self._task: asyncio.Task[None] | None = None

    def _key(self, worker_id: int) -> str:
        return f"snowflake:worker:{worker_id}"

    @property
    def valid(self) -> bool:
        return (
            self.worker_id is not None
            and self.monotonic() - self.confirmed_at < LEASE_TRUST_SECONDS
        )

    async def acquire(self) -> int:
        start = random.randrange(MAX_WORKERS)  # noqa: S311 - spreads processes, not a secret
        for offset in range(MAX_WORKERS):
            candidate = (start + offset) % MAX_WORKERS
            if await self.redis.set(
                self._key(candidate), self.token, nx=True, ex=LEASE_TTL_SECONDS
            ):
                self.worker_id = candidate
                self.confirmed_at = self.monotonic()
                logger.info("snowflake_lease_acquired", worker_id=candidate)
                return candidate
        raise SnowflakeUnavailableError("every worker id is leased")

    async def renew(self) -> None:
        """One renewal. A failed call keeps the lease trusted until 50 s have passed; a lost key ends it."""
        if self.worker_id is None:
            await self.acquire()
            return
        try:
            renewed = await self.redis.eval(  # type: ignore[no-untyped-call]
                _RENEW, 1, self._key(self.worker_id), self.token, str(LEASE_TTL_SECONDS)
            )
        except (RedisError, OSError) as exc:
            logger.warning("snowflake_lease_renewal_failed", error=type(exc).__name__)
            return
        if renewed:
            self.confirmed_at = self.monotonic()
            return
        # Expired or taken by another process: this id must never be used again by us.
        logger.error("snowflake_lease_lost", worker_id=self.worker_id)
        self.worker_id = None
        self.confirmed_at = float("-inf")
        await self.acquire()

    async def _keep(self) -> None:
        while True:
            try:
                await self.renew()
            except (RedisError, OSError, SnowflakeUnavailableError) as exc:
                logger.warning("snowflake_lease_unavailable", error=type(exc).__name__)
            await asyncio.sleep(self.renew_interval)

    def start(self) -> None:
        self._task = asyncio.create_task(self._keep())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        if self.worker_id is not None:
            with contextlib.suppress(RedisError, OSError):
                await self.redis.eval(  # type: ignore[no-untyped-call]
                    _RENEW, 1, self._key(self.worker_id), self.token, "1"
                )


class Snowflake:
    def __init__(
        self,
        lease: WorkerLease,
        *,
        clock_ms: Callable[[], int] = lambda: time.time_ns() // 1_000_000,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.lease = lease
        self.clock_ms = clock_ms
        self.sleep = sleep
        self.last_ms = -1
        self.sequence = 0
        self._lock = asyncio.Lock()

    async def next_id(self) -> int:
        async with self._lock:
            if not self.lease.valid or self.lease.worker_id is None:
                raise SnowflakeUnavailableError("worker id lease not confirmed")
            now = await self._now()
            if now == self.last_ms:
                self.sequence = (self.sequence + 1) & MAX_SEQUENCE
                if self.sequence == 0:
                    # 4,096 ids in this millisecond: continue in the next one.
                    while now <= self.last_ms:
                        await self.sleep(0.001)
                        now = self.clock_ms() - EPOCH_MS
            else:
                self.sequence = 0
            self.last_ms = now
            return (
                (now << TIMESTAMP_SHIFT) | (self.lease.worker_id << SEQUENCE_BITS) | self.sequence
            )

    async def _now(self) -> int:
        now = self.clock_ms() - EPOCH_MS
        if now >= self.last_ms:
            return now
        behind = self.last_ms - now
        if behind > MAX_CLOCK_WAIT_MS:
            logger.error("snowflake_clock_regression", behind_ms=behind)
            raise SnowflakeUnavailableError("clock moved backwards")
        # A small step back (NTP slew): wait until the clock has caught up rather than reorder ids.
        while now < self.last_ms:
            await self.sleep((self.last_ms - now) / 1000)
            now = self.clock_ms() - EPOCH_MS
            if self.last_ms - now > MAX_CLOCK_WAIT_MS:
                raise SnowflakeUnavailableError("clock moved backwards")
        return now
