"""Assignments: offering-scoped access, scanned submissions, late policy and grading (§6, §13, D-092)."""

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ratelimit import RateLimit
from app.core.time import utc_now
from app.modules.assignments import service as assignment_service
from app.modules.assignments.models import Assignment, AssignmentFile, LatePolicy
from app.modules.assignments.scanner import SubmissionScanner
from app.modules.assignments.service import effective_points, submission_blocker
from app.modules.audit.models import AuditLog
from app.modules.chat.models import ScanStatus
from app.modules.chat.tests.conftest import MakePerson, Person
from app.modules.chat.tests.test_attachments import EICAR, PDF, FakeScanner
from app.modules.materials.tests.test_materials import sign_in
from tests.support import FakeJobs, MemoryStorage, TokenFactory

API = "/api/v1"
Seed = Callable[..., Awaitable[None]]


def assignment(policy: LatePolicy = LatePolicy.REJECT, penalty: str = "0") -> Assignment:
    return Assignment(
        max_points=Decimal("100"), late_policy=policy, late_penalty_percent=Decimal(penalty)
    )


def test_late_penalty_reduces_the_points_and_nothing_else_does() -> None:
    assert effective_points(assignment(LatePolicy.PENALIZE, "25"), Decimal("80"), is_late=True) == (
        Decimal("60.00")
    )
    assert effective_points(
        assignment(LatePolicy.PENALIZE, "25"), Decimal("80"), is_late=False
    ) == (Decimal("80"))
    assert effective_points(assignment(LatePolicy.ACCEPT), Decimal("80"), is_late=True) == Decimal(
        "80"
    )
    assert effective_points(
        assignment(LatePolicy.PENALIZE, "33.33"), Decimal("77"), is_late=True
    ) == Decimal("51.34")


def test_who_can_submit_and_why_not() -> None:
    now = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
    past, future = now - timedelta(hours=1), now + timedelta(hours=1)
    base = assignment()
    open_now = {"graded": False, "role": "student"}
    assert submission_blocker(base, now, **open_now) is None  # type: ignore[arg-type]
    assert submission_blocker(base, now, graded=False, role="manager") == "not_student"
    assert submission_blocker(base, now, graded=False, role="reader") == "not_student"
    assert submission_blocker(base, now, graded=True, role="student") == "graded"
    base.available_from = future
    assert submission_blocker(base, now, graded=False, role="student") == "not_available"
    base.available_from, base.deadline = None, past
    assert submission_blocker(base, now, graded=False, role="student") == "closed"
    base.late_policy = LatePolicy.PENALIZE
    assert submission_blocker(base, now, graded=False, role="student") is None


@pytest.fixture
async def people(
    client: AsyncClient, tokens: TokenFactory, seed: Seed, person: MakePerson
) -> dict[str, Person]:
    await seed()
    return {
        "leyla": await sign_in(
            client, tokens, "leyla.hasanova@smartazmiu.test", ["teacher"], "Leyla", "Həsənova"
        ),
        "aysel": await sign_in(
            client, tokens, "aysel.mammadova@smartazmiu.test", ["student"], "Aysel", "Məmmədova"
        ),
        "rauf": await sign_in(
            client, tokens, "rauf.mammadov@smartazmiu.test", ["teacher"], "Rauf", "Məmmədov"
        ),
        "outsider": await person("Orxan", "Rzayev"),
        "staff": await person("Günel", "Səfərova", roles=["staff"]),
    }


async def statistika(client: AsyncClient, who: Person) -> str:
    offerings = await client.get(f"{API}/coursework/offerings", headers=who.headers)
    assert offerings.status_code == 200, offerings.text
    found: str = next(
        o["id"]
        for o in offerings.json()["items"]
        if (o["subject_code"], o["groups"]) == ("IQT-2102", ["765a2"])
    )
    return found


async def make(client: AsyncClient, who: Person, offering: str, **extra: Any) -> dict[str, Any]:
    response = await client.post(
        f"{API}/assignments",
        headers=who.headers,
        json={"course_offering_id": offering, "title": "Təsviri statistika", **extra},
    )
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


async def upload(
    client: AsyncClient,
    storage: MemoryStorage,
    db: AsyncSession,
    who: Person,
    assignment_id: str,
    data: bytes = PDF,
    filename: str = "Laboratoriya işi.pdf",
) -> str:
    presigned = await client.post(
        f"{API}/assignments/{assignment_id}/uploads/presign",
        headers=who.headers,
        json={"filename": filename, "mime": "application/pdf", "size": len(data)},
    )
    assert presigned.status_code == 200, presigned.text
    upload_id: str = presigned.json()["upload_id"]
    file = await db.get(AssignmentFile, uuid.UUID(upload_id))
    assert file is not None
    await storage.put(file.object_key, data, "application/pdf")
    return upload_id


async def submit(client: AsyncClient, who: Person, assignment_id: str, upload_id: str) -> Any:
    return await client.post(
        f"{API}/assignments/{assignment_id}/submissions",
        headers=who.headers,
        json={"upload_id": upload_id},
    )


async def scan(
    db: AsyncSession, storage: MemoryStorage, scanner: FakeScanner | None = None
) -> None:
    await SubmissionScanner(db, storage, scanner or FakeScanner()).scan_pending()


async def test_only_people_who_manage_the_offering_create_for_it(
    client: AsyncClient, people: dict[str, Person]
) -> None:
    leyla, rauf, aysel, outsider, staff = (
        people[k] for k in ("leyla", "rauf", "aysel", "outsider", "staff")
    )
    offering = await statistika(client, leyla)
    assert [
        o["subject_code"]
        for o in (await client.get(f"{API}/coursework/offerings", headers=aysel.headers)).json()[
            "items"
        ]
    ] == []

    created = await make(client, leyla, offering, max_points="40.5")
    assert (created["can_manage"], created["my_status"]) == (True, None)
    roster = created["enrolled_count"]
    assert roster >= 2
    assert created["offering"]["subject_name"] == "Statistika"
    assert created["offering"]["groups"] == ["765a2"]

    # A teacher of other offerings, a student of this one and an outsider learn nothing: the same 404.
    for who in (rauf, aysel, outsider):
        refused = await client.post(
            f"{API}/assignments",
            headers=who.headers,
            json={"course_offering_id": offering, "title": "Başqasının fənni"},
        )
        assert (refused.status_code, refused.json()["error"]["code"]) == (
            404,
            "assignments.offering_not_found",
        )
    unknown = await client.post(
        f"{API}/assignments",
        headers=leyla.headers,
        json={"course_offering_id": str(uuid.uuid4()), "title": "Yoxdur"},
    )
    assert unknown.status_code == 404
    # Staff manage any offering.
    assert (await make(client, staff, offering, title="Dekanlığın tapşırığı"))["can_manage"] is True

    for invalid in (
        {"late_policy": "accept", "late_penalty_percent": "10", "deadline": "2030-01-01T00:00:00Z"},
        {"deadline": "2030-01-01T00:00:00Z", "available_from": "2030-02-01T00:00:00Z"},
        {"max_points": "0", "late_policy": "accept"},
    ):
        response = await client.post(
            f"{API}/assignments",
            headers=leyla.headers,
            json={"course_offering_id": offering, "title": "Səhv", **invalid},
        )
        assert response.status_code == 422, invalid


async def test_students_see_only_assignments_that_have_opened_in_their_courses(
    client: AsyncClient, people: dict[str, Person]
) -> None:
    leyla, aysel, outsider, rauf = (people[k] for k in ("leyla", "aysel", "outsider", "rauf"))
    offering = await statistika(client, leyla)
    now = utc_now()
    open_now = await make(client, leyla, offering, late_policy="accept")
    later = await make(
        client,
        leyla,
        offering,
        title="Gələn həftə",
        available_from=(now + timedelta(days=7)).isoformat(),
        deadline=(now + timedelta(days=14)).isoformat(),
    )

    mine = (await client.get(f"{API}/assignments", headers=aysel.headers)).json()["items"]
    assert [a["id"] for a in mine] == [open_now["id"]]
    assert (mine[0]["can_manage"], mine[0]["my_status"], mine[0]["enrolled_count"]) == (
        False,
        "not_submitted",
        None,
    )
    seen = await client.get(f"{API}/assignments/{later['id']}", headers=aysel.headers)
    assert (seen.status_code, seen.json()["error"]["code"]) == (404, "assignments.not_found")
    assert len((await client.get(f"{API}/assignments", headers=leyla.headers)).json()["items"]) == 2
    for stranger in (outsider, rauf):
        assert (await client.get(f"{API}/assignments", headers=stranger.headers)).json()[
            "items"
        ] == []
        gone = await client.get(f"{API}/assignments/{open_now['id']}", headers=stranger.headers)
        assert gone.status_code == 404
        assert (
            await client.get(
                f"{API}/assignments/{later['id']}/submissions", headers=stranger.headers
            )
        ).status_code == 404
    refused = await client.get(
        f"{API}/assignments/{open_now['id']}/submissions", headers=aysel.headers
    )
    assert (refused.status_code, refused.json()["error"]["code"]) == (403, "auth.forbidden")


async def test_a_submission_is_uploaded_scanned_graded_and_graded_work_is_final(
    client: AsyncClient,
    db: AsyncSession,
    people: dict[str, Person],
    storage: MemoryStorage,
    jobs: FakeJobs,
) -> None:
    leyla, aysel, outsider = people["leyla"], people["aysel"], people["outsider"]
    offering = await statistika(client, leyla)
    work = await make(client, leyla, offering, max_points="50", late_policy="accept")

    first = await upload(client, storage, db, aysel, work["id"])
    done = await submit(client, aysel, work["id"], first)
    assert done.status_code == 201, done.text
    mine = done.json()["my_submission"]
    assert jobs.scans == 1
    assert [(f["version"], f["status"]) for f in mine["files"]] == [(1, "pending")]
    assert (done.json()["my_status"], mine["is_late"], mine["grade"]) == ("submitted", False, None)
    again = await submit(client, aysel, work["id"], first)
    assert again.status_code == 201
    assert again.json()["my_submission"]["id"] == mine["id"]
    assert len(again.json()["my_submission"]["files"]) == 1

    file_id = mine["files"][0]["id"]
    early = await client.get(f"{API}/assignment-files/{file_id}/download", headers=aysel.headers)
    assert (early.status_code, early.json()["error"]["code"]) == (
        409,
        "assignments.file_not_available",
    )
    await scan(db, storage)
    clean = await client.get(
        f"{API}/assignment-files/{file_id}/download",
        headers=aysel.headers,
        params={"inline": "true"},
    )
    assert clean.status_code == 200, clean.text
    assert storage.last_download["disposition"].startswith("inline")
    assert (
        await client.get(f"{API}/assignment-files/{file_id}/download", headers=leyla.headers)
    ).status_code == 200
    assert (
        await client.get(f"{API}/assignment-files/{file_id}/download", headers=outsider.headers)
    ).status_code == 404

    # A new upload before grading is the next version of the same submission; the old one is kept.
    second = await upload(client, storage, db, aysel, work["id"], PDF + b"\n%second", "Düzəliş.pdf")
    resubmitted = (await submit(client, aysel, work["id"], second)).json()["my_submission"]
    assert [f["version"] for f in resubmitted["files"]] == [2, 1]
    assert resubmitted["id"] == mine["id"]

    rows = (
        await client.get(f"{API}/assignments/{work['id']}/submissions", headers=leyla.headers)
    ).json()["items"]
    sent = next(r for r in rows if r["student"]["display_name"] == "Aysel Məmmədova")
    assert (sent["file_status"], sent["graded"], sent["points"]) == ("pending", False, None)
    assert (
        len(rows)
        == (await client.get(f"{API}/assignments/{work['id']}", headers=leyla.headers)).json()[
            "enrolled_count"
        ]
    )
    assert sum(r["submission_id"] is not None for r in rows) == 1

    # Points above the maximum are refused; the student cannot grade; the teacher can.
    submission_id = mine["id"]
    too_many = await client.post(
        f"{API}/assignment-submissions/{submission_id}/grade",
        headers=leyla.headers,
        json={"points": "50.01"},
    )
    assert (too_many.status_code, too_many.json()["error"]["code"]) == (
        422,
        "assignments.grade_exceeds_maximum",
    )
    for who in (aysel, outsider):
        assert (
            await client.post(
                f"{API}/assignment-submissions/{submission_id}/grade",
                headers=who.headers,
                json={"points": "10"},
            )
        ).status_code in (403, 404)
        assert (
            await client.get(f"{API}/assignment-submissions/{submission_id}", headers=who.headers)
        ).status_code in (403, 404)
    graded = await client.post(
        f"{API}/assignment-submissions/{submission_id}/grade",
        headers=leyla.headers,
        json={"points": "42.5", "feedback": "  Yaxşı iş, nəticələri şərh edin.  "},
    )
    assert graded.status_code == 200, graded.text
    assert graded.json()["grade"]["points"] == "42.50"
    assert graded.json()["grade"]["feedback"] == "Yaxşı iş, nəticələri şərh edin."
    regraded = await client.post(
        f"{API}/assignment-submissions/{submission_id}/grade",
        headers=leyla.headers,
        json={"points": "45"},
    )
    assert regraded.json()["grade"]["points"] == "45.00"

    # The student sees their own grade; graded work cannot be replaced.
    detail = (await client.get(f"{API}/assignments/{work['id']}", headers=aysel.headers)).json()
    assert (detail["my_status"], detail["can_submit"], detail["submit_blocked"]) == (
        "graded",
        False,
        "graded",
    )
    assert detail["my_submission"]["grade"]["points"] == "45.00"
    third = await client.post(
        f"{API}/assignments/{work['id']}/uploads/presign",
        headers=aysel.headers,
        json={"filename": "Gec.pdf", "mime": "application/pdf", "size": 10},
    )
    assert (third.status_code, third.json()["error"]["code"]) == (409, "assignments.graded")

    # The audit trail names the grading but never the points (§5.4).
    entries = list(
        await db.scalars(
            select(AuditLog)
            .where(AuditLog.action == "assignment.graded")
            .order_by(AuditLog.occurred_at)
        )
    )
    assert [e.details["regraded"] for e in entries] == [False, True]
    assert entries[1].details == {"assignment_id": work["id"], "regraded": True}


async def test_late_submissions_follow_the_policy_of_the_assignment(
    client: AsyncClient, db: AsyncSession, people: dict[str, Person], storage: MemoryStorage
) -> None:
    leyla, aysel = people["leyla"], people["aysel"]
    offering = await statistika(client, leyla)
    past = (utc_now() - timedelta(hours=2)).isoformat()
    strict = await make(client, leyla, offering, deadline=past)
    refused = await client.post(
        f"{API}/assignments/{strict['id']}/uploads/presign",
        headers=aysel.headers,
        json={"filename": "Gec.pdf", "mime": "application/pdf", "size": 10},
    )
    assert (refused.status_code, refused.json()["error"]["code"]) == (409, "assignments.closed")
    assert (await client.get(f"{API}/assignments/{strict['id']}", headers=aysel.headers)).json()[
        "submit_blocked"
    ] == "closed"

    soft = await make(
        client, leyla, offering, deadline=past, late_policy="penalize", late_penalty_percent="25"
    )
    late = await submit(
        client, aysel, soft["id"], await upload(client, storage, db, aysel, soft["id"])
    )
    assert late.status_code == 201, late.text
    submission = late.json()["my_submission"]
    assert submission["is_late"] is True
    graded = await client.post(
        f"{API}/assignment-submissions/{submission['id']}/grade",
        headers=leyla.headers,
        json={"points": "80"},
    )
    assert (graded.json()["grade"]["raw_points"], graded.json()["grade"]["points"]) == (
        "80.00",
        "60.00",
    )
    # The limit applies to what the teacher enters: 120 of 100 is refused although 25 % off would fit.
    over = await client.post(
        f"{API}/assignment-submissions/{submission['id']}/grade",
        headers=leyla.headers,
        json={"points": "120"},
    )
    assert over.status_code == 422


async def test_upload_checks_and_storage_outage(
    client: AsyncClient,
    db: AsyncSession,
    people: dict[str, Person],
    storage: MemoryStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    leyla, aysel = people["leyla"], people["aysel"]
    work = await make(client, leyla, await statistika(client, leyla), late_policy="accept")
    presign = f"{API}/assignments/{work['id']}/uploads/presign"
    for body, code in (
        (
            {"filename": "virus.exe", "mime": "application/pdf", "size": 10},
            "assignments.type_not_allowed",
        ),
        (
            {"filename": "a.pdf", "mime": "application/zip", "size": 10},
            "assignments.type_not_allowed",
        ),
        (
            {"filename": "a.pdf", "mime": "application/pdf", "size": 26 * 1024 * 1024},
            "assignments.too_large",
        ),
    ):
        refused = await client.post(presign, headers=aysel.headers, json=body)
        assert (refused.status_code, refused.json()["error"]["code"]) == (422, code)
    # Teachers do not submit.
    assert (
        await client.post(
            presign,
            headers=leyla.headers,
            json={"filename": "a.pdf", "mime": "application/pdf", "size": 10},
        )
    ).status_code == 403

    # An upload that never reached storage, one with the wrong size, and one that is not the student's.
    missing = await client.post(
        presign,
        headers=aysel.headers,
        json={"filename": "a.pdf", "mime": "application/pdf", "size": 10},
    )
    assert (await submit(client, aysel, work["id"], missing.json()["upload_id"])).json()["error"][
        "code"
    ] == "assignments.upload_missing"
    file = await db.get(AssignmentFile, uuid.UUID(missing.json()["upload_id"]))
    assert file is not None
    await storage.put(file.object_key, b"%PDF-1.7 short", "application/pdf")
    assert (await submit(client, aysel, work["id"], missing.json()["upload_id"])).json()["error"][
        "code"
    ] == "assignments.upload_size_mismatch"
    foreign = await upload(client, storage, db, aysel, work["id"])
    thief = await submit(client, people["outsider"], work["id"], foreign)
    assert thief.status_code in (404, 422)

    storage.available = False
    down = await client.post(
        presign,
        headers=aysel.headers,
        json={"filename": "a.pdf", "mime": "application/pdf", "size": 10},
    )
    assert (down.status_code, down.json()["error"]["code"]) == (
        503,
        "assignments.storage_unavailable",
    )
    storage.available = True

    monkeypatch.setattr(assignment_service, "UPLOAD_LIMIT", RateLimit(f"t{uuid.uuid4()}", 1, 60))
    await client.post(
        presign,
        headers=aysel.headers,
        json={"filename": "a.pdf", "mime": "application/pdf", "size": 10},
    )
    limited = await client.post(
        presign,
        headers=aysel.headers,
        json={"filename": "a.pdf", "mime": "application/pdf", "size": 10},
    )
    assert limited.status_code == 429


async def test_infected_files_are_blocked_and_purged_and_outages_leave_files_pending(
    client: AsyncClient, db: AsyncSession, people: dict[str, Person], storage: MemoryStorage
) -> None:
    leyla, aysel = people["leyla"], people["aysel"]
    work = await make(client, leyla, await statistika(client, leyla), late_policy="accept")
    bad = await upload(client, storage, db, aysel, work["id"], PDF + EICAR)
    detail = (await submit(client, aysel, work["id"], bad)).json()
    file_id = detail["my_submission"]["files"][0]["id"]

    scanner = FakeScanner()
    scanner.available = False
    await scan(db, storage, scanner)
    pending = await db.get(AssignmentFile, uuid.UUID(file_id))
    assert pending is not None
    await db.refresh(pending)
    assert (pending.scan_status, pending.scan_attempts) == (ScanStatus.PENDING, 1)
    await db.execute(update(AssignmentFile).values(scan_after=utc_now() - timedelta(seconds=1)))
    await db.commit()

    await scan(db, storage)
    await db.refresh(pending)
    assert pending.scan_status is ScanStatus.INFECTED
    shown = (await client.get(f"{API}/assignments/{work['id']}", headers=aysel.headers)).json()
    assert shown["my_submission"]["files"][0]["status"] == "infected"
    blocked = await client.get(f"{API}/assignment-files/{file_id}/download", headers=leyla.headers)
    assert blocked.status_code == 409

    # An upload that was never submitted disappears after a day, with its object.
    abandoned = await upload(client, storage, db, aysel, work["id"])
    file = await db.get(AssignmentFile, uuid.UUID(abandoned))
    assert file is not None
    key = file.object_key
    assert await SubmissionScanner(db, storage, FakeScanner()).purge() == 1
    assert pending.object_key not in storage.objects
    assert key in storage.objects
    purged = await SubmissionScanner(db, storage, FakeScanner()).purge(
        utc_now() + timedelta(days=2)
    )
    assert purged == 1
    assert key not in storage.objects
    assert await db.get(AssignmentFile, uuid.UUID(abandoned)) is None


async def test_files_of_a_deleted_assignment_are_still_purged(
    client: AsyncClient, db: AsyncSession, people: dict[str, Person], storage: MemoryStorage
) -> None:
    leyla, aysel = people["leyla"], people["aysel"]
    work = await make(client, leyla, await statistika(client, leyla), late_policy="accept")
    sent = await submit(
        client, aysel, work["id"], await upload(client, storage, db, aysel, work["id"])
    )
    file_id = uuid.UUID(sent.json()["my_submission"]["files"][0]["id"])
    file = await db.get(AssignmentFile, file_id)
    assert file is not None
    key = file.object_key

    await db.execute(delete(Assignment).where(Assignment.id == uuid.UUID(work["id"])))
    await db.commit()
    await db.refresh(file)
    # The row outlives the assignment, detached, so the stored object can still be found and removed.
    assert (file.assignment_id, file.submission_id) == (None, None)
    assert key in storage.objects
    gone = await client.get(f"{API}/assignment-files/{file_id}/download", headers=aysel.headers)
    assert gone.status_code == 404
    assert (
        await SubmissionScanner(db, storage, FakeScanner()).purge(utc_now() + timedelta(days=2))
        == 1
    )
    assert key not in storage.objects
