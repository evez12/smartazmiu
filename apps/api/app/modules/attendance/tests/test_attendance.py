"""QR attendance: rotating codes, idempotent check-in, manual marks and reports (§6.1, D-094)."""

import asyncio
import io
import uuid
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

import pytest
from alembic import command
from httpx import AsyncClient
from openpyxl import load_workbook
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.ratelimit import RateLimit
from app.core.time import utc_now
from app.modules.academics.models import AcademicGroup, Enrollment
from app.modules.attendance import codes, export
from app.modules.attendance import service as attendance_service
from app.modules.attendance.models import AttendanceRecord, AttendanceSession
from app.modules.audit.models import AuditLog
from app.modules.chat.tests.conftest import MakePerson, Person
from app.modules.materials.tests.test_materials import sign_in
from app.modules.users.models import User
from conftest import alembic_config
from tests.support import TokenFactory

API = "/api/v1/attendance"
SECRET = "unit-test-secret"
SESSION = uuid.UUID(int=7)
Seed = Callable[..., Awaitable[None]]


def test_a_code_is_valid_for_its_step_and_five_seconds_into_the_next() -> None:
    step = codes.step_at(1_000_000)
    scanned = codes.parse_qr(codes.qr_code(SECRET, SESSION, step))
    assert scanned is not None
    start_of_next = (step + 1) * codes.STEP_SECONDS
    assert codes.qr_status(SECRET, scanned, start_of_next - 1) == "ok"
    assert codes.qr_status(SECRET, scanned, start_of_next + 4.9) == "ok"
    assert codes.qr_status(SECRET, scanned, start_of_next + 5) == "expired"
    assert codes.qr_status(SECRET, scanned, start_of_next + 60) == "expired"
    # A code from the future is not valid either: nobody can pre-print the next hour.
    assert codes.qr_status(SECRET, scanned, step * codes.STEP_SECONDS - 1) == "expired"


def test_a_code_is_bound_to_its_session_and_secret() -> None:
    step = codes.step_at(1_000_000)
    scanned = codes.parse_qr(codes.qr_code(SECRET, SESSION, step))
    assert scanned is not None
    now = step * codes.STEP_SECONDS + 1
    other_session = codes.ScannedCode(uuid.UUID(int=8), scanned.step, scanned.signature)
    assert codes.qr_status(SECRET, other_session, now) == "forged"
    assert codes.qr_status("another-secret", scanned, now) == "forged"
    assert codes.parse_qr("SAT1.nonsense") is None
    assert codes.parse_qr("SA1." + codes.qr_code(SECRET, SESSION, step).split(".", 1)[1]) is None


def test_typed_digits_follow_the_same_window() -> None:
    step = codes.step_at(1_000_000)
    digits = codes.digits_code(SECRET, SESSION, step)
    assert len(digits) == 6
    assert digits.isdigit()
    start_of_next = (step + 1) * codes.STEP_SECONDS
    assert codes.digits_match(SECRET, SESSION, f" {digits} ", start_of_next + 1)
    assert not codes.digits_match(SECRET, SESSION, digits, start_of_next + 6)


def test_spreadsheet_cells_never_start_a_formula() -> None:
    assert export._safe("=HYPERLINK(1)") == "'=HYPERLINK(1)"
    assert export._safe("@SUM(A1)") == "'@SUM(A1)"
    assert export._safe("Aysel Məmmədova") == "Aysel Məmmədova"


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
        "curator": await person("Samir", "Quliyev"),
    }


async def statistika(client: AsyncClient, who: Person) -> str:
    offerings = await client.get(f"{API}/offerings", headers=who.headers)
    assert offerings.status_code == 200, offerings.text
    found: str = next(
        o["id"]
        for o in offerings.json()["items"]
        if (o["subject_code"], o["groups"]) == ("IQT-2102", ["765a2"])
    )
    return found


async def open_meeting(
    client: AsyncClient, who: Person, offering: str, **extra: Any
) -> dict[str, Any]:
    response = await client.post(
        f"{API}/sessions",
        headers=who.headers,
        json={"course_offering_id": offering, "title": "Mühazirə 5", **extra},
    )
    assert response.status_code == 201, response.text
    opened: dict[str, Any] = response.json()
    return opened


async def current(client: AsyncClient, who: Person, session_id: str) -> dict[str, Any]:
    response = await client.get(f"{API}/sessions/{session_id}/code", headers=who.headers)
    assert response.status_code == 200, response.text
    shown: dict[str, Any] = response.json()
    return shown


async def check_in(client: AsyncClient, who: Person, **body: str) -> Any:
    return await client.post(f"{API}/check-in", headers=who.headers, json=body)


async def test_a_student_checks_in_once_and_the_teacher_sees_the_count(
    client: AsyncClient, people: dict[str, Person]
) -> None:
    leyla, aysel = people["leyla"], people["aysel"]
    meeting = await open_meeting(client, leyla, await statistika(client, leyla))
    assert (meeting["is_open"], meeting["present"]) == (True, 0)
    shown = await current(client, leyla, meeting["id"])

    first = await check_in(client, aysel, qr=shown["qr"])
    assert first.status_code == 200, first.text
    assert first.json()["already_present"] is False
    again = await check_in(client, aysel, qr=shown["qr"])
    assert (again.status_code, again.json()["already_present"]) == (200, True)
    assert again.json()["checked_in_at"] == first.json()["checked_in_at"]

    detail = (await client.get(f"{API}/sessions/{meeting['id']}", headers=leyla.headers)).json()
    assert detail["present"] == 1
    present = [row for row in detail["roster"] if row["present"]]
    assert [(r["display_name"], r["method"]) for r in present] == [("Aysel Məmmədova", "qr")]
    assert (await current(client, leyla, meeting["id"]))["present"] == 1


async def test_the_six_digits_work_for_a_student_without_a_camera(
    client: AsyncClient, people: dict[str, Person]
) -> None:
    leyla, aysel = people["leyla"], people["aysel"]
    meeting = await open_meeting(client, leyla, await statistika(client, leyla))
    shown = await current(client, leyla, meeting["id"])
    wrong = "000000" if shown["digits"] != "000000" else "111111"
    assert (await check_in(client, aysel, digits=wrong)).json()["error"]["code"] == (
        "attendance.code_invalid"
    )
    ok = await check_in(client, aysel, digits=shown["digits"])
    assert ok.status_code == 200, ok.text
    detail = (await client.get(f"{API}/sessions/{meeting['id']}", headers=leyla.headers)).json()
    assert [r["method"] for r in detail["roster"] if r["present"]] == ["code"]
    assert (await check_in(client, aysel)).status_code == 422
    assert (await check_in(client, aysel, qr="x", digits="123456")).status_code == 422


async def test_typed_errors_for_expired_forged_foreign_and_closed_codes(
    client: AsyncClient,
    db: AsyncSession,
    settings: Settings,
    people: dict[str, Person],
) -> None:
    leyla, aysel, outsider = people["leyla"], people["aysel"], people["outsider"]
    meeting = await open_meeting(client, leyla, await statistika(client, leyla))
    session_id = uuid.UUID(meeting["id"])
    shown = await current(client, leyla, meeting["id"])

    stale_step = codes.step_at(utc_now().timestamp()) - 3
    stale = codes.qr_code(settings.attendance_secret, session_id, stale_step)
    expired = await check_in(client, aysel, qr=stale)
    assert (expired.status_code, expired.json()["error"]["code"]) == (
        410,
        "attendance.code_expired",
    )
    forged = await check_in(client, aysel, qr=shown["qr"][:-3] + "AAA")
    assert (forged.status_code, forged.json()["error"]["code"]) == (400, "attendance.code_invalid")
    junk = await check_in(client, aysel, qr="https://example.test/")
    assert junk.json()["error"]["code"] == "attendance.code_invalid"
    # A genuine code is no use to someone who is not enrolled; the digits name no meeting for them at all.
    foreign = await check_in(client, outsider, qr=shown["qr"])
    assert (foreign.status_code, foreign.json()["error"]["code"]) == (
        403,
        "attendance.not_enrolled",
    )
    nameless = await check_in(client, outsider, digits=shown["digits"])
    assert nameless.json()["error"]["code"] == "attendance.code_invalid"
    assert (await db.scalar(select(AttendanceSession.id))) == session_id

    closed = await client.post(f"{API}/sessions/{meeting['id']}/close", headers=leyla.headers)
    assert (closed.status_code, closed.json()["is_open"]) == (200, False)
    shown = await current(client, leyla, meeting["id"])
    late = await check_in(client, aysel, qr=shown["qr"])
    assert (late.status_code, late.json()["error"]["code"]) == (409, "attendance.session_closed")
    # Closing twice is a no-op.
    assert (
        await client.post(f"{API}/sessions/{meeting['id']}/close", headers=leyla.headers)
    ).is_success


async def test_only_one_meeting_is_open_per_offering_and_a_lapsed_one_does_not_count(
    client: AsyncClient, db: AsyncSession, people: dict[str, Person]
) -> None:
    leyla, aysel = people["leyla"], people["aysel"]
    offering = await statistika(client, leyla)
    first = await open_meeting(client, leyla, offering)
    twice = await client.post(
        f"{API}/sessions", headers=leyla.headers, json={"course_offering_id": offering}
    )
    assert (twice.status_code, twice.json()["error"]["code"]) == (409, "attendance.session_open")

    shown = await current(client, leyla, first["id"])
    await db.execute(
        update(AttendanceSession)
        .where(AttendanceSession.id == uuid.UUID(first["id"]))
        .values(
            opened_at=utc_now() - timedelta(hours=3),
            expires_at=utc_now() - timedelta(minutes=1),
        )
    )
    await db.commit()
    expired = await check_in(client, aysel, qr=shown["qr"])
    assert expired.json()["error"]["code"] == "attendance.session_closed"
    second = await open_meeting(client, leyla, offering)
    assert second["id"] != first["id"]
    listed = await client.get(
        f"{API}/sessions", headers=leyla.headers, params={"offering_id": offering}
    )
    assert [s["id"] for s in listed.json()["items"]] == [second["id"], first["id"]]
    assert [s["is_open"] for s in listed.json()["items"]] == [True, False]


async def test_only_the_teacher_of_the_offering_and_staff_run_a_meeting(
    client: AsyncClient, people: dict[str, Person]
) -> None:
    leyla, rauf, aysel, outsider, staff = (
        people[k] for k in ("leyla", "rauf", "aysel", "outsider", "staff")
    )
    offering = await statistika(client, leyla)
    # Rauf teaches another course; to him this offering does not exist.
    assert offering not in [
        o["id"]
        for o in (await client.get(f"{API}/offerings", headers=rauf.headers)).json()["items"]
    ]
    for denied in (rauf, aysel, outsider):
        refused = await client.post(
            f"{API}/sessions", headers=denied.headers, json={"course_offering_id": offering}
        )
        assert (refused.status_code, refused.json()["error"]["code"]) == (
            404,
            "attendance.offering_not_found",
        )
    meeting = await open_meeting(client, leyla, offering)
    for denied in (rauf, aysel, outsider):
        for url in (f"{API}/sessions/{meeting['id']}", f"{API}/sessions/{meeting['id']}/code"):
            assert (await client.get(url, headers=denied.headers)).status_code == 404
        assert (
            await client.post(f"{API}/sessions/{meeting['id']}/close", headers=denied.headers)
        ).status_code == 404
    unauthenticated = await client.get(f"{API}/sessions/{meeting['id']}")
    assert unauthenticated.status_code == 401
    # The dean's office (staff) runs any offering.
    assert (
        await client.get(f"{API}/sessions/{meeting['id']}", headers=staff.headers)
    ).status_code == 200
    assert (
        await client.post(f"{API}/sessions/{meeting['id']}/close", headers=staff.headers)
    ).is_success


async def test_manual_marks_need_a_reason_are_idempotent_and_audited(
    client: AsyncClient, db: AsyncSession, people: dict[str, Person]
) -> None:
    leyla, aysel, outsider = people["leyla"], people["aysel"], people["outsider"]
    meeting = await open_meeting(client, leyla, await statistika(client, leyla))
    url = f"{API}/sessions/{meeting['id']}/students/{aysel.id}"

    no_reason = await client.put(url, headers=leyla.headers, json={"present": True, "reason": ""})
    assert no_reason.status_code == 422
    for _ in range(2):
        marked = await client.put(
            url, headers=leyla.headers, json={"present": True, "reason": "Telefonu işləmirdi"}
        )
        assert marked.status_code == 200, marked.text
    assert (marked.json()["present"], marked.json()["method"]) == (True, "manual")
    assert marked.json()["reason"] == "Telefonu işləmirdi"
    # A student who later scans keeps the manual record rather than creating a second one.
    shown = await current(client, leyla, meeting["id"])
    assert (await check_in(client, aysel, qr=shown["qr"])).json()["already_present"] is True

    unmarked = await client.put(
        url, headers=leyla.headers, json={"present": False, "reason": "Auditoriyada yox idi"}
    )
    assert (unmarked.status_code, unmarked.json()["present"]) == (200, False)
    assert (
        await client.put(
            url, headers=leyla.headers, json={"present": False, "reason": "Təkrar yoxlama"}
        )
    ).status_code == 200

    unknown = await client.put(
        f"{API}/sessions/{meeting['id']}/students/{outsider.id}",
        headers=leyla.headers,
        json={"present": True, "reason": "Səhv şəxs"},
    )
    assert (unknown.status_code, unknown.json()["error"]["code"]) == (
        404,
        "attendance.student_not_found",
    )
    assert (
        await client.put(url, headers=aysel.headers, json={"present": True, "reason": "Özüm"})
    ).status_code == 404

    entries = list(
        await db.scalars(
            select(AuditLog)
            .where(AuditLog.action.like("attendance.%"))
            .order_by(AuditLog.occurred_at)
        )
    )
    assert [e.action for e in entries] == [
        "attendance.marked",
        "attendance.marked",
        "attendance.unmarked",
        "attendance.unmarked",
    ]
    assert all(e.actor_id == leyla.id and e.target_id == meeting["id"] for e in entries)
    assert entries[2].details == {"student_id": str(aysel.id), "reason": "Auditoriyada yox idi"}


async def test_students_see_only_their_own_rate_and_meetings(
    client: AsyncClient, people: dict[str, Person]
) -> None:
    leyla, aysel, outsider = people["leyla"], people["aysel"], people["outsider"]
    offering = await statistika(client, leyla)
    for index in range(2):
        meeting = await open_meeting(client, leyla, offering, title=f"Mühazirə {index + 1}")
        if index == 0:
            shown = await current(client, leyla, meeting["id"])
            assert (await check_in(client, aysel, qr=shown["qr"])).is_success
        await client.post(f"{API}/sessions/{meeting['id']}/close", headers=leyla.headers)

    mine = (await client.get(f"{API}/my", headers=aysel.headers)).json()["items"]
    row = next(i for i in mine if i["offering"]["id"] == offering)
    assert (row["attended"], row["total"], row["rate"]) == (1, 2, 0.5)
    assert row["sessions"] == []
    detail = (await client.get(f"{API}/my/{offering}", headers=aysel.headers)).json()
    assert [(s["title"], s["present"]) for s in detail["sessions"]] == [
        ("Mühazirə 2", False),
        ("Mühazirə 1", True),
    ]
    assert (await client.get(f"{API}/my", headers=outsider.headers)).json() == {"items": []}
    assert (await client.get(f"{API}/my/{offering}", headers=outsider.headers)).status_code == 404
    # The report is for the teacher: a student reading it is told the offering does not exist.
    assert (
        await client.get(f"{API}/offerings/{offering}/report", headers=aysel.headers)
    ).status_code == 404


async def test_reports_for_teacher_curator_and_exports(
    client: AsyncClient, db: AsyncSession, people: dict[str, Person]
) -> None:
    leyla, aysel, curator, outsider = (people[k] for k in ("leyla", "aysel", "curator", "outsider"))
    offering = await statistika(client, leyla)
    meeting = await open_meeting(client, leyla, offering, title="=HYPERLINK(1)")
    shown = await current(client, leyla, meeting["id"])
    assert (await check_in(client, aysel, qr=shown["qr"])).is_success

    report = (await client.get(f"{API}/offerings/{offering}/report", headers=leyla.headers)).json()
    assert [s["title"] for s in report["sessions"]] == ["=HYPERLINK(1)"]
    by_name = {r["display_name"]: r for r in report["rows"]}
    assert (by_name["Aysel Məmmədova"]["attended"], by_name["Aysel Məmmədova"]["marks"]) == (
        1,
        [True],
    )
    assert any(r["attended"] == 0 and r["marks"] == [False] for r in report["rows"])

    # A curator reads the report of the groups they curate, and nothing else.
    group = await db.scalar(select(AcademicGroup).where(AcademicGroup.code == "765a2"))
    assert group is not None
    assert (
        await client.get(f"{API}/offerings/{offering}/report", headers=curator.headers)
    ).status_code == 404
    group.curator_id = curator.id
    await db.commit()
    listed = (await client.get(f"{API}/offerings", headers=curator.headers)).json()["items"]
    assert (offering, "curator") in [(o["id"], o["role"]) for o in listed]
    assert {o["role"] for o in listed} == {"curator"}
    curated = (
        await client.get(f"{API}/offerings/{offering}/report", headers=curator.headers)
    ).json()
    assert {r["group"] for r in curated["rows"]} == {"765a2"}
    assert (
        await client.post(
            f"{API}/sessions", headers=curator.headers, json={"course_offering_id": offering}
        )
    ).status_code == 404
    assert (
        await client.get(f"{API}/offerings/{offering}/report", headers=outsider.headers)
    ).status_code == 404

    csv = await client.get(f"{API}/offerings/{offering}/report.csv", headers=leyla.headers)
    assert csv.status_code == 200
    assert csv.content.startswith(b"\xef\xbb\xbf")
    text = csv.content.decode("utf-8-sig")
    assert "Məmmədova" in text
    assert "=HYPERLINK(1)" in text
    xlsx = await client.get(f"{API}/offerings/{offering}/report.xlsx", headers=leyla.headers)
    sheet = load_workbook(io.BytesIO(xlsx.content)).active
    assert sheet is not None
    assert [cell.value for cell in sheet[1]][:6] == [
        "Ad",
        "Tələbə nömrəsi",
        "Qrup",
        "İştirak",
        "Ümumi",
        "Faiz",
    ]
    assert (
        await client.get(f"{API}/offerings/{offering}/report.pdf", headers=leyla.headers)
    ).status_code == 422
    assert (
        await client.get(f"{API}/offerings/{offering}/report.csv", headers=aysel.headers)
    ).status_code == 404


async def test_a_deleted_account_leaves_anonymous_rows_the_report_still_counts(
    client: AsyncClient, db: AsyncSession, settings: Settings, people: dict[str, Person]
) -> None:
    """D-108: deleting the student or the teacher keeps the meeting and its tally; the downgrade refuses to lose them."""
    leyla, aysel, staff = people["leyla"], people["aysel"], people["staff"]
    offering = await statistika(client, leyla)
    meeting = await open_meeting(client, staff, offering)
    shown = await current(client, staff, meeting["id"])
    assert (await check_in(client, aysel, qr=shown["qr"])).is_success

    # Enrolments are the deletion task's to clear; the three D-108 references are what this test is about.
    await db.execute(delete(Enrollment).where(Enrollment.user_id == aysel.id))
    await db.execute(delete(User).where(User.id.in_([aysel.id, staff.id])))
    await db.commit()

    record = await db.scalar(select(AttendanceRecord))
    assert record is not None
    assert record.student_id is None
    opened = await db.scalar(select(AttendanceSession.opened_by))
    assert opened is None
    detail = (await client.get(f"{API}/sessions/{meeting['id']}", headers=leyla.headers)).json()
    assert detail["present"] == 1
    report = (await client.get(f"{API}/offerings/{offering}/report", headers=leyla.headers)).json()
    assert [(s["id"], s["title"]) for s in report["sessions"]] == [(meeting["id"], "Mühazirə 5")]
    assert "Aysel Məmmədova" not in {r["display_name"] for r in report["rows"]}

    with pytest.raises(RuntimeError, match="belong to deleted accounts"):
        await asyncio.to_thread(command.downgrade, alembic_config(settings), "0035")
    await db.execute(delete(AttendanceRecord))
    await db.execute(delete(AttendanceSession))
    await db.commit()


async def test_guessing_codes_is_rate_limited(
    client: AsyncClient,
    people: dict[str, Person],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    leyla, aysel = people["leyla"], people["aysel"]
    meeting = await open_meeting(client, leyla, await statistika(client, leyla))
    shown = await current(client, leyla, meeting["id"])
    monkeypatch.setattr(
        attendance_service, "USER_CHECK_IN", RateLimit("attendance_user_test", 3, 60)
    )
    wrong = "000000" if shown["digits"] != "000000" else "111111"
    for _ in range(3):
        assert (await check_in(client, aysel, digits=wrong)).status_code == 400
    blocked = await check_in(client, aysel, digits=shown["digits"])
    assert (blocked.status_code, blocked.json()["error"]["code"]) == (429, "request.rate_limited")
