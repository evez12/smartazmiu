"""The student and staff endpoints of the cabinet mirror: own data only, no grades to anyone else (§5.4, D-126)."""

import json
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ratelimit import RateLimit
from app.modules.academics.models import CourseOffering, Enrollment, ImportKind, Subject
from app.modules.audit.models import AuditAction, AuditLog
from app.modules.cabinet import router as cabinet_router
from app.modules.cabinet.fake import FakeCabinetProvider
from app.modules.cabinet.models import CabinetSyncRun, SyncOutcome, SyncTrigger
from app.modules.cabinet.sync import CabinetSync
from app.modules.chat.tests.conftest import MakePerson, Person
from app.modules.materials.tests.test_materials import sign_in
from app.modules.users.models import PersonType, User
from tests.support import FakeJobs, TokenFactory

Seed = Callable[..., Awaitable[None]]
TRANSCRIPT = "/api/v1/me/transcript"
APPEALS = "/api/v1/me/transcript/appeals"
AYSEL = "25765201"
RAMIN = "25765202"


@pytest.fixture
async def seeded(seed: Seed) -> None:
    await seed(ImportKind.ENROLLMENTS)


@pytest.fixture
def cabinet() -> FakeCabinetProvider:
    return FakeCabinetProvider()


@pytest.fixture
async def aysel(client: AsyncClient, tokens: TokenFactory, seeded: None) -> Person:
    return await sign_in(
        client, tokens, "aysel.mammadova@smartazmiu.test", ["student"], "Aysel", "Məmmədova"
    )


@pytest.fixture
async def ramin(client: AsyncClient, tokens: TokenFactory, seeded: None) -> Person:
    return await sign_in(
        client, tokens, "ramin.aliyev@smartazmiu.test", ["student"], "Ramin", "Əliyev"
    )


async def run_sync(db: AsyncSession, cabinet: FakeCabinetProvider) -> CabinetSyncRun:
    run = await CabinetSync(db, cabinet).run(SyncTrigger.NIGHTLY)
    assert run is not None
    return run


async def test_before_the_first_run_the_student_is_told_nothing_was_synced(
    client: AsyncClient, aysel: Person
) -> None:
    response = await client.get(TRANSCRIPT, headers=aysel.headers)

    assert response.status_code == 200
    assert response.json() == {
        "source": {"state": "never_synced", "last_synced_at": None},
        "student": None,
        "semesters": [],
    }
    assert response.headers["cache-control"] == "no-store"


async def test_a_student_reads_their_own_transcript(
    client: AsyncClient, aysel: Person, db: AsyncSession, cabinet: FakeCabinetProvider
) -> None:
    cabinet.set_score(AYSEL, "SOS-1101", 87)  # the seeded registry grade, so no conflict
    await run_sync(db, cabinet)

    response = await client.get(TRANSCRIPT, headers=aysel.headers)

    assert response.status_code == 200
    body = response.json()
    assert body["source"]["state"] == "ok"
    assert [(s["semester_year"], s["semester_term"]) for s in body["semesters"]] == [
        (2025, "fall"),
        (2026, "spring"),
    ]
    expected = {g.subject_code: g.score for g in (await cabinet.grades(AYSEL)).items}
    shown = {c["subject_code"]: c["score"] for s in body["semesters"] for c in s["courses"]}
    assert shown == expected
    assert body["student"]["credits_earned"] > 0
    assert response.headers["cache-control"] == "no-store"
    assert all(not c["differs"] for s in body["semesters"] for c in s["courses"])


async def test_a_student_never_sees_another_students_records(
    client: AsyncClient,
    aysel: Person,
    ramin: Person,
    db: AsyncSession,
    cabinet: FakeCabinetProvider,
) -> None:
    await run_sync(db, cabinet)

    theirs = await client.get(TRANSCRIPT, headers=ramin.headers)
    mine = await client.get(TRANSCRIPT, headers=aysel.headers)

    ramin_scores = {g.subject_code: g.score for g in (await cabinet.grades(RAMIN)).items}
    shown = {
        c["subject_code"]: c["score"] for s in theirs.json()["semesters"] for c in s["courses"]
    }
    assert shown == ramin_scores
    assert theirs.json() != mine.json()
    for text in (theirs.text, mine.text):
        assert AYSEL not in text
        assert RAMIN not in text
        assert str(aysel.id) not in text
        assert str(ramin.id) not in text


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/users/{other}/transcript",
        "/api/v1/me/transcript/{other}",
        "/api/v1/cabinet/students/{other}",
        "/api/v1/cabinet/transcripts/{other}",
    ],
)
async def test_no_route_names_another_person(
    client: AsyncClient, aysel: Person, ramin: Person, path: str
) -> None:
    response = await client.get(path.format(other=ramin.id), headers=aysel.headers)

    assert response.status_code in (404, 405)


async def test_someone_without_a_cabinet_record_sees_nothing(
    client: AsyncClient,
    seeded: None,
    db: AsyncSession,
    cabinet: FakeCabinetProvider,
    person: MakePerson,
) -> None:
    await run_sync(db, cabinet)
    outsider = await person("Orxan", "Rzayev")

    transcript = await client.get(TRANSCRIPT, headers=outsider.headers)
    appeals = await client.get(APPEALS, headers=outsider.headers)

    assert transcript.json()["student"] is None
    assert transcript.json()["semesters"] == []
    assert appeals.json()["items"] == []


async def test_a_teacher_has_no_student_records(
    client: AsyncClient,
    tokens: TokenFactory,
    seeded: None,
    db: AsyncSession,
    cabinet: FakeCabinetProvider,
) -> None:
    await run_sync(db, cabinet)
    leyla = await sign_in(
        client, tokens, "leyla.hasanova@smartazmiu.test", ["teacher"], "Leyla", "Həsənova"
    )

    assert (await client.get(TRANSCRIPT, headers=leyla.headers)).json()["semesters"] == []


async def test_appeals_are_listed_with_their_status(
    client: AsyncClient,
    seeded: None,
    db: AsyncSession,
    cabinet: FakeCabinetProvider,
    tokens: TokenFactory,
) -> None:
    await run_sync(db, cabinet)
    # Some seeded student has at least one appeal in the made-up data; find one through the provider.
    holder = None
    for user in await db.scalars(select(User).where(User.person_type == PersonType.STUDENT)):
        if user.university_id and (await cabinet.appeals(user.university_id)).items:
            holder = user
            break
    assert holder is not None
    token = tokens.issue(str(uuid.uuid4()), ["student"], email=holder.email)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get(APPEALS, headers=headers)

    assert response.status_code == 200
    expected = (await cabinet.appeals(holder.university_id or "")).items
    items = response.json()["items"]
    assert sorted(i["reference"] for i in items) == sorted(a.reference for a in expected)
    assert {i["status"] for i in items} <= {"submitted", "under_review", "upheld", "rejected"}
    assert response.headers["cache-control"] == "no-store"


async def test_a_failed_run_keeps_the_data_and_says_the_source_is_unavailable(
    client: AsyncClient, aysel: Person, db: AsyncSession, cabinet: FakeCabinetProvider
) -> None:
    good_time = (await run_sync(db, cabinet)).finished_at
    cabinet.break_connection()
    await run_sync(db, cabinet)

    body = (await client.get(TRANSCRIPT, headers=aysel.headers)).json()

    assert body["source"]["state"] == "unavailable"
    assert datetime.fromisoformat(body["source"]["last_synced_at"]) == good_time
    assert body["semesters"]


async def test_the_registry_value_is_shown_and_the_mirror_value_is_not(
    client: AsyncClient, aysel: Person, db: AsyncSession, cabinet: FakeCabinetProvider
) -> None:
    cabinet.set_score(AYSEL, "SOS-1101", 61)
    user = await db.scalar(select(User).where(User.university_id == AYSEL))
    offerings = select(CourseOffering.id).join(Subject).where(Subject.code == "SOS-1101")
    assert user is not None
    await db.execute(
        update(Enrollment)
        .where(Enrollment.user_id == user.id, Enrollment.course_offering_id.in_(offerings))
        .values(grade=87, passed=True)
    )
    await db.commit()
    await run_sync(db, cabinet)

    body = (await client.get(TRANSCRIPT, headers=aysel.headers)).json()

    course = next(
        c for s in body["semesters"] for c in s["courses"] if c["subject_code"] == "SOS-1101"
    )
    assert course == {
        "subject_code": "SOS-1101",
        "subject_name": "Azərbaycan tarixi",
        "credits": 5,
        "score": 87,
        "passed": True,
        "differs": True,
    }
    assert sum(c["differs"] for s in body["semesters"] for c in s["courses"]) == 1


async def test_reads_are_audited_by_kind_only_and_rate_limited(
    client: AsyncClient,
    aysel: Person,
    db: AsyncSession,
    cabinet: FakeCabinetProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await run_sync(db, cabinet)
    monkeypatch.setattr(cabinet_router, "READS", RateLimit(f"t{uuid.uuid4()}", 2, 60))

    assert (await client.get(TRANSCRIPT, headers=aysel.headers)).status_code == 200
    assert (await client.get(APPEALS, headers=aysel.headers)).status_code == 200
    limited = await client.get(TRANSCRIPT, headers=aysel.headers)

    assert limited.status_code == 429
    entries = list(
        await db.scalars(select(AuditLog).where(AuditLog.action == AuditAction.CABINET_VIEWED))
    )
    assert sorted(e.details["kind"] for e in entries) == ["appeals", "transcript"]
    assert all(e.target_id == str(aysel.id) and set(e.details) == {"kind"} for e in entries)


async def test_sign_in_is_required(client: AsyncClient) -> None:
    assert (await client.get(TRANSCRIPT)).status_code == 401
    assert (await client.get(APPEALS)).status_code == 401
    assert (await client.get("/api/v1/cabinet/sync-runs")).status_code == 401


async def test_the_export_holds_the_requesters_mirror_and_nobody_elses(
    client: AsyncClient,
    aysel: Person,
    ramin: Person,
    db: AsyncSession,
    cabinet: FakeCabinetProvider,
) -> None:
    cabinet.set_score(AYSEL, "SOS-1101", 87)  # the seeded registry grade, so no conflict
    await run_sync(db, cabinet)

    document = (await client.get("/api/v1/me/export", headers=aysel.headers)).json()

    mirror = document["cabinet"]
    expected = {g.subject_code: g.score for g in (await cabinet.grades(AYSEL)).items}
    exported = {c["subject_code"]: c["score"] for s in mirror["semesters"] for c in s["courses"]}
    assert exported == expected
    assert mirror["synced_at"]
    text = json.dumps(document)
    assert RAMIN not in text
    assert str(ramin.id) not in text


async def test_the_export_of_an_outsider_has_no_cabinet_section_content(
    client: AsyncClient, seeded: None, person: MakePerson
) -> None:
    outsider = await person("Orxan", "Rzayev")

    document = (await client.get("/api/v1/me/export", headers=outsider.headers)).json()

    assert document["cabinet"] is None


# --- staff -------------------------------------------------------------------------------------------


async def test_students_cannot_use_the_staff_endpoints(client: AsyncClient, aysel: Person) -> None:
    for method, path in (
        ("GET", "/api/v1/cabinet/sync-runs"),
        ("POST", "/api/v1/cabinet/sync-runs"),
        ("GET", "/api/v1/cabinet/conflicts"),
    ):
        response = await client.request(method, path, headers=aysel.headers)
        assert response.status_code == 403, path


async def test_staff_see_runs_as_counts_and_conflicts_without_any_grade(
    client: AsyncClient,
    staff_headers: dict[str, str],
    seeded: None,
    db: AsyncSession,
    cabinet: FakeCabinetProvider,
) -> None:
    cabinet.set_score(AYSEL, "SOS-1101", 61)
    user = await db.scalar(select(User).where(User.university_id == AYSEL))
    assert user is not None
    offerings = select(CourseOffering.id).join(Subject).where(Subject.code == "SOS-1101")
    await db.execute(
        update(Enrollment)
        .where(Enrollment.user_id == user.id, Enrollment.course_offering_id.in_(offerings))
        .values(grade=87, passed=True)
    )
    await db.commit()
    await run_sync(db, cabinet)

    runs = await client.get("/api/v1/cabinet/sync-runs", headers=staff_headers)
    conflicts = await client.get("/api/v1/cabinet/conflicts", headers=staff_headers)

    assert runs.status_code == conflicts.status_code == 200
    run = runs.json()["items"][0]
    assert (run["outcome"], run["trigger"], run["conflicts"]) == ("succeeded", "nightly", 1)
    assert runs.json()["source"]["state"] == "ok"
    assert conflicts.json()["items"] == [
        {
            "university_id": AYSEL,
            "subject_code": "SOS-1101",
            "semester_year": 2025,
            "semester_term": "fall",
            "detected_at": conflicts.json()["items"][0]["detected_at"],
        }
    ]
    for text in (runs.text, conflicts.text):
        assert '"score"' not in text
        assert '"grade"' not in text
    viewed = await db.scalar(
        select(AuditLog).where(AuditLog.action == AuditAction.CABINET_CONFLICTS_VIEWED)
    )
    assert viewed is not None
    assert viewed.details == {"count": 1}


async def test_staff_start_a_sync_and_it_is_audited_and_limited(
    client: AsyncClient,
    staff_headers: dict[str, str],
    jobs: FakeJobs,
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cabinet_router, "SYNC_REQUESTS", RateLimit(f"t{uuid.uuid4()}", 1, 60))

    first = await client.post("/api/v1/cabinet/sync-runs", headers=staff_headers)
    second = await client.post("/api/v1/cabinet/sync-runs", headers=staff_headers)

    assert first.status_code == 202
    assert first.json() == {"queued": True}
    assert second.status_code == 429
    assert len(jobs.cabinet_syncs) == 1
    entry = await db.scalar(
        select(AuditLog).where(AuditLog.action == AuditAction.CABINET_SYNC_REQUESTED)
    )
    assert entry is not None
    assert str(entry.actor_id) == jobs.cabinet_syncs[0]


async def test_the_scrape_reports_the_sync_without_any_person(
    client: AsyncClient, aysel: Person, db: AsyncSession, cabinet: FakeCabinetProvider
) -> None:
    await run_sync(db, cabinet)
    cabinet.break_connection()
    await run_sync(db, cabinet)
    await run_sync(db, cabinet)

    text = (await client.get("/metrics")).text

    assert 'smartazmiu_cabinet_sync_runs{outcome="succeeded"} 1.0' in text
    assert 'smartazmiu_cabinet_sync_runs{outcome="failed"} 2.0' in text
    assert "smartazmiu_cabinet_sync_consecutive_failures 2.0" in text
    assert "smartazmiu_cabinet_sync_last_duration_seconds" in text
    assert "smartazmiu_cabinet_sync_last_success_timestamp_seconds" in text
    assert "smartazmiu_cabinet_conflicts " in text
    assert AYSEL not in text
    assert str(aysel.id) not in text
    assert aysel.name not in text


async def test_a_new_success_resets_the_failure_count(
    client: AsyncClient, seeded: None, db: AsyncSession, cabinet: FakeCabinetProvider
) -> None:
    cabinet.break_connection()
    await run_sync(db, cabinet)
    cabinet.break_connection(False)
    run = await run_sync(db, cabinet)

    text = (await client.get("/metrics")).text

    assert run.outcome is SyncOutcome.SUCCEEDED
    assert "smartazmiu_cabinet_sync_consecutive_failures 0.0" in text
