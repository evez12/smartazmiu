import asyncio
import contextlib
import json
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import pytest
import pytest_asyncio
import uvicorn
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed
from websockets.typing import Origin

# Channels are derived from the imported registry, loaded through the import fixtures.
from app.modules.academics.tests.conftest import seed, staff_headers, upload
from app.modules.chat.models import Channel, ChannelMember, ChannelType, MemberRole
from tests.support import TokenFactory

__all__ = ["seed", "staff_headers", "upload"]

ORIGIN = "https://smartazmiu.test"


@dataclass(frozen=True)
class Person:
    id: uuid.UUID
    headers: dict[str, str]
    name: str


MakePerson = Callable[..., Awaitable[Person]]


@pytest.fixture
def person(client: AsyncClient, tokens: TokenFactory) -> MakePerson:
    """A signed-in account (provisioned through ``/me`` like a first request)."""

    async def create(
        given: str = "Aysel", family: str = "Məmmədova", roles: list[str] | None = None
    ) -> Person:
        token = tokens.issue(
            str(uuid.uuid4()),
            roles if roles is not None else ["student"],
            given_name=given,
            family_name=family,
            email=f"{uuid.uuid4().hex[:8]}@smartazmiu.test",
        )
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.get("/api/v1/me", headers=headers)
        assert response.status_code == 200, response.text
        return Person(uuid.UUID(response.json()["id"]), headers, f"{given} {family}")

    return create


MakeChannel = Callable[..., Awaitable[uuid.UUID]]


@pytest.fixture
def channel(db: AsyncSession) -> MakeChannel:
    """A private group with the given members; other channel fields can be overridden."""

    async def create(
        *members: Person, name: str = "Statistika layihəsi", **fields: Any
    ) -> uuid.UUID:
        channel_id: uuid.UUID | None = await db.scalar(
            insert(Channel)
            .values(type=fields.pop("type", ChannelType.PRIVATE_GROUP), name=name, **fields)
            .returning(Channel.id)
        )
        assert channel_id is not None
        if members:
            await db.execute(
                insert(ChannelMember),
                [
                    {"channel_id": channel_id, "user_id": member.id, "role": MemberRole.MEMBER}
                    for member in members
                ],
            )
        await db.commit()
        return channel_id

    return create


@pytest_asyncio.fixture
async def server(app: FastAPI) -> AsyncIterator[str]:
    """The test app served by uvicorn on a free port; WebSockets need a real server, not ASGITransport."""
    config = uvicorn.Config(app, host="127.0.0.1", port=0, lifespan="off", log_config=None)
    instance = uvicorn.Server(config)
    task = asyncio.create_task(instance.serve())
    while not instance.started:  # noqa: ASYNC110 - uvicorn offers no event for "started"
        await asyncio.sleep(0.01)
    port = instance.servers[0].sockets[0].getsockname()[1]
    yield f"ws://127.0.0.1:{port}"
    instance.should_exit = True
    await task


class Socket:
    """A client connection that keeps every frame, so tests can wait for the one they expect."""

    def __init__(self, connection: ClientConnection) -> None:
        self.connection = connection
        self.frames: list[dict[str, Any]] = []
        self.counter = 0

    async def send(self, event_type: str, data: dict[str, Any] | None = None) -> str:
        self.counter += 1
        event_id = f"e{self.counter}"
        await self.connection.send(
            json.dumps({"type": event_type, "id": event_id, "data": data or {}})
        )
        return event_id

    async def next(self, within: float = 3.0) -> dict[str, Any]:
        async with asyncio.timeout(within):
            frame: dict[str, Any] = json.loads(await self.connection.recv())
        self.frames.append(frame)
        return frame

    async def expect(self, event_type: str, within: float = 3.0, **match: Any) -> dict[str, Any]:
        """The next frame of this type whose data contains ``match``; others are kept in ``frames``."""
        async with asyncio.timeout(within):
            while True:
                frame = await self.next(within)
                data: dict[str, Any] = frame.get("data", {})
                if frame["type"] == event_type and all(data.get(k) == v for k, v in match.items()):
                    return data

    async def reply(self, event_type: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Sends an event and returns its ack or error."""
        event_id = await self.send(event_type, data)
        async with asyncio.timeout(3):
            while True:
                frame = await self.next()
                if frame["type"] in ("ack", "error") and frame["data"].get("id") == event_id:
                    return frame

    async def silent(self, seconds: float = 0.3) -> list[dict[str, Any]]:
        """Frames that arrive within ``seconds``, for asserting that something did not happen."""
        received: list[dict[str, Any]] = []
        with contextlib.suppress(TimeoutError):
            async with asyncio.timeout(seconds):
                while True:
                    received.append(await self.next(seconds))
        return received

    async def closed(self, within: float = 3.0) -> int | None:
        """Reads until the server closes the socket and returns the close code."""
        with contextlib.suppress(TimeoutError, ConnectionClosed):
            async with asyncio.timeout(within):
                while True:
                    await self.next(within)
        return self.connection.close_code


Open = Callable[..., Awaitable[Socket]]


@pytest_asyncio.fixture
async def open_socket(server: str, client: AsyncClient) -> AsyncIterator[Open]:
    sockets: list[Socket] = []

    async def open_(
        person: Person | None = None, *, ticket: str | None = None, origin: str = ORIGIN
    ) -> Socket:
        if ticket is None:
            assert person is not None
            response = await client.post("/api/v1/ws/ticket", headers=person.headers)
            assert response.status_code == 200, response.text
            ticket = response.json()["ticket"]
        connection = await connect(
            f"{server}/ws?ticket={ticket}",
            origin=Origin(origin),
            proxy=None,
        )
        socket = Socket(connection)
        sockets.append(socket)
        return socket

    yield open_
    for socket in sockets:
        await socket.connection.close()
