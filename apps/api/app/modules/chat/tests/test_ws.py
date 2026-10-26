import asyncio
import hashlib
import logging
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import REDACTED, RedactTicketsFilter, redact_sensitive
from app.core.observability import scrub_event
from app.modules.chat import hub as hub_module
from app.modules.chat import tickets
from app.modules.chat import ws as ws_module
from app.modules.chat.bus import ChatBus
from app.modules.chat.hub import Close, CloseCode, Connection
from app.modules.chat.models import ChannelMember, Message
from app.modules.chat.snowflake import created_at_of, floor_id
from app.modules.notifications.models import NotificationCategory, NotificationKind
from app.modules.notifications.service import NotificationSpec, Notifier
from app.modules.users.models import User, UserStatus
from app.modules.users.service import CurrentUser

from .conftest import MakeChannel, MakePerson, Open, Person, Socket


def body(text_: str = "Sabahkı seminar 1-305 otağındadır.") -> dict[str, str]:
    return {"body": text_, "client_msg_id": str(uuid.uuid4())}


async def joined(socket: Socket, *channel_ids: uuid.UUID, **extra: object) -> dict[str, object]:
    reply = await socket.reply("subscribe", {"channel_ids": [str(c) for c in channel_ids], **extra})
    assert reply["type"] == "ack", reply
    data: dict[str, object] = reply["data"]
    return data


async def ticket_for(app: FastAPI, person: Person, valid_for: timedelta) -> str:
    ticket, _ = await tickets.issue(
        app.state.durable_redis, person.id, datetime.now(UTC) + valid_for
    )
    return ticket


async def test_a_ticket_opens_one_socket_once(
    open_socket: Open, person: MakePerson, client: AsyncClient, app: FastAPI
) -> None:
    aysel = await person()
    response = await client.post("/api/v1/ws/ticket", headers=aysel.headers)
    ticket = response.json()["ticket"]
    assert len(ticket) == 43
    first = await open_socket(ticket=ticket)
    assert (await first.reply("ping"))["type"] == "ack"
    # A second use of the same ticket, an unknown one and a missing one are refused before any data.
    for attempt in (ticket, "x" * 43, ""):
        refused = await open_socket(ticket=attempt)
        assert await refused.closed() == CloseCode.UNAUTHORIZED
    # Only the hash is stored, on Redis A, for at most 60 s.
    redis = app.state.durable_redis
    fresh = (await client.post("/api/v1/ws/ticket", headers=aysel.headers)).json()["ticket"]
    assert await redis.get(f"ws:ticket:{fresh}") is None
    key = f"ws:ticket:{hashlib.sha256(fresh.encode()).hexdigest()}"
    assert 0 < await redis.ttl(key) <= 60
    await redis.delete(key)  # as if 60 s had passed
    assert await (await open_socket(ticket=fresh)).closed() == CloseCode.UNAUTHORIZED
    # A token that has already expired cannot open a socket either.
    stale = await ticket_for(app, aysel, timedelta(seconds=-1))
    assert await (await open_socket(ticket=stale)).closed() == CloseCode.UNAUTHORIZED
    assert (await client.post("/api/v1/ws/ticket")).status_code == 401


async def test_ticket_issuing_is_rate_limited(person: MakePerson, client: AsyncClient) -> None:
    aysel = await person()
    statuses = [
        (await client.post("/api/v1/ws/ticket", headers=aysel.headers)).status_code
        for _ in range(31)
    ]
    assert statuses[:30] == [200] * 30
    assert statuses[30] == 429


async def test_foreign_origins_and_inactive_accounts_are_refused(
    open_socket: Open, person: MakePerson, db: AsyncSession, app: FastAPI
) -> None:
    aysel = await person()
    foreign = await open_socket(aysel, origin="https://evil.test")
    assert await foreign.closed() == CloseCode.FORBIDDEN
    await db.execute(update(User).where(User.id == aysel.id).values(status=UserStatus.INACTIVE))
    await db.commit()
    inactive = await open_socket(ticket=await ticket_for(app, aysel, timedelta(minutes=5)))
    assert await inactive.closed() == CloseCode.FORBIDDEN


async def test_messages_are_stored_before_they_are_delivered(
    open_socket: Open, person: MakePerson, channel: MakeChannel, db: AsyncSession
) -> None:
    aysel, ramin = await person(), await person("Ramin", "Əliyev")
    stranger = await person("Orxan", "Rzayev")
    room = await channel(aysel, ramin)
    elsewhere = await channel(stranger, name="Başqa qrup")
    sender, receiver = await open_socket(aysel), await open_socket(ramin)
    # Channels the user is not in are dropped from the subscription without saying they exist.
    assert (await joined(sender, room, elsewhere))["channel_ids"] == [str(room)]
    await joined(receiver, room)

    payload = body()
    reply = await sender.reply("message.send", {"channel_id": str(room), **payload})
    assert reply["type"] == "ack"
    assert reply["data"]["client_msg_id"] == payload["client_msg_id"]
    assert reply["data"]["duplicate"] is False
    delivered = await receiver.expect("message.created", id=reply["data"]["message_id"])
    # The row was committed before the event went out (§5.9).
    stored = await db.scalar(select(Message.body).where(Message.id == int(delivered["id"])))
    assert stored == payload["body"]
    assert delivered["author"]["display_name"] == "Aysel Məmmədova"
    assert delivered["channel_id"] == str(room)
    assert "grade" not in str(delivered)

    # A retry of the same client id (reconnect, double click) gets the same ack and stores nothing new.
    again = await sender.reply("message.send", {"channel_id": str(room), **payload})
    assert again["data"]["message_id"] == reply["data"]["message_id"]
    assert again["data"]["duplicate"] is True
    assert await db.scalar(select(func.count()).select_from(Message)) == 1
    assert not [f for f in await receiver.silent() if f["type"] == "message.created"]

    # A channel the sender is not in looks exactly like one that does not exist.
    for target in (elsewhere, uuid.uuid4()):
        refused = await sender.reply("message.send", {"channel_id": str(target), **body()})
        assert refused["data"]["code"] == "chat.channel_not_found"
    too_long = await sender.reply("message.send", {"channel_id": str(room), **body("ə" * 4001)})
    assert too_long["data"]["code"] == "chat.message_too_long"
    assert too_long["data"]["detail"] == {"max_length": 4000}
    assert (await sender.reply("message.send", {"channel_id": str(room), **body("ə" * 4000)}))[
        "type"
    ] == "ack"


async def test_reconnecting_clients_receive_what_they_missed(
    open_socket: Open, person: MakePerson, channel: MakeChannel, db: AsyncSession
) -> None:
    aysel, ramin = await person(), await person("Ramin", "Əliyev")
    room = await channel(aysel, ramin)
    sender = await open_socket(aysel)
    await joined(sender, room)
    first = await sender.reply("message.send", {"channel_id": str(room), **body("Birinci")})
    last_seen = first["data"]["message_id"]
    sent = []
    for text_ in ("İkinci", "Üçüncü", "Dördüncü"):
        reply = await sender.reply("message.send", {"channel_id": str(room), **body(text_)})
        sent.append(reply["data"]["message_id"])

    receiver = await open_socket(ramin)
    ack = await joined(receiver, room, after=last_seen)
    replayed = [f["data"]["id"] for f in receiver.frames if f["type"] == "message.created"]
    assert replayed == sent  # in id order, nothing duplicated, nothing missing
    assert ack["truncated"] == []

    # More than 1,000 missed messages, or a gap beyond the three-day window: the client reloads (§13.2).
    start = floor_id(datetime.now(UTC) - timedelta(hours=1))
    await db.execute(
        text(
            "INSERT INTO messages (id, created_at, channel_id, author_id, body, client_msg_id)"
            " SELECT CAST(:start AS bigint) + n, :at, :channel, :author, 'Köhnə mesaj ' || n, gen_random_uuid()"
            " FROM generate_series(1, 1001) AS n"
        ),
        {"start": start, "at": created_at_of(start), "channel": room, "author": aysel.id},
    )
    await db.commit()
    reconnect = await open_socket(ramin)
    assert (await joined(reconnect, room, after=str(start)))["truncated"] == [str(room)]
    old = str(floor_id(datetime.now(UTC) - timedelta(days=4)))
    later = await open_socket(ramin)
    assert (await joined(later, room, after=old))["truncated"] == [str(room)]


async def test_revoked_access_takes_effect_while_connected(
    open_socket: Open,
    person: MakePerson,
    channel: MakeChannel,
    db: AsyncSession,
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    aysel, ramin = await person(), await person("Ramin", "Əliyev")
    room, other = await channel(aysel, ramin), await channel(aysel, ramin, name="765a2")
    sender, receiver = await open_socket(aysel), await open_socket(ramin)
    await joined(sender, room, other)
    await joined(receiver, room, other)

    # Provisioning removed Ramin (a group transfer) and announced it on his control channel.
    await db.execute(
        delete(ChannelMember).where(
            ChannelMember.channel_id == room, ChannelMember.user_id == ramin.id
        )
    )
    await db.commit()
    await ChatBus(app.state.redis).membership_changed([], [(room, ramin.id)])
    removed = await receiver.expect("channel.updated", channel_id=str(room))
    assert removed["removed"] is True
    await sender.reply("message.send", {"channel_id": str(room), **body("Ramin bunu görməməlidir")})
    assert not [f for f in await receiver.silent() if f["type"] == "message.created"]
    refused = await receiver.reply("message.send", {"channel_id": str(room), **body()})
    assert refused["data"]["code"] == "chat.channel_not_found"

    # The control event got lost: the next heartbeat notices the missing membership anyway.
    app.state.chat_gateway.heartbeat_seconds = 0.1
    late = await open_socket(ramin)
    await joined(late, other)
    await db.execute(
        delete(ChannelMember).where(
            ChannelMember.channel_id == other, ChannelMember.user_id == ramin.id
        )
    )
    await db.commit()
    assert (await late.expect("channel.updated", channel_id=str(other)))["removed"] is True


async def test_presence_survives_a_short_drop_and_ends_after_the_grace_period(
    open_socket: Open,
    person: MakePerson,
    channel: MakeChannel,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ws_module, "OFFLINE_GRACE_SECONDS", 0.5)
    aysel, ramin = await person(), await person("Ramin", "Əliyev")
    stranger = await person("Orxan", "Rzayev")
    room = await channel(aysel, ramin)
    watcher = await open_socket(aysel)
    await joined(watcher, room, presence=[str(ramin.id), str(stranger.id)])
    first_tab = await open_socket(ramin)
    assert (await watcher.expect("presence", user_id=str(ramin.id)))["status"] == "online"
    second_tab = await open_socket(ramin)
    await first_tab.connection.close()
    await asyncio.sleep(0.8)
    # One tab is still open: no offline event.
    assert not [f for f in await watcher.silent(0.3) if f["type"] == "presence"]
    await second_tab.connection.close()
    assert (await watcher.expect("presence", user_id=str(ramin.id), within=3))["status"] == (
        "offline"
    )
    # People who share no channel with the watcher are never reported.
    await open_socket(stranger)
    assert not [
        f
        for f in await watcher.silent(0.5)
        if f["type"] == "presence" and f["data"]["user_id"] == str(stranger.id)
    ]


async def test_sending_is_rate_limited_and_typing_throttled(
    open_socket: Open, person: MakePerson, channel: MakeChannel
) -> None:
    aysel, ramin = await person(), await person("Ramin", "Əliyev")
    room = await channel(aysel, ramin)
    sender, receiver = await open_socket(aysel), await open_socket(ramin)
    await joined(sender, room)
    await joined(receiver, room)
    replies = [
        await sender.reply("message.send", {"channel_id": str(room), **body(f"Mesaj {n}")})
        for n in range(11)
    ]
    assert [r["type"] for r in replies] == ["ack"] * 10 + ["error"]
    assert replies[10]["data"]["code"] == "chat.rate_limited"
    assert 0 < replies[10]["data"]["detail"]["retry_after_seconds"] <= 10

    for _ in range(3):
        await sender.send("typing", {"channel_id": str(room)})
    frames = await receiver.silent(0.5)
    typing = [f for f in frames if f["type"] == "typing"]
    assert len(typing) == 1
    assert typing[0]["data"]["user_id"] == str(aysel.id)


async def test_tabs_stay_consistent_and_the_bell_updates_live(
    open_socket: Open, person: MakePerson, channel: MakeChannel, db: AsyncSession
) -> None:
    aysel, ramin = await person(), await person("Ramin", "Əliyev")
    room = await channel(aysel, ramin)
    sender = await open_socket(ramin)
    await joined(sender, room)
    message = await sender.reply("message.send", {"channel_id": str(room), **body()})
    tab_a, tab_b = await open_socket(aysel), await open_socket(aysel)
    await joined(tab_a, room)
    await joined(tab_b, room)
    read = await tab_a.reply(
        "read", {"channel_id": str(room), "message_id": message["data"]["message_id"]}
    )
    assert read["data"]["last_read_message_id"] == message["data"]["message_id"]
    updated = await tab_b.expect("read.updated", channel_id=str(room))
    assert updated["last_read_message_id"] == message["data"]["message_id"]
    # The marker never moves backwards (D-002).
    back = await tab_a.reply("read", {"channel_id": str(room), "message_id": "1"})
    assert back["data"]["last_read_message_id"] == message["data"]["message_id"]

    # A notification committed anywhere (here: directly) reaches every open tab of its recipient.
    subject = uuid.uuid4()
    await Notifier(db).notify(
        select(User.id).where(User.id == aysel.id),
        NotificationSpec(
            category=NotificationCategory.EVENTS,
            kind=NotificationKind.EVENT_PUBLISHED,
            subject_type="event",
            subject_id=subject,
            dedupe_key=f"event:{subject}",
            title="Karyera günü",
            link=f"/events/{subject}",
        ),
        deliver=False,
    )
    await db.commit()
    await tab_a.expect("notification")
    await tab_b.expect("notification")


async def test_the_session_ends_with_the_token_unless_refreshed(
    open_socket: Open, person: MakePerson, app: FastAPI, client: AsyncClient
) -> None:
    aysel = await person()
    socket = await open_socket(ticket=await ticket_for(app, aysel, timedelta(seconds=61)))
    await socket.expect("auth.refresh_needed", within=3)
    fresh = (await client.post("/api/v1/ws/ticket", headers=aysel.headers)).json()["ticket"]
    assert (await socket.reply("auth.refresh", {"ticket": fresh}))["type"] == "ack"

    expiring = await open_socket(ticket=await ticket_for(app, aysel, timedelta(seconds=1)))
    await expiring.expect("auth.refresh_needed")
    error = await expiring.expect("error", within=3)
    assert error["code"] == "auth.expired"
    assert await expiring.closed() == CloseCode.UNAUTHORIZED

    # A ticket of somebody else cannot extend this socket.
    ramin = await person("Ramin", "Əliyev")
    foreign = (await client.post("/api/v1/ws/ticket", headers=ramin.headers)).json()["ticket"]
    await socket.send("auth.refresh", {"ticket": foreign})
    assert await socket.closed() == CloseCode.UNAUTHORIZED


async def test_unknown_and_malformed_events_get_typed_errors(
    open_socket: Open, person: MakePerson
) -> None:
    socket = await open_socket(await person())
    assert (await socket.reply("message.edit", {}))["data"]["code"] == "request.validation_failed"
    assert (await socket.reply("presence.watch", {}))["data"]["code"] == "request.unknown_event"
    invalid = await socket.reply("message.send", {"channel_id": "not-a-uuid"})
    assert invalid["data"]["code"] == "request.validation_failed"
    await socket.connection.send("{not json")
    assert (await socket.expect("error"))["code"] == "request.invalid_event"
    for _ in range(ws_module.EVENT_BUDGET + 5):
        await socket.send("ping")
    assert await socket.closed() == CloseCode.TOO_MANY


async def test_a_lost_bus_sends_clients_to_the_rest_fallback(
    open_socket: Open, person: MakePerson, app: FastAPI
) -> None:
    aysel = await person()
    socket = await open_socket(aysel)
    await socket.reply("ping")  # registered with the hub
    hub = app.state.chat_gateway.hub
    hub._lost_bus(ConnectionError("redis down"))
    assert (await socket.expect("error"))["code"] == "chat.realtime_unavailable"
    assert await socket.closed() == CloseCode.TRY_AGAIN_LATER
    assert await (await open_socket(aysel)).closed() == CloseCode.TRY_AGAIN_LATER
    hub.healthy = True


def test_a_slow_consumer_is_disconnected_with_a_reconnect_hint() -> None:
    user = CurrentUser(
        id=uuid.uuid4(),
        display_name="Aysel Məmmədova",
        given_name="Aysel",
        family_name="Məmmədova",
        status=UserStatus.ACTIVE,
        roles=frozenset({"student"}),
        permissions=frozenset(),
    )
    connection = Connection(websocket=None, user=user, authorized_until=datetime.now(UTC))  # type: ignore[arg-type]
    for index in range(hub_module.SEND_QUEUE_LIMIT + 10):
        connection.push(f'{{"n":{index}}}')
    assert connection.closing
    frames = [connection.queue.get_nowait() for _ in range(connection.queue.qsize())]
    assert len(frames) == hub_module.SEND_QUEUE_LIMIT + 1
    assert frames[-1] == Close(CloseCode.SLOW_CONSUMER, "chat.slow_consumer")


async def test_tickets_never_reach_logs_or_error_reports(
    open_socket: Open, person: MakePerson, client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    aysel = await person()
    ticket = (await client.post("/api/v1/ws/ticket", headers=aysel.headers)).json()["ticket"]
    # The application's own log handler redacts tickets; the capture handler gets the same filter here.
    assert any(
        isinstance(rule, RedactTicketsFilter)
        for handler in logging.getLogger().handlers
        for rule in handler.filters
    )
    caplog.handler.addFilter(RedactTicketsFilter())
    with caplog.at_level(logging.INFO):
        socket = await open_socket(ticket=ticket)
        await socket.reply("ping")
        await socket.connection.close()
        await asyncio.sleep(0.1)
    lines = [caplog.handler.format(record) for record in caplog.records]
    assert any("socket_opened" in line for line in lines)
    assert any("WebSocket /ws?ticket=[redacted]" in line for line in lines)
    assert not [line for line in lines if ticket in line]
    assert redact_sensitive(None, "info", {"ticket": ticket})["ticket"] == REDACTED
    event = scrub_event(
        {
            "request": {
                "url": f"https://smartazmiu.test/ws?ticket={ticket}",
                "query_string": f"ticket={ticket}",
            }
        },
        {},
    )
    assert event == {"request": {"url": "https://smartazmiu.test/ws"}}


async def test_notifications_are_announced_only_on_commit(db: AsyncSession, app: FastAPI) -> None:
    hub = app.state.chat_gateway.hub
    received: list[uuid.UUID] = []
    hub.notify = received.append
    user = User(display_name="Aysel Məmmədova", idp_subject=str(uuid.uuid4()))
    db.add(user)
    await db.commit()
    user_id = user.id
    subject = uuid.uuid4()
    spec = NotificationSpec(
        category=NotificationCategory.EVENTS,
        kind=NotificationKind.EVENT_PUBLISHED,
        subject_type="event",
        subject_id=subject,
        dedupe_key=f"event:{subject}",
        title="Karyera günü",
        link=f"/events/{subject}",
    )
    await Notifier(db).notify(select(User.id).where(User.id == user_id), spec, deliver=False)
    await db.rollback()
    await asyncio.sleep(0.3)
    assert received == []
    await Notifier(db).notify(select(User.id).where(User.id == user_id), spec, deliver=False)
    await db.commit()
    for _ in range(50):
        if received:
            break
        await asyncio.sleep(0.05)
    assert received == [user_id]


def test_the_proxy_logs_paths_without_query_strings() -> None:
    """The ticket rides in the query string; nginx must log ``$uri`` only (ADR 0003)."""
    config = (Path(__file__).resolve().parents[6] / "infra" / "nginx" / "nginx.conf").read_text()
    log_format = config[config.index("log_format") : config.index("access_log")]
    assert "$uri" in log_format
    for leaky in ("$request_uri", "$args", "$query_string", '$request"', "$request "):
        assert leaky not in log_format
    assert "location = /ws" in config
    assert "proxy_set_header Upgrade $http_upgrade;" in config
