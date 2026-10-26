"""The pilot feedback form (D-074): sent by anyone signed in, read and closed by staff only."""

import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog
from app.modules.chat.tests.conftest import MakePerson
from app.modules.feedback.models import Feedback

API = "/api/v1"


async def test_people_send_feedback_and_staff_close_it(
    client: AsyncClient, db: AsyncSession, person: MakePerson, staff_headers: dict[str, str]
) -> None:
    aysel, ramin = await person(), await person("Ramin", "Əliyev")
    sent = await client.post(
        f"{API}/feedback",
        headers=aysel.headers,
        json={
            "category": "problem",
            "message": "  Cədvəldə otaq göstərilmir.  ",
            "page": "/schedule?week=2026-11-02#monday",
            "contact_ok": True,
        },
    )
    assert sent.status_code == 201, sent.text
    stored = await db.get(Feedback, uuid.UUID(sent.json()["id"]))
    assert stored is not None
    # Only the path is kept; the message is trimmed.
    assert (stored.page, stored.message) == ("/schedule", "Cədvəldə otaq göstərilmir.")
    await client.post(
        f"{API}/feedback",
        headers=ramin.headers,
        json={
            "category": "suggestion",
            "message": "Qaranlıq rejim əladır.",
            "page": "https://x.test",
        },
    )
    blank = await client.post(
        f"{API}/feedback", headers=ramin.headers, json={"category": "other", "message": "   "}
    )
    assert (blank.status_code, blank.json()["error"]["code"]) == (422, "feedback.message_required")
    invalid = await client.post(
        f"{API}/feedback", headers=ramin.headers, json={"category": "spam", "message": "x"}
    )
    assert invalid.status_code == 422

    assert (await client.get(f"{API}/admin/feedback", headers=aysel.headers)).status_code == 403
    listed = (await client.get(f"{API}/admin/feedback", headers=staff_headers)).json()
    assert listed["total"] == 2
    newest, oldest = listed["items"]
    assert newest["sender"] == {"id": str(ramin.id), "display_name": ramin.name, "email": None}
    assert newest["page"] == ""
    # The e-mail is shown only to reach someone who asked to be contacted (§5.4).
    assert oldest["sender"]["email"].endswith("@smartazmiu.test")

    closed = await client.patch(
        f"{API}/admin/feedback/{oldest['id']}", headers=staff_headers, json={"status": "closed"}
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["handled_by"] == "Elvin Quliyev"
    assert closed.json()["handled_at"] is not None
    same = await client.patch(
        f"{API}/admin/feedback/{oldest['id']}", headers=staff_headers, json={"status": "closed"}
    )
    assert same.json()["status"] == "closed"
    open_only = (
        await client.get(f"{API}/admin/feedback", headers=staff_headers, params={"status": "open"})
    ).json()
    assert [item["id"] for item in open_only["items"]] == [newest["id"]]
    reopened = await client.patch(
        f"{API}/admin/feedback/{oldest['id']}", headers=staff_headers, json={"status": "open"}
    )
    assert reopened.json()["handled_by"] is None
    entries = list(await db.scalars(select(AuditLog).where(AuditLog.action == "feedback.handled")))
    assert len(entries) == 2
    assert all("message" not in entry.details for entry in entries)
    assert (
        await client.patch(
            f"{API}/admin/feedback/{oldest['id']}", headers=aysel.headers, json={"status": "closed"}
        )
    ).status_code == 403
    missing = await client.patch(
        f"{API}/admin/feedback/{uuid.uuid4()}", headers=staff_headers, json={"status": "closed"}
    )
    assert missing.status_code == 404

    # Own feedback is part of the personal data export.
    export = await client.get(f"{API}/me/export", headers=aysel.headers)
    assert [item["message"] for item in export.json()["feedback"]] == ["Cədvəldə otaq göstərilmir."]


async def test_feedback_is_rate_limited(client: AsyncClient, person: MakePerson) -> None:
    aysel = await person()
    statuses = [
        (
            await client.post(
                f"{API}/feedback",
                headers=aysel.headers,
                json={"category": "other", "message": f"Qeyd {n}"},
            )
        ).status_code
        for n in range(11)
    ]
    assert statuses == [201] * 10 + [429]
