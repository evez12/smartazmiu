"""Blocked terms and distinct-reporter hiding (§5.5, §13.2)."""

import uuid

from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog
from app.modules.chat.models import (
    BlockedTerm,
    ChannelMember,
    MemberRole,
    Message,
    MessageModeration,
)
from app.modules.chat.tests.conftest import MakeChannel, MakePerson, Open
from app.modules.reports.models import Report

API = "/api/v1"


async def test_blocked_terms_reject_and_hold_on_normalized_text(
    client: AsyncClient, db: AsyncSession, person: MakePerson, channel: MakeChannel
) -> None:
    admin = await person("Elvin", "Quliyev", ["admin"])
    author = await person()
    peer = await person("Ramin", "Əliyev")
    room = await channel(author, peer)
    path = f"{API}/moderation/blocked-terms"
    assert (await client.get(path, headers=author.headers)).status_code == 403
    rejected = await client.post(
        path,
        headers=admin.headers,
        json={"pattern": "İSTİFADƏÇİ", "action": "reject", "lang": "az"},
    )
    assert rejected.status_code == 201, rejected.text
    held = await client.post(
        path,
        headers=admin.headers,
        json={"pattern": "imtahan[ ]+sualı", "is_regex": True, "action": "hold", "lang": "az"},
    )
    assert held.status_code == 201, held.text
    assert len((await client.get(path, headers=admin.headers)).json()) == 2

    send = f"{API}/chat/channels/{room}/messages"
    refused = await client.post(
        send,
        headers=author.headers,
        json={"body": "ISTIFADECI məlumatı", "client_msg_id": str(uuid.uuid4())},
    )
    assert (refused.status_code, refused.json()["error"]["code"]) == (422, "chat.message_blocked")
    assert await db.scalar(select(Message.id)) is None
    held_send = await client.post(
        send,
        headers=author.headers,
        json={"body": "İmtahan sualı", "client_msg_id": str(uuid.uuid4())},
    )
    assert held_send.status_code == 201, held_send.text
    assert held_send.json()["message"]["moderation"] == "held"
    message_id = held_send.json()["message"]["id"]
    own = await client.get(f"{API}/chat/channels/{room}/messages", headers=author.headers)
    other = await client.get(f"{API}/chat/channels/{room}/messages", headers=peer.headers)
    assert own.json()["messages"][0]["body"] == "İmtahan sualı"
    assert other.json()["messages"][0]["body"] == ""
    stored = await db.scalar(select(Message).where(Message.id == int(message_id)))
    assert stored is not None
    assert stored.body_tsv is None
    assert stored.moderation is MessageModeration.HELD
    assert (
        await client.delete(f"{path}/{held.json()['id']}", headers=admin.headers)
    ).status_code == 204
    disabled = await db.get(BlockedTerm, uuid.UUID(held.json()["id"]))
    assert disabled is not None
    assert disabled.disabled_at is not None
    changed = await client.patch(
        f"{API}/chat/messages/{message_id}",
        headers=author.headers,
        json={"body": "Yoxlanmış mətn"},
    )
    assert changed.status_code == 200, changed.text
    public = await client.get(f"{API}/chat/channels/{room}/messages", headers=peer.headers)
    assert public.json()["messages"][0]["moderation"] == "visible"
    assert public.json()["messages"][0]["body"] == "Yoxlanmış mətn"


async def test_three_distinct_reports_hide_content_without_deleting_it(
    client: AsyncClient, db: AsyncSession, person: MakePerson, channel: MakeChannel
) -> None:
    author = await person("Ramin", "Əliyev")
    reporters = [await person("Aysel", f"Məmmədova{number}") for number in range(3)]
    moderator = await person("Nigar", "Quliyeva")
    outsider = await person("Leyla", "Həsənova")
    room = await channel(author, *reporters, moderator)
    await db.execute(
        update(ChannelMember)
        .where(ChannelMember.channel_id == room, ChannelMember.user_id == moderator.id)
        .values(role=MemberRole.MODERATOR)
    )
    await db.commit()
    sent = await client.post(
        f"{API}/chat/channels/{room}/messages",
        headers=author.headers,
        json={"body": "Cari suallar buradadır", "client_msg_id": str(uuid.uuid4())},
    )
    assert sent.status_code == 201, sent.text
    message_id = sent.json()["message"]["id"]
    for index, reporter in enumerate(reporters):
        payload = {"target_type": "message", "target_id": message_id, "reason": "exam_leak"}
        response = await client.post(f"{API}/reports", headers=reporter.headers, json=payload)
        assert response.status_code == 201, response.text
        if index == 0:
            duplicate = await client.post(f"{API}/reports", headers=reporter.headers, json=payload)
            assert duplicate.status_code == 200
        stored = await db.scalar(select(Message).where(Message.id == int(message_id)))
        assert stored is not None
        await db.refresh(stored)
        assert stored.moderation is (
            MessageModeration.HIDDEN if index == 2 else MessageModeration.VISIBLE
        )
    assert len(list(await db.scalars(select(Report).where(Report.target_id == message_id)))) == 3
    assert (
        len(
            list(await db.scalars(select(AuditLog).where(AuditLog.action == "message.auto_hidden")))
        )
        == 1
    )
    for viewer, body in [
        (author, "Cari suallar buradadır"),
        (moderator, "Cari suallar buradadır"),
        (reporters[0], ""),
    ]:
        page = await client.get(f"{API}/chat/channels/{room}/messages", headers=viewer.headers)
        assert page.json()["messages"][0]["body"] == body
        assert page.json()["messages"][0]["moderation"] == "hidden"
    unseen = await client.get(f"{API}/chat/channels/{room}/messages", headers=outsider.headers)
    assert unseen.status_code == 404


async def test_held_message_does_not_broadcast_its_text(
    client: AsyncClient, person: MakePerson, channel: MakeChannel, open_socket: Open
) -> None:
    admin = await person("Elvin", "Quliyev", ["admin"])
    author, peer = await person(), await person("Ramin", "Əliyev")
    room = await channel(author, peer)
    added = await client.post(
        f"{API}/moderation/blocked-terms",
        headers=admin.headers,
        json={"pattern": "saxlanmalı", "action": "hold", "lang": "az"},
    )
    assert added.status_code == 201
    sender, receiver = await open_socket(author), await open_socket(peer)
    for socket in (sender, receiver):
        joined = await socket.reply("subscribe", {"channel_ids": [str(room)]})
        assert joined["type"] == "ack"
    ack = await sender.reply(
        "message.send",
        {"channel_id": str(room), "body": "Saxlanmalı mətn", "client_msg_id": str(uuid.uuid4())},
    )
    assert ack["type"] == "ack"
    assert not [frame for frame in await receiver.silent() if frame["type"] == "message.created"]
