"""Guides and advice requests (§5.2): eligibility, opt-in, badge, request state machine, capacity, feedback."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academics.models import CourseOffering, Enrollment, Subject
from app.modules.chat.models import Channel, ChannelType, UserBlock
from app.modules.chat.provisioning import ChannelProvisioner
from app.modules.chat.tests.conftest import Person
from app.modules.materials.tests.test_materials import sign_in
from app.modules.mentorship.models import MentorRequest, RequestStatus
from app.modules.mentorship.service import MentorshipService
from app.modules.notifications.models import Notification, NotificationKind
from tests.support import TokenFactory

API = "/api/v1"
Seed = Callable[..., Awaitable[None]]


@pytest.fixture
async def people(client: AsyncClient, tokens: TokenFactory, seed: Seed) -> dict[str, Person]:
    await seed()
    accounts = {
        # Passed Mikroiqtisadiyyat (IQT-2101) in 2025 Payız.
        "tarlan": ("tarlan.agayev@smartazmiu.test", "Tərlan", "Ağayev"),
        "konul": ("konul.azimova@smartazmiu.test", "Könül", "Əzimova"),
        # Failed it in 2025 Payız and retakes it now.
        "anar": ("anar.rustamov@smartazmiu.test", "Anar", "Rüstəmov"),
        # Take it now (765a2).
        "aysel": ("aysel.mammadova@smartazmiu.test", "Aysel", "Məmmədova"),
        "ramin": ("ramin.aliyev@smartazmiu.test", "Ramin", "Əliyev"),
    }
    return {
        key: await sign_in(client, tokens, email, ["student"], given, family)
        for key, (email, given, family) in accounts.items()
    }


@pytest.fixture
async def micro(db: AsyncSession, people: dict[str, Person]) -> str:
    subject_id = await db.scalar(select(Subject.id).where(Subject.code == "IQT-2101"))
    assert subject_id is not None
    return str(subject_id)


async def opt_in(client: AsyncClient, person: Person, subject: str, **fields: Any) -> Any:
    return await client.post(
        f"{API}/subjects/{subject}/guides/me",
        headers=person.headers,
        json={"consent": True, **fields},
    )


async def ask(
    client: AsyncClient, person: Person, subject: str, mentor: Person | None = None
) -> Any:
    return await client.post(
        f"{API}/mentor-requests",
        headers=person.headers,
        json={
            "subject_id": subject,
            "mentor_id": str(mentor.id) if mentor else None,
            "topic": "exam",
            "body": "İmtahan necə keçir? Hansı mövzulara diqqət edim?",
        },
    )


async def test_eligibility_opt_in_and_badge(
    client: AsyncClient, db: AsyncSession, people: dict[str, Person], micro: str
) -> None:
    tarlan, anar, aysel = people["tarlan"], people["anar"], people["aysel"]
    eligible = (await client.get(f"{API}/guides/eligible", headers=tarlan.headers)).json()
    entry = next(item for item in eligible if item["subject_code"] == "IQT-2101")
    assert (entry["semester"], entry["opted_in"]) == ("2025 Payız", False)
    # Retaking, and never passed: not eligible, whatever the client sends.
    assert (await opt_in(client, anar, micro)).json()["error"]["code"] == "mentorship.not_eligible"
    assert (await opt_in(client, aysel, micro)).status_code == 403
    no_consent = await opt_in(client, tarlan, micro, consent=False)
    assert no_consent.json()["error"]["code"] == "mentorship.consent_required"

    created = await opt_in(client, tarlan, micro, bio="Mikroiqtisadiyyatı 2025-də keçmişəm.")
    assert created.status_code == 200, created.text
    assert (created.json()["grade_visibility"], created.json()["max_open_requests"]) == (
        "hidden",
        3,
    )
    assert created.json()["availability"] == "available"

    # Provisioning keeps the guide in the community; the badge shows the semester, never the grade.
    await ChannelProvisioner(db).run()
    community = await db.scalar(
        select(Channel.id).where(
            Channel.type == ChannelType.SUBJECT_COMMUNITY, Channel.subject_id == uuid.UUID(micro)
        )
    )
    members = await client.get(f"{API}/chat/channels/{community}/members", headers=aysel.headers)
    assert members.status_code == 200, members.text
    guide = next(m for m in members.json()["members"] if m["id"] == str(tarlan.id))
    assert (guide["badge"], guide["guide_semester"]) == ("guide", "2025 Payız")
    assert "grade" not in str(members.json())

    directory = (await client.get(f"{API}/subjects/{micro}/guides", headers=aysel.headers)).json()
    listed = directory["guides"][0]
    assert listed["user"]["id"] == str(tarlan.id)
    assert (listed["grade_exact"], listed["grade_range"], listed["teacher_name"]) == (
        None,
        None,
        None,
    )
    # Someone outside the subject learns nothing about it.
    outsider = await client.get(f"{API}/subjects/{uuid.uuid4()}/guides", headers=aysel.headers)
    assert outsider.status_code == 404

    # A later results correction revokes the guide and closes requests addressed to them.
    open_request = await ask(client, aysel, micro, tarlan)
    assert open_request.status_code == 201, open_request.text
    offerings = select(CourseOffering.id).where(CourseOffering.subject_id == uuid.UUID(micro))
    await db.execute(
        update(Enrollment)
        .where(Enrollment.user_id == tarlan.id, Enrollment.course_offering_id.in_(offerings))
        .values(passed=False)
    )
    await db.commit()
    report = await MentorshipService(db).sync()
    assert report.revoked == 1
    request = await db.get(MentorRequest, uuid.UUID(open_request.json()["id"]))
    assert request is not None
    await db.refresh(request)
    assert request.status is RequestStatus.DECLINED


async def test_invitations_go_to_eligible_people_once(
    db: AsyncSession, people: dict[str, Person], micro: str
) -> None:
    service = MentorshipService(db)
    first = await service.sync()
    assert first.invited > 0
    assert (await service.sync()).invited == 0
    invited = set(
        await db.scalars(
            select(Notification.user_id).where(
                Notification.kind == NotificationKind.MENTORSHIP_INVITATION,
                Notification.subject_id == uuid.UUID(micro),
            )
        )
    )
    assert people["tarlan"].id in invited
    assert people["anar"].id not in invited
    assert people["aysel"].id not in invited


async def test_request_lifecycle_feedback_and_stats(
    client: AsyncClient, people: dict[str, Person], micro: str
) -> None:
    tarlan, aysel, ramin = people["tarlan"], people["aysel"], people["ramin"]
    assert (await opt_in(client, tarlan, micro)).status_code == 200
    created = await ask(client, aysel, micro, tarlan)
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]
    duplicate = await ask(client, aysel, micro, tarlan)
    assert duplicate.json()["error"]["code"] == "mentorship.request_exists"
    assert (await ask(client, aysel, micro, aysel)).status_code == 422

    # Only the addressed guide may act on it; others get a 404.
    url = f"{API}/mentor-requests/{request_id}"
    assert (await client.post(f"{url}/accept", headers=ramin.headers)).status_code == 404
    assert (await client.post(f"{url}/decline", headers=aysel.headers)).status_code == 404

    accepted = await client.post(f"{url}/accept", headers=tarlan.headers)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted"
    dm = accepted.json()["dm_channel_id"]
    assert dm is not None
    in_dm = await client.get(
        f"{API}/mentor-requests", headers=aysel.headers, params={"channel_id": dm}
    )
    assert [item["id"] for item in in_dm.json()["items"]] == [request_id]
    assert (await client.post(f"{url}/accept", headers=tarlan.headers)).status_code == 409

    early = await client.post(
        f"{url}/feedback", headers=aysel.headers, json={"feedback": "helpful"}
    )
    assert early.json()["error"]["code"] == "mentorship.request_not_resolved"
    resolved = await client.post(f"{url}/resolve", headers=aysel.headers)
    assert resolved.json()["status"] == "resolved"
    # Only the requester rates, once.
    by_guide = await client.post(
        f"{url}/feedback", headers=tarlan.headers, json={"feedback": "helpful"}
    )
    assert by_guide.status_code == 404
    rated = await client.post(
        f"{url}/feedback",
        headers=aysel.headers,
        json={"feedback": "helpful", "note": "Çox faydalı oldu."},
    )
    assert rated.status_code == 200, rated.text
    assert "note" not in rated.json()
    again = await client.post(
        f"{url}/feedback", headers=aysel.headers, json={"feedback": "not_helpful"}
    )
    assert again.json()["error"]["code"] == "mentorship.feedback_exists"

    mine = (await client.get(f"{API}/guides/me", headers=tarlan.headers)).json()
    assert mine[0]["stats"]["helped_count"] == 1
    assert mine[0]["stats"]["helpful_rate"] == 1.0


async def test_capacity_race_and_availability(
    client: AsyncClient, people: dict[str, Person], micro: str
) -> None:
    tarlan, aysel, ramin = people["tarlan"], people["aysel"], people["ramin"]
    assert (await opt_in(client, tarlan, micro, max_open_requests=1)).status_code == 200
    first = (await ask(client, aysel, micro)).json()["id"]
    second = (await ask(client, ramin, micro)).json()["id"]
    results = await asyncio.gather(
        *(
            client.post(f"{API}/mentor-requests/{request_id}/accept", headers=tarlan.headers)
            for request_id in (first, second)
        )
    )
    codes = sorted(r.status_code for r in results)
    assert codes == [200, 409]
    refused = next(r for r in results if r.status_code == 409)
    assert refused.json()["error"]["code"] == "mentorship.capacity_reached"

    # Paused guides take nothing and receive no new addressed requests.
    paused = await client.patch(
        f"{API}/subjects/{micro}/guides/me", headers=tarlan.headers, json={"availability": "paused"}
    )
    assert paused.json()["availability"] == "paused"
    blocked = await ask(client, people["konul"], micro, tarlan)
    assert blocked.status_code in {403, 409}


async def test_blocks_and_expiry(
    client: AsyncClient, db: AsyncSession, people: dict[str, Person], micro: str
) -> None:
    tarlan, aysel, ramin = people["tarlan"], people["aysel"], people["ramin"]
    assert (await opt_in(client, tarlan, micro)).status_code == 200
    db.add(UserBlock(blocker_id=tarlan.id, blocked_id=aysel.id))
    await db.commit()
    refused = await ask(client, aysel, micro, tarlan)
    assert refused.json()["error"]["code"] == "mentorship.guide_unavailable"

    open_id = (await ask(client, ramin, micro, tarlan)).json()["id"]
    service = MentorshipService(db)
    assert await service.expire() == 0
    await db.execute(
        update(MentorRequest)
        .where(MentorRequest.id == uuid.UUID(open_id))
        .values(created_at=MentorRequest.created_at - timedelta(hours=73))
    )
    await db.commit()
    assert await service.expire() == 1
    assert await service.expire() == 0
    request = await db.get(MentorRequest, uuid.UUID(open_id))
    assert request is not None
    await db.refresh(request)
    assert request.status is RequestStatus.EXPIRED
