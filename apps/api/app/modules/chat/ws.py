"""The WebSocket gateway, ``/ws?ticket=…`` (§5.9, ADR 0003).

Every client event is authorised on its own against current membership and channel state (ADR 0004). Frames to
the client go through one queue per socket, written by a single task; a socket that cannot keep up is closed with
a reconnect hint instead of slowing everyone else down.
"""

import asyncio
import contextlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, ValidationError
from redis.exceptions import RedisError
from sqlalchemy import select

from app.core.config import Settings
from app.core.db import Database
from app.core.errors import AppError
from app.core.time import utc_now
from app.modules.chat import tickets
from app.modules.chat.access import ChannelAccess
from app.modules.chat.bus import ChatBus, channel_topic, encode
from app.modules.chat.hub import Close, CloseCode, Connection, Hub
from app.modules.chat.messages import MessageService
from app.modules.chat.models import ChannelMember
from app.modules.chat.policy import Action, ExamWindowProvider
from app.modules.chat.presence import OFFLINE_GRACE_SECONDS, Presence
from app.modules.chat.snowflake import Snowflake
from app.modules.users.service import UserService

logger = structlog.get_logger(__name__)

router = APIRouter()

HEARTBEAT_SECONDS = 25.0
# Three missed client pings: the connection is gone even if TCP has not noticed.
SILENCE_LIMIT_SECONDS = 75.0
REFRESH_NOTICE_SECONDS = 60.0
MAX_SUBSCRIBE = 500
MAX_PRESENCE = 200
# Client frames per 10 s before the socket is closed with 4429.
EVENT_BUDGET = 60
EVENT_WINDOW_SECONDS = 10.0


class SubscribeIn(BaseModel):
    channel_ids: list[uuid.UUID] = Field(max_length=MAX_SUBSCRIBE)
    after: str | None = Field(default=None, pattern=r"^[0-9]{1,19}$")
    """The newest message id the client has; missed messages are replayed before the ack."""
    presence: list[uuid.UUID] = Field(default_factory=list, max_length=MAX_PRESENCE)


class SendIn(BaseModel):
    channel_id: uuid.UUID
    body: str = Field(max_length=100_000)
    client_msg_id: uuid.UUID
    topic_id: uuid.UUID | None = None


class ChannelIn(BaseModel):
    channel_id: uuid.UUID


class ReadIn(BaseModel):
    channel_id: uuid.UUID
    message_id: str = Field(pattern=r"^[0-9]{1,19}$")


class RefreshIn(BaseModel):
    ticket: str = Field(max_length=64)


# In the protocol (§5.9) but built in Sprint 6.
LATER_EVENTS = frozenset({"message.edit", "message.delete", "reaction.add", "reaction.remove"})


def allowed_origins(settings: Settings) -> set[str]:
    def origin(url: str) -> str:
        parts = urlsplit(url)
        return f"{parts.scheme}://{parts.netloc}"

    return {origin(settings.app_public_url), *(origin(url) for url in settings.ws_allowed_origins)}


@dataclass
class Gateway:
    """Per-process dependencies, created in the application lifespan."""

    hub: Hub
    database: Database
    settings: Settings
    snowflake: Snowflake
    exams: ExamWindowProvider
    heartbeat_seconds: float = HEARTBEAT_SECONDS

    def __post_init__(self) -> None:
        self.presence = Presence(self.hub.cache)


@router.websocket("/ws")
async def chat_socket(websocket: WebSocket, ticket: str = "") -> None:
    gateway: Gateway = websocket.app.state.chat_gateway
    # Accept first, so the client receives a close code it can act on rather than a bare HTTP 403.
    await websocket.accept()
    if websocket.headers.get("origin") not in allowed_origins(gateway.settings):
        await websocket.close(CloseCode.FORBIDDEN)
        return
    if not gateway.hub.healthy:
        await websocket.close(CloseCode.TRY_AGAIN_LATER)
        return
    try:
        redeemed = await tickets.redeem(websocket.app.state.durable_redis, ticket)
    except (RedisError, OSError):
        await websocket.close(CloseCode.TRY_AGAIN_LATER)
        return
    if redeemed is None or redeemed.token_expires_at <= utc_now():
        await websocket.close(CloseCode.UNAUTHORIZED)
        return
    async with gateway.database.sessionmaker() as session:
        user = await UserService(session).current(redeemed.user_id)
    if user is None or not user.is_active:
        await websocket.close(CloseCode.FORBIDDEN)
        return

    connection = Connection(websocket, user, redeemed.token_expires_at)
    gateway.hub.register(connection)
    await gateway.presence.connected(user.id, connection.id)
    structlog.contextvars.bind_contextvars(user_id=str(user.id), socket_id=connection.id)
    logger.info("socket_opened")
    session_runner = SocketSession(gateway, connection)
    tasks = [
        asyncio.create_task(session_runner.receive()),
        asyncio.create_task(session_runner.send()),
        asyncio.create_task(session_runner.tick()),
    ]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError, WebSocketDisconnect, RuntimeError):
                await task
        gateway.hub.unregister(connection)
        await gateway.presence.disconnected(user.id, connection.id)
        settle = asyncio.create_task(_settle_later(gateway.presence, user.id, connection.id))
        _background.add(settle)
        settle.add_done_callback(_background.discard)
        logger.info("socket_closed")


_background: set[asyncio.Task[None]] = set()


async def _settle_later(presence: Presence, user_id: uuid.UUID, socket_id: str) -> None:
    await asyncio.sleep(OFFLINE_GRACE_SECONDS)
    await presence.settle(user_id, socket_id)


class SocketSession:
    def __init__(self, gateway: Gateway, connection: Connection) -> None:
        self.gateway = gateway
        self.connection = connection
        self.last_heard = asyncio.get_running_loop().time()
        self.refresh_requested = False
        self.window_started = self.last_heard
        self.window_events = 0

    async def send(self) -> None:
        websocket = self.connection.websocket
        while True:
            frame = await self.connection.queue.get()
            self.connection.drained.set()
            if isinstance(frame, Close):
                if frame.error is not None:
                    await websocket.send_text(encode("error", {"id": None, "code": frame.error}))
                await websocket.close(frame.code)
                return
            await websocket.send_text(frame)

    async def receive(self) -> None:
        websocket = self.connection.websocket
        while True:
            text = await websocket.receive_text()
            loop_time = asyncio.get_running_loop().time()
            self.last_heard = loop_time
            if loop_time - self.window_started > EVENT_WINDOW_SECONDS:
                self.window_started, self.window_events = loop_time, 0
            self.window_events += 1
            if self.window_events > EVENT_BUDGET:
                self.connection.terminate(CloseCode.TOO_MANY, "request.rate_limited")
                return
            await self.handle(text)

    async def handle(self, text: str) -> None:
        try:
            event = json.loads(text)
            event_type = str(event["type"])
            event_id = str(event.get("id") or "")[:64] or None
            data = event.get("data") or {}
            if not isinstance(data, dict):
                raise TypeError
        except (ValueError, KeyError, TypeError):
            self.connection.send(
                "error", {"id": None, "code": "request.invalid_event", "detail": {}}
            )
            return
        handler = {
            "ping": self.on_ping,
            "subscribe": self.on_subscribe,
            "message.send": self.on_send,
            "typing": self.on_typing,
            "read": self.on_read,
            "auth.refresh": self.on_refresh,
        }.get(event_type)
        if handler is None:
            code = (
                "request.not_supported" if event_type in LATER_EVENTS else "request.unknown_event"
            )
            self.connection.send("error", {"id": event_id, "code": code, "detail": {}})
            return
        try:
            await handler(event_id, data)
        except ValidationError as exc:
            fields = [{"loc": list(error["loc"]), "type": error["type"]} for error in exc.errors()]
            self.connection.send(
                "error",
                {"id": event_id, "code": "request.validation_failed", "detail": {"fields": fields}},
            )
        except AppError as exc:
            self.connection.send("error", {"id": event_id, "code": exc.code, "detail": exc.details})

    def _services(self, session: Any) -> tuple[ChannelAccess, MessageService]:
        access = ChannelAccess(session, self.gateway.hub.cache, self.gateway.exams)
        messages = MessageService(
            session, access, self.gateway.snowflake, ChatBus(self.gateway.hub.cache)
        )
        return access, messages

    async def on_ping(self, event_id: str | None, _data: dict[str, Any]) -> None:
        self.connection.send("ack", {"id": event_id})

    async def on_subscribe(self, event_id: str | None, data: dict[str, Any]) -> None:
        request = SubscribeIn.model_validate(data)
        user = self.connection.user
        async with self.gateway.database.sessionmaker() as session:
            access, messages = self._services(session)
            states = await access.states(user, list(set(request.channel_ids)))
            # Channels the user is not in are dropped silently: their existence is not revealed (ADR 0004).
            allowed = {channel_id for channel_id, state in states.items() if state.is_member}
            self.gateway.hub.subscribe(self.connection, allowed)
            truncated: list[str] = []
            if request.after is not None:
                for channel_id in sorted(allowed):
                    page = await messages.backfill(channel_id, int(request.after))
                    if page.has_more:
                        # Too much to replay: the client drops its window and loads the latest page (§13.2).
                        truncated.append(str(channel_id))
                        continue
                    for message in page.messages:
                        await self.connection.send_patiently(
                            "message.created", message.model_dump(mode="json")
                        )
            watched = await self._shared_people(session, set(request.presence))
        self.gateway.hub.watch(self.connection, watched)
        for user_id in await self.gateway.presence.online(sorted(watched)):
            self.connection.send("presence", {"user_id": str(user_id), "status": "online"})
        self.connection.send(
            "ack",
            {
                "id": event_id,
                "channel_ids": sorted(str(channel_id) for channel_id in allowed),
                "truncated": truncated,
            },
        )

    async def _shared_people(self, session: Any, user_ids: set[uuid.UUID]) -> set[uuid.UUID]:
        """Presence is visible only to people who share a channel with the user (§5.4, data minimisation)."""
        if not user_ids:
            return set()
        mine = select(ChannelMember.channel_id).where(
            ChannelMember.user_id == self.connection.user.id
        )
        rows = await session.scalars(
            select(ChannelMember.user_id)
            .distinct()
            .where(ChannelMember.user_id.in_(user_ids), ChannelMember.channel_id.in_(mine))
        )
        return set(rows)

    async def on_send(self, event_id: str | None, data: dict[str, Any]) -> None:
        request = SendIn.model_validate(data)
        if not self.gateway.hub.healthy:
            # Nobody would hear it in real time; the client resends through REST (§13.5).
            raise AppError("chat.realtime_unavailable", 503)
        async with self.gateway.database.sessionmaker() as session:
            _, messages = self._services(session)
            outcome = await messages.send(
                self.connection.user,
                request.channel_id,
                request.body,
                request.client_msg_id,
                request.topic_id,
            )
        self.connection.send(
            "ack",
            {
                "id": event_id,
                "message_id": outcome.message.id,
                "client_msg_id": outcome.message.client_msg_id,
                "duplicate": not outcome.created,
            },
        )

    async def on_typing(self, event_id: str | None, data: dict[str, Any]) -> None:
        request = ChannelIn.model_validate(data)
        user = self.connection.user
        async with self.gateway.database.sessionmaker() as session:
            access, _ = self._services(session)
            decision = await access.decide(user, request.channel_id, Action.SEND)
        if not decision.allowed or not await self.gateway.presence.may_type(
            request.channel_id, user.id
        ):
            return
        await ChatBus(self.gateway.hub.cache).publish(
            channel_topic(request.channel_id),
            "typing",
            {
                "channel_id": str(request.channel_id),
                "user_id": str(user.id),
                "display_name": user.display_name,
            },
        )

    async def on_read(self, event_id: str | None, data: dict[str, Any]) -> None:
        request = ReadIn.model_validate(data)
        async with self.gateway.database.sessionmaker() as session:
            _, messages = self._services(session)
            marker = await messages.mark_read(
                self.connection.user, request.channel_id, int(request.message_id)
            )
        self.connection.send("ack", {"id": event_id, "last_read_message_id": str(marker)})

    async def on_refresh(self, event_id: str | None, data: dict[str, Any]) -> None:
        request = RefreshIn.model_validate(data)
        try:
            redeemed = await tickets.redeem(
                self.connection.websocket.app.state.durable_redis, request.ticket
            )
        except (RedisError, OSError) as exc:
            raise AppError("chat.unavailable", 503) from exc
        if redeemed is None or redeemed.user_id != self.connection.user.id:
            self.connection.terminate(CloseCode.UNAUTHORIZED, "auth.expired")
            return
        self.connection.authorized_until = redeemed.token_expires_at
        self.refresh_requested = False
        self.connection.send("ack", {"id": event_id})

    async def tick(self) -> None:
        """Heartbeat: presence, silent clients, the end of the token's lifetime, and memberships that were
        revoked while a control event got lost (§5.9)."""
        while self._authorized():
            await asyncio.sleep(self._next_tick())
            if not self._authorized():
                return
            if asyncio.get_running_loop().time() - self.last_heard > SILENCE_LIMIT_SECONDS:
                self.connection.terminate(1001)
                return
            await self.gateway.presence.heartbeat(self.connection.user.id, self.connection.id)
            await self._recheck()

    def _remaining(self) -> float:
        return (self.connection.authorized_until - datetime.now(UTC)).total_seconds()

    def _authorized(self) -> bool:
        """Asks for a fresh ticket a minute before the token ends and closes the socket when it has."""
        remaining = self._remaining()
        if remaining <= 0:
            self.connection.terminate(CloseCode.UNAUTHORIZED, "auth.expired")
            return False
        if remaining <= REFRESH_NOTICE_SECONDS and not self.refresh_requested:
            self.refresh_requested = True
            self.connection.send("auth.refresh_needed", {})
        return True

    def _next_tick(self) -> float:
        remaining = self._remaining()
        candidates = [self.gateway.heartbeat_seconds, remaining]
        if not self.refresh_requested:
            candidates.append(remaining - REFRESH_NOTICE_SECONDS)
        return max(0.05, min(candidates))

    async def _recheck(self) -> None:
        connection = self.connection
        async with self.gateway.database.sessionmaker() as session:
            user = await UserService(session).current(connection.user.id)
            if user is None or not user.is_active:
                connection.terminate(CloseCode.FORBIDDEN, "auth.account_inactive")
                return
            if not connection.channels:
                return
            kept = set(
                await session.scalars(
                    select(ChannelMember.channel_id).where(
                        ChannelMember.user_id == user.id,
                        ChannelMember.channel_id.in_(connection.channels),
                    )
                )
            )
        for channel_id in connection.channels - kept:
            self.gateway.hub.revoke(user.id, channel_id)
