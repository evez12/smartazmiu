"""Presence and typing on the cache instance B (D-053), both disposable: losing them costs a dot, never data.

A user is online while at least one socket is alive, across tabs, devices and API processes (§5.9). Each
socket keeps a member of ``chat:presence:<user>`` whose score is its expiry; heartbeats push it forward, so a
process that dies without cleaning up stops counting within a minute.
"""

import json
import time
import uuid

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = structlog.get_logger(__name__)

PRESENCE_TOPIC = "chat:presence"
SOCKET_TTL_SECONDS = 60
# A closed socket counts as online for this long, so a reload or a short network drop shows no flicker (§5.9).
OFFLINE_GRACE_SECONDS = 30
TYPING_THROTTLE_SECONDS = 3


def _key(user_id: uuid.UUID) -> str:
    return f"chat:presence:{user_id}"


class Presence:
    def __init__(self, cache: Redis) -> None:
        self.cache = cache

    async def connected(self, user_id: uuid.UUID, socket_id: str) -> None:
        now = time.time()
        try:
            async with self.cache.pipeline(transaction=True) as pipe:
                pipe.zremrangebyscore(_key(user_id), "-inf", now)
                pipe.zcard(_key(user_id))
                pipe.zadd(_key(user_id), {socket_id: now + SOCKET_TTL_SECONDS})
                pipe.expire(_key(user_id), SOCKET_TTL_SECONDS * 2)
                _, before, *_ = await pipe.execute()
        except RedisError as exc:
            logger.warning("presence_unavailable", error=type(exc).__name__)
            return
        if before == 0:
            await self._announce(user_id, "online")

    async def heartbeat(self, user_id: uuid.UUID, socket_id: str) -> None:
        try:
            async with self.cache.pipeline(transaction=True) as pipe:
                pipe.zadd(_key(user_id), {socket_id: time.time() + SOCKET_TTL_SECONDS})
                pipe.expire(_key(user_id), SOCKET_TTL_SECONDS * 2)
                await pipe.execute()
        except RedisError as exc:
            logger.warning("presence_unavailable", error=type(exc).__name__)

    async def disconnected(self, user_id: uuid.UUID, socket_id: str) -> None:
        """Keeps the socket counted for the grace period; ``settle`` decides afterwards."""
        try:
            await self.cache.zadd(_key(user_id), {socket_id: time.time() + OFFLINE_GRACE_SECONDS})
        except RedisError as exc:
            logger.warning("presence_unavailable", error=type(exc).__name__)

    async def settle(self, user_id: uuid.UUID, socket_id: str) -> None:
        """After the grace period: the socket stops counting, and if no other one is left the user is offline."""
        try:
            async with self.cache.pipeline(transaction=True) as pipe:
                pipe.zrem(_key(user_id), socket_id)
                pipe.zremrangebyscore(_key(user_id), "-inf", time.time())
                pipe.zcard(_key(user_id))
                *_, remaining = await pipe.execute()
        except RedisError as exc:
            logger.warning("presence_unavailable", error=type(exc).__name__)
            return
        if remaining == 0:
            await self._announce(user_id, "offline")

    async def online(self, user_ids: list[uuid.UUID]) -> set[uuid.UUID]:
        if not user_ids:
            return set()
        now = time.time()
        try:
            async with self.cache.pipeline(transaction=False) as pipe:
                for user_id in user_ids:
                    pipe.zcount(_key(user_id), now, "+inf")
                counts = await pipe.execute()
        except RedisError as exc:
            logger.warning("presence_unavailable", error=type(exc).__name__)
            return set()
        return {user_id for user_id, count in zip(user_ids, counts, strict=True) if count}

    async def may_type(self, channel_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """At most one typing event per user and channel every 3 s (§5.3)."""
        try:
            claimed = await self.cache.set(
                f"chat:typing:{channel_id}:{user_id}", "1", nx=True, ex=TYPING_THROTTLE_SECONDS
            )
        except RedisError:
            return False
        return bool(claimed)

    async def _announce(self, user_id: uuid.UUID, status: str) -> None:
        payload = json.dumps(
            {"type": "presence", "data": {"user_id": str(user_id), "status": status}}
        )
        try:
            await self.cache.publish(PRESENCE_TOPIC, payload)
        except RedisError as exc:
            logger.warning("presence_unavailable", error=type(exc).__name__)
