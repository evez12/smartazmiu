"""Edit, delete, threads, reactions, mentions and the consistency job (§5.3, §13.2, D-067)."""

import uuid
from datetime import timedelta
from typing import Any
from urllib.parse import quote

from httpx import AsyncClient
from sqlalchemy import func, insert, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.modules.chat import consistency, mentions
from app.modules.chat.models import (
    ChannelMember,
    MemberRole,
    Message,
    MessageMention,
    MessageReaction,
    NotifyLevel,
    UserBlock,
)
from app.modules.chat.reactions import REACTIONS
from app.modules.notifications.models import Notification, NotificationDelivery

from .conftest import MakeChannel, MakePerson, Open, Person
from .test_rest import add_messages

API = "/api/v1"


async def send(
    client: AsyncClient, person: Person, channel_id: uuid.UUID, body: str, **extra: Any
) -> dict[str, Any]:
    response = await client.post(
        f"{API}/chat/channels/{channel_id}/messages",
        headers=person.headers,
        json={"body": body, "client_msg_id": str(uuid.uuid4()), **extra},
    )
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


async def notified(db: AsyncSession, person: Person) -> list[Notification]:
    return list(await db.scalars(select(Notification).where(Notification.user_id == person.id)))


async def test_the_author_edits_and_deletes_within_fifteen_minutes(
    client: AsyncClient, db: AsyncSession, person: MakePerson, channel: MakeChannel
) -> None:
    aysel, ramin = await person(), await person("Ramin", "Əliyev")
    room = await channel(aysel, ramin)
    sent = (await send(client, aysel, room, "Seminar 1-305 otağındadır."))["message"]
    message_id = int(sent["id"])
    await db.execute(
        update(Message)
        .where(Message.id == message_id)
        .values(is_verified_answer=True, verified_by=ramin.id)
    )
    await db.commit()
    reacted = await client.post(
        f"{API}/chat/messages/{message_id}/reactions", headers=ramin.headers, json={"emoji": "👍"}
    )
    assert reacted.status_code == 200, reacted.text

    edited = await client.patch(
        f"{API}/chat/messages/{message_id}",
        headers=aysel.headers,
        json={"body": "Seminar 2-104 otağındadır."},
    )
    assert edited.status_code == 200, edited.text
    message = edited.json()["message"]
    assert message["body"] == "Seminar 2-104 otağındadır."
    assert message["edited_at"] is not None
    # Editing removes the verified mark and keeps reactions (§13.2).
    assert message["is_verified_answer"] is False
    assert message["reactions"] == [{"emoji": "👍", "count": 1}]
    assert message["my_reactions"] == []

    # Someone else may neither edit nor delete it; outsiders do not learn it exists.
    other = await client.patch(
        f"{API}/chat/messages/{message_id}", headers=ramin.headers, json={"body": "Dəyişdim"}
    )
    assert (other.status_code, other.json()["error"]["code"]) == (403, "chat.not_author")
    outsider = await person("Nigar", "Quliyeva")
    hidden = await client.delete(f"{API}/chat/messages/{message_id}", headers=outsider.headers)
    assert (hidden.status_code, hidden.json()["error"]["code"]) == (404, "chat.message_not_found")
    assert (
        await client.delete(f"{API}/chat/messages/9{message_id}", headers=aysel.headers)
    ).status_code == 404
    huge = await client.delete(f"{API}/chat/messages/9999999999999999999", headers=aysel.headers)
    assert huge.status_code == 404

    deleted = await client.delete(f"{API}/chat/messages/{message_id}", headers=aysel.headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["body"] == ""
    assert deleted.json()["deleted_at"] is not None
    assert deleted.json()["reactions"] == []
    stored = await db.scalar(select(Message).where(Message.id == message_id))
    assert stored is not None
    await db.refresh(stored)
    # Soft delete: the text stays for moderation but leaves the search index.
    assert stored.body == "Seminar 2-104 otağındadır."
    assert stored.body_tsv is None
    again = await client.patch(
        f"{API}/chat/messages/{message_id}", headers=aysel.headers, json={"body": "Yenə"}
    )
    assert again.status_code == 404

    # A message older than 15 minutes is final.
    old = await add_messages(db, room, aysel.id, 1, utc_now() - timedelta(minutes=16))
    for response in (
        await client.patch(f"{API}/chat/messages/{old}", headers=aysel.headers, json={"body": "x"}),
        await client.delete(f"{API}/chat/messages/{old}", headers=aysel.headers),
    ):
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "chat.change_window_expired"
        assert response.json()["error"]["details"] == {"window_minutes": 15}

    empty = (await send(client, aysel, room, "Bir dəqiqə"))["message"]["id"]
    blank = await client.patch(
        f"{API}/chat/messages/{empty}", headers=aysel.headers, json={"body": " "}
    )
    assert blank.json()["error"]["code"] == "chat.message_empty"
    long_ = await client.patch(
        f"{API}/chat/messages/{empty}", headers=aysel.headers, json={"body": "ə" * 4001}
    )
    assert long_.json()["error"]["code"] == "chat.message_too_long"


async def test_archived_channels_refuse_edits(
    client: AsyncClient, db: AsyncSession, person: MakePerson, channel: MakeChannel
) -> None:
    aysel = await person()
    room = await channel(aysel)
    sent = (await send(client, aysel, room, "Son mesaj"))["message"]["id"]
    await db.execute(text("UPDATE channels SET is_archived = true WHERE id = :id"), {"id": room})
    await db.commit()
    refused = await client.patch(
        f"{API}/chat/messages/{sent}", headers=aysel.headers, json={"body": "Dəyişiklik"}
    )
    assert (refused.status_code, refused.json()["error"]["code"]) == (403, "chat.channel_archived")


async def test_threads_are_one_level_deep_and_survive_a_deleted_root(
    client: AsyncClient, db: AsyncSession, person: MakePerson, channel: MakeChannel
) -> None:
    aysel, ramin = await person(), await person("Ramin", "Əliyev")
    room = await channel(aysel, ramin)
    other_room = await channel(aysel, name="Başqa qrup")
    root = (await send(client, aysel, room, "Kollokvium nə vaxtdır?"))["message"]
    reply = (await send(client, ramin, room, "Cümə günü.", parent_id=root["id"]))["message"]
    assert reply["parent_id"] == root["id"]
    # A reply to a reply joins the root's thread.
    nested = (await send(client, aysel, room, "Təşəkkürlər.", parent_id=reply["id"]))["message"]
    assert nested["parent_id"] == root["id"]
    foreign = await client.post(
        f"{API}/chat/channels/{other_room}/messages",
        headers=aysel.headers,
        json={"body": "Səhv kanal", "client_msg_id": str(uuid.uuid4()), "parent_id": root["id"]},
    )
    assert foreign.json()["error"]["code"] == "chat.parent_not_found"

    # The channel shows only the root, with its reply count; replies do not raise the badge.
    history = (
        await client.get(f"{API}/chat/channels/{room}/messages", headers=ramin.headers)
    ).json()
    assert [m["id"] for m in history["messages"]] == [root["id"]]
    assert history["messages"][0]["reply_count"] == 2
    assert history["messages"][0]["last_reply_at"] is not None
    listed = (await client.get(f"{API}/chat/channels/{room}", headers=ramin.headers)).json()
    assert listed["unread_count"] == 1

    thread = await client.get(f"{API}/chat/messages/{reply['id']}/thread", headers=ramin.headers)
    assert thread.status_code == 200, thread.text
    assert thread.json()["root"]["id"] == root["id"]
    assert [m["id"] for m in thread.json()["replies"]] == [reply["id"], nested["id"]]
    paged = await client.get(
        f"{API}/chat/messages/{root['id']}/thread",
        headers=ramin.headers,
        params={"after": reply["id"], "limit": 1},
    )
    assert [m["id"] for m in paged.json()["replies"]] == [nested["id"]]
    assert paged.json()["has_more"] is False

    # Deleting the root keeps the replies under a placeholder; new replies are refused.
    await client.delete(f"{API}/chat/messages/{root['id']}", headers=aysel.headers)
    after = (
        await client.get(f"{API}/chat/messages/{root['id']}/thread", headers=ramin.headers)
    ).json()
    assert after["root"]["deleted_at"] is not None
    assert after["root"]["body"] == ""
    assert len(after["replies"]) == 2
    late = await client.post(
        f"{API}/chat/channels/{room}/messages",
        headers=ramin.headers,
        json={"body": "Gecikdim", "client_msg_id": str(uuid.uuid4()), "parent_id": root["id"]},
    )
    assert late.json()["error"]["code"] == "chat.parent_not_found"
    outsider = await person("Nigar", "Quliyeva")
    hidden = await client.get(f"{API}/chat/messages/{root['id']}/thread", headers=outsider.headers)
    assert hidden.status_code == 404


async def test_reactions_are_idempotent_from_a_fixed_set(
    client: AsyncClient, db: AsyncSession, person: MakePerson, channel: MakeChannel
) -> None:
    aysel, ramin = await person(), await person("Ramin", "Əliyev")
    room = await channel(aysel, ramin)
    message_id = (await send(client, aysel, room, "Sabah imtahan var."))["message"]["id"]
    url = f"{API}/chat/messages/{message_id}/reactions"
    for _ in range(2):
        added = await client.post(url, headers=ramin.headers, json={"emoji": "❤️"})
        assert added.json() == {"message_id": message_id, "emoji": "❤️", "count": 1, "reacted": True}
    await client.post(url, headers=aysel.headers, json={"emoji": "❤️"})
    await client.post(url, headers=aysel.headers, json={"emoji": "👍"})
    refused = await client.post(url, headers=aysel.headers, json={"emoji": "🍕"})
    assert (refused.status_code, refused.json()["error"]["code"]) == (
        422,
        "chat.reaction_not_allowed",
    )
    assert refused.json()["error"]["details"]["allowed"] == list(REACTIONS)

    page = (await client.get(f"{API}/chat/channels/{room}/messages", headers=ramin.headers)).json()
    # Counts follow the order of the fixed set, whatever order they were added in.
    assert page["messages"][0]["reactions"] == [
        {"emoji": "👍", "count": 1},
        {"emoji": "❤️", "count": 2},
    ]
    assert page["messages"][0]["my_reactions"] == ["❤️"]

    for _ in range(2):
        removed = await client.delete(f"{url}/{quote('❤️')}", headers=ramin.headers)
        assert removed.json() == {
            "message_id": message_id,
            "emoji": "❤️",
            "count": 1,
            "reacted": False,
        }
    outsider = await person("Nigar", "Quliyeva")
    hidden = await client.post(url, headers=outsider.headers, json={"emoji": "👍"})
    assert hidden.status_code == 404
    await db.execute(
        update(ChannelMember)
        .where(ChannelMember.user_id == ramin.id)
        .values(role=MemberRole.READONLY)
    )
    await db.commit()
    readonly = await client.post(url, headers=ramin.headers, json={"emoji": "👍"})
    assert readonly.json()["error"]["code"] == "chat.channel_readonly"
    await client.delete(f"{API}/chat/messages/{message_id}", headers=aysel.headers)
    gone = await client.post(url, headers=aysel.headers, json={"emoji": "👍"})
    assert gone.status_code == 404


async def test_mentions_reach_members_only_and_respect_levels_and_blocks(
    client: AsyncClient, db: AsyncSession, person: MakePerson, channel: MakeChannel
) -> None:
    aysel, ramin = await person(), await person("Ramin", "Əliyev")
    leyla, nigar = await person("Leyla", "Həsənova"), await person("Nigar", "Quliyeva")
    outsider = await person("Tural", "Babayev")
    room = await channel(aysel, ramin, leyla, nigar)
    await db.execute(
        update(ChannelMember)
        .where(ChannelMember.user_id == nigar.id)
        .values(notify_level=NotifyLevel.NONE)
    )
    await db.execute(insert(UserBlock).values(blocker_id=leyla.id, blocked_id=aysel.id))
    await db.commit()

    body = (
        f"<@{ramin.id}> <@{leyla.id}> <@{nigar.id}> <@{outsider.id}> `<@{aysel.id}>` cədvələ baxın"
    )
    result = await send(client, aysel, room, body)
    message = result["message"]
    # The outsider stays plain text: not recorded, not named, not notified (§13.2).
    assert {m["id"] for m in message["mentions"]} == {str(ramin.id), str(leyla.id), str(nigar.id)}
    assert result["notices"] == []
    assert [n.kind.value for n in await notified(db, ramin)] == ["chat.mention"]
    note = (await notified(db, ramin))[0]
    assert note.title == f"{aysel.name} · Statistika layihəsi"
    assert note.link == f"/chat/{room}"
    assert note.subject_id == mentions.subject_id(int(message["id"]))
    # Leyla blocked the author and Nigar chose "none"; the outsider is not a member.
    for person_ in (leyla, nigar, outsider, aysel):
        assert await notified(db, person_) == []
    assert (
        await db.scalar(
            select(func.count())
            .select_from(NotificationDelivery)
            .where(NotificationDelivery.notification_id == note.id)
        )
        == 1
    )  # push only; chat e-mail is a later digest

    listed = (await client.get(f"{API}/chat/channels/{room}", headers=ramin.headers)).json()
    assert listed["mention_count"] == 1

    # An edit that names someone new notifies only them, once.
    await client.patch(
        f"{API}/chat/messages/{message['id']}",
        headers=aysel.headers,
        json={"body": f"<@{ramin.id}> və <@{leyla.id}>, düzəliş: cədvəl dəyişdi"},
    )
    assert len(await notified(db, ramin)) == 1
    stored = set(
        await db.scalars(
            select(MessageMention.user_id).where(MessageMention.message_id == int(message["id"]))
        )
    )
    assert stored == {ramin.id, leyla.id}

    # A reply notifies the parent's author; a reply that also mentions them notifies once.
    reply = await send(client, ramin, room, f"<@{aysel.id}> aydındır", parent_id=message["id"])
    kinds = [n.kind.value for n in await notified(db, aysel)]
    assert kinds == ["chat.mention"]
    assert (await notified(db, aysel))[0].link == f"/chat/{room}?thread={message['id']}"
    await send(client, leyla, room, "Mən də gəlirəm", parent_id=message["id"])
    assert len(await notified(db, aysel)) == 2
    assert reply["message"]["parent_id"] == message["id"]


async def test_channel_mentions_are_for_teachers_moderators_and_staff(
    client: AsyncClient, db: AsyncSession, person: MakePerson, channel: MakeChannel
) -> None:
    aysel, ramin = await person(), await person("Ramin", "Əliyev")
    teacher = await person("Elnur", "Hüseynov", roles=["teacher"])
    room = await channel(aysel, ramin, teacher)
    student = await send(client, aysel, room, "@channel sabah dərs yoxdur?")
    assert student["notices"] == ["chat.channel_mention_not_allowed"]
    assert student["message"]["mentions_channel"] is False
    assert await notified(db, ramin) == []
    # Quoted code is not a mention.
    quoted = await send(client, teacher, room, "Nümunə: `@channel` yazmayın")
    assert quoted["message"]["mentions_channel"] is False

    official = await send(client, teacher, room, "@channel sabahkı dərs 1-305 otağındadır.")
    assert official["notices"] == []
    assert official["message"]["mentions_channel"] is True
    assert [n.kind.value for n in await notified(db, ramin)] == ["chat.mention"]
    assert len(await notified(db, aysel)) == 1
    assert await notified(db, teacher) == []
    for viewer in (ramin, aysel):
        listed = (await client.get(f"{API}/chat/channels/{room}", headers=viewer.headers)).json()
        assert listed["mention_count"] == 1

    # A channel moderator may use it as well.
    await db.execute(
        update(ChannelMember)
        .where(ChannelMember.user_id == ramin.id)
        .values(role=MemberRole.MODERATOR)
    )
    await db.commit()
    moderated = await send(client, ramin, room, "@channel qaydaları oxuyun")
    assert moderated["message"]["mentions_channel"] is True


async def test_delivery_rechecks_mute_level_membership_and_blocks(
    client: AsyncClient, db: AsyncSession, person: MakePerson, channel: MakeChannel
) -> None:
    aysel, ramin = await person(), await person("Ramin", "Əliyev")
    room = await channel(aysel, ramin)
    message_id = int((await send(client, aysel, room, f"<@{ramin.id}> bax"))["message"]["id"])
    subject = mentions.subject_id(message_id)
    assert await mentions.still_relevant(db, subject, ramin.id)

    # Snoozing the channel suppresses push but keeps the bell (§5.6).
    snoozed = await client.patch(
        f"{API}/chat/channels/{room}/members/me",
        headers=ramin.headers,
        json={"muted_until": (utc_now() + timedelta(hours=8)).isoformat()},
    )
    assert snoozed.status_code == 200
    assert snoozed.json()["muted_until"] is not None
    assert not await mentions.still_relevant(db, subject, ramin.id)
    await client.patch(
        f"{API}/chat/channels/{room}/members/me", headers=ramin.headers, json={"muted_until": None}
    )
    assert await mentions.still_relevant(db, subject, ramin.id)
    await client.patch(
        f"{API}/chat/channels/{room}/members/me",
        headers=ramin.headers,
        json={"notify_level": "none"},
    )
    assert not await mentions.still_relevant(db, subject, ramin.id)
    await client.patch(
        f"{API}/chat/channels/{room}/members/me",
        headers=ramin.headers,
        json={"notify_level": "mentions"},
    )
    assert await mentions.still_relevant(db, subject, ramin.id)
    await client.post(f"{API}/users/{aysel.id}/block", headers=ramin.headers)
    assert not await mentions.still_relevant(db, subject, ramin.id)
    await client.delete(f"{API}/users/{aysel.id}/block", headers=ramin.headers)
    await client.delete(f"{API}/chat/messages/{message_id}", headers=aysel.headers)
    assert not await mentions.still_relevant(db, subject, ramin.id)
    assert not await mentions.still_relevant(db, mentions.subject_id(message_id + 1), ramin.id)
    outsider = await person("Nigar", "Quliyeva")
    assert not await mentions.still_relevant(db, subject, outsider.id)


async def test_the_consistency_job_removes_orphans_idempotently(
    client: AsyncClient, db: AsyncSession, person: MakePerson, channel: MakeChannel
) -> None:
    aysel, ramin = await person(), await person("Ramin", "Əliyev")
    room = await channel(aysel, ramin)
    kept = int((await send(client, aysel, room, f"<@{ramin.id}> salam"))["message"]["id"])
    await client.post(
        f"{API}/chat/messages/{kept}/reactions", headers=ramin.headers, json={"emoji": "👍"}
    )
    missing = kept + (5 << 22)
    await db.execute(
        insert(MessageReaction).values(message_id=missing, user_id=aysel.id, emoji="👍")
    )
    await db.execute(insert(MessageMention).values(message_id=missing, user_id=ramin.id))
    await db.execute(
        text(
            "INSERT INTO message_attachments (id, message_id, channel_id, object_key, mime, size_bytes)"
            " VALUES (gen_random_uuid(), :id, :channel, 'chat/x', 'application/pdf', 10)"
        ),
        {"id": missing, "channel": room},
    )
    await db.commit()
    report = await consistency.remove_orphans(db)
    assert report.removed == {
        "message_reactions": 1,
        "message_mentions": 1,
        "message_attachments": 1,
    }
    assert (await consistency.remove_orphans(db)).total == 0
    assert await db.scalar(select(func.count()).select_from(MessageReaction)) == 1
    assert await db.scalar(select(func.count()).select_from(MessageMention)) == 1


async def test_edits_deletes_and_reactions_travel_over_the_socket(
    open_socket: Open, person: MakePerson, channel: MakeChannel
) -> None:
    aysel, ramin = await person(), await person("Ramin", "Əliyev")
    room = await channel(aysel, ramin)
    writer, reader = await open_socket(aysel), await open_socket(ramin)
    for socket in (writer, reader):
        assert (await socket.reply("subscribe", {"channel_ids": [str(room)]}))["type"] == "ack"
    root = await writer.reply(
        "message.send",
        {"channel_id": str(room), "body": "Sual var", "client_msg_id": str(uuid.uuid4())},
    )
    root_id = root["data"]["message_id"]
    reply = await reader.reply(
        "message.send",
        {
            "channel_id": str(room),
            "body": "Buyurun",
            "client_msg_id": str(uuid.uuid4()),
            "parent_id": root_id,
        },
    )
    assert reply["type"] == "ack"
    created = await writer.expect("message.created", parent_id=root_id)
    assert created["body"] == "Buyurun"

    edited = await writer.reply("message.edit", {"message_id": root_id, "body": "Bir sual var"})
    assert edited["data"]["notices"] == []
    update_ = await reader.expect("message.updated", id=root_id)
    assert update_["body"] == "Bir sual var"
    assert update_["my_reactions"] is None
    assert update_["reply_count"] == 1

    reacted = await reader.reply("reaction.add", {"message_id": root_id, "emoji": "🙏"})
    assert reacted["data"]["count"] == 1
    assert reacted["data"]["reacted"] is True
    event = await writer.expect("reaction.updated", message_id=root_id)
    assert event == {
        "message_id": root_id,
        "channel_id": str(room),
        "emoji": "🙏",
        "count": 1,
        "user_id": str(ramin.id),
        "added": True,
    }
    removed = await reader.reply("reaction.remove", {"message_id": root_id, "emoji": "🙏"})
    assert removed["data"]["count"] == 0
    await writer.expect("reaction.updated", message_id=root_id, added=False)

    refused = await reader.reply("message.delete", {"message_id": root_id})
    assert refused["data"]["code"] == "chat.not_author"
    deleted = await writer.reply("message.delete", {"message_id": root_id})
    assert deleted["type"] == "ack"
    gone = await reader.expect("message.deleted", id=root_id)
    assert gone["channel_id"] == str(room)
    assert gone["deleted_at"] is not None
    bad = await writer.reply("reaction.add", {"message_id": root_id, "emoji": "🍕"})
    assert bad["data"]["code"] == "chat.reaction_not_allowed"
