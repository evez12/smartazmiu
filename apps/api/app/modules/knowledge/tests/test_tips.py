"""Subject Guide cards (§5.2 flow 5, D-084): eligibility, one card per subject and semester, moderation,
aggregation, upvotes and reports."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academics.models import Semester, SemesterTerm, Subject
from app.modules.knowledge.models import CourseTip
from app.modules.knowledge.service import TipService
from app.modules.materials.tests.test_materials import sign_in
from app.modules.notifications.models import Notification, NotificationKind
from tests.support import TokenFactory

API = "/api/v1"
Seed = Callable[..., Awaitable[None]]


def card(semester_id: str, **fields: Any) -> dict[str, Any]:
    return {
        "semester_id": semester_id,
        "difficulty": 4,
        "weekly_hours": "4_6",
        "key_topics": "Tələb və təklif, elastiklik, istehlakçı seçimi.",
        "resources": [
            {"title": "Mankiw, Principles of Economics", "url": "https://example.org/mankiw"}
        ],
        "exam_advice": "Qrafik tapşırıqlarını çox həll edin.",
        "retrospective": "Seminarlara daha tez hazırlaşardım.",
        **fields,
    }


async def test_cards_from_passing_students_are_moderated_and_upvoted(
    client: AsyncClient,
    db: AsyncSession,
    tokens: TokenFactory,
    seed: Seed,
    staff_headers: dict[str, str],
) -> None:
    await seed()
    tarlan = await sign_in(
        client, tokens, "tarlan.agayev@smartazmiu.test", ["student"], "Tərlan", "Ağayev"
    )
    konul = await sign_in(
        client, tokens, "konul.azimova@smartazmiu.test", ["student"], "Könül", "Əzimova"
    )
    anar = await sign_in(
        client, tokens, "anar.rustamov@smartazmiu.test", ["student"], "Anar", "Rüstəmov"
    )
    aysel = await sign_in(
        client, tokens, "aysel.mammadova@smartazmiu.test", ["student"], "Aysel", "Məmmədova"
    )
    ramin = await sign_in(
        client, tokens, "ramin.aliyev@smartazmiu.test", ["student"], "Ramin", "Əliyev"
    )
    micro = await db.scalar(select(Subject.id).where(Subject.code == "IQT-2101"))
    fall = await db.scalar(
        select(Semester.id).where(Semester.year == 2025, Semester.term == SemesterTerm.FALL)
    )
    assert micro is not None
    assert fall is not None
    url = f"{API}/subjects/{micro}/tips/mine"

    eligible = (await client.get(f"{API}/tips/eligible", headers=tarlan.headers)).json()
    assert any(
        item["subject_id"] == str(micro) and item["semester"] == "2025 Payız" for item in eligible
    )
    # Failed that semester, and never took it: no card.
    assert (await client.put(url, headers=anar.headers, json=card(str(fall)))).status_code == 403
    assert (await client.put(url, headers=aysel.headers, json=card(str(fall)))).json()["error"][
        "code"
    ] == ("tips.not_eligible")
    bad_link = await client.put(
        url,
        headers=tarlan.headers,
        json=card(str(fall), resources=[{"title": "x", "url": "javascript:alert(1)"}]),
    )
    assert bad_link.json()["error"]["code"] == "tips.invalid_link"

    first = await client.put(url, headers=tarlan.headers, json=card(str(fall)))
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "pending"
    # Writing again edits the same card and sends it back to moderation.
    again = await client.put(url, headers=tarlan.headers, json=card(str(fall), difficulty=5))
    assert again.json()["id"] == first.json()["id"]
    assert await db.scalar(select(func.count()).select_from(CourseTip)) == 1
    other = await client.put(
        url, headers=konul.headers, json=card(str(fall), difficulty=3, weekly_hours="2_4")
    )
    assert other.status_code == 200

    page_url = f"{API}/subjects/{micro}/tips"
    assert (await client.get(page_url, headers=aysel.headers)).json()["tip_count"] == 0
    assert (await client.get(f"{API}/moderation/tips", headers=aysel.headers)).status_code == 403
    queue = (await client.get(f"{API}/moderation/tips", headers=staff_headers)).json()
    assert queue["total"] == 2
    assert {item["author_name"] for item in queue["items"]} == {"Tərlan Ağayev", "Könül Əzimova"}
    for item in queue["items"]:
        reviewed = await client.patch(
            f"{API}/moderation/tips/{item['id']}",
            headers=staff_headers,
            json={"status": "published"},
        )
        assert reviewed.status_code == 204

    page = (await client.get(page_url, headers=aysel.headers)).json()
    assert (page["tip_count"], page["average_difficulty"]) == (2, 4.0)
    assert {w["weekly_hours"]: w["count"] for w in page["workload"]} == {"2_4": 1, "4_6": 1}
    assert page["resources"][0]["mentions"] == 2
    # Students see the semester, never the author or a grade.
    assert "Tərlan" not in str(page)
    assert "grade" not in str(page)

    tip_id = first.json()["id"]
    upvote = f"{API}/tips/{tip_id}/upvote"
    assert (await client.put(upvote, headers=tarlan.headers)).json()["error"][
        "code"
    ] == "tips.own_tip"
    results = await asyncio.gather(
        client.put(upvote, headers=aysel.headers),
        client.put(upvote, headers=aysel.headers),
        client.put(upvote, headers=ramin.headers),
    )
    assert all(r.status_code == 200 for r in results)
    assert (await client.get(page_url, headers=aysel.headers)).json()["tips"][0]["upvotes"] == 2
    assert (await client.delete(upvote, headers=aysel.headers)).json() == 1
    assert (await client.delete(upvote, headers=aysel.headers)).json() == 1

    reported = await client.post(
        f"{API}/reports",
        headers=aysel.headers,
        json={"target_type": "tip", "target_id": tip_id, "reason": "exam_leak"},
    )
    assert reported.status_code == 201, reported.text
    own = await client.post(
        f"{API}/reports",
        headers=tarlan.headers,
        json={"target_type": "tip", "target_id": tip_id, "reason": "other"},
    )
    assert own.status_code == 422
    staff_reports = (await client.get(f"{API}/moderation/reports", headers=staff_headers)).json()
    listed = next(item for item in staff_reports["items"] if item["target_type"] == "tip")
    assert listed["tip"]["subject_name"] == "Mikroiqtisadiyyat"

    hidden = await client.patch(
        f"{API}/moderation/tips/{tip_id}",
        headers=staff_headers,
        json={"status": "hidden", "note": "İmtahan sualı"},
    )
    assert hidden.status_code == 204
    assert (await client.get(page_url, headers=aysel.headers)).json()["tip_count"] == 1
    assert "İmtahan sualı" not in str((await client.get(url, headers=tarlan.headers)).json())


async def test_end_of_semester_prompt_goes_out_once(db: AsyncSession, seed: Seed) -> None:
    await seed()
    service = TipService(db)
    first = await service.prompt_authors()
    assert await service.prompt_authors() == 0
    prompts = await db.scalar(
        select(func.count()).where(Notification.kind == NotificationKind.MENTORSHIP_TIP_PROMPT)
    )
    assert prompts == first
