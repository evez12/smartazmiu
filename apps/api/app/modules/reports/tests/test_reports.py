"""Reports: once per person and target, rate limited, audited, listed for staff (§5.4, §5.5, D-070)."""

import uuid
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog
from app.modules.chat.tests.conftest import MakeChannel, MakePerson, Person
from app.modules.reports.models import Report

API = "/api/v1"


async def say(client: AsyncClient, author: Person, channel_id: uuid.UUID, text: str) -> str:
    response = await client.post(
        f"{API}/chat/channels/{channel_id}/messages",
        headers=author.headers,
        json={"body": text, "client_msg_id": str(uuid.uuid4())},
    )
    assert response.status_code == 201, response.text
    message_id: str = response.json()["message"]["id"]
    return message_id


async def report(client: AsyncClient, reporter: Person, **body: Any) -> Any:
    return await client.post(f"{API}/reports", headers=reporter.headers, json=body)


async def test_a_person_reports_a_target_once_and_only_what_they_can_see(
    client: AsyncClient, db: AsyncSession, person: MakePerson, channel: MakeChannel
) -> None:
    aysel, ramin = await person(), await person("Ramin", "Əliyev")
    outsider = await person("Nigar", "Quliyeva")
    room = await channel(aysel, ramin)
    message_id = await say(client, ramin, room, "Sabahkı imtahanın sualları məndədir.")

    first = await report(
        client, aysel, target_type="message", target_id=message_id, reason="exam_leak", note=" Bax "
    )
    assert first.status_code == 201, first.text
    assert first.json()["status"] == "open"
    assert first.json()["duplicate"] is False
    again = await report(client, aysel, target_type="message", target_id=message_id, reason="spam")
    assert again.status_code == 200
    assert again.json() == {**first.json(), "duplicate": True}
    stored = list(await db.scalars(select(Report)))
    assert len(stored) == 1
    assert (stored[0].note, stored[0].channel_id, stored[0].reason.value) == (
        "Bax",
        room,
        "exam_leak",
    )

    # Non-members cannot report (or learn about) a message; unknown targets look the same.
    for attempt in (message_id, "9" * 19, "abc"):
        hidden = await report(
            client, outsider, target_type="message", target_id=attempt, reason="spam"
        )
        assert (hidden.status_code, hidden.json()["error"]["code"]) == (
            404,
            "reports.target_not_found",
        )
    own = await report(client, ramin, target_type="message", target_id=message_id, reason="spam")
    assert own.json()["error"]["code"] == "reports.own_content"
    self_report = await report(
        client, aysel, target_type="user", target_id=str(aysel.id), reason="spam"
    )
    assert self_report.json()["error"]["code"] == "reports.own_content"
    nobody = await report(
        client, aysel, target_type="user", target_id=str(uuid.uuid4()), reason="spam"
    )
    assert nobody.status_code == 404
    bad_reason = await report(
        client, aysel, target_type="user", target_id=str(ramin.id), reason="x"
    )
    assert bad_reason.status_code == 422
    person_report = await report(
        client, aysel, target_type="user", target_id=str(ramin.id), reason="harassment"
    )
    assert person_report.status_code == 201

    # Audited without the reporter's own words (D-034).
    entries = list(await db.scalars(select(AuditLog).where(AuditLog.action == "report.created")))
    assert len(entries) == 2
    assert all("note" not in entry.details and entry.actor_id == aysel.id for entry in entries)


async def test_report_creation_is_rate_limited(
    client: AsyncClient, person: MakePerson, channel: MakeChannel
) -> None:
    aysel = await person()
    others = [await person("Ramin", f"Əliyev{n}") for n in range(11)]
    statuses = [
        (
            await report(client, aysel, target_type="user", target_id=str(o.id), reason="spam")
        ).status_code
        for o in others
    ]
    assert statuses[:10] == [201] * 10
    assert statuses[10] == 429


async def test_staff_list_and_close_reports_others_cannot(
    client: AsyncClient,
    db: AsyncSession,
    person: MakePerson,
    channel: MakeChannel,
    staff_headers: dict[str, str],
) -> None:
    aysel, ramin, leyla = (
        await person(),
        await person("Ramin", "Əliyev"),
        await person("Leyla", "Həsənova"),
    )
    room = await channel(aysel, ramin, leyla)
    message_id = await say(client, ramin, room, "Reklam: ucuz kurs işləri, 50 ₼.")
    for reporter in (aysel, leyla):
        await report(client, reporter, target_type="message", target_id=message_id, reason="spam")
    await report(client, aysel, target_type="user", target_id=str(ramin.id), reason="harassment")
    # The author deleting the message afterwards does not hide it from staff.
    await client.delete(f"{API}/chat/messages/{message_id}", headers=ramin.headers)

    student = await client.get(f"{API}/moderation/reports", headers=aysel.headers)
    assert (student.status_code, student.json()["error"]["code"]) == (403, "auth.forbidden")
    listed = await client.get(f"{API}/moderation/reports", headers=staff_headers)
    assert listed.status_code == 200, listed.text
    page = listed.json()
    assert page["total"] == 3
    message_reports = [item for item in page["items"] if item["target_type"] == "message"]
    assert {item["reporter"]["display_name"] for item in message_reports} == {
        aysel.name,
        leyla.name,
    }
    sample = message_reports[0]
    assert sample["reporters"] == 2
    assert sample["message"]["body"] == "Reklam: ucuz kurs işləri, 50 ₼."
    assert sample["message"]["deleted"] is True
    assert sample["message"]["channel_name"] == "Statistika layihəsi"
    assert sample["reported_user"]["display_name"] == ramin.name
    # Payloads carry names and photos only: no e-mail, phone or grades (§5.4).
    assert "email" not in str(page)
    assert "grade" not in str(page)

    handled = await client.patch(
        f"{API}/moderation/reports/{sample['id']}",
        headers=staff_headers,
        json={"status": "dismissed"},
    )
    assert handled.status_code == 200, handled.text
    assert handled.json()["status"] == "dismissed"
    assert handled.json()["handled_by"]["display_name"] == "Elvin Quliyev"
    open_only = await client.get(
        f"{API}/moderation/reports", headers=staff_headers, params={"status": "open"}
    )
    assert open_only.json()["total"] == 2
    reopened = await client.patch(
        f"{API}/moderation/reports/{sample['id']}", headers=staff_headers, json={"status": "open"}
    )
    assert reopened.json()["handled_by"] is None
    assert (
        len(list(await db.scalars(select(AuditLog).where(AuditLog.action == "report.handled"))))
        == 2
    )
    student_patch = await client.patch(
        f"{API}/moderation/reports/{sample['id']}",
        headers=aysel.headers,
        json={"status": "dismissed"},
    )
    assert student_patch.status_code == 403
    missing = await client.patch(
        f"{API}/moderation/reports/{uuid.uuid4()}",
        headers=staff_headers,
        json={"status": "actioned"},
    )
    assert missing.status_code == 404
