"""Moderator scope, protected targets, actions and SLA (§5.5)."""

import uuid
from datetime import timedelta

from httpx import AsyncClient, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.modules.audit.models import AuditLog
from app.modules.chat.models import (
    Channel,
    ChannelBan,
    ChannelMember,
    GlobalChatBan,
    MemberRole,
    Message,
    MessageModeration,
    ModerationAction,
    ThreadLock,
)
from app.modules.chat.tests.conftest import MakeChannel, MakePerson, Person
from app.modules.reports.models import Report

API = "/api/v1"


async def send(client: AsyncClient, author: Person, channel_id: uuid.UUID) -> dict[str, object]:
    response = await client.post(
        f"{API}/chat/channels/{channel_id}/messages",
        headers=author.headers,
        json={"body": "Qaydaya zidd mətn", "client_msg_id": str(uuid.uuid4())},
    )
    assert response.status_code == 201
    result: dict[str, object] = response.json()["message"]
    return result


async def report(client: AsyncClient, person: Person, message_id: str) -> None:
    response = await client.post(
        f"{API}/reports",
        headers=person.headers,
        json={"target_type": "message", "target_id": message_id, "reason": "spam"},
    )
    assert response.status_code == 201


async def act(client: AsyncClient, actor: Person, **values: object) -> Response:
    return await client.post(
        f"{API}/moderation/actions",
        headers=actor.headers,
        json={"reason": "Kanal qaydasının pozulması", **values},
    )


async def test_moderator_sees_only_assigned_reports_and_sla(
    client: AsyncClient, db: AsyncSession, person: MakePerson, channel: MakeChannel
) -> None:
    moderator = await person("Nigar", "Quliyeva", ["moderator"])
    author, reporter = await person(), await person("Ramin", "Əliyev")
    assigned = await channel(moderator, author, reporter)
    other = await channel(author, reporter, name="Başqa kanal")
    await db.execute(
        update(ChannelMember)
        .where(ChannelMember.channel_id == assigned, ChannelMember.user_id == moderator.id)
        .values(role=MemberRole.MODERATOR)
    )
    await db.commit()
    first, second = await send(client, author, assigned), await send(client, author, other)
    await report(client, reporter, str(first["id"]))
    await report(client, reporter, str(second["id"]))
    stored = await db.scalar(select(Report).where(Report.target_id == str(first["id"])))
    assert stored is not None
    stored.created_at = utc_now() - timedelta(hours=13)
    await db.commit()

    page = await client.get(f"{API}/moderation/reports", headers=moderator.headers)
    assert page.status_code == 200, page.text
    assert page.json()["total"] == 1
    assert page.json()["items"][0]["message"]["channel_id"] == str(assigned)
    assert page.json()["items"][0]["sla_breached"] is True
    hidden = await client.patch(
        f"{API}/moderation/reports/{(await db.scalar(select(Report.id).where(Report.target_id == str(second['id']))))}",
        headers=moderator.headers,
        json={"status": "dismissed"},
    )
    assert hidden.status_code == 404


async def test_scoped_actions_are_enforced_and_audited(
    client: AsyncClient, db: AsyncSession, person: MakePerson, channel: MakeChannel
) -> None:
    moderator = await person("Nigar", "Quliyeva", ["moderator"])
    author = await person()
    teacher = await person("Leyla", "Həsənova", ["teacher"])
    room = await channel(moderator, author, teacher)
    other = await channel(author)
    await db.execute(
        update(ChannelMember)
        .where(ChannelMember.channel_id == room, ChannelMember.user_id == moderator.id)
        .values(role=MemberRole.MODERATOR)
    )
    await db.commit()
    message = await send(client, author, room)
    deleted = await act(
        client,
        moderator,
        action="delete_message",
        channel_id=str(room),
        message_id=message["id"],
        target_user_id=str(author.id),
    )
    assert deleted.status_code == 201, deleted.text
    stored = await db.scalar(select(Message).where(Message.id == int(str(message["id"]))))
    assert stored is not None
    assert stored.deleted_at is not None
    assert len(list(await db.scalars(select(ModerationAction)))) == 1
    assert (
        len(list(await db.scalars(select(AuditLog).where(AuditLog.action == "moderation.action"))))
        == 1
    )

    protected = await act(
        client,
        moderator,
        action="mute",
        channel_id=str(room),
        target_user_id=str(teacher.id),
        duration_seconds=3600,
    )
    assert (protected.status_code, protected.json()["error"]["code"]) == (
        403,
        "moderation.protected_target",
    )
    out_of_scope = await act(
        client,
        moderator,
        action="slow_mode",
        channel_id=str(other),
        duration_seconds=30,
    )
    assert out_of_scope.status_code == 404
    global_ban = await act(client, moderator, action="global_ban", target_user_id=str(author.id))
    assert global_ban.status_code == 403


async def test_mute_ban_thread_lock_and_slow_mode_take_effect(
    client: AsyncClient, db: AsyncSession, person: MakePerson, channel: MakeChannel
) -> None:
    admin = await person("Elvin", "Quliyev", ["admin"])
    author, peer = await person(), await person("Ramin", "Əliyev")
    room = await channel(author, peer)
    message = await send(client, author, room)
    assert (
        await act(
            client,
            admin,
            action="mute",
            channel_id=str(room),
            target_user_id=str(author.id),
            duration_seconds=3600,
        )
    ).status_code == 201
    refused = await client.post(
        f"{API}/chat/channels/{room}/messages",
        headers=author.headers,
        json={"body": "Yeni", "client_msg_id": str(uuid.uuid4())},
    )
    assert refused.json()["error"]["code"] == "chat.muted"
    assert (
        await act(
            client,
            admin,
            action="lock_thread",
            channel_id=str(room),
            message_id=message["id"],
            target_user_id=str(author.id),
        )
    ).status_code == 201
    reply = await client.post(
        f"{API}/chat/channels/{room}/messages",
        headers=peer.headers,
        json={"body": "Cavab", "client_msg_id": str(uuid.uuid4()), "parent_id": message["id"]},
    )
    assert reply.json()["error"]["code"] == "chat.thread_locked"
    assert await db.get(ThreadLock, int(str(message["id"]))) is not None
    assert (
        await act(client, admin, action="slow_mode", channel_id=str(room), duration_seconds=30)
    ).status_code == 201
    assert await db.scalar(select(Channel.slow_mode_seconds).where(Channel.id == room)) == 30
    assert (
        await act(client, admin, action="ban", channel_id=str(room), target_user_id=str(author.id))
    ).status_code == 201
    assert await db.get(ChannelBan, (room, author.id)) is not None
    hidden = await client.get(f"{API}/chat/channels/{room}", headers=author.headers)
    assert hidden.status_code == 404


async def test_admin_can_restore_kick_and_apply_global_chat_ban(
    client: AsyncClient, db: AsyncSession, person: MakePerson, channel: MakeChannel
) -> None:
    admin = await person("Elvin", "Quliyev", ["admin"])
    author, peer = await person(), await person("Ramin", "Əliyev")
    room = await channel(author, peer)
    sent = await send(client, author, room)
    message = await db.scalar(select(Message).where(Message.id == int(str(sent["id"]))))
    assert message is not None
    message.moderation = MessageModeration.HIDDEN
    message.body_tsv = None
    await db.commit()

    restored = await act(
        client,
        admin,
        action="restore_message",
        channel_id=str(room),
        message_id=sent["id"],
    )
    assert restored.status_code == 201, restored.text
    await db.refresh(message)
    assert message.moderation is MessageModeration.VISIBLE
    assert message.body_tsv is not None

    kicked = await act(
        client, admin, action="kick", channel_id=str(room), target_user_id=str(peer.id)
    )
    assert kicked.status_code == 201
    assert await db.get(ChannelMember, (room, peer.id)) is None

    banned = await act(client, admin, action="global_ban", target_user_id=str(author.id))
    assert banned.status_code == 201
    assert await db.get(GlobalChatBan, author.id) is not None
    assert (
        await client.get(f"{API}/chat/channels/{room}", headers=author.headers)
    ).status_code == 404
