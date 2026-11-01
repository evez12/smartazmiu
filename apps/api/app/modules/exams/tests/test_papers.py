"""Past papers: consent, the finished-semester rule, approval, scanning and who can see what (D-097)."""

import uuid
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.modules.academics.models import Semester, Subject
from app.modules.audit.models import AuditLog
from app.modules.chat.models import ScanStatus
from app.modules.chat.tests.conftest import MakePerson, Person
from app.modules.chat.tests.test_attachments import EICAR, PDF, FakeScanner
from app.modules.exams.models import PastPaper, PastPaperStatus
from app.modules.exams.notifications import still_decided
from app.modules.exams.papers import PaperScanner
from app.modules.materials.tests.test_materials import sign_in
from app.modules.notifications.models import (
    Notification,
    NotificationCategory,
    NotificationKind,
)
from tests.support import MemoryStorage, TokenFactory

API = "/api/v1/exams"
Seed = Callable[..., Awaitable[None]]


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


async def statistika(db: AsyncSession) -> uuid.UUID:
    subject = await db.scalar(select(Subject.id).where(Subject.code == "IQT-2102"))
    assert subject is not None
    return subject


async def finished_semester(client: AsyncClient, who: Person, subject: uuid.UUID) -> str:
    form = await client.get(
        f"{API}/papers/form", headers=who.headers, params={"subject_id": str(subject)}
    )
    assert form.status_code == 200, form.text
    labels = {s["label"]: s["id"] for s in form.json()["semesters"]}
    assert "2026 Payız" not in labels, "the running semester must never be offered"
    semester: str = labels["2025 Payız"]
    return semester


async def upload(
    client: AsyncClient,
    db: AsyncSession,
    storage: MemoryStorage,
    who: Person,
    subject: uuid.UUID,
    data: bytes = PDF,
    filename: str = "Yekun imtahan 2025.pdf",
) -> str:
    presigned = await client.post(
        f"{API}/papers/uploads/presign",
        headers=who.headers,
        json={
            "subject_id": str(subject),
            "filename": filename,
            "mime": "application/pdf",
            "size": len(data),
        },
    )
    assert presigned.status_code == 200, presigned.text
    upload_id: str = presigned.json()["upload_id"]
    paper = await db.get(PastPaper, uuid.UUID(upload_id))
    assert paper is not None
    storage.objects[paper.object_key] = (data, "application/pdf")
    return upload_id


async def save(
    client: AsyncClient,
    who: Person,
    upload_id: str,
    semester: str,
    *,
    consent: bool = True,
    **extra: Any,
) -> Any:
    return await client.post(
        f"{API}/papers",
        headers=who.headers,
        json={
            "upload_id": upload_id,
            "semester_id": semester,
            "kind": "final",
            "title": "Yekun imtahan, 2025 payız",
            "consent": consent,
            **extra,
        },
    )


async def listed(client: AsyncClient, who: Person, subject: uuid.UUID) -> list[dict[str, Any]]:
    response = await client.get(
        f"{API}/papers", headers=who.headers, params={"subject_id": str(subject)}
    )
    assert response.status_code == 200, response.text
    items: list[dict[str, Any]] = response.json()["items"]
    return items


async def scan(
    db: AsyncSession, storage: MemoryStorage, scanner: FakeScanner | None = None
) -> None:
    await PaperScanner(db, storage, scanner or FakeScanner()).scan_pending()


async def test_a_student_paper_waits_for_a_teacher_then_everyone_in_the_subject_sees_it(
    client: AsyncClient, db: AsyncSession, storage: MemoryStorage, people: dict[str, Person]
) -> None:
    subject = await statistika(db)
    semester = await finished_semester(client, people["aysel"], subject)
    upload_id = await upload(client, db, storage, people["aysel"], subject)

    # Consent is required, and a second upload form of the same file cannot skip it.
    refused = await save(client, people["aysel"], upload_id, semester, consent=False)
    assert (refused.status_code, refused.json()["error"]["code"]) == (422, "exams.consent_required")
    saved = await save(client, people["aysel"], upload_id, semester)
    assert saved.status_code == 201, saved.text
    paper = saved.json()
    assert (paper["status"], paper["uploaded_by_me"], paper["can_review"]) == (
        "pending",
        True,
        False,
    )
    assert (await save(client, people["aysel"], upload_id, semester)).json()["id"] == paper["id"]

    # Only the uploader and reviewers see it while it is pending; the student cannot download before the scan.
    assert [p["id"] for p in await listed(client, people["aysel"], subject)] == [paper["id"]]
    assert [p["id"] for p in await listed(client, people["leyla"], subject)] == [paper["id"]]
    early = await client.get(
        f"{API}/papers/{paper['id']}/download", headers=people["aysel"].headers
    )
    assert (early.status_code, early.json()["error"]["code"]) == (409, "exams.paper_not_available")
    unscanned = await client.post(
        f"{API}/papers/{paper['id']}/review",
        headers=people["leyla"].headers,
        json={"approve": True},
    )
    assert (unscanned.status_code, unscanned.json()["error"]["code"]) == (
        409,
        "exams.paper_not_scanned",
    )

    await scan(db, storage)
    # The author of a paper does not approve it; other students cannot; a teacher of another subject cannot.
    for denied in ("aysel", "rauf"):
        no = await client.post(
            f"{API}/papers/{paper['id']}/review",
            headers=people[denied].headers,
            json={"approve": True},
        )
        assert no.status_code in (403, 404), denied
    approved = await client.post(
        f"{API}/papers/{paper['id']}/review",
        headers=people["leyla"].headers,
        json={"approve": True, "note": "Uyğundur"},
    )
    assert approved.status_code == 200, approved.text
    assert (approved.json()["status"], approved.json()["can_download"]) == ("approved", True)

    mine = await client.get(f"{API}/papers/{paper['id']}/download", headers=people["aysel"].headers)
    assert mine.status_code == 200
    assert mine.json()["filename"] == "Yekun imtahan 2025.pdf"
    audit = list(await db.scalars(select(AuditLog).where(AuditLog.action == "past_paper.reviewed")))
    assert len(audit) == 1
    assert audit[0].details == {"approved": True, "subject_id": str(subject)}

    # Outsiders are told the subject does not exist; another subject's teacher and students get nothing.
    for stranger in ("outsider", "rauf"):
        gone = await client.get(
            f"{API}/papers", headers=people[stranger].headers, params={"subject_id": str(subject)}
        )
        assert gone.status_code == 404, stranger
        assert (
            await client.get(
                f"{API}/papers/{paper['id']}/download", headers=people[stranger].headers
            )
        ).status_code == 404


async def test_a_teachers_own_upload_is_approved_at_once_and_staff_review_anything(
    client: AsyncClient, db: AsyncSession, storage: MemoryStorage, people: dict[str, Person]
) -> None:
    subject = await statistika(db)
    semester = await finished_semester(client, people["leyla"], subject)
    upload_id = await upload(client, db, storage, people["leyla"], subject)
    saved = await save(client, people["leyla"], upload_id, semester)
    assert saved.json()["status"] == "approved"
    await scan(db, storage)
    visible = await listed(client, people["aysel"], subject)
    assert [(p["id"], p["can_download"]) for p in visible] == [(saved.json()["id"], True)]

    # A student's paper can be turned down by staff, and a rejected paper disappears for everyone but its author.
    second = await upload(client, db, storage, people["aysel"], subject, filename="Aralıq.pdf")
    pending = await save(client, people["aysel"], second, semester, title="Aralıq imtahanı")
    await scan(db, storage)
    rejected = await client.post(
        f"{API}/papers/{pending.json()['id']}/review",
        headers=people["staff"].headers,
        json={"approve": False, "note": "Sual yoxdur"},
    )
    assert (rejected.status_code, rejected.json()["status"]) == (200, "rejected")
    others = [p["id"] for p in await listed(client, people["leyla"], subject)]
    assert pending.json()["id"] in others
    student_view = {p["id"]: p for p in await listed(client, people["aysel"], subject)}
    assert student_view[pending.json()["id"]]["review_note"] == "Sual yoxdur"
    again = await client.get(
        f"{API}/papers/{pending.json()['id']}/download", headers=people["staff"].headers
    )
    assert again.status_code == 200


async def test_the_integrity_rules_keep_current_exams_out_and_check_the_file(
    client: AsyncClient, db: AsyncSession, storage: MemoryStorage, people: dict[str, Person]
) -> None:
    subject = await statistika(db)
    finished = await finished_semester(client, people["aysel"], subject)
    # The running semester cannot be chosen, even by sending its id by hand.
    running = await db.scalar(
        select(Semester.id).where(
            Semester.starts_on <= utc_now().date(), Semester.ends_on >= utc_now().date()
        )
    )
    upload_id = await upload(client, db, storage, people["aysel"], subject)
    refused = await save(client, people["aysel"], upload_id, str(running))
    assert (refused.status_code, refused.json()["error"]["code"]) == (
        422,
        "exams.semester_not_finished",
    )

    # The type, the size and the stored object are checked.
    bad_type = await client.post(
        f"{API}/papers/uploads/presign",
        headers=people["aysel"].headers,
        json={
            "subject_id": str(subject),
            "filename": "x.exe",
            "mime": "application/x-msdownload",
            "size": 10,
        },
    )
    assert (bad_type.status_code, bad_type.json()["error"]["code"]) == (
        422,
        "exams.type_not_allowed",
    )
    huge = await client.post(
        f"{API}/papers/uploads/presign",
        headers=people["aysel"].headers,
        json={
            "subject_id": str(subject),
            "filename": "x.pdf",
            "mime": "application/pdf",
            "size": 10**9,
        },
    )
    assert huge.json()["error"]["code"] == "exams.too_large"
    never = await client.post(
        f"{API}/papers/uploads/presign",
        headers=people["aysel"].headers,
        json={
            "subject_id": str(subject),
            "filename": "x.pdf",
            "mime": "application/pdf",
            "size": 10,
        },
    )
    missing = await save(client, people["aysel"], never.json()["upload_id"], finished)
    assert (missing.status_code, missing.json()["error"]["code"]) == (422, "exams.upload_missing")
    foreign = await save(client, people["outsider"], upload_id, finished)
    assert foreign.status_code == 422
    assert foreign.json()["error"]["code"] == "exams.upload_not_found"
    nobody = await client.post(
        f"{API}/papers/uploads/presign",
        headers=people["outsider"].headers,
        json={
            "subject_id": str(subject),
            "filename": "x.pdf",
            "mime": "application/pdf",
            "size": 10,
        },
    )
    assert nobody.status_code == 404


async def test_an_infected_paper_is_blocked_and_its_object_purged(
    client: AsyncClient, db: AsyncSession, storage: MemoryStorage, people: dict[str, Person]
) -> None:
    subject = await statistika(db)
    semester = await finished_semester(client, people["aysel"], subject)
    upload_id = await upload(client, db, storage, people["aysel"], subject, data=PDF + EICAR)
    saved = await save(client, people["aysel"], upload_id, semester)
    assert saved.status_code == 201
    await scan(db, storage)
    paper = await db.get(PastPaper, uuid.UUID(upload_id))
    assert paper is not None
    await db.refresh(paper)
    assert paper.scan_status is ScanStatus.INFECTED
    assert paper.status is PastPaperStatus.PENDING
    blocked = await client.get(
        f"{API}/papers/{upload_id}/download", headers=people["aysel"].headers
    )
    assert blocked.status_code == 409
    approve = await client.post(
        f"{API}/papers/{upload_id}/review", headers=people["leyla"].headers, json={"approve": True}
    )
    assert approve.json()["error"]["code"] == "exams.paper_not_scanned"
    assert await PaperScanner(db, storage, FakeScanner()).purge() == 1
    assert paper.object_key not in storage.objects
    await db.refresh(paper)
    assert paper.purged_at is not None
    assert await listed(client, people["aysel"], subject) == []


async def test_unsaved_uploads_are_removed_after_a_day(
    client: AsyncClient, db: AsyncSession, storage: MemoryStorage, people: dict[str, Person]
) -> None:
    subject = await statistika(db)
    upload_id = await upload(client, db, storage, people["aysel"], subject)
    paper = await db.get(PastPaper, uuid.UUID(upload_id))
    assert paper is not None
    key = paper.object_key
    scanner = PaperScanner(db, storage, FakeScanner())
    assert await scanner.purge() == 0
    assert await scanner.purge(utc_now() + timedelta(days=2)) == 1
    assert key not in storage.objects
    assert await db.get(PastPaper, uuid.UUID(upload_id)) is None


async def test_reviewers_see_how_many_papers_wait_for_them(
    client: AsyncClient, db: AsyncSession, storage: MemoryStorage, people: dict[str, Person]
) -> None:
    subject = await statistika(db)
    semester = await finished_semester(client, people["aysel"], subject)
    await save(
        client,
        people["aysel"],
        await upload(client, db, storage, people["aysel"], subject),
        semester,
    )
    for who, expected in (("leyla", 1), ("staff", 1), ("aysel", 0)):
        items = (await client.get(f"{API}/papers/subjects", headers=people[who].headers)).json()[
            "items"
        ]
        row = next((i for i in items if i["id"] == str(subject)), None)
        assert row is not None or who == "staff", who
        if row is not None:
            assert row["pending"] == expected, who
    assert (
        await client.get(f"{API}/papers/subjects", headers=people["outsider"].headers)
    ).json() == {"items": []}


async def test_the_uploader_hears_about_an_approval_or_a_rejection_once_per_decision(
    client: AsyncClient, db: AsyncSession, storage: MemoryStorage, people: dict[str, Person]
) -> None:
    subject = await statistika(db)
    semester = await finished_semester(client, people["aysel"], subject)
    first = await save(
        client,
        people["aysel"],
        await upload(client, db, storage, people["aysel"], subject),
        semester,
    )
    await scan(db, storage)
    review = f"{API}/papers/{first.json()['id']}/review"

    async def heard(who: str) -> list[Notification]:
        found = await db.scalars(
            select(Notification)
            .where(
                Notification.user_id == people[who].id, Notification.subject_type == "past_paper"
            )
            .order_by(Notification.id)
            .execution_options(populate_existing=True)
        )
        return list(found)

    assert await heard("aysel") == []
    approved = await client.post(review, headers=people["leyla"].headers, json={"approve": True})
    assert approved.status_code == 200
    [note] = await heard("aysel")
    assert note.kind is NotificationKind.PAST_PAPER_APPROVED
    assert note.category is NotificationCategory.SCHEDULE
    assert note.title == "Yekun imtahan, 2025 payız"
    assert note.link == "/exams/papers"
    # Only the uploader is told: not the reviewer, and not the rest of the subject.
    for other in ("leyla", "rauf", "staff", "outsider"):
        assert await heard(other) == [], other

    # A changed decision is a new event; the same decision repeated later is one too (it has its own time).
    rejected = await client.post(
        review, headers=people["staff"].headers, json={"approve": False, "note": "Sual yoxdur"}
    )
    assert rejected.status_code == 200
    assert [n.kind for n in await heard("aysel")] == [
        NotificationKind.PAST_PAPER_APPROVED,
        NotificationKind.PAST_PAPER_REJECTED,
    ]

    # Delivery time: still decided and still theirs, until the paper is gone.
    paper_id = uuid.UUID(first.json()["id"])
    assert await still_decided(db, paper_id, people["aysel"].id)
    assert not await still_decided(db, paper_id, people["leyla"].id)
    paper = await db.get(PastPaper, paper_id)
    assert paper is not None
    paper.status = PastPaperStatus.PENDING
    await db.commit()
    assert not await still_decided(db, paper_id, people["aysel"].id)


async def test_a_teachers_own_upload_and_an_unreviewed_paper_notify_nobody(
    client: AsyncClient, db: AsyncSession, storage: MemoryStorage, people: dict[str, Person]
) -> None:
    subject = await statistika(db)
    semester = await finished_semester(client, people["leyla"], subject)
    own = await save(
        client,
        people["leyla"],
        await upload(client, db, storage, people["leyla"], subject),
        semester,
    )
    assert own.json()["status"] == "approved"
    pending = await save(
        client,
        people["aysel"],
        await upload(client, db, storage, people["aysel"], subject, filename="Aralıq.pdf"),
        semester,
    )
    assert pending.json()["status"] == "pending"
    count = await db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.subject_type == "past_paper")
    )
    assert count == 0
