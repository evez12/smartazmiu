"""The WebSocket hub of one API process: which local sockets want which channels, users and presence, and the
listeners that feed them (§5.9).

Every process pattern-subscribes once to ``chat:*`` on Redis B and filters locally; at the pilot's scale (two API
processes, 3,000 sockets) that is simpler and cheaper than one subscription per channel. Notifications come from
PostgreSQL ``LISTEN``: the notifications table announces new rows on commit, wherever they were created.
"""

import asyncio
import contextlib
import json
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import asyncpg
import structlog
from fastapi import WebSocket
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.modules.chat.bus import CHANNEL_PREFIX, USER_PREFIX, encode
from app.modules.chat.presence import PRESENCE_TOPIC
from app.modules.users.service import CurrentUser

logger = structlog.get_logger(__name__)

# Frames waiting for one socket; a client that falls this far behind is disconnected (backpressure, §5.9).
SEND_QUEUE_LIMIT = 256
NOTIFICATION_CHANNEL = "notification_created"
RECONNECT_DELAY_SECONDS = 1.0


class CloseCode:
    """Close codes of ADR 0003."""

    UNAUTHORIZED = 4401
    FORBIDDEN = 4403
    SLOW_CONSUMER = 4408
    TOO_MANY = 4429
    TRY_AGAIN_LATER = 1013


@dataclass(frozen=True, slots=True)
class Close:
    code: int
    error: str | None = None


@dataclass(eq=False)
class Connection:
    websocket: WebSocket
    user: CurrentUser
    authorized_until: datetime
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    channels: set[uuid.UUID] = field(default_factory=set)
    watching: set[uuid.UUID] = field(default_factory=set)
    """Users whose presence this socket asked for (people it shares a channel with)."""
    queue: "asyncio.Queue[str | Close]" = field(default_factory=asyncio.Queue)
    closing: bool = False
    drained: asyncio.Event = field(default_factory=asyncio.Event)
    """Set by the sender after each frame, so a backlog can be written at the client's pace."""

    def push(self, frame: str) -> None:
        if self.closing:
            return
        if self.queue.qsize() >= SEND_QUEUE_LIMIT:
            logger.info("socket_slow_consumer", user_id=str(self.user.id))
            self.terminate(CloseCode.SLOW_CONSUMER, "chat.slow_consumer")
            return
        self.queue.put_nowait(frame)

    def send(self, event_type: str, data: dict[str, Any]) -> None:
        self.push(encode(event_type, data))

    async def send_patiently(self, event_type: str, data: dict[str, Any]) -> None:
        """For replays the socket asked for: waits for room instead of counting as a slow consumer."""
        while self.queue.qsize() >= SEND_QUEUE_LIMIT // 2 and not self.closing:
            self.drained.clear()
            await self.drained.wait()
        self.send(event_type, data)

    def terminate(self, code: int, error: str | None = None) -> None:
        """Ends the socket after the frames already queued; the sender writes the error and closes."""
        if self.closing:
            return
        self.closing = True
        self.queue.put_nowait(Close(code, error))


class Hub:
    def __init__(self, cache: Redis, database_url: str) -> None:
        self.cache = cache
        self.database_url = database_url
        self.connections: dict[str, Connection] = {}
        self.by_channel: defaultdict[uuid.UUID, set[Connection]] = defaultdict(set)
        self.by_user: defaultdict[uuid.UUID, set[Connection]] = defaultdict(set)
        self.watchers: defaultdict[uuid.UUID, set[Connection]] = defaultdict(set)
        self.healthy = False
        """Whether this process currently receives chat events; while not, sockets are refused (§13.5)."""
        self._tasks: list[asyncio.Task[None]] = []
        self._ready = asyncio.Event()

    async def start(self) -> None:
        self._tasks = [
            asyncio.create_task(self._listen_bus()),
            asyncio.create_task(self._listen_notifications()),
        ]

    async def ready(self) -> bool:
        """Waits for the first attempt to reach the bus; callers bound the wait with ``asyncio.timeout``."""
        await self._ready.wait()
        return self.healthy

    async def stop(self) -> None:
        for connection in list(self.connections.values()):
            connection.terminate(1001)
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task

    def register(self, connection: Connection) -> None:
        self.connections[connection.id] = connection
        self.by_user[connection.user.id].add(connection)

    def unregister(self, connection: Connection) -> None:
        self.connections.pop(connection.id, None)
        self.by_user[connection.user.id].discard(connection)
        if not self.by_user[connection.user.id]:
            del self.by_user[connection.user.id]
        for channel_id in list(connection.channels):
            self.unsubscribe(connection, channel_id)
        for user_id in list(connection.watching):
            self._unwatch(connection, user_id)

    def subscribe(self, connection: Connection, channel_ids: set[uuid.UUID]) -> None:
        for channel_id in channel_ids:
            connection.channels.add(channel_id)
            self.by_channel[channel_id].add(connection)

    def unsubscribe(self, connection: Connection, channel_id: uuid.UUID) -> None:
        connection.channels.discard(channel_id)
        subscribers = self.by_channel.get(channel_id)
        if subscribers is not None:
            subscribers.discard(connection)
            if not subscribers:
                del self.by_channel[channel_id]

    def watch(self, connection: Connection, user_ids: set[uuid.UUID]) -> None:
        for user_id in user_ids:
            connection.watching.add(user_id)
            self.watchers[user_id].add(connection)

    def _unwatch(self, connection: Connection, user_id: uuid.UUID) -> None:
        connection.watching.discard(user_id)
        watching = self.watchers.get(user_id)
        if watching is not None:
            watching.discard(connection)
            if not watching:
                del self.watchers[user_id]

    def revoke(self, user_id: uuid.UUID, channel_id: uuid.UUID) -> None:
        """Access is gone: unsubscribe every socket of the user at once and tell the client (§13.2)."""
        for connection in list(self.by_user.get(user_id, ())):
            if channel_id in connection.channels:
                self.unsubscribe(connection, channel_id)
            connection.send("channel.updated", {"channel_id": str(channel_id), "removed": True})

    def dispatch(self, topic: str, raw: str) -> None:
        if topic == PRESENCE_TOPIC:
            data = json.loads(raw)["data"]
            for connection in list(self.watchers.get(uuid.UUID(data["user_id"]), ())):
                connection.push(raw)
            return
        if topic.startswith(CHANNEL_PREFIX):
            channel_id = uuid.UUID(topic.removeprefix(CHANNEL_PREFIX))
            event = json.loads(raw)
            if event["type"] == "channel.changed":
                # State (archive, exam mode, mute) is per user; clients reload the channel through REST.
                raw = encode("channel.updated", {"channel_id": str(channel_id)})
            for connection in list(self.by_channel.get(channel_id, ())):
                connection.push(raw)
            return
        if topic.startswith(USER_PREFIX):
            user_id = uuid.UUID(topic.removeprefix(USER_PREFIX))
            event = json.loads(raw)
            if event["type"] == "membership.revoked":
                self.revoke(user_id, uuid.UUID(event["data"]["channel_id"]))
                return
            if event["type"] == "membership.added":
                raw = encode(
                    "channel.updated", {"channel_id": event["data"]["channel_id"], "added": True}
                )
            for connection in list(self.by_user.get(user_id, ())):
                connection.push(raw)

    def notify(self, user_id: uuid.UUID) -> None:
        """A notification was committed for the user: the bell refreshes its count (D-049 polling fallback)."""
        for connection in list(self.by_user.get(user_id, ())):
            connection.send("notification", {})

    async def _listen_bus(self) -> None:
        while True:
            pubsub = self.cache.pubsub()
            try:
                await pubsub.psubscribe("chat:*")
                self.healthy = True
                self._ready.set()
                logger.info("chat_bus_listening")
                while True:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=5.0)
                    if message is None:
                        # Detects a silently dropped connection between messages.
                        await pubsub.ping()
                        continue
                    if message["type"] == "pmessage":
                        try:
                            self.dispatch(message["channel"], message["data"])
                        except (ValueError, KeyError) as exc:
                            logger.warning("chat_event_invalid", error=type(exc).__name__)
            except (RedisError, OSError) as exc:
                self._lost_bus(exc)
            finally:
                with contextlib.suppress(RedisError, OSError):
                    await pubsub.aclose()  # type: ignore[no-untyped-call]
            await asyncio.sleep(RECONNECT_DELAY_SECONDS)

    def _lost_bus(self, exc: BaseException) -> None:
        """Without the bus no socket would hear anything: clients fall back to REST until it is back (§13.5)."""
        if self.healthy:
            logger.error("chat_bus_lost", error=type(exc).__name__)
        self.healthy = False
        self._ready.set()
        for connection in list(self.connections.values()):
            connection.terminate(CloseCode.TRY_AGAIN_LATER, "chat.realtime_unavailable")

    async def _listen_notifications(self) -> None:
        dsn = self.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
        while True:
            try:
                connection = await asyncpg.connect(dsn)
            except (OSError, asyncpg.PostgresError) as exc:
                logger.warning("notification_listener_unavailable", error=type(exc).__name__)
                await asyncio.sleep(RECONNECT_DELAY_SECONDS * 5)
                continue
            closed = asyncio.Event()
            try:
                connection.add_termination_listener(lambda _, done=closed: done.set())
                await connection.add_listener(NOTIFICATION_CHANNEL, self._on_notification)
                await closed.wait()
            except (OSError, asyncpg.PostgresError) as exc:
                logger.warning("notification_listener_unavailable", error=type(exc).__name__)
            finally:
                with contextlib.suppress(OSError, asyncpg.PostgresError):
                    await connection.close(timeout=2)
            await asyncio.sleep(RECONNECT_DELAY_SECONDS)

    def _on_notification(self, _connection: object, _pid: int, _channel: str, payload: str) -> None:
        with contextlib.suppress(ValueError):
            self.notify(uuid.UUID(payload))
