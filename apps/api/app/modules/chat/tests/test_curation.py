"""Knowledge in channels (§5.3, D-084): pins, polls, saved messages, anonymous questions, verified answers."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.modules.academics.models import CourseOffering, Subject
from app.modules.audit.models import AuditLog
from app.modules.chat.models import (
    Channel,
    ChannelMember,
    ChannelType,
    MemberRole,
    PinnedMessage,
    Poll,
)
from app.modules.chat.provisioning import ChannelProvisioner
from app.modules.materials.tests.test_materials import sign_in
from app.modules.notifications.models import Notification, NotificationKind
from tests.support import TokenFactory

from .conftest import MakeChannel, MakePerson, Person

API = "/api/v1"
Seed = Callable[..., Awaitable[None]]


def body(text_: str = "Sabahkı seminar 1-305 otağındadır.", **extra: Any) -> dict[str, Any]:
    return {"body": text_, "client_msg_id": str(uuid.uuid4()), **extra}


async def post(
    client: AsyncClient, person: Person, channel_id: uuid.UUID | str, **extra: Any
) -> Any:
    response = await client.post(
        f"{API}/chat/channels/{channel_id}/messages", headers=person.headers, json=body(**extra)
    )
    assert response.status_code == 201, response.text
    return response.json()["message"]


async def test_pins_need_a_moderator_and_stop_at_fifty(
    client: AsyncClient, db: AsyncSession, person: MakePerson, channel: MakeChannel
) -> None:
    aysel, ramin, stranger = (
        await person(),
        await person("Ramin", "Əliyev"),
        await person("Orxan", "Rzayev"),
    )
    room = await channel(aysel, ramin)
    await db.execute(
        update(ChannelMember)
        .where(ChannelMember.channel_id == room, ChannelMember.user_id == aysel.id)
        .values(role=MemberRole.OWNER)
    )
    await db.commit()
    message = await post(client, ramin, room)
    url = f"{API}/chat/channels/{room}/pins/{message['id']}"
    assert (await client.post(url, headers=ramin.headers)).json()["error"][
        "code"
    ] == "chat.pin_not_allowed"
    assert (await client.post(url, headers=stranger.headers)).status_code == 404
    pinned = await client.post(url, headers=aysel.headers)
    assert pinned.status_code == 200, pinned.text
    assert pinned.json()["pinned"] is True
    listed = await client.get(f"{API}/chat/channels/{room}/pins", headers=ramin.headers)
    assert [m["id"] for m in listed.json()["messages"]] == [message["id"]]
    assert (
        await client.get(f"{API}/chat/channels/{room}/pins", headers=stranger.headers)
    ).status_code == 404

    db.add_all(PinnedMessage(channel_id=room, message_id=1000 + n) for n in range(49))
    await db.commit()
    another = await post(client, ramin, room)
    over = await client.post(
        f"{API}/chat/channels/{room}/pins/{another['id']}", headers=aysel.headers
    )
    assert (over.status_code, over.json()["error"]["code"]) == (409, "chat.pin_limit")
    assert (await client.delete(url, headers=aysel.headers)).status_code == 204
    again = await client.post(
        f"{API}/chat/channels/{room}/pins/{another['id']}", headers=aysel.headers
    )
    assert again.status_code == 200


async def test_polls_count_each_vote_once(
    client: AsyncClient, db: AsyncSession, person: MakePerson, channel: MakeChannel
) -> None:
    people = [await person(f"Tələbə{n}", "Əliyev") for n in range(4)]
    stranger = await person("Orxan", "Rzayev")
    room = await channel(*people)
    url = f"{API}/chat/channels/{room}/polls"
    poll_body = {
        "question": "Seminar hansı gün olsun?",
        "client_msg_id": str(uuid.uuid4()),
        "options": ["Bazar ertəsi", "Çərşənbə"],
    }
    assert (
        await client.post(url, headers=people[0].headers, json={**poll_body, "options": ["A"]})
    ).status_code == 422
    bad = await client.post(
        url, headers=people[0].headers, json={**poll_body, "options": ["A", "A"]}
    )
    assert bad.json()["error"]["code"] == "chat.poll_invalid_options"
    created = await client.post(url, headers=people[0].headers, json=poll_body)
    assert created.status_code == 201, created.text
    poll = created.json()["poll"]
    first, second = (option["id"] for option in poll["options"])
    vote_url = f"{API}/chat/polls/{poll['id']}/votes"

    both = await client.post(
        vote_url, headers=people[1].headers, json={"option_ids": [first, second]}
    )
    assert both.json()["error"]["code"] == "chat.poll_invalid_vote"
    assert (
        await client.post(vote_url, headers=stranger.headers, json={"option_ids": [first]})
    ).status_code == 404
    results = await asyncio.gather(
        *(client.post(vote_url, headers=p.headers, json={"option_ids": [first]}) for p in people)
    )
    assert all(r.status_code == 200 for r in results)
    changed = await client.post(vote_url, headers=people[1].headers, json={"option_ids": [second]})
    counts = {o["id"]: o["votes"] for o in changed.json()["poll"]["options"]}
    assert counts == {first: 3, second: 1}
    assert changed.json()["poll"]["voters"] == 4
    assert changed.json()["poll"]["my_votes"] == [second]

    await db.execute(update(Poll).values(closes_at=utc_now() - timedelta(minutes=1)))
    await db.commit()
    closed = await client.post(vote_url, headers=people[2].headers, json={"option_ids": [second]})
    assert closed.json()["error"]["code"] == "chat.poll_closed"


async def test_saved_messages_are_private_and_respect_access(
    client: AsyncClient, db: AsyncSession, person: MakePerson, channel: MakeChannel
) -> None:
    aysel, ramin = await person(), await person("Ramin", "Əliyev")
    stranger = await person("Orxan", "Rzayev")
    room = await channel(aysel, ramin)
    message = await post(client, ramin, room)
    url = f"{API}/chat/messages/{message['id']}/saved"
    assert (await client.put(url, headers=stranger.headers)).status_code == 404
    saved = await client.put(url, headers=aysel.headers)
    assert saved.json()["saved"] is True
    mine = (await client.get(f"{API}/chat/saved", headers=aysel.headers)).json()["items"]
    assert [item["message"]["id"] for item in mine] == [message["id"]]
    assert (await client.get(f"{API}/chat/saved", headers=ramin.headers)).json()["items"] == []

    # Losing access hides the content and the channel name, but the entry stays for the owner to remove.
    await db.execute(
        delete(ChannelMember).where(
            ChannelMember.channel_id == room, ChannelMember.user_id == aysel.id
        )
    )
    await db.commit()
    gone = (await client.get(f"{API}/chat/saved", headers=aysel.headers)).json()["items"]
    assert (gone[0]["message"], gone[0]["channel_name"]) == (None, None)
    assert message["body"] not in str(gone)
    assert (await client.delete(url, headers=aysel.headers)).status_code == 204
    assert (await client.get(f"{API}/chat/saved", headers=aysel.headers)).json()["items"] == []


async def test_anonymous_questions_and_verified_answers(
    client: AsyncClient, db: AsyncSession, tokens: TokenFactory, seed: Seed
) -> None:
    await seed()
    aysel = await sign_in(
        client, tokens, "aysel.mammadova@smartazmiu.test", ["student"], "Aysel", "Məmmədova"
    )
    ramin = await sign_in(
        client, tokens, "ramin.aliyev@smartazmiu.test", ["student"], "Ramin", "Əliyev"
    )
    teacher = await sign_in(
        client, tokens, "farid.ismayilov@smartazmiu.test", ["teacher"], "Fərid", "İsmayılov"
    )
    await ChannelProvisioner(db).run()
    # Mikroiqtisadiyyat for 765a2 in 2026 Payız, taught by Fərid İsmayılov among others.
    course = await db.scalar(
        select(Channel.id)
        .join(CourseOffering, CourseOffering.id == Channel.course_offering_id)
        .join(Subject, Subject.id == CourseOffering.subject_id)
        .join(ChannelMember, ChannelMember.channel_id == Channel.id)
        .where(
            Channel.type == ChannelType.COURSE_OFFERING,
            Subject.code == "IQT-2101",
            ChannelMember.user_id == teacher.id,
            ~Channel.is_archived,
        )
        .limit(1)
    )
    assert course is not None
    detail = (await client.get(f"{API}/chat/channels/{course}", headers=aysel.headers)).json()
    topics = {topic["slug"]: topic["id"] for topic in detail["topics"]}
    assert detail["can_see_anonymous"] is False
    teacher_view = (
        await client.get(f"{API}/chat/channels/{course}", headers=teacher.headers)
    ).json()
    assert (teacher_view["can_verify"], teacher_view["can_see_anonymous"]) == (True, True)

    elsewhere = await client.post(
        f"{API}/chat/channels/{course}/messages",
        headers=aysel.headers,
        json=body("Sual", topic_id=topics["umumi"], is_anonymous=True),
    )
    assert elsewhere.json()["error"]["code"] == "chat.anonymous_not_allowed"
    question = await post(
        client,
        aysel,
        course,
        topic_id=topics["suallar"],
        is_anonymous=True,
        text_="Elastiklik mövzusu imtahana düşəcək?",
    )
    assert (question["author"], question["is_anonymous"]) == (None, True)
    history = (
        await client.get(f"{API}/chat/channels/{course}/messages", headers=ramin.headers)
    ).json()["messages"]
    seen = next(m for m in history if m["id"] == question["id"])
    assert seen["author"] is None
    assert "Aysel" not in str(seen)

    reveal = f"{API}/chat/messages/{question['id']}/anonymous-author"
    assert (await client.get(reveal, headers=ramin.headers)).status_code == 403
    revealed = await client.get(reveal, headers=teacher.headers)
    assert revealed.json()["display_name"] == "Aysel Məmmədova"
    audited = await db.scalar(
        select(AuditLog.actor_id).where(
            AuditLog.action == "message.author_revealed", AuditLog.target_id == question["id"]
        )
    )
    assert audited == teacher.id

    answer = await post(
        client, ramin, course, parent_id=question["id"], text_="Bəli, keçən il düşmüşdü."
    )
    verify = f"{API}/chat/messages/{answer['id']}/verify"
    assert (await client.post(verify, headers=ramin.headers)).json()["error"][
        "code"
    ] == "chat.verify_not_allowed"
    root_verify = await client.post(
        f"{API}/chat/messages/{question['id']}/verify", headers=teacher.headers
    )
    assert root_verify.json()["error"]["code"] == "chat.verify_needs_reply"
    verified = await client.post(verify, headers=teacher.headers)
    assert verified.status_code == 200, verified.text
    assert (verified.json()["is_verified_answer"], verified.json()["verified_by_name"]) == (
        True,
        "Fərid İsmayılov",
    )
    notified = await db.scalar(
        select(Notification.user_id).where(
            Notification.kind == NotificationKind.CHAT_ANSWER_VERIFIED
        )
    )
    # The real author of the anonymous question hears about it; nobody else learns who that is.
    assert notified == aysel.id

    edited = await client.patch(
        f"{API}/chat/messages/{answer['id']}",
        headers=ramin.headers,
        json={"body": "Bəli, düşəcək."},
    )
    assert edited.json()["message"]["is_verified_answer"] is False
