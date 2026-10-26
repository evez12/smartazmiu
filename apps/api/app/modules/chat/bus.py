"""Real-time fan-out through Redis pub/sub on the cache instance B (D-053).

Every event is published only after the change it describes has been committed (§5.9), so a lost publish never
loses data: clients backfill from the database, and the gateway re-checks memberships on its own.
"""

import json
import uuid
from typing import Any

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = structlog.get_logger(__name__)

CHANNEL_PREFIX = "chat:channel:"
USER_PREFIX = "chat:user:"


def channel_topic(channel_id: uuid.UUID) -> str:
    return f"{CHANNEL_PREFIX}{channel_id}"


def user_topic(user_id: uuid.UUID) -> str:
    """Per-user control channel: membership changes and notifications for every socket of the user."""
    return f"{USER_PREFIX}{user_id}"


def encode(event_type: str, data: dict[str, Any]) -> str:
    return json.dumps({"type": event_type, "data": data}, separators=(",", ":"), default=str)


class ChatBus:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def publish(self, topic: str, event_type: str, data: dict[str, Any]) -> bool:
        """Returns whether Redis accepted the event; failures are logged, never raised (§13.5)."""
        try:
            await self.redis.publish(topic, encode(event_type, data))
        except (RedisError, OSError) as exc:
            logger.warning("chat_publish_failed", event_type=event_type, error=type(exc).__name__)
            return False
        return True

    async def membership_changed(
        self, added: list[tuple[uuid.UUID, uuid.UUID]], removed: list[tuple[uuid.UUID, uuid.UUID]]
    ) -> None:
        for channel_id, user_id in removed:
            await self.publish(
                user_topic(user_id), "membership.revoked", {"channel_id": channel_id}
            )
        for channel_id, user_id in added:
            await self.publish(user_topic(user_id), "membership.added", {"channel_id": channel_id})

    async def channels_changed(self, channel_ids: list[uuid.UUID]) -> None:
        for channel_id in channel_ids:
            await self.publish(
                channel_topic(channel_id), "channel.changed", {"channel_id": channel_id}
            )
