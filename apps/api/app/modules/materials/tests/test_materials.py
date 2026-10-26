"""Materials v1: catalogue access, versioned uploads with consent, scan, download, reports (§6.1, §13.2, D-071)."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import Database
from app.core.ratelimit import RateLimit
from app.core.time import utc_now
from app.modules.audit.models import AuditLog
from app.modules.chat.tests.conftest import Person
from app.modules.chat.tests.test_attachments import EICAR, PDF, FakeScanner
from app.modules.materials import service as material_service
from app.modules.materials.models import MaterialVersion
from app.modules.materials.service import MaterialScanner
from app.modules.notifications.models import Notification, NotificationKind
from app.modules.privacy.models import ConsentPurpose, ConsentRecord
from app.workers import main as worker
from tests.support import FakeJobs, MemoryStorage, TokenFactory

API = "/api/v1"
Seed = Callable[..., Awaitable[None]]


async def sign_in(
    client: AsyncClient, tokens: TokenFactory, email: str, roles: list[str], given: str, family: str
) -> Person:
    """An account from the imported registry, linked by e-mail on the first request."""
    token = tokens.issue(
        str(uuid.uuid4()), roles, given_name=given, family_name=family, email=email
    )
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get(f"{API}/me", headers=headers)
    assert response.status_code == 200, response.text
    return Person(uuid.UUID(response.json()["id"]), headers, f"{given} {family}")


class Statistika:
    """IQT-2102 from the sample data: Leyla Həsənova teaches it, Aysel Məmmədova takes it in 2026 Payız."""

    def __init__(self, subject_id: str, semesters: dict[str, str]) -> None:
        self.subject_id = subject_id
        self.semesters = semesters

    @property
    def fall_2026(self) -> str:
        return self.semesters["2026 Payız"]


@pytest.fixture
async def people(client: AsyncClient, tokens: TokenFactory, seed: Seed) -> dict[str, Person]:
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
    }


@pytest.fixture
async def statistika(client: AsyncClient, people: dict[str, Person]) -> Statistika:
    subjects = await client.get(f"{API}/materials/subjects", headers=people["leyla"].headers)
    assert subjects.status_code == 200, subjects.text
    subject = next(s for s in subjects.json()["items"] if s["code"] == "IQT-2102")
    catalog = await client.get(
        f"{API}/subjects/{subject['id']}/materials", headers=people["leyla"].headers
    )
    return Statistika(subject["id"], {s["label"]: s["id"] for s in catalog.json()["semesters"]})


async def presign(
    client: AsyncClient,
    person: Person,
    subject: Statistika,
    semester_id: str | None = None,
    filename: str = "Mühazirə 1 - Təsviri statistika.pdf",
    mime: str = "application/pdf",
    size: int = len(PDF),
) -> Any:
    return await client.post(
        f"{API}/materials/uploads/presign",
        headers=person.headers,
        json={
            "subject_id": subject.subject_id,
            "semester_id": semester_id or subject.fall_2026,
            "filename": filename,
            "mime": mime,
            "size": size,
        },
    )


async def upload(
    client: AsyncClient,
    storage: MemoryStorage,
    person: Person,
    subject: Statistika,
    data: bytes = PDF,
) -> str:
    response = await presign(client, person, subject, size=len(data))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["headers"] == {"Content-Type": "application/pdf"}
    storage.objects[body["object_key"]] = (data, "application/pdf")
    return str(body["upload_id"])


async def create(client: AsyncClient, person: Person, upload_id: str, **fields: Any) -> Any:
    return await client.post(
        f"{API}/materials",
        headers=person.headers,
        json={
            "upload_id": upload_id,
            "type": "lecture",
            "title": "Təsviri statistika",
            "description": "Orta, median, moda.",
            "copyright_confirmed": True,
            **fields,
        },
    )


async def scan(db: AsyncSession, storage: MemoryStorage) -> None:
    await MaterialScanner(db, storage, FakeScanner()).scan_pending()


async def test_who_reads_and_who_uploads(
    client: AsyncClient, people: dict[str, Person], statistika: Statistika
) -> None:
    leyla, aysel, rauf = people["leyla"], people["aysel"], people["rauf"]
    assert set(statistika.semesters) == {"2025 Payız", "2026 Payız"}

    teacher = await client.get(
        f"{API}/subjects/{statistika.subject_id}/materials", headers=leyla.headers
    )
    assert teacher.json()["can_upload"] is True
    assert teacher.json()["can_manage"] is False
    assert all(s["can_upload"] for s in teacher.json()["semesters"])
    assert teacher.json()["materials"] == []

    student = await client.get(
        f"{API}/subjects/{statistika.subject_id}/materials", headers=aysel.headers
    )
    assert student.status_code == 200
    assert student.json()["can_upload"] is False
    assert "IQT-2102" in {
        s["code"]
        for s in (await client.get(f"{API}/materials/subjects", headers=aysel.headers)).json()[
            "items"
        ]
    }
    denied = await presign(client, aysel, statistika)
    assert (denied.status_code, denied.json()["error"]["code"]) == (
        403,
        "materials.upload_not_allowed",
    )

    # A teacher of other subjects neither sees nor learns about this one.
    other = await client.get(
        f"{API}/subjects/{statistika.subject_id}/materials", headers=rauf.headers
    )
    assert (other.status_code, other.json()["error"]["code"]) == (
        404,
        "materials.subject_not_found",
    )
    assert "IQT-2102" not in {
        s["code"]
        for s in (await client.get(f"{API}/materials/subjects", headers=rauf.headers)).json()[
            "items"
        ]
    }
    unknown = await client.get(f"{API}/subjects/{uuid.uuid4()}/materials", headers=aysel.headers)
    assert unknown.status_code == 404


async def test_upload_checks_type_size_and_storage(
    client: AsyncClient,
    people: dict[str, Person],
    statistika: Statistika,
    storage: MemoryStorage,
) -> None:
    leyla = people["leyla"]
    script = await presign(
        client, leyla, statistika, filename="setup.exe", mime="application/x-msdownload"
    )
    assert (script.status_code, script.json()["error"]["code"]) == (
        422,
        "materials.type_not_allowed",
    )
    big = await presign(client, leyla, statistika, size=50 * 1024 * 1024 + 1)
    assert big.json()["error"]["code"] == "materials.too_large"
    storage.available = False
    down = await presign(client, leyla, statistika)
    assert (down.status_code, down.json()["error"]["code"]) == (
        503,
        "materials.storage_unavailable",
    )
    storage.available = True

    reserved = await presign(client, leyla, statistika)
    upload_id = reserved.json()["upload_id"]
    missing = await create(client, leyla, upload_id)
    assert missing.json()["error"]["code"] == "materials.upload_missing"
    storage.objects[reserved.json()["object_key"]] = (PDF + b"extra", "application/pdf")
    mismatch = await create(client, leyla, upload_id)
    assert mismatch.json()["error"]["code"] == "materials.upload_size_mismatch"
    storage.objects[reserved.json()["object_key"]] = (PDF, "application/pdf")
    no_consent = await create(client, leyla, upload_id, copyright_confirmed=False)
    assert no_consent.json()["error"]["code"] == "materials.copyright_required"
    blank = await create(client, leyla, upload_id, title="   ")
    assert blank.json()["error"]["code"] == "materials.title_required"
    stolen = await create(client, people["aysel"], upload_id)
    assert stolen.json()["error"]["code"] == "materials.upload_not_found"
    assert (await create(client, leyla, upload_id)).status_code == 201
    # An upload joins one material only.
    again = await create(client, leyla, upload_id)
    assert again.json()["error"]["code"] == "materials.upload_not_found"


async def test_versions_scan_download_and_purge(
    client: AsyncClient,
    db: AsyncSession,
    people: dict[str, Person],
    statistika: Statistika,
    storage: MemoryStorage,
    jobs: FakeJobs,
) -> None:
    leyla, aysel = people["leyla"], people["aysel"]
    created = await create(client, leyla, await upload(client, storage, leyla, statistika))
    assert created.status_code == 201, created.text
    material = created.json()
    assert jobs.scans == 1
    assert (material["current"], material["scanning"], material["can_edit"]) == (None, True, True)
    assert [v["status"] for v in material["versions"]] == ["pending"]
    version = await db.get(MaterialVersion, uuid.UUID(material["versions"][0]["id"]))
    assert version is not None
    assert version.copyright_confirmed_at is not None
    assert version.copyright_text_version == "2026-10-26"

    # Students do not see a file before it is checked, nor that a check is running.
    unchecked = (
        await client.get(f"{API}/materials/{material['id']}", headers=aysel.headers)
    ).json()
    assert (unchecked["versions"], unchecked["current"], unchecked["scanning"]) == ([], None, False)
    early = await client.get(
        f"{API}/materials/versions/{material['versions'][0]['id']}/download", headers=aysel.headers
    )
    assert (early.status_code, early.json()["error"]["code"]) == (409, "materials.not_available")

    await scan(db, storage)
    checked = (await client.get(f"{API}/materials/{material['id']}", headers=aysel.headers)).json()
    assert checked["current"]["version"] == 1
    assert checked["subject_name"] == "Statistika"
    assert checked["current"]["previewable"] is True
    assert checked["current"]["uploaded_by"]["display_name"] == "Leyla Həsənova"
    assert checked["can_edit"] is False
    preview = await client.get(
        f"{API}/materials/versions/{checked['current']['id']}/download",
        headers=aysel.headers,
        params={"inline": "true"},
    )
    assert preview.status_code == 200, preview.text
    assert storage.last_download["disposition"].startswith("inline")
    await client.get(
        f"{API}/materials/versions/{checked['current']['id']}/download", headers=aysel.headers
    )
    assert storage.last_download["disposition"].startswith("attachment")

    # A new upload is the next version; an infected one never replaces the clean one.
    infected_id = await upload(client, storage, leyla, statistika, PDF + EICAR)
    student_version = await client.post(
        f"{API}/materials/{material['id']}/versions",
        headers=aysel.headers,
        json={"upload_id": infected_id, "copyright_confirmed": True},
    )
    assert student_version.status_code == 403
    no_consent = await client.post(
        f"{API}/materials/{material['id']}/versions",
        headers=leyla.headers,
        json={"upload_id": infected_id, "copyright_confirmed": False},
    )
    assert no_consent.json()["error"]["code"] == "materials.copyright_required"
    second = await client.post(
        f"{API}/materials/{material['id']}/versions",
        headers=leyla.headers,
        json={"upload_id": infected_id, "note": "Düzəliş: 3-cü slayd", "copyright_confirmed": True},
    )
    assert second.status_code == 201, second.text
    assert [v["version"] for v in second.json()["versions"]] == [2, 1]
    assert jobs.scans == 2
    await scan(db, storage)
    teacher_view = (
        await client.get(f"{API}/materials/{material['id']}", headers=leyla.headers)
    ).json()
    assert [v["status"] for v in teacher_view["versions"]] == ["infected", "clean"]
    assert teacher_view["versions"][0]["note"] == "Düzəliş: 3-cü slayd"
    student_view = (
        await client.get(f"{API}/materials/{material['id']}", headers=aysel.headers)
    ).json()
    assert [v["version"] for v in student_view["versions"]] == [1]
    assert (student_view["current"]["version"], student_view["version_count"]) == (1, 1)

    infected = await db.get(MaterialVersion, uuid.UUID(teacher_view["versions"][0]["id"]))
    assert infected is not None
    infected_key = infected.object_key
    abandoned = await presign(client, leyla, statistika)
    storage.objects[abandoned.json()["object_key"]] = (PDF, "application/pdf")
    scanner = MaterialScanner(db, storage, FakeScanner())
    assert await scanner.purge() == 1
    assert infected_key not in storage.objects
    await db.refresh(infected)
    assert infected.purged_at is not None
    # Uploads never saved into a material go after a day, row and object.
    assert await scanner.purge(utc_now() + timedelta(hours=25)) == 1
    assert abandoned.json()["object_key"] not in storage.objects
    assert await db.get(MaterialVersion, uuid.UUID(abandoned.json()["upload_id"])) is None


async def test_scan_waits_out_outages_and_rejects_wrong_content(
    client: AsyncClient,
    db: AsyncSession,
    people: dict[str, Person],
    statistika: Statistika,
    storage: MemoryStorage,
) -> None:
    leyla = people["leyla"]
    material = (
        await create(client, leyla, await upload(client, storage, leyla, statistika))
    ).json()
    scanner = FakeScanner()
    scanner.available = False
    report = await MaterialScanner(db, storage, scanner).scan_pending()
    assert (report.clean, report.waiting) == (0, 1)
    version = await db.get(MaterialVersion, uuid.UUID(material["versions"][0]["id"]))
    assert version is not None
    await db.refresh(version)
    assert version.scan_attempts == 1
    assert version.scan_after > utc_now()

    # Not a PDF at all, though named and declared as one.
    fake = await upload(client, storage, leyla, statistika, b"MZ\x90\x00not a pdf")
    created = (await create(client, leyla, fake, title="Saxta fayl")).json()
    storage.available = False
    assert (await MaterialScanner(db, storage, FakeScanner()).scan_pending()).waiting == 1
    storage.available = True
    fake_version = await db.get(MaterialVersion, uuid.UUID(created["versions"][0]["id"]))
    assert fake_version is not None
    fake_version.scan_after = utc_now()
    await db.commit()
    assert (await MaterialScanner(db, storage, FakeScanner()).scan_pending()).rejected == 1
    await db.refresh(fake_version)
    assert fake_version.scan_status.value == "failed"


async def test_reports_and_hiding(
    client: AsyncClient,
    db: AsyncSession,
    people: dict[str, Person],
    statistika: Statistika,
    storage: MemoryStorage,
    staff_headers: dict[str, str],
) -> None:
    leyla, aysel = people["leyla"], people["aysel"]
    material = (
        await create(client, leyla, await upload(client, storage, leyla, statistika))
    ).json()
    await scan(db, storage)
    url = f"{API}/materials/{material['id']}"

    first = await client.post(
        f"{url}/reports", headers=aysel.headers, json={"reason": "copyright", "note": " Kitabdan "}
    )
    assert first.status_code == 201, first.text
    again = await client.post(f"{url}/reports", headers=aysel.headers, json={"reason": "other"})
    assert (again.status_code, again.json()["duplicate"]) == (200, True)
    unseen = await client.post(
        f"{url}/reports", headers=people["rauf"].headers, json={"reason": "other"}
    )
    assert unseen.status_code == 404

    assert (
        await client.get(f"{API}/moderation/material-reports", headers=aysel.headers)
    ).status_code == 403
    listed = (await client.get(f"{API}/moderation/material-reports", headers=staff_headers)).json()
    assert listed["total"] == 1
    item = listed["items"][0]
    assert (item["material_title"], item["subject_name"], item["note"]) == (
        "Təsviri statistika",
        "Statistika",
        "Kitabdan",
    )
    assert item["reporter"]["display_name"] == "Aysel Məmmədova"
    assert "email" not in str(listed)

    handled = await client.patch(
        f"{API}/moderation/material-reports/{item['id']}",
        headers=staff_headers,
        json={"status": "actioned"},
    )
    assert handled.status_code == 204
    reopened = await client.patch(
        f"{API}/moderation/material-reports/{item['id']}",
        headers=staff_headers,
        json={"status": "open"},
    )
    assert reopened.status_code == 204
    same = await client.patch(
        f"{API}/moderation/material-reports/{item['id']}",
        headers=staff_headers,
        json={"status": "open"},
    )
    assert same.status_code == 204
    open_only = (
        await client.get(
            f"{API}/moderation/material-reports", headers=staff_headers, params={"status": "open"}
        )
    ).json()
    assert open_only["items"][0]["handled_by"] is None
    missing = await client.patch(
        f"{API}/moderation/material-reports/{uuid.uuid4()}",
        headers=staff_headers,
        json={"status": "dismissed"},
    )
    assert missing.status_code == 404

    teacher_hide = await client.patch(
        f"{url}/visibility", headers=leyla.headers, json={"hidden": True}
    )
    assert teacher_hide.status_code == 403
    assert (
        await client.patch(f"{url}/visibility", headers=staff_headers, json={"hidden": True})
    ).status_code == 204
    catalog_url = f"{API}/subjects/{statistika.subject_id}/materials"
    assert (await client.get(catalog_url, headers=aysel.headers)).json()["materials"] == []
    assert (await client.get(url, headers=aysel.headers)).status_code == 404
    staff_catalog = (await client.get(catalog_url, headers=staff_headers)).json()
    assert staff_catalog["can_manage"] is True
    assert [m["hidden"] for m in staff_catalog["materials"]] == [True]
    # Staff see the subject in their list because it has materials.
    staff_subjects = (await client.get(f"{API}/materials/subjects", headers=staff_headers)).json()
    assert [s["code"] for s in staff_subjects["items"]] == ["IQT-2102"]
    await client.patch(f"{url}/visibility", headers=staff_headers, json={"hidden": True})
    await client.patch(f"{url}/visibility", headers=staff_headers, json={"hidden": False})
    assert len((await client.get(catalog_url, headers=aysel.headers)).json()["materials"]) == 1
    missing_material = await client.patch(
        f"{API}/materials/{uuid.uuid4()}/visibility", headers=staff_headers, json={"hidden": True}
    )
    assert missing_material.status_code == 404

    actions = [entry.action for entry in await db.scalars(select(AuditLog).order_by(AuditLog.id))]
    assert [a for a in actions if a.startswith("material.")] == [
        "material.created",
        "material.reported",
        "material.report_handled",
        "material.report_handled",
        "material.hidden",
        "material.shown",
    ]


async def test_semester_filter_and_staff_upload(
    client: AsyncClient,
    db: AsyncSession,
    people: dict[str, Person],
    statistika: Statistika,
    storage: MemoryStorage,
    staff_headers: dict[str, str],
) -> None:
    leyla = people["leyla"]
    await create(client, leyla, await upload(client, storage, leyla, statistika))
    older = await presign(client, leyla, statistika, semester_id=statistika.semesters["2025 Payız"])
    storage.objects[older.json()["object_key"]] = (PDF, "application/pdf")
    await create(client, leyla, older.json()["upload_id"], type="syllabus", title="Sillabus 2025")
    await scan(db, storage)
    catalog_url = f"{API}/subjects/{statistika.subject_id}/materials"
    fall = (
        await client.get(
            catalog_url,
            headers=people["aysel"].headers,
            params={"semester_id": statistika.fall_2026},
        )
    ).json()
    assert [m["title"] for m in fall["materials"]] == ["Təsviri statistika"]
    everything = (await client.get(catalog_url, headers=people["aysel"].headers)).json()
    assert {m["semester"]["label"] for m in everything["materials"]} == {"2026 Payız", "2025 Payız"}

    # Staff upload for any subject and semester (materials.manage).
    staff = Person(uuid.uuid4(), staff_headers, "Elvin Quliyev")
    staff_upload = await presign(client, staff, statistika)
    assert staff_upload.status_code == 200, staff_upload.text


async def test_worker_jobs_include_materials(
    client: AsyncClient,
    app: Any,
    settings: Settings,
    people: dict[str, Person],
    statistika: Statistika,
    storage: MemoryStorage,
) -> None:
    leyla = people["leyla"]
    await create(client, leyla, await upload(client, storage, leyla, statistika))
    await create(client, leyla, await upload(client, storage, leyla, statistika, PDF + EICAR))
    database = Database(str(settings.database_url))
    try:
        ctx: dict[str, Any] = {
            "database": database,
            "cache_redis": app.state.redis,
            "storage": storage,
            "scanner": FakeScanner(),
        }
        assert await worker.scan_attachments(ctx) == 2
        assert await worker.purge_attachments(ctx) == 1
    finally:
        await database.dispose()


async def test_consent_audit_rejection_notice_and_current_version(
    client: AsyncClient,
    db: AsyncSession,
    people: dict[str, Person],
    statistika: Statistika,
    storage: MemoryStorage,
) -> None:
    leyla, aysel, rauf = people["leyla"], people["aysel"], people["rauf"]
    material = (
        await create(client, leyla, await upload(client, storage, leyla, statistika))
    ).json()
    url = f"{API}/materials/{material['id']}/versions"
    infected = await client.post(
        url,
        headers=leyla.headers,
        json={
            "upload_id": await upload(client, storage, leyla, statistika, PDF + EICAR),
            "copyright_confirmed": True,
        },
    )
    assert infected.status_code == 201, infected.text
    await scan(db, storage)

    # Each version is a consent in the uploader's history, with the wording that was shown (§6.1).
    consents = list(
        await db.scalars(
            select(ConsentRecord).where(
                ConsentRecord.user_id == leyla.id,
                ConsentRecord.purpose == ConsentPurpose.MATERIAL_COPYRIGHT,
            )
        )
    )
    assert [(c.granted, c.policy_version) for c in consents] == [(True, "2026-10-26")] * 2
    actions = list(
        await db.scalars(
            select(AuditLog.action)
            .where(AuditLog.target_id == material["id"])
            .order_by(AuditLog.id)
        )
    )
    assert actions == ["material.created", "material.version_added"]

    notices = list(
        await db.scalars(
            select(Notification).where(
                Notification.kind == NotificationKind.MATERIAL_VERSION_REJECTED
            )
        )
    )
    assert [(n.user_id, n.link) for n in notices] == [
        (leyla.id, f"/materials/{statistika.subject_id}/{material['id']}")
    ]
    assert notices[0].title == "Mühazirə 1 - Təsviri statistika.pdf"

    # A clean third version replaces the first as current for students; the infected one stays out of sight.
    third = await client.post(
        url,
        headers=leyla.headers,
        json={
            "upload_id": await upload(client, storage, leyla, statistika),
            "copyright_confirmed": True,
        },
    )
    assert third.status_code == 201, third.text
    await scan(db, storage)
    student = (await client.get(f"{API}/materials/{material['id']}", headers=aysel.headers)).json()
    assert student["current"]["version"] == 3
    assert [v["version"] for v in student["versions"]] == [3, 1]

    # Outsiders and guessed ids get the same 404, never a hint that the file exists (§14).
    current_id = student["current"]["id"]
    for person, version_id in ((rauf, current_id), (aysel, str(uuid.uuid4()))):
        guessed = await client.get(
            f"{API}/materials/versions/{version_id}/download", headers=person.headers
        )
        assert guessed.status_code == 404, guessed.text
    rejected_id = infected.json()["versions"][0]["id"]
    hidden = await client.get(
        f"{API}/materials/versions/{rejected_id}/download", headers=aysel.headers
    )
    assert hidden.status_code in {404, 409}
    assert (
        await client.get(f"{API}/materials/{material['id']}", headers=rauf.headers)
    ).status_code == 404


async def test_uploads_and_reports_are_rate_limited(
    client: AsyncClient,
    db: AsyncSession,
    people: dict[str, Person],
    statistika: Statistika,
    storage: MemoryStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    leyla, aysel = people["leyla"], people["aysel"]
    first = await create(client, leyla, await upload(client, storage, leyla, statistika))
    second = await create(client, leyla, await upload(client, storage, leyla, statistika))
    await scan(db, storage)

    monkeypatch.setattr(material_service, "UPLOAD_LIMIT", RateLimit(f"t{uuid.uuid4()}", 1, 60))
    assert (await presign(client, leyla, statistika)).status_code == 200
    limited = await presign(client, leyla, statistika)
    assert (limited.status_code, limited.json()["error"]["code"]) == (429, "request.rate_limited")

    monkeypatch.setattr(material_service, "REPORT_LIMIT", RateLimit(f"t{uuid.uuid4()}", 1, 60))
    statuses = [
        (
            await client.post(
                f"{API}/materials/{material.json()['id']}/reports",
                headers=aysel.headers,
                json={"reason": "wrong_content"},
            )
        ).status_code
        for material in (first, second)
    ]
    assert statuses == [201, 429]


async def test_concurrent_versions_get_distinct_numbers(
    client: AsyncClient,
    people: dict[str, Person],
    statistika: Statistika,
    storage: MemoryStorage,
) -> None:
    leyla = people["leyla"]
    material = (
        await create(client, leyla, await upload(client, storage, leyla, statistika))
    ).json()
    uploads = [await upload(client, storage, leyla, statistika) for _ in range(3)]
    responses = await asyncio.gather(
        *(
            client.post(
                f"{API}/materials/{material['id']}/versions",
                headers=leyla.headers,
                json={"upload_id": upload_id, "copyright_confirmed": True},
            )
            for upload_id in uploads
        )
    )
    assert [r.status_code for r in responses] == [201] * 3
    detail = (await client.get(f"{API}/materials/{material['id']}", headers=leyla.headers)).json()
    assert [v["version"] for v in detail["versions"]] == [4, 3, 2, 1]
