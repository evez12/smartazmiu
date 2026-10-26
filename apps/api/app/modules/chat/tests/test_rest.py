import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import FastAPI
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.chat.models import Channel, ChannelMember, ChannelType
from app.modules.chat.provisioning import ChannelProvisioner
from app.modules.chat.snowflake import created_at_of, floor_id
from app.modules.users.models import DmPolicy, User
from tests.support import TokenFactory
from tests.test_jobs import _closed_port

from .conftest import MakeChannel, MakePerson, Person

Seed = Callable[..., Awaitable[None]]

API = "/api/v1"


def signed_in(
    tokens: TokenFactory, email: str, given: str, family: str, roles: list[str]
) -> dict[str, str]:
    token = tokens.issue(
        str(uuid.uuid4()), roles, given_name=given, family_name=family, email=email
    )
    return {"Authorization": f"Bearer {token}"}


async def add_messages(
    db: AsyncSession, channel_id: uuid.UUID, author_id: uuid.UUID, count: int, at: datetime
) -> int:
    """Inserts ``count`` messages one millisecond apart starting at ``at``; returns the last id."""
    start = floor_id(at)
    await db.execute(
        text(
            "INSERT INTO messages (id, created_at, channel_id, author_id, body, client_msg_id)"
            " SELECT CAST(:start AS bigint) + (n << 22), CAST(:at AS timestamptz) + n * interval '1 millisecond',"
            " :channel, :author, 'Mesaj ' || n, gen_random_uuid() FROM generate_series(0, :last) AS n"
        ),
        {
            "start": start,
            "at": created_at_of(start),
            "channel": channel_id,
            "author": author_id,
            "last": count - 1,
        },
    )
    await db.commit()
    return start + ((count - 1) << 22)


def keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for item in value.values() for k in keys(item)}
    if isinstance(value, list):
        return {k for item in value for k in keys(item)}
    return set()


async def test_my_channels_are_grouped_with_capped_unread_counts_and_no_grades(
    client: AsyncClient, db: AsyncSession, seed: Seed, tokens: TokenFactory
) -> None:
    await seed()
    await ChannelProvisioner(db).run()
    aysel = signed_in(tokens, "aysel.mammadova@smartazmiu.test", "Aysel", "Məmmədova", ["student"])
    ramin = signed_in(tokens, "ramin.aliyev@smartazmiu.test", "Ramin", "Əliyev", ["student"])
    listed = await client.get(f"{API}/chat/channels", headers=aysel)
    assert listed.status_code == 200, listed.text
    channels = listed.json()["channels"]
    types = [channel["type"] for channel in channels]
    # Sidebar order: courses, communities, group, faculty (§12.7).
    assert types == sorted(
        types, key=["course_offering", "subject_community", "academic_group", "faculty"].index
    )
    statistics = next(
        c
        for c in channels
        if c["name"] == "Statistika" and c["type"] == "course_offering" and not c["is_archived"]
    )
    assert statistics["context"] == "765a2 · 2026 Payız"
    assert statistics["posting"] == {
        "allowed": True,
        "reason": None,
        "until": None,
        "retry_after_seconds": None,
    }
    archived = next(c for c in channels if c["is_archived"])
    assert archived["posting"]["reason"] == "chat.channel_archived"
    group = next(c for c in channels if c["type"] == "academic_group")
    assert group["name"] == "765a2"
    # Aysel has a graded, completed enrollment (D-038); nothing about results reaches chat payloads (§5.4).
    assert not {k for k in keys(listed.json()) if "grade" in k or k in ("passed", "status")}

    me = (await client.get(f"{API}/me", headers=ramin)).json()["id"]
    channel_id = uuid.UUID(statistics["id"])
    joined_at = await db.scalar(
        select(ChannelMember.joined_at).where(ChannelMember.channel_id == channel_id).limit(1)
    )
    assert joined_at is not None
    # Messages from before Aysel joined do not count as unread; 150 after it count as "99+" (100).
    await add_messages(db, channel_id, uuid.UUID(me), 3, joined_at - timedelta(minutes=5))
    last = await add_messages(db, channel_id, uuid.UUID(me), 150, joined_at + timedelta(seconds=1))
    counted = await client.get(f"{API}/chat/channels/{channel_id}", headers=aysel)
    assert counted.json()["unread_count"] == 100
    assert [topic["slug"] for topic in counted.json()["topics"]] == [
        "umumi",
        "suallar",
        "materiallar",
        "imtahan-hazirligi",
    ]
    read = await client.post(
        f"{API}/chat/channels/{channel_id}/read",
        headers=aysel,
        json={"last_read_message_id": str(last - (10 << 22))},
    )
    assert read.json() == {
        "channel_id": str(channel_id),
        "last_read_message_id": str(last - (10 << 22)),
    }
    assert (await client.get(f"{API}/chat/channels/{channel_id}", headers=aysel)).json()[
        "unread_count"
    ] == 10
    # The marker only moves forward, and never past the newest message.
    await client.post(
        f"{API}/chat/channels/{channel_id}/read", headers=aysel, json={"last_read_message_id": "5"}
    )
    far = await client.post(
        f"{API}/chat/channels/{channel_id}/read",
        headers=aysel,
        json={"last_read_message_id": str(last + (1 << 40))},
    )
    assert far.json()["last_read_message_id"] == str(last)
    # Own messages never count.
    assert (await client.get(f"{API}/chat/channels/{channel_id}", headers=ramin)).json()[
        "unread_count"
    ] == 0

    members = (await client.get(f"{API}/chat/channels/{channel_id}/members", headers=aysel)).json()[
        "members"
    ]
    leyla = next(m for m in members if m["display_name"] == "Leyla Həsənova")
    assert leyla["badge"] == "teacher"
    assert not {k for k in keys(members) if k in ("email", "grade", "university_id")}
    page = (
        await client.get(f"{API}/chat/channels/{channel_id}/messages?limit=5", headers=aysel)
    ).json()
    assert len(page["messages"]) == 5
    assert page["has_more"] is True
    assert not {k for k in keys(page) if "grade" in k}


async def test_other_peoples_channels_are_indistinguishable_from_missing_ones(
    client: AsyncClient, person: MakePerson, channel: MakeChannel
) -> None:
    aysel, stranger = await person(), await person("Orxan", "Rzayev")
    room = await channel(aysel)
    payload = {"body": "Salam", "client_msg_id": str(uuid.uuid4())}
    for target in (room, uuid.uuid4()):
        for method, path, body in (
            ("GET", f"/chat/channels/{target}", None),
            ("GET", f"/chat/channels/{target}/messages", None),
            ("GET", f"/chat/channels/{target}/members", None),
            ("POST", f"/chat/channels/{target}/messages", payload),
            ("POST", f"/chat/channels/{target}/read", {"last_read_message_id": "1"}),
            ("PATCH", f"/chat/channels/{target}/members/me", {"notify_level": "none"}),
        ):
            response = await client.request(
                method, f"{API}{path}", headers=stranger.headers, json=body
            )
            assert response.status_code == 404, (method, path)
            assert response.json()["error"]["code"] == "chat.channel_not_found"


async def test_the_rest_fallback_sends_idempotently_even_without_redis(
    client: AsyncClient, person: MakePerson, channel: MakeChannel, app: FastAPI, db: AsyncSession
) -> None:
    aysel = await person()
    room = await channel(aysel)
    payload = {"body": "Mühazirə 1-301-də olacaq.", "client_msg_id": str(uuid.uuid4())}
    healthy = app.state.redis
    app.state.redis = Redis(host="127.0.0.1", port=_closed_port(), socket_connect_timeout=0.2)
    try:
        first = await client.post(
            f"{API}/chat/channels/{room}/messages", headers=aysel.headers, json=payload
        )
        again = await client.post(
            f"{API}/chat/channels/{room}/messages", headers=aysel.headers, json=payload
        )
    finally:
        await app.state.redis.aclose()
        app.state.redis = healthy
    assert (first.status_code, again.status_code) == (201, 200)
    assert first.json()["message"]["id"] == again.json()["message"]["id"]
    assert again.json()["duplicate"] is True
    assert first.json()["message"]["author"]["display_name"] == "Aysel Məmmədova"
    too_long = await client.post(
        f"{API}/chat/channels/{room}/messages",
        headers=aysel.headers,
        json={"body": "x" * 4001, "client_msg_id": str(uuid.uuid4())},
    )
    assert too_long.status_code == 422
    assert too_long.json()["error"]["code"] == "chat.message_too_long"
    limited = [
        (
            await client.post(
                f"{API}/chat/channels/{room}/messages",
                headers=aysel.headers,
                json={"body": f"Mesaj {n}", "client_msg_id": str(uuid.uuid4())},
            )
        ).status_code
        for n in range(20)
    ]
    # 10 per 10 s per channel (§5.5); 20 quick sends cannot all fit in one window or two.
    assert 429 in limited


async def set_policy(db: AsyncSession, person: Person, policy: DmPolicy) -> None:
    await db.execute(update(User).where(User.id == person.id).values(dm_policy=policy))
    await db.commit()


async def test_direct_messages_follow_dm_policy_and_blocks(
    client: AsyncClient, person: MakePerson, channel: MakeChannel, db: AsyncSession
) -> None:
    aysel, ramin = await person(), await person("Ramin", "Əliyev")
    stranger = await person("Orxan", "Rzayev")
    teacher = await person("Leyla", "Həsənova", roles=["teacher"])
    await channel(aysel, ramin, type=ChannelType.ACADEMIC_GROUP, name="765a2")

    async def open_dm(sender: Person, target: Person | uuid.UUID) -> Any:
        target_id = target.id if isinstance(target, Person) else target
        return await client.post(
            f"{API}/chat/dm", headers=sender.headers, json={"user_id": str(target_id)}
        )

    # Default shared_context: people of the same group may write; others may not.
    created = await open_dm(aysel, ramin)
    assert created.status_code == 201, created.text
    dm = created.json()
    assert (dm["type"], dm["name"], dm["peer"]["display_name"]) == (
        "dm",
        "Ramin Əliyev",
        "Ramin Əliyev",
    )
    reopened = await open_dm(ramin, aysel)
    assert (reopened.status_code, reopened.json()["id"]) == (200, dm["id"])
    assert reopened.json()["name"] == "Aysel Məmmədova"
    refused = await open_dm(stranger, aysel)
    assert (refused.status_code, refused.json()["error"]["code"]) == (403, "chat.dm_unavailable")
    await set_policy(db, aysel, DmPolicy.EVERYONE)
    assert (await open_dm(stranger, aysel)).status_code == 201

    # nobody and guides_and_teachers: students are refused, teachers always reach people (§5.4).
    for policy in (DmPolicy.NOBODY, DmPolicy.GUIDES_AND_TEACHERS):
        target = await person("Səbinə", "Quliyeva")
        await set_policy(db, target, policy)
        assert (await open_dm(stranger, target)).json()["error"]["code"] == "chat.dm_unavailable"
        assert (await open_dm(teacher, target)).status_code == 201

    # A policy changed later keeps the DM readable; sending is refused with the reason, teachers excepted.
    await set_policy(db, ramin, DmPolicy.NOBODY)
    kept = await open_dm(aysel, ramin)
    assert kept.status_code == 200
    assert kept.json()["posting"]["reason"] == "chat.dm_unavailable"
    send = await client.post(
        f"{API}/chat/channels/{dm['id']}/messages",
        headers=aysel.headers,
        json={"body": "Salam", "client_msg_id": str(uuid.uuid4())},
    )
    assert (send.status_code, send.json()["error"]["code"]) == (403, "chat.dm_unavailable")

    # Blocks: the blocker is told; the blocked person gets the same answer as a closed inbox.
    blocker, blocked = await person("Kənan", "Babayev"), await person("Nigar", "İsmayılova")
    await set_policy(db, blocker, DmPolicy.EVERYONE)
    await set_policy(db, blocked, DmPolicy.EVERYONE)
    assert (
        await client.post(f"{API}/users/{blocked.id}/block", headers=blocker.headers)
    ).status_code == 204
    assert (
        await client.post(f"{API}/users/{blocked.id}/block", headers=blocker.headers)
    ).status_code == 204
    assert (await open_dm(blocker, blocked)).json()["error"]["code"] == "chat.user_blocked"
    assert (await open_dm(blocked, blocker)).json()["error"]["code"] == "chat.dm_unavailable"
    listed = (await client.get(f"{API}/chat/channels", headers=blocker.headers)).json()
    assert listed["blocked_user_ids"] == [str(blocked.id)]
    assert (
        await client.delete(f"{API}/users/{blocked.id}/block", headers=blocker.headers)
    ).status_code == 204
    assert (await open_dm(blocked, blocker)).status_code == 201

    assert (await open_dm(aysel, aysel)).json()["error"]["code"] == "chat.dm_self"
    assert (await open_dm(aysel, uuid.uuid4())).status_code == 404
    block_self = await client.post(f"{API}/users/{aysel.id}/block", headers=aysel.headers)
    assert block_self.json()["error"]["code"] == "chat.block_self"
    assert (
        await client.post(f"{API}/users/{uuid.uuid4()}/block", headers=aysel.headers)
    ).status_code == 404
    pairs = await db.scalar(
        select(func.count()).select_from(Channel).where(Channel.type == ChannelType.DM)
    )
    assert pairs == 5


async def test_members_choose_their_own_notification_level(
    client: AsyncClient, person: MakePerson, channel: MakeChannel
) -> None:
    aysel = await person()
    room = await channel(aysel)
    until = (datetime.now(UTC) + timedelta(hours=8)).replace(microsecond=0)
    updated = await client.patch(
        f"{API}/chat/channels/{room}/members/me",
        headers=aysel.headers,
        json={"notify_level": "mentions", "muted_until": until.isoformat()},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["notify_level"] == "mentions"
    assert datetime.fromisoformat(updated.json()["muted_until"]) == until
    # The member's snooze is not a moderator mute: posting stays allowed.
    assert updated.json()["posting"]["allowed"] is True
    cleared = await client.patch(
        f"{API}/chat/channels/{room}/members/me", headers=aysel.headers, json={"muted_until": None}
    )
    assert cleared.json()["muted_until"] is None
    assert cleared.json()["notify_level"] == "mentions"
