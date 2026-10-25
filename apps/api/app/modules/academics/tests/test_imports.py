import asyncio
import io
import uuid
from collections.abc import Awaitable, Callable
from datetime import timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient
from openpyxl import Workbook
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ratelimit import RateLimit
from app.modules.academics import router as academics_router
from app.modules.academics.models import (
    AcademicGroup,
    AcademicImport,
    CourseOffering,
    CourseOfferingGroup,
    CourseOfferingTeacher,
    Enrollment,
    EnrollmentStatus,
    Faculty,
    ImportKind,
    Subject,
)
from app.modules.academics.seed import seed as run_seed
from app.modules.audit.models import AuditLog
from app.modules.users.models import PersonType, User, UserStatus
from tests.support import TokenFactory

from .conftest import SEED_DIR, Upload

Seed = Callable[..., Awaitable[None]]


def issues(body: dict[str, object]) -> list[tuple[object, object, object]]:
    errors = body["errors"]
    assert isinstance(errors, list)
    return [(e["row"], e["column"], e["code"]) for e in errors]


async def payload_is_sql_null(db: AsyncSession, import_id: uuid.UUID) -> bool:
    """Raw SQL, because the ORM reads JSON null and SQL NULL both as None."""
    query = text("SELECT payload IS NULL FROM academic_imports WHERE id = :id")
    return bool(await db.scalar(query, {"id": import_id}))


async def test_sample_data_imports_and_reimport_is_a_no_op(
    seed: Seed, upload: Upload, db: AsyncSession
) -> None:
    await seed()

    assert await db.scalar(select(func.count()).select_from(Enrollment)) == 617
    audit = await db.scalars(select(AuditLog.details).where(AuditLog.action == "import.applied"))
    registry = list(ImportKind)[: list(ImportKind).index(ImportKind.ENROLLMENTS) + 1]
    assert {entry["kind"] for entry in audit} == {kind.value for kind in registry}

    again = await upload(ImportKind.ENROLLMENTS, (SEED_DIR / "enrollments.csv").read_bytes())
    assert again["status"] == "ready"
    assert again["summary"] == {"created": 0, "updated": 0, "unchanged": 617, "removed": 0}
    assert again["previously_applied_at"] is not None


async def test_importing_requires_the_permission(client: AsyncClient, tokens: TokenFactory) -> None:
    headers = {"Authorization": f"Bearer {tokens.issue(str(uuid.uuid4()), ['student'])}"}
    listing = await client.get("/api/v1/admin/imports", headers=headers)
    created = await client.post(
        "/api/v1/admin/imports",
        headers=headers,
        data={"kind": "faculties"},
        files={"file": ("f.csv", b"code,name_az\nMEM,M\n", "text/csv")},
    )
    assert listing.status_code == created.status_code == 403
    assert created.json()["error"]["details"] == {"permission": "academics.import"}


async def test_header_problems_stop_validation(upload: Upload) -> None:
    body = await upload("faculties", "kod,name_az,name_az\nMEM,Memarlıq,x\n")
    assert body["status"] == "invalid"
    assert issues(body) == [
        (None, "code", "missing_column"),
        (None, "kod", "unknown_column"),
        (None, "name_az", "duplicate_column"),
    ]
    assert body["summary"] == {"created": 0, "updated": 0, "unchanged": 0, "removed": 0}


async def test_row_errors_are_reported_together(upload: Upload, db: AsyncSession) -> None:
    await upload("faculties", "code,name_az\nTIQ,Tikinti iqtisadiyyatı fakültəsi\n", apply=True)

    body = await upload(
        "subjects",
        "code,faculty_code,name_az,credits\n"
        "IQT-2101,TIQ,Mikroiqtisadiyyat,10\n"
        "IQT-2101,TIQ,Mikroiqtisadiyyat,10\n"
        "IQT 2102,XYZ,,ten\n"
        "IQT-2201,XYZ,Makroiqtisadiyyat,10\n",
    )

    assert body["status"] == "invalid"
    assert issues(body) == [
        (3, "code", "duplicate_in_file"),
        (4, "code", "invalid_format"),
        (4, "name_az", "required"),
        (4, "credits", "invalid_number"),
        (5, "faculty_code", "unknown_reference"),
    ]
    assert body["error_count"] == 5
    # Nothing is written by a preview, valid rows included.
    assert await db.scalar(select(func.count()).select_from(Subject)) == 0


async def test_invalid_imports_cannot_be_applied(
    client: AsyncClient, upload: Upload, staff_headers: dict[str, str]
) -> None:
    body = await upload("faculties", "code,name_az\nMEM,\n")
    response = await client.post(f"/api/v1/admin/imports/{body['id']}/apply", headers=staff_headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "import.not_applicable"


async def test_apply_is_idempotent_and_audited_once(
    client: AsyncClient, upload: Upload, staff_headers: dict[str, str], db: AsyncSession
) -> None:
    body = await upload("faculties", "code,name_az,name_en\nMEM,Memarlıq fakültəsi,Architecture\n")
    url = f"/api/v1/admin/imports/{body['id']}/apply"

    responses = await asyncio.gather(*(client.post(url, headers=staff_headers) for _ in range(3)))

    assert {r.status_code for r in responses} == {200}
    assert {r.json()["status"] for r in responses} == {"applied"}
    assert {r.json()["applied_by"]["display_name"] for r in responses} == {"Elvin Quliyev"}
    assert await db.scalar(select(func.count()).select_from(Faculty)) == 1
    assert (
        await db.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.action == "import.applied")
        )
        == 1
    )
    record = await db.get(AcademicImport, uuid.UUID(body["id"]))
    assert record is not None
    assert record.payload is None
    assert await payload_is_sql_null(db, record.id)


async def test_data_changed_since_the_preview_fails_the_apply(
    client: AsyncClient, upload: Upload, staff_headers: dict[str, str], db: AsyncSession
) -> None:
    first = await upload(
        "teachers",
        "university_id,family_name,given_name,email\nT-10412,Ağayeva,Şəhla,shahla.agayeva@smartazmiu.test\n",
    )
    # Meanwhile another file gives the same e-mail to a different employee number.
    await upload(
        "teachers",
        "university_id,family_name,given_name,email\nT-20001,Ağayeva,Şəhla,shahla.agayeva@smartazmiu.test\n",
        apply=True,
    )

    response = await client.post(
        f"/api/v1/admin/imports/{first['id']}/apply", headers=staff_headers
    )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert issues(response.json()) == [(2, "email", "email_conflict")]
    assert await db.scalar(select(func.count()).select_from(User)) == 2  # staff member + T-20001


async def test_previews_expire_and_their_cells_are_purged(
    client: AsyncClient, upload: Upload, staff_headers: dict[str, str], db: AsyncSession
) -> None:
    body = await upload("faculties", "code,name_az\nMEM,Memarlıq fakültəsi\n")
    import_id = uuid.UUID(body["id"])
    await db.execute(
        update(AcademicImport)
        .where(AcademicImport.id == import_id)
        .values(created_at=func.now() - timedelta(hours=25))
    )
    await db.commit()

    response = await client.post(f"/api/v1/admin/imports/{import_id}/apply", headers=staff_headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "import.expired"

    await upload("faculties", "code,name_az\nINS,İnşaat fakültəsi\n")
    record = await db.get(AcademicImport, import_id, populate_existing=True)
    assert record is not None
    assert record.payload is None
    assert await payload_is_sql_null(db, record.id)


async def test_unknown_import_is_not_found(
    client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    response = await client.get(f"/api/v1/admin/imports/{uuid.uuid4()}", headers=staff_headers)
    assert response.status_code == 404
    response = await client.post(
        f"/api/v1/admin/imports/{uuid.uuid4()}/apply", headers=staff_headers
    )
    assert response.status_code == 404


async def test_people_rules(seed: Seed, upload: Upload, db: AsyncSession) -> None:
    await seed(until=ImportKind.STUDENTS)
    header = "university_id,family_name,given_name,email,group_code,status\n"

    body = await upload(
        "students",
        header
        # Same e-mail as Aysel Məmmədova, different student number: rejected, never merged (§13.1).
        + "25765299,Məmmədova,Aysel,aysel.mammadova@smartazmiu.test,765a2,active\n"
        # A teacher's employee number used for a student.
        + "T-10412,Ağayeva,Şəhla,shahla.agayeva@smartazmiu.test,765a2,active\n"
        + "25765298,Məmm?dova,Aysel,new.student@smartazmiu.test,765a9,active\n"
        + "25765297,Orucov,Elçin,new.student@smartazmiu.test,765a2,active\n",
    )

    assert issues(body) == [
        (2, "email", "email_conflict"),
        (3, "university_id", "person_type_mismatch"),
        (4, "family_name", "invalid_characters"),
    ]


async def test_group_transfer_and_academic_leave(
    seed: Seed, upload: Upload, db: AsyncSession
) -> None:
    await seed(until=ImportKind.STUDENTS)
    body = await upload(
        "students",
        "university_id,family_name,given_name,email,group_code,status\n"
        "25765201,Məmmədova,Aysel,aysel.mammadova@smartazmiu.test,765a1,active\n"
        "25765202,Əliyev,Ramin,ramin.aliyev@smartazmiu.test,765a2,inactive\n"
        "25765203,Hüseynov,Orxan,orxan.huseynov@smartazmiu.test,765a2,active\n",
        apply=True,
    )
    assert body["summary"] == {"created": 0, "updated": 2, "unchanged": 1, "removed": 0}

    aysel = await db.scalar(select(User).where(User.university_id == "25765201"))
    ramin = await db.scalar(select(User).where(User.university_id == "25765202"))
    group = await db.scalar(select(AcademicGroup).where(AcademicGroup.code == "765a1"))
    assert aysel is not None
    assert ramin is not None
    assert group is not None
    assert aysel.academic_group_id == group.id
    assert ramin.status is UserStatus.INACTIVE


async def test_someone_who_signed_in_first_gets_their_registry_record(
    client: AsyncClient, tokens: TokenFactory, seed: Seed, upload: Upload, db: AsyncSession
) -> None:
    subject = str(uuid.uuid4())
    token = tokens.issue(
        subject,
        ["student"],
        given_name="Tərlan",
        family_name="Agayev",
        email="tarlan.agayev@smartazmiu.test",
    )
    await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})

    await seed(until=ImportKind.STUDENTS)

    user = await db.scalar(select(User).where(User.idp_subject == subject))
    assert user is not None
    assert (user.university_id, user.person_type, user.display_name) == (
        "24764101",
        PersonType.STUDENT,
        "Tərlan Ağayev",
    )
    assert user.search_key == "terlan agayev tarlan.agayev@smartazmiu.test 24764101"


async def test_offerings_replace_groups_and_teachers(
    seed: Seed, upload: Upload, db: AsyncSession
) -> None:
    await seed(until=ImportKind.OFFERINGS)
    header = "subject_code,year,term,code,group_codes,teacher_ids\n"

    # The seminar teacher leaves; a third group joins the Mülki müdafiə lecture.
    body = await upload(
        "offerings",
        header
        + "IQT-2101,2026,payiz,,765a2,T-10412\n"
        + "HFT-2101,2026,Payız,765a1+765a2,765a1;765a2;764a1,T-10502\n"
        + "IQT-2102,2026,Payız,,765a2,T-10457\n",
        apply=True,
    )
    assert body["summary"] == {"created": 0, "updated": 2, "unchanged": 1, "removed": 0}

    micro = await db.scalar(
        select(CourseOffering)
        .join(Subject)
        .where(Subject.code == "IQT-2101", CourseOffering.code == "765a2")
    )
    assert micro is not None
    teachers = await db.scalars(
        select(User.university_id)
        .join(CourseOfferingTeacher, CourseOfferingTeacher.teacher_id == User.id)
        .where(CourseOfferingTeacher.course_offering_id == micro.id)
    )
    assert list(teachers) == ["T-10412"]
    joint = await db.scalar(
        select(CourseOffering)
        .where(CourseOffering.code == "765a1+765a2")
        .join(Subject)
        .where(Subject.code == "HFT-2101")
    )
    assert joint is not None
    groups = await db.scalars(
        select(AcademicGroup.code)
        .join(CourseOfferingGroup, CourseOfferingGroup.academic_group_id == AcademicGroup.id)
        .where(CourseOfferingGroup.course_offering_id == joint.id)
        .order_by(AcademicGroup.code)
    )
    assert list(groups) == ["764a1", "765a1", "765a2"]


async def test_offering_references_are_checked(seed: Seed, upload: Upload) -> None:
    await seed(until=ImportKind.GROUPS)
    body = await upload(
        "offerings",
        "subject_code,year,term,group_codes,teacher_ids\n"
        "XXX-0001,2026,Payız,765a2,T-10412\n"
        "IQT-2101,2031,Payız,765a2,T-10412\n"
        "IQT-2101,2026,Payız,765a9,T-10412\n"
        "IQT-2101,2026,Payız,765a2,T-99999\n"
        "IQT-2102,2026,Payız,765a2,T-10457;T-10412\n",
    )
    assert issues(body) == [
        (2, "subject_code", "unknown_reference"),
        (3, "year", "unknown_reference"),
        (4, "group_codes", "unknown_reference"),
        (5, "teacher_ids", "unknown_reference"),
    ]


async def test_curator_and_offering_teacher_must_be_teachers(seed: Seed, upload: Upload) -> None:
    await seed(until=ImportKind.STUDENTS)
    groups = await upload(
        "groups",
        "code,specialty_code,admission_year,language,curator_id\n"
        "766a1,6004004,2026,az,25765201\n"
        "766a2,6004004,2026,az,T-00000\n"
        "766a3,9999999,2026,az,\n",
    )
    assert issues(groups) == [
        (2, "curator_id", "not_a_teacher"),
        (3, "curator_id", "unknown_reference"),
        (4, "specialty_code", "unknown_reference"),
    ]
    offerings = await upload(
        "offerings",
        "subject_code,year,term,group_codes,teacher_ids\nIQT-2101,2026,Payız,765a2,25765201\n",
    )
    assert issues(offerings) == [(2, "teacher_ids", "not_a_teacher")]


async def test_enrollment_rules(seed: Seed, upload: Upload) -> None:
    await seed(until=ImportKind.OFFERINGS)
    header = "student_id,subject_code,year,term,offering_code,status,passed,grade\n"
    body = await upload(
        "enrollments",
        header
        + "25765201,IQT-2101,2026,Payız,,completed,,\n"
        + "25765201,IQT-2102,2026,Payız,,active,true,\n"
        + "25765201,IQT-2102,2026,Payız,,dropped,,70\n"
        + "T-10412,IQT-2101,2026,Payız,,active,,\n"
        + "25765201,SOS-2103,2026,Payız,,active,,\n"
        + "25765201,SOS-2103,2026,Payız,765a1+765a2,active,,\n"
        + "25765201,IQT-2101,2026,Payız,764a1,active,,\n"
        + "99999999,IQT-2101,2026,Payız,,active,,\n"
        + "25765201,XXX-0001,2026,Payız,,active,,\n"
        + "25765201,IQT-2101,2031,Payız,,active,,\n",
    )
    assert issues(body) == [
        (2, "passed", "result_required"),
        (3, "passed", "result_not_allowed"),
        (4, "grade", "result_not_allowed"),
        (5, "student_id", "not_a_student"),
        (7, "student_id", "duplicate_in_file"),
        (8, "offering_code", "unknown_reference"),
        (9, "student_id", "unknown_reference"),
        (10, "subject_code", "unknown_reference"),
        (11, "year", "unknown_reference"),
    ]


async def test_ambiguous_offering_needs_a_code(seed: Seed, upload: Upload) -> None:
    await seed(until=ImportKind.OFFERINGS)
    await upload(
        "offerings",
        "subject_code,year,term,code,group_codes,teacher_ids\n"
        "IQT-2101,2026,Payız,765a2-2,765a2,T-10412\n",
        apply=True,
    )
    body = await upload(
        "enrollments",
        "student_id,subject_code,year,term\n25765201,IQT-2101,2026,Payız\n",
    )
    assert issues(body) == [(2, "offering_code", "ambiguous_offering")]


async def test_retake_and_results_update_the_right_rows(
    seed: Seed, upload: Upload, db: AsyncSession
) -> None:
    await seed()
    anar = await db.scalar(select(User).where(User.university_id == "24764105"))
    assert anar is not None
    statuses = await db.execute(
        select(CourseOffering.code, Enrollment.status, Enrollment.passed)
        .join(Enrollment, Enrollment.course_offering_id == CourseOffering.id)
        .join(Subject)
        .where(Enrollment.user_id == anar.id, Subject.code == "IQT-2101")
        .order_by(CourseOffering.code)
    )
    # The failed attempt stays; the retake is a separate row in the 765a2 offering (§13.1).
    assert list(statuses) == [
        ("764a1", EnrollmentStatus.COMPLETED, False),
        ("765a2", EnrollmentStatus.ACTIVE, None),
    ]

    body = await upload(
        "enrollments",
        "student_id,subject_code,year,term,offering_code,status,passed,grade\n"
        "24764105,IQT-2101,2026,Payız,765a2,completed,bəli,64\n",
        apply=True,
    )
    assert body["summary"] == {"created": 0, "updated": 1, "unchanged": 0, "removed": 0}
    grades = await db.scalars(select(Enrollment.grade).where(Enrollment.user_id == anar.id))
    assert sorted(g for g in grades if g is not None) == [64]


async def test_xlsx_upload(upload: Upload, db: AsyncSession) -> None:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(["code", "name_az", "name_en"])
    sheet.append(["DIZ", "Dizayn fakültəsi", "Faculty of Design"])
    buffer = io.BytesIO()
    workbook.save(buffer)

    body = await upload("faculties", buffer.getvalue(), file_name="Fakültələr.xlsx", apply=True)

    assert body["encoding"] is None
    assert body["file_name"] == "Fakültələr.xlsx"
    assert await db.scalar(select(Faculty.name_az)) == "Dizayn fakültəsi"


async def test_non_utf8_csv_reports_the_detected_encoding(upload: Upload) -> None:
    content = "code,name_az\nINS,İnşaat\n".encode("cp1254")
    detected = await upload("faculties", content)
    assert detected["encoding"] == "windows-1254"
    assert detected["status"] == "ready"

    overridden = await upload("faculties", content, encoding="windows-1251")
    assert overridden["encoding"] == "windows-1251"

    wrong = await upload("faculties", content, encoding="utf-8", expected_status=422)
    assert wrong["error"]["code"] == "import.encoding_mismatch"


async def test_letters_lost_to_a_code_page_are_rejected(upload: Upload) -> None:
    # cp1254 has no "ə"; Excel writes "?" instead, which must not reach the database.
    content = "code,name_az\nINS,İnşaat fakültəsi\n".encode("cp1254", errors="replace")
    body = await upload("faculties", content)
    assert body["encoding"] == "windows-1254"
    assert issues(body) == [(2, "name_az", "invalid_characters")]


async def test_unreadable_and_oversized_files(
    upload: Upload, monkeypatch: pytest.MonkeyPatch
) -> None:
    unsupported = await upload("faculties", b"%PDF", file_name="list.pdf", expected_status=422)
    assert unsupported["error"]["code"] == "import.unsupported_format"

    monkeypatch.setattr("app.modules.academics.files.MAX_FILE_BYTES", 10)
    monkeypatch.setattr(academics_router, "MAX_FILE_BYTES", 10)
    too_large = await upload("faculties", b"code,name_az\n" * 5, expected_status=413)
    assert too_large["error"]["code"] == "import.file_too_large"


async def test_uploads_are_rate_limited(upload: Upload, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(academics_router, "IMPORT_UPLOADS", RateLimit(f"t{uuid.uuid4()}", 1, 60))
    await upload("faculties", "code,name_az\nMEM,Memarlıq fakültəsi\n")
    limited = await upload(
        "faculties", "code,name_az\nMEM,Memarlıq fakültəsi\n", expected_status=429
    )
    assert limited["error"]["code"] == "request.rate_limited"
    assert 0 < limited["error"]["details"]["retry_after_seconds"] <= 60


async def test_template_and_listing(
    client: AsyncClient, upload: Upload, staff_headers: dict[str, str]
) -> None:
    template = await client.get("/api/v1/admin/imports/templates/students", headers=staff_headers)
    assert template.status_code == 200
    assert template.headers["content-disposition"] == 'attachment; filename="students.csv"'
    assert template.content.decode("utf-8") == (
        "\ufeffuniversity_id,family_name,given_name,email,group_code,status\r\n"
    )

    await upload("faculties", "code,name_az\nMEM,Memarlıq fakültəsi\n", apply=True)
    await upload("semesters", "year,term,starts_on,ends_on\n2026,Payız,2026-09-15,2027-01-31\n")
    await upload("semesters", "year,term,starts_on,ends_on\n2026,Payız,2027-01-31,2026-09-15\n")

    page = (await client.get("/api/v1/admin/imports?limit=2", headers=staff_headers)).json()
    assert page["total"] == 3
    assert [item["status"] for item in page["items"]] == ["invalid", "ready"]
    assert page["items"][1]["expires_at"] is not None
    filtered = (
        await client.get("/api/v1/admin/imports?kind=faculties", headers=staff_headers)
    ).json()
    assert [item["status"] for item in filtered["items"]] == ["applied"]
    assert filtered["items"][0]["expires_at"] is None

    detail = await client.get(
        f"/api/v1/admin/imports/{page['items'][0]['id']}", headers=staff_headers
    )
    assert issues(detail.json()) == [(2, "ends_on", "dates_out_of_order")]


async def test_seed_command(
    db: AsyncSession, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert await run_seed(SEED_DIR) == 0
    assert "enrollments: created 617, updated 0, unchanged 0" in capsys.readouterr().out
    assert await db.scalar(select(func.count()).select_from(Enrollment)) == 617

    (tmp_path / "faculties.csv").write_bytes(b"code,name_az\nMEM,\n")
    assert await run_seed(tmp_path) == 1
    assert "faculties: invalid" in capsys.readouterr().out
