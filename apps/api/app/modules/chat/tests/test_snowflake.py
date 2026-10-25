import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from redis.asyncio import Redis

from app.core.config import Settings
from app.modules.chat.snowflake import (
    EPOCH_MS,
    LEASE_TTL_SECONDS,
    MAX_SEQUENCE,
    SEQUENCE_BITS,
    TIMESTAMP_SHIFT,
    Snowflake,
    SnowflakeUnavailableError,
    WorkerLease,
    created_at_of,
    floor_id,
)
from tests.test_jobs import _closed_port


class Monotonic:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class WallClock:
    """Milliseconds since the Unix epoch, moved by hand; ``sleep`` advances it."""

    def __init__(self, at: datetime) -> None:
        self.ms = int(at.timestamp() * 1000)
        self.slept: list[float] = []

    def __call__(self) -> int:
        return self.ms

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.ms += max(1, round(seconds * 1000))


@pytest_asyncio.fixture
async def lease_redis(settings: Settings) -> AsyncIterator[Redis]:
    redis = Redis.from_url(str(settings.queue_redis_url), decode_responses=True)
    yield redis
    async for key in redis.scan_iter("snowflake:worker:*"):
        await redis.delete(key)
    await redis.aclose()


async def held_lease(redis: Redis, monotonic: Monotonic | None = None) -> WorkerLease:
    lease = WorkerLease(redis, monotonic=monotonic or Monotonic())
    await lease.acquire()
    return lease


async def test_ids_carry_their_time_and_sort_by_it(lease_redis: Redis) -> None:
    clock = WallClock(datetime(2026, 11, 2, 9, 30, tzinfo=UTC))
    generator = Snowflake(await held_lease(lease_redis), clock_ms=clock, sleep=clock.sleep)
    first = await generator.next_id()
    clock.ms += 5
    second = await generator.next_id()
    assert 0 < first < second < 2**63
    assert created_at_of(first) == datetime(2026, 11, 2, 9, 30, tzinfo=UTC)
    assert (
        floor_id(created_at_of(second))
        <= second
        < floor_id(created_at_of(second)) + (1 << TIMESTAMP_SHIFT)
    )


async def test_generators_with_leased_workers_never_collide(lease_redis: Redis) -> None:
    leases = [await held_lease(lease_redis) for _ in range(4)]
    assert len({lease.worker_id for lease in leases}) == 4
    generators = [Snowflake(lease) for lease in leases]

    async def issue(generator: Snowflake) -> list[int]:
        return [await generator.next_id() for _ in range(50_000)]

    batches = await asyncio.gather(*(issue(generator) for generator in generators))
    ids = [message_id for batch in batches for message_id in batch]
    assert len(set(ids)) == 200_000
    assert all(batch == sorted(batch) for batch in batches)


async def test_sequence_overflow_moves_to_the_next_millisecond(lease_redis: Redis) -> None:
    clock = WallClock(datetime(2026, 11, 2, tzinfo=UTC))
    generator = Snowflake(await held_lease(lease_redis), clock_ms=clock, sleep=clock.sleep)
    ids = [await generator.next_id() for _ in range(MAX_SEQUENCE + 2)]
    assert len(set(ids)) == len(ids)
    assert ids == sorted(ids)
    assert ids[-1] >> TIMESTAMP_SHIFT == (ids[0] >> TIMESTAMP_SHIFT) + 1
    assert ids[-1] & ((1 << SEQUENCE_BITS) - 1) == 0


async def test_a_small_clock_regression_waits(lease_redis: Redis) -> None:
    clock = WallClock(datetime(2026, 11, 2, tzinfo=UTC))
    generator = Snowflake(await held_lease(lease_redis), clock_ms=clock, sleep=clock.sleep)
    before = await generator.next_id()
    clock.ms -= 5
    after = await generator.next_id()
    assert after > before
    assert clock.slept


async def test_a_large_clock_regression_refuses_ids(lease_redis: Redis) -> None:
    clock = WallClock(datetime(2026, 11, 2, tzinfo=UTC))
    generator = Snowflake(await held_lease(lease_redis), clock_ms=clock, sleep=clock.sleep)
    before = await generator.next_id()
    clock.ms -= 1000
    with pytest.raises(SnowflakeUnavailableError):
        await generator.next_id()
    clock.ms += 1001
    assert await generator.next_id() > before


async def test_a_short_redis_outage_does_not_stop_ids(lease_redis: Redis) -> None:
    """Two missed renewals (40 s) still leave the 60 s lease ours (D-056)."""
    monotonic = Monotonic()
    lease = await held_lease(lease_redis, monotonic)
    generator = Snowflake(lease)
    healthy = lease.redis
    lease.redis = Redis(host="127.0.0.1", port=_closed_port(), socket_connect_timeout=0.2)
    try:
        for _ in range(2):
            monotonic.now += 20
            await lease.renew()
        assert await generator.next_id() > 0
        # A third missed renewal (60 s without confirmation) is too long: the lease may have expired.
        monotonic.now += 20
        await lease.renew()
        with pytest.raises(SnowflakeUnavailableError):
            await generator.next_id()
    finally:
        await lease.redis.aclose()
        lease.redis = healthy
    await lease.renew()
    assert await generator.next_id() > 0


async def test_a_lost_lease_stops_ids_until_a_new_one_is_held(lease_redis: Redis) -> None:
    monotonic = Monotonic()
    lease = await held_lease(lease_redis, monotonic)
    generator = Snowflake(lease)
    original = lease.worker_id
    # Paused past the TTL; another process took the worker id in the meantime.
    monotonic.now += LEASE_TTL_SECONDS + 10
    await lease_redis.set(f"snowflake:worker:{original}", "another-process", ex=LEASE_TTL_SECONDS)
    with pytest.raises(SnowflakeUnavailableError):
        await generator.next_id()

    await lease.renew()
    assert lease.worker_id not in (None, original)
    assert await lease_redis.get(f"snowflake:worker:{original}") == "another-process"
    message_id = await generator.next_id()
    assert (message_id >> SEQUENCE_BITS) & 0x3FF == lease.worker_id


async def test_stopping_releases_the_worker_id(lease_redis: Redis) -> None:
    lease = await held_lease(lease_redis)
    lease.start()
    await lease.stop()
    assert await lease_redis.ttl(f"snowflake:worker:{lease.worker_id}") in (-2, 0, 1)


def test_the_epoch_is_the_start_of_2026() -> None:
    assert datetime.fromtimestamp(EPOCH_MS / 1000, tz=UTC) == datetime(2026, 1, 1, tzinfo=UTC)
