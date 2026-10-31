"""Feed and Q&A forum (§6, Sprint 12, D-090): visibility, idempotency, reports and hiding, votes, promotion."""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.ratelimit import RateLimit
from app.modules.audit.models import AuditLog
from app.modules.chat.models import BlockedTerm, BlockedTermAction, ChannelType
from app.modules.chat.tests.conftest import MakeChannel, MakePerson, Person
from app.modules.community import service as community_service
from app.modules.community.service import _cursor, _decode

API = "/api/v1"


def test_cursor_round_trip_and_garbage() -> None:
    created = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
    item_id = uuid.uuid4()
    assert _decode(_cursor(created, item_id)) == (created, item_id)
    with pytest.raises(AppError, match=r"community\.invalid_cursor"):
        _decode("not-a-cursor")


async def tags(client: AsyncClient, who: Person) -> dict[str, str]:
    response = await client.get(f"{API}/community/tags", headers=who.headers)
    assert response.status_code == 200, response.text
    return {tag["slug"]: tag["id"] for tag in response.json()["items"]}


async def post(client: AsyncClient, who: Person, body: str, **extra: Any) -> Any:
    response = await client.post(
        f"{API}/feed/posts", headers=who.headers, json={"body": body, **extra}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def feed(client: AsyncClient, who: Person, **params: str) -> list[dict[str, Any]]:
    response = await client.get(f"{API}/feed/posts", headers=who.headers, params=params)
    assert response.status_code == 200, response.text
    items: list[dict[str, Any]] = response.json()["items"]
    return items


async def report(client: AsyncClient, who: Person, kind: str, item_id: str) -> Any:
    return await client.post(
        f"{API}/reports",
        headers=who.headers,
        json={"target_type": kind, "target_id": item_id, "reason": "spam"},
    )


async def test_posts_tags_comments_and_helpful(client: AsyncClient, person: MakePerson) -> None:
    aysel, ramin = await person(), await person("Ramin", "Əliyev")
    catalogue = await tags(client, aysel)
    assert {"imtahanlar", "kitabxana", "yataqxana"} <= catalogue.keys()

    unknown = await client.post(
        f"{API}/feed/posts",
        headers=aysel.headers,
        json={"body": "Salam", "tag_ids": [str(uuid.uuid4())]},
    )
    assert (unknown.status_code, unknown.json()["error"]["code"]) == (
        422,
        "community.tag_not_found",
    )

    created = await post(
        client,
        aysel,
        "  Kitabxana şənbə günü 10:00-a qədər açıqdır.  ",
        tag_ids=[catalogue["kitabxana"]],
    )
    assert created["body"] == "Kitabxana şənbə günü 10:00-a qədər açıqdır."
    assert created["author"]["display_name"] == "Aysel Məmmədova"
    assert [tag["slug"] for tag in created["tags"]] == ["kitabxana"]
    assert (created["mine"], created["helpful_count"], created["comment_count"]) == (True, 0, 0)
    await post(client, ramin, "Yataqxana qeydiyyatı başladı.", tag_ids=[catalogue["yataqxana"]])

    assert [p["id"] for p in await feed(client, ramin, tag="kitabxana")] == [created["id"]]
    assert len(await feed(client, ramin)) == 2

    comment = await client.post(
        f"{API}/feed/posts/{created['id']}/comments",
        headers=ramin.headers,
        json={"body": "Təşəkkürlər, bazar günü də açıqdır?"},
    )
    assert comment.status_code == 201, comment.text
    comments = await client.get(f"{API}/feed/posts/{created['id']}/comments", headers=aysel.headers)
    assert [c["body"] for c in comments.json()["items"]] == ["Təşəkkürlər, bazar günü də açıqdır?"]
    assert comments.json()["items"][0]["mine"] is False

    own = await client.put(f"{API}/feed/posts/{created['id']}/helpful", headers=aysel.headers)
    assert (own.status_code, own.json()["error"]["code"]) == (422, "community.own_content")
    for _ in range(2):
        marked = await client.put(
            f"{API}/feed/posts/{created['id']}/helpful", headers=ramin.headers
        )
        assert marked.status_code == 204
    seen = next(p for p in await feed(client, ramin) if p["id"] == created["id"])
    assert (seen["helpful_count"], seen["my_helpful"], seen["comment_count"]) == (1, True, 1)
    await client.delete(f"{API}/feed/posts/{created['id']}/helpful", headers=ramin.headers)
    seen = next(p for p in await feed(client, ramin) if p["id"] == created["id"])
    assert (seen["helpful_count"], seen["my_helpful"]) == (0, False)

    # Only the author deletes; for others the post does not exist.
    refused = await client.delete(f"{API}/feed/posts/{created['id']}", headers=ramin.headers)
    assert refused.status_code == 404
    assert (
        await client.delete(f"{API}/feed/posts/{created['id']}", headers=aysel.headers)
    ).status_code == 204
    assert created["id"] not in {p["id"] for p in await feed(client, ramin)}
    gone = await client.get(f"{API}/feed/posts/{created['id']}/comments", headers=ramin.headers)
    assert gone.status_code == 404


async def test_pagination_and_idempotent_creation(
    client: AsyncClient, person: MakePerson, monkeypatch: pytest.MonkeyPatch
) -> None:
    aysel = await person()
    monkeypatch.setattr(community_service, "POST_LIMIT", RateLimit(f"t{uuid.uuid4()}", 50, 60))
    for n in range(community_service.PAGE + 1):
        await post(client, aysel, f"Elan {n}")
    first = await client.get(f"{API}/feed/posts", headers=aysel.headers)
    assert len(first.json()["items"]) == community_service.PAGE
    assert first.json()["items"][0]["body"] == f"Elan {community_service.PAGE}"
    rest = await client.get(
        f"{API}/feed/posts", headers=aysel.headers, params={"cursor": first.json()["next_cursor"]}
    )
    assert [p["body"] for p in rest.json()["items"]] == ["Elan 0"]
    assert rest.json()["next_cursor"] is None

    key = {"Idempotency-Key": f"e2e-{uuid.uuid4()}", **aysel.headers}
    a = await client.post(f"{API}/feed/posts", headers=key, json={"body": "Bir dəfə"})
    b = await client.post(f"{API}/feed/posts", headers=key, json={"body": "Bir dəfə"})
    assert a.json()["id"] == b.json()["id"]
    question = {"title": "Sessiya nə vaxt başlayır?", "body": "Qış sessiyası"}
    q1 = await client.post(f"{API}/forum/questions", headers=key, json=question)
    q2 = await client.post(f"{API}/forum/questions", headers=key, json=question)
    assert q1.json()["id"] == q2.json()["id"]


async def test_rate_limit_and_blocked_terms(
    client: AsyncClient, person: MakePerson, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    aysel = await person()
    term = BlockedTerm(
        pattern="cavablar satılır", is_regex=False, action=BlockedTermAction.HOLD, lang="az"
    )
    db.add(term)
    await db.commit()
    try:
        refused = await client.post(
            f"{API}/forum/questions",
            headers=aysel.headers,
            json={"title": "İmtahan", "body": "CAVABLAR SATILIR, yazın"},
        )
        assert (refused.status_code, refused.json()["error"]["code"]) == (
            422,
            "community.content_rejected",
        )
    finally:
        await db.execute(delete(BlockedTerm).where(BlockedTerm.id == term.id))
        await db.commit()

    monkeypatch.setattr(community_service, "POST_LIMIT", RateLimit(f"t{uuid.uuid4()}", 1, 60))
    await post(client, aysel, "Birinci")
    limited = await client.post(f"{API}/feed/posts", headers=aysel.headers, json={"body": "İkinci"})
    assert limited.status_code == 429


async def test_three_reports_hide_until_staff_restore(
    client: AsyncClient, person: MakePerson, db: AsyncSession
) -> None:
    author = await person()
    readers = [
        await person("Ramin", "Əliyev"),
        await person("Orxan", "Rzayev"),
        await person("Nərmin", "Şükürova"),
    ]
    staff = await person("Günel", "Səfərova", roles=["staff"])
    item = await post(client, author, "Reklam: ucuz kurs işləri")

    assert (await report(client, author, "post", item["id"])).status_code == 422
    assert (await report(client, readers[0], "post", str(uuid.uuid4()))).status_code == 404
    for reader in readers[:2]:
        assert (await report(client, reader, "post", item["id"])).status_code == 201
    assert (await report(client, readers[0], "post", item["id"])).json()["duplicate"] is True
    assert item["id"] in {p["id"] for p in await feed(client, readers[2])}

    assert (await report(client, readers[2], "post", item["id"])).status_code == 201
    assert item["id"] not in {p["id"] for p in await feed(client, readers[0])}
    own = next(p for p in await feed(client, author) if p["id"] == item["id"])
    assert own["hidden"] is True
    assert next(p for p in await feed(client, staff) if p["id"] == item["id"])["hidden"] is True
    # A hidden post cannot be reported again by someone who can no longer see it.
    assert (
        await report(client, await person("Səbinə", "Rəsulova"), "post", item["id"])
    ).status_code == 404

    listed = await client.get(f"{API}/moderation/reports", headers=staff.headers)
    entry = next(r for r in listed.json()["items"] if r["target_type"] == "post")
    assert entry["content"]["excerpt"] == "Reklam: ucuz kurs işləri"
    assert entry["content"]["hidden"] is True
    assert entry["reported_user"]["display_name"] == "Aysel Məmmədova"
    assert entry["reporters"] == 3

    student = await client.put(
        f"{API}/community/post/{item['id']}/visibility",
        headers=readers[0].headers,
        json={"hidden": False},
    )
    assert student.status_code == 403
    for _ in range(2):
        restored = await client.put(
            f"{API}/community/post/{item['id']}/visibility",
            headers=staff.headers,
            json={"hidden": False},
        )
        assert restored.status_code == 204
    assert item["id"] in {p["id"] for p in await feed(client, readers[0])}
    actions = list(
        await db.scalars(
            select(AuditLog.action)
            .where(AuditLog.target_id == item["id"])
            .order_by(AuditLog.occurred_at)
        )
    )
    assert actions == ["community.auto_hidden", "community.shown"]


async def test_questions_answers_votes_accept_and_verify(
    client: AsyncClient, person: MakePerson
) -> None:
    asker, helper = await person(), await person("Ramin", "Əliyev")
    teacher = await person("Leyla", "Həsənova", roles=["teacher"])
    catalogue = await tags(client, asker)
    created = await client.post(
        f"{API}/forum/questions",
        headers=asker.headers,
        json={
            "title": "Statistika imtahanında kalkulyator olar?",
            "body": "Keçən il icazə verilirdi.",
            "tag_ids": [catalogue["imtahanlar"]],
        },
    )
    assert created.status_code == 201, created.text
    question_id = created.json()["id"]

    answered = await client.post(
        f"{API}/forum/questions/{question_id}/answers",
        headers=helper.headers,
        json={"body": "Bəli, sadə kalkulyator olar."},
    )
    assert answered.status_code == 201, answered.text
    answer_id = answered.json()["answers"][0]["id"]

    own = await client.put(f"{API}/forum/answers/{answer_id}/vote?value=1", headers=helper.headers)
    assert (own.status_code, own.json()["error"]["code"]) == (422, "community.own_content")
    assert (
        await client.put(f"{API}/forum/answers/{answer_id}/vote?value=2", headers=asker.headers)
    ).status_code == 422
    for value, score in ((1, 1), (-1, -1), (0, 0), (1, 1)):
        voted = await client.put(
            f"{API}/forum/answers/{answer_id}/vote?value={value}", headers=asker.headers
        )
        assert voted.status_code == 204
        detail = (
            await client.get(f"{API}/forum/questions/{question_id}", headers=asker.headers)
        ).json()
        assert (detail["answers"][0]["score"], detail["answers"][0]["my_vote"]) == (score, value)

    stranger = await client.put(
        f"{API}/forum/questions/{question_id}/accepted-answer",
        headers=helper.headers,
        json={"answer_id": answer_id},
    )
    assert (stranger.status_code, stranger.json()["error"]["code"]) == (
        403,
        "community.not_question_author",
    )
    accepted = await client.put(
        f"{API}/forum/questions/{question_id}/accepted-answer",
        headers=asker.headers,
        json={"answer_id": answer_id},
    )
    assert accepted.status_code == 204

    student = await client.put(
        f"{API}/forum/answers/{answer_id}/verification", headers=asker.headers
    )
    assert (student.status_code, student.json()["error"]["code"]) == (403, "community.not_verifier")
    assert (
        await client.put(f"{API}/forum/answers/{answer_id}/verification", headers=teacher.headers)
    ).status_code == 204
    detail = (
        await client.get(f"{API}/forum/questions/{question_id}", headers=teacher.headers)
    ).json()
    assert detail["can_verify"] is True
    assert detail["accepted_answer_id"] == answer_id
    assert detail["teacher_verified"] is True
    assert detail["answers"][0]["accepted"] is True
    assert detail["answers"][0]["verified_by"]["display_name"] == "Leyla Həsənova"

    listed = await client.get(
        f"{API}/forum/questions", headers=helper.headers, params={"tag": "imtahanlar"}
    )
    summary = listed.json()["items"][0]
    assert (summary["answer_count"], summary["accepted"], summary["teacher_verified"]) == (
        1,
        True,
        True,
    )
    assert (
        await client.get(
            f"{API}/forum/questions", headers=helper.headers, params={"tag": "kitabxana"}
        )
    ).json()["items"] == []

    await client.delete(f"{API}/forum/answers/{answer_id}/verification", headers=teacher.headers)
    await client.put(
        f"{API}/forum/questions/{question_id}/accepted-answer",
        headers=asker.headers,
        json={"answer_id": None},
    )
    detail = (
        await client.get(f"{API}/forum/questions/{question_id}", headers=asker.headers)
    ).json()
    assert (detail["accepted_answer_id"], detail["teacher_verified"]) == (None, False)
    assert detail["can_verify"] is False

    await client.put(
        f"{API}/forum/questions/{question_id}/accepted-answer",
        headers=asker.headers,
        json={"answer_id": answer_id},
    )
    assert (
        await client.delete(f"{API}/forum/answers/{answer_id}", headers=helper.headers)
    ).status_code == 204
    after = (await client.get(f"{API}/forum/questions/{question_id}", headers=asker.headers)).json()
    # Deleting the accepted answer clears the mark instead of leaving a question that points at nothing.
    assert (after["accepted_answer_id"], after["answers"]) == (None, [])
    assert (
        await client.delete(f"{API}/forum/questions/{question_id}", headers=asker.headers)
    ).status_code == 204
    missing = await client.get(f"{API}/forum/questions/{question_id}", headers=asker.headers)
    assert (missing.status_code, missing.json()["error"]["code"]) == (
        404,
        "community.question_not_found",
    )


async def test_only_the_author_promotes_a_visible_signed_thread_root(
    client: AsyncClient, person: MakePerson, channel: MakeChannel, db: AsyncSession
) -> None:
    aysel, ramin, outsider = (
        await person(),
        await person("Ramin", "Əliyev"),
        await person("Orxan", "Rzayev"),
    )
    channel_id = await channel(aysel, ramin, type=ChannelType.PRIVATE_GROUP)

    async def send(who: Person, body: str) -> str:
        sent = await client.post(
            f"{API}/chat/channels/{channel_id}/messages",
            headers=who.headers,
            json={"body": body, "client_msg_id": str(uuid.uuid4())},
        )
        assert sent.status_code == 201, sent.text
        message_id: str = sent.json()["message"]["id"]
        return message_id

    async def promote(who: Person, message_id: str) -> Any:
        return await client.post(
            f"{API}/chat/channels/{channel_id}/messages/{message_id}/promote",
            headers=who.headers,
            json={"title": "Layihə hesabatının formatı"},
        )

    mine = await send(aysel, f"Hesabat <@{ramin.id}> ilə birlikdə PDF formatında olmalıdır?")
    theirs = await send(ramin, "Mən də bilmirəm.")
    assert (await promote(outsider, mine)).status_code == 404
    refused = await promote(aysel, theirs)
    assert (refused.status_code, refused.json()["error"]["code"]) == (
        403,
        "community.promotion_not_allowed",
    )

    for change in (
        "UPDATE messages SET is_anonymous = true WHERE id = :id",
        "UPDATE messages SET moderation = 'held' WHERE id = :id",
    ):
        await db.execute(text(change), {"id": int(mine)})
        await db.commit()
        assert (await promote(aysel, mine)).status_code == 403
        await db.execute(
            text("UPDATE messages SET is_anonymous = false, moderation = 'visible' WHERE id = :id"),
            {"id": int(mine)},
        )
        await db.commit()

    promoted = await promote(aysel, mine)
    assert promoted.status_code == 201, promoted.text
    assert promoted.json()["body"] == "Hesabat ilə birlikdə PDF formatında olmalıdır?"
    assert promoted.json()["author"]["display_name"] == "Aysel Məmmədova"
