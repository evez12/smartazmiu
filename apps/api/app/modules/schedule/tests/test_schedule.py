import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, tzinfo
from typing import Any

import pytest
from httpx import AsyncClient

from app.core import time as clock
from app.modules.academics.models import ImportKind
from app.modules.academics.tests.conftest import SEED_DIR, Upload
from app.modules.schedule import imports, router
from tests.support import TokenFactory

Seed = Callable[..., Awaitable[None]]
Headers = dict[str, str]

TODAY = date(2026, 10, 25)
TIMETABLE = (SEED_DIR / "schedule.csv").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def autumn_2026(monkeypatch: pytest.MonkeyPatch) -> Callable[[date], None]:
    """Sunday 25 October 2026, in the sample data's current semester; tests may move the clock."""

    def set_today(day: date) -> None:
        monkeypatch.setattr(imports, "baku_today", lambda: day)
        monkeypatch.setattr(router, "baku_today", lambda: day)

    set_today(TODAY)
    return set_today


def person(tokens: TokenFactory, email: str, roles: list[str], given: str, family: str) -> Headers:
    token = tokens.issue(
        str(uuid.uuid4()), roles, given_name=given, family_name=family, email=email
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def aysel(tokens: TokenFactory) -> Headers:
    return person(tokens, "aysel.mammadova@smartazmiu.test", ["student"], "Aysel", "Məmmədova")


@pytest.fixture
def nigar(tokens: TokenFactory) -> Headers:
    return person(tokens, "nigar.ismayilova@smartazmiu.test", ["student"], "Nigar", "İsmayılova")


@pytest.fixture
def leyla(tokens: TokenFactory) -> Headers:
    return person(tokens, "leyla.hasanova@smartazmiu.test", ["teacher"], "Leyla", "Həsənova")


@pytest.fixture
def farid(tokens: TokenFactory) -> Headers:
    return person(tokens, "farid.ismayilov@smartazmiu.test", ["teacher"], "Fərid", "İsmayılov")


async def week(
    client: AsyncClient, headers: Headers, start: str, end: str | None = None
) -> dict[str, Any]:
    params = {"start": start, **({"end": end} if end else {})}
    response = await client.get("/api/v1/me/schedule", params=params, headers=headers)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def summary(body: dict[str, Any]) -> list[tuple[str, str, str, str, str | None, str]]:
    return [
        (
            item["date"],
            item["starts_at"],
            item["subject"]["code"],
            item["class_type"],
            item["room"]["code"] if item["room"] else None,
            item["status"],
        )
        for day in body["days"]
        for item in day["classes"]
    ]


async def test_student_week_with_parity_and_changes(
    client: AsyncClient, seed: Seed, aysel: Headers
) -> None:
    await seed(ImportKind.SCHEDULE_CHANGES)

    body = await week(client, aysel, "2026-10-26")

    assert (body["start"], body["end"], body["today"]) == ("2026-10-26", "2026-11-01", "2026-10-25")
    assert [day["parity"] for day in body["days"]] == ["upper"] * 7
    assert summary(body) == [
        ("2026-10-26", "08:30", "IQT-2101", "lecture", "1-301", "scheduled"),
        ("2026-10-26", "10:05", "IQT-2102", "seminar", "2-204", "scheduled"),
        ("2026-10-26", "11:40", "XDL-2103", "seminar", "1-206", "scheduled"),
        ("2026-10-27", "08:30", "HFT-2101", "lecture", "2-101", "scheduled"),
        # Sosiologiya, her elective; Fəlsəfə at the same time is not hers.
        ("2026-10-27", "10:05", "SOS-2104", "lecture", "2-201", "scheduled"),
        ("2026-10-28", "10:05", "IQT-2101", "seminar", "1-305", "moved_away"),
        ("2026-10-28", "11:40", "IQT-2102", "lecture", "2-101", "changed"),
        ("2026-10-29", "08:30", "XDL-2103", "seminar", "1-206", "changed"),
        # The joint seminar of 765a2 (upper weeks); 765a1's runs in lower weeks.
        ("2026-10-30", "10:05", "IQT-2101", "seminar", "1-305", "moved_here"),
        ("2026-10-30", "11:40", "HFT-2101", "seminar", "2-105", "scheduled"),
    ]
    classes = [item for day in body["days"] for item in day["classes"]]
    monday_lecture, moved_away, room_change, substitute, moved_here = (
        classes[0],
        classes[5],
        classes[6],
        classes[7],
        classes[8],
    )
    assert monday_lecture["teachers"] == ["Şəhla Ağayeva"]
    assert monday_lecture["groups"] == ["765a2"]
    assert monday_lecture["room"] == {
        "code": "1-301",
        "name": "Mühazirə zalı",
        "building": "Tədris korpusu 1",
        "floor": "3-cü mərtəbə",
    }
    assert classes[3]["groups"] == ["765a1", "765a2"]
    assert moved_away["moved_to"] == {
        "date": "2026-10-30",
        "starts_at": "10:05",
        "ends_at": "11:25",
    }
    assert moved_away["note"] == "Müəllim konfransdadır"
    assert moved_here["original_date"] == "2026-10-28"
    assert moved_here["id"] == moved_away["id"]
    assert moved_here["teachers"] == ["Fərid İsmayılov"]
    assert room_change["room_changed"]
    assert not room_change["teacher_changed"]
    assert room_change["note"] == "1-101 konfrans üçün ayrılıb"
    assert substitute["teachers"] == ["Fərid İsmayılov"]
    assert substitute["teacher_changed"]
    assert not substitute["room_changed"]


async def test_holiday_cancellations_and_parity_override(
    client: AsyncClient, seed: Seed, aysel: Headers
) -> None:
    await seed(ImportKind.SCHEDULE_CHANGES)

    holiday = await week(client, aysel, "2026-11-09", "2026-11-09")
    assert summary(holiday) == [
        ("2026-11-09", "08:30", "IQT-2101", "lecture", "1-301", "cancelled"),
        ("2026-11-09", "10:05", "IQT-2102", "seminar", "2-204", "cancelled"),
        ("2026-11-09", "11:40", "XDL-2103", "seminar", "1-206", "cancelled"),
    ]
    assert holiday["days"][0]["classes"][0]["note"] == "Dövlət Bayrağı Günü"

    # 16 November would be a lower week; the override restarts the rhythm with an upper week.
    mondays = await week(client, aysel, "2026-11-16", "2026-11-23")
    parities = {day["date"]: day["parity"] for day in mondays["days"]}
    assert (parities["2026-11-16"], parities["2026-11-23"]) == ("upper", "lower")
    upper_week_language = [
        c for c in summary(mondays) if c[2] == "XDL-2103" and c[0] < "2026-11-17"
    ]
    assert upper_week_language == [
        ("2026-11-16", "11:40", "XDL-2103", "seminar", "1-206", "scheduled")
    ]
    assert not [c for c in summary(mondays) if c[0] == "2026-11-23" and c[2] == "XDL-2103"]


async def test_groups_of_a_joint_offering_see_only_their_classes(
    client: AsyncClient, seed: Seed, aysel: Headers, nigar: Headers
) -> None:
    await seed(ImportKind.SCHEDULE_CHANGES)

    # A lower week: 765a1's civil defence seminar, not 765a2's.
    friday = "2026-11-06"
    nigar_friday = summary(await week(client, nigar, friday, friday))
    aysel_friday = summary(await week(client, aysel, friday, friday))

    assert ("2026-11-06", "11:40", "HFT-2101", "seminar", "2-105", "scheduled") in nigar_friday
    assert [c for c in aysel_friday if c[2] == "HFT-2101"] == []


async def test_teachers_see_their_classes_and_substitutions(
    client: AsyncClient, seed: Seed, leyla: Headers, farid: Headers
) -> None:
    await seed(ImportKind.SCHEDULE_CHANGES)

    statistics = summary(await week(client, leyla, "2026-10-26"))
    assert statistics == [
        ("2026-10-26", "10:05", "IQT-2102", "seminar", "2-204", "scheduled"),
        ("2026-10-26", "11:40", "IQT-2102", "seminar", "2-203", "scheduled"),
        ("2026-10-28", "11:40", "IQT-2102", "lecture", "1-101", "scheduled"),
        ("2026-10-28", "11:40", "IQT-2102", "lecture", "2-101", "changed"),
    ]

    # Fərid teaches the 765a2 seminar (the lecture is Şəhla Ağayeva's) and substitutes on Thursday only.
    farid_week = summary(await week(client, farid, "2026-10-26"))
    assert farid_week == [
        ("2026-10-28", "10:05", "IQT-2101", "seminar", "1-305", "moved_away"),
        ("2026-10-29", "08:30", "XDL-2103", "seminar", "1-206", "changed"),
        ("2026-10-30", "10:05", "IQT-2101", "seminar", "1-305", "moved_here"),
    ]
    next_week = summary(await week(client, farid, "2026-11-02"))
    assert [c for c in next_week if c[2] == "XDL-2103"] == []


async def test_dropped_subjects_and_unenrolled_users_have_no_classes(
    client: AsyncClient, seed: Seed, upload: Upload, aysel: Headers, tokens: TokenFactory
) -> None:
    await seed(ImportKind.SCHEDULE_CHANGES)
    await upload(
        ImportKind.ENROLLMENTS,
        "student_id,subject_code,year,term,offering_code,status,passed,grade\n"
        "25765201,IQT-2102,2026,Payız,,dropped,,\n",
        apply=True,
    )

    codes = {c[2] for c in summary(await week(client, aysel, "2026-10-26"))}
    assert "IQT-2102" not in codes
    assert "IQT-2101" in codes

    newcomer = person(tokens, "nermin.sukurova@smartazmiu.test", ["student"], "Nərmin", "Şükürova")
    body = await week(client, newcomer, "2026-10-26")
    assert summary(body) == []
    assert len(body["days"]) == 7


async def test_payload_never_contains_grades_or_contacts(
    client: AsyncClient, seed: Seed, aysel: Headers
) -> None:
    await seed(ImportKind.SCHEDULE_CHANGES)
    response = await client.get(
        "/api/v1/me/schedule", params={"start": "2026-09-14", "end": "2026-10-25"}, headers=aysel
    )
    assert response.status_code == 200
    for forbidden in ("grade", "passed", "email", "@smartazmiu"):
        assert forbidden not in response.text


async def test_range_defaults_to_this_week_and_is_bounded(
    client: AsyncClient, seed: Seed, aysel: Headers, autumn_2026: Callable[[date], None]
) -> None:
    await seed(ImportKind.SCHEDULE_CHANGES)

    body = (await client.get("/api/v1/me/schedule", headers=aysel)).json()
    assert (body["start"], body["end"]) == ("2026-10-19", "2026-10-25")

    autumn_2026(date(2026, 10, 26))
    body = (await client.get("/api/v1/me/schedule", headers=aysel)).json()
    assert (body["start"], body["end"]) == ("2026-10-26", "2026-11-01")

    for params in (
        {"start": "2026-10-26", "end": "2026-10-25"},
        {"start": "2026-10-01", "end": "2026-11-12"},
    ):
        response = await client.get("/api/v1/me/schedule", params=params, headers=aysel)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "schedule.invalid_range"
    # 42 days, both ends included.
    longest = await client.get(
        "/api/v1/me/schedule", params={"start": "2026-10-01", "end": "2026-11-11"}, headers=aysel
    )
    assert longest.status_code == 200

    # Between semesters a day has no parity.
    summer = (await week(client, aysel, "2026-07-06", "2026-07-06"))["days"][0]
    assert summer == {"date": "2026-07-06", "parity": None, "classes": []}


@pytest.mark.parametrize(
    ("utc", "today", "week", "parity"),
    [
        # Baku is UTC+4: from 20:00 UTC on, it is already the next calendar day there.
        ("2026-10-25T19:59:59", "2026-10-25", ("2026-10-19", "2026-10-25"), "lower"),
        ("2026-10-25T20:00:00", "2026-10-26", ("2026-10-26", "2026-11-01"), "upper"),
        ("2026-10-25T23:59:59", "2026-10-26", ("2026-10-26", "2026-11-01"), "upper"),
    ],
)
async def test_today_week_and_parity_follow_the_baku_date_around_midnight(
    client: AsyncClient,
    seed: Seed,
    aysel: Headers,
    monkeypatch: pytest.MonkeyPatch,
    utc: str,
    today: str,
    week: tuple[str, str],
    parity: str,
) -> None:
    await seed(ImportKind.SCHEDULE)
    instant = datetime.fromisoformat(utc).replace(tzinfo=UTC)

    class FrozenClock(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> "FrozenClock":
            return cls.fromtimestamp(instant.timestamp(), tz)

    # The real conversion from the UTC clock, not the fixed date the other tests use.
    monkeypatch.setattr(clock, "datetime", FrozenClock)
    monkeypatch.setattr(router, "baku_today", clock.baku_today)

    body = (await client.get("/api/v1/me/schedule", headers=aysel)).json()
    assert body["today"] == today
    assert (body["start"], body["end"]) == week
    assert {day["parity"] for day in body["days"]} == {parity}
    lessons = next(day for day in body["days"] if day["date"] == today)["classes"]
    expected_weekday = date.fromisoformat(today).isoweekday()
    assert all(
        date.fromisoformat(item["date"]).isoweekday() == expected_weekday for item in lessons
    )


async def test_schedule_requires_sign_in(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/me/schedule")).status_code == 401
    assert (await client.get("/api/v1/me/schedule.ics")).status_code == 401


async def test_ics_export_of_the_semester(client: AsyncClient, seed: Seed, aysel: Headers) -> None:
    await seed(ImportKind.SCHEDULE_CHANGES)

    response = await client.get("/api/v1/me/schedule.ics", headers=aysel)

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/calendar; charset=utf-8"
    assert 'filename="ders-cedveli.ics"' in response.headers["content-disposition"]
    raw = response.content.decode()
    assert raw.startswith("BEGIN:VCALENDAR\r\n")
    assert raw.endswith("END:VCALENDAR\r\n")
    assert "\n" not in raw.replace("\r\n", "")
    assert all(len(line.encode()) <= 75 for line in raw.split("\r\n"))
    assert "TZID:Asia/Baku" in raw
    assert "TZOFFSETTO:+0400" in raw

    unfolded = raw.replace("\r\n ", "")
    events = unfolded.split("BEGIN:VEVENT\r\n")[1:]
    by_start = {
        line.split(":", 1)[1]: event
        for event in events
        for line in event.split("\r\n")
        if line.startswith("DTSTART")
    }
    lecture = by_start["20261026T083000"]
    assert "DTEND;TZID=Asia/Baku:20261026T095000" in lecture
    assert "SUMMARY:Mikroiqtisadiyyat (mühazirə)" in lecture
    assert "LOCATION:1-301\\, Tədris korpusu 1" in lecture
    assert "STATUS:CONFIRMED" in lecture
    # Cancelled for the holiday, kept so calendars mark it as cancelled.
    assert "STATUS:CANCELLED" in by_start["20261109T083000"]
    # The moved seminar appears once, on its new day, with the UID of its original occurrence.
    assert "20261028T100500" not in by_start
    moved = by_start["20261030T100500"]
    uid = next(line for line in moved.split("\r\n") if line.startswith("UID:"))
    assert uid.endswith("-20261028@smartazmiu")
    # Weeks before today are included: calendars get the whole semester.
    assert "20260921T083000" in by_start


async def test_timetable_import_validation(upload: Upload, seed: Seed) -> None:
    await seed(ImportKind.WEEK_PARITY)
    header = TIMETABLE.splitlines()[0]
    rows = [
        # Ends before it starts.
        "IQT-2101,2026,Payız,765a2,,1,10:05,09:50,hər həftə,seminar,1-305,",
        # Unknown room.
        "IQT-2101,2026,Payız,765a2,,2,10:05,11:25,hər həftə,seminar,9-999,",
        # Teaches, but not this offering.
        "IQT-2101,2026,Payız,765a2,,3,10:05,11:25,hər həftə,seminar,1-305,T-10457",
        # 765a1 is not a group of 765a2's offering.
        "IQT-2101,2026,Payız,765a2,765a1,1,10:05,11:25,hər həftə,seminar,1-305,",
        # Without a code there are two Mikroiqtisadiyyat offerings in 2026 Payız.
        "IQT-2101,2026,Payız,,,1,10:05,11:25,hər həftə,seminar,1-305,",
        "IQT-2101,2026,Payız,765a2,,Bazar günü,25:00,11:25,iki həftədən bir,dərs,1-305,",
        # The same joint class once with both group codes and once without.
        "HFT-2101,2026,Payız,,765a1;765a2,2,08:30,09:50,hər həftə,mühazirə,2-101,",
        "HFT-2101,2026,Payız,765a1+765a2,,2,08:30,09:50,hər həftə,mühazirə,2-101,",
    ]
    preview = await upload(ImportKind.SCHEDULE, "\n".join([header, *rows]) + "\n")

    assert preview["status"] == "invalid"
    assert [(e["row"], e["column"], e["code"]) for e in preview["errors"]] == [
        (2, "ends_at", "times_out_of_order"),
        (3, "room_code", "unknown_reference"),
        (4, "teacher_id", "teacher_not_in_offering"),
        (5, "group_codes", "group_not_in_offering"),
        (6, "offering_code", "ambiguous_offering"),
        (7, "weekday", "invalid_choice"),
        (7, "starts_at", "invalid_time"),
        (7, "week_parity", "invalid_choice"),
        (7, "class_type", "invalid_choice"),
        (9, "group_codes", "duplicate_in_file"),
    ]


async def test_reimport_is_a_no_op_and_edits_keep_past_weeks(
    client: AsyncClient,
    upload: Upload,
    seed: Seed,
    aysel: Headers,
    autumn_2026: Callable[[date], None],
) -> None:
    await seed(ImportKind.SCHEDULE)

    again = await upload(ImportKind.SCHEDULE, TIMETABLE, file_name="cedvel.csv")
    assert again["summary"] == {"created": 0, "updated": 0, "unchanged": 20, "removed": 0}

    # Mid-semester: the lecture moves to another hall and the language seminar is dropped from the file.
    edited = TIMETABLE.replace(
        "IQT-2101,2026,Payız,765a2,,Bazar ertəsi,08:30,09:50,hər həftə,mühazirə,1-301,T-10412",
        "IQT-2101,2026,Payız,765a2,,Bazar ertəsi,08:30,09:50,hər həftə,mühazirə,2-101,T-10412",
    ).replace("XDL-2103,2026,Payız,765a2,,Bazar ertəsi,11:40,13:00,üst,seminar,1-206,\n", "")
    assert edited.count("\n") == TIMETABLE.count("\n") - 1
    applied = await upload(ImportKind.SCHEDULE, edited, apply=True)
    assert applied["summary"] == {"created": 0, "updated": 1, "unchanged": 18, "removed": 1}

    # 12 October is an upper week, like 26 October: the language seminar took place then.
    before = summary(await week(client, aysel, "2026-10-12", "2026-10-12"))
    after = summary(await week(client, aysel, "2026-10-26", "2026-10-26"))
    assert before == [
        ("2026-10-12", "08:30", "IQT-2101", "lecture", "1-301", "scheduled"),
        ("2026-10-12", "10:05", "IQT-2102", "seminar", "2-204", "scheduled"),
        ("2026-10-12", "11:40", "XDL-2103", "seminar", "1-206", "scheduled"),
    ]
    assert after == [
        ("2026-10-26", "08:30", "IQT-2101", "lecture", "2-101", "scheduled"),
        ("2026-10-26", "10:05", "IQT-2102", "seminar", "2-204", "scheduled"),
    ]

    # Applying the edited file again changes nothing.
    assert (await upload(ImportKind.SCHEDULE, edited))["summary"] == {
        "created": 0,
        "updated": 0,
        "unchanged": 19,
        "removed": 0,
    }


async def test_edits_before_the_semester_starts_replace_the_timetable(
    client: AsyncClient,
    upload: Upload,
    seed: Seed,
    aysel: Headers,
    autumn_2026: Callable[[date], None],
) -> None:
    autumn_2026(date(2026, 9, 1))
    await seed(ImportKind.SCHEDULE)
    edited = TIMETABLE.replace(",mühazirə,1-301,T-10412", ",mühazirə,2-101,T-10412")
    applied = await upload(ImportKind.SCHEDULE, edited, apply=True)
    assert applied["summary"]["updated"] == 1

    first_week = summary(await week(client, aysel, "2026-09-14", "2026-09-14"))
    assert ("2026-09-14", "08:30", "IQT-2101", "lecture", "2-101", "scheduled") not in first_week
    # The semester starts on Tuesday; the first Monday class is on 21 September, in the new hall.
    second_week = summary(await week(client, aysel, "2026-09-21", "2026-09-21"))
    assert ("2026-09-21", "08:30", "IQT-2101", "lecture", "2-101", "scheduled") in second_week


async def test_change_import_validation(upload: Upload, seed: Seed) -> None:
    await seed(ImportKind.SCHEDULE)
    header = (SEED_DIR / "schedule_changes.csv").read_text(encoding="utf-8").splitlines()[0]
    rows = [
        # Tuesday has no Mikroiqtisadiyyat class at 08:30.
        "IQT-2101,2026,Payız,765a2,,2026-10-27,08:30,ləğv,,,,,,",
        # A cancellation cannot also move the class.
        "IQT-2101,2026,Payız,765a2,,2026-10-26,08:30,ləğv,2026-10-30,,,,,",
        "IQT-2101,2026,Payız,765a2,,2026-10-26,08:30,dəyişiklik,,,,,,",
        "IQT-2101,2026,Payız,765a2,,2026-10-26,08:30,dəyişiklik,,10:05,,,,",
        "IQT-2101,2026,Payız,765a2,,2026-10-26,08:30,dəyişiklik,,11:25,10:05,,,",
        "IQT-2101,2026,Payız,765a2,,2026-10-26,08:30,dəyişiklik,2027-03-01,,,,,",
        "IQT-2101,2026,Payız,765a2,,2027-03-01,08:30,ləğv,,,,,,",
        # XDL-2103 for 765a2 is an upper-week class; 2 November is in a lower week.
        "XDL-2103,2026,Payız,765a2,,2026-11-02,11:40,ləğv,,,,,,",
        "IQT-2101,2026,Payız,765a2,,2026-11-02,08:30,dəyişiklik,,,,,T-99999,",
    ]
    preview = await upload(ImportKind.SCHEDULE_CHANGES, "\n".join([header, *rows]) + "\n")

    assert [(e["row"], e["column"], e["code"]) for e in preview["errors"]] == [
        (2, "date", "no_class_on_date"),
        (3, "new_date", "not_allowed_when_cancelled"),
        (4, "action", "change_without_details"),
        (5, "new_ends_at", "required"),
        (6, "new_ends_at", "times_out_of_order"),
        (7, "new_date", "outside_semester"),
        (8, "date", "outside_semester"),
        (9, "date", "no_class_on_date"),
        (10, "teacher_id", "unknown_reference"),
    ]


async def test_change_import_is_idempotent_and_updates_by_occurrence(
    client: AsyncClient, upload: Upload, seed: Seed, aysel: Headers
) -> None:
    await seed(ImportKind.SCHEDULE_CHANGES)
    changes = (SEED_DIR / "schedule_changes.csv").read_text(encoding="utf-8")

    again = await upload(ImportKind.SCHEDULE_CHANGES, changes, file_name="deyisiklikler.csv")
    assert again["summary"] == {"created": 0, "updated": 0, "unchanged": 8, "removed": 0}

    # The same occurrence written again: the substitute changes, no second change is created.
    header = changes.splitlines()[0]
    applied = await upload(
        ImportKind.SCHEDULE_CHANGES,
        f"{header}\nXDL-2103,2026,Payız,765a2,,2026-10-29,08:30,dəyişiklik,,,,1-207,,\n",
        apply=True,
    )
    assert applied["summary"] == {"created": 0, "updated": 1, "unchanged": 0, "removed": 0}
    thursday = (await week(client, aysel, "2026-10-29", "2026-10-29"))["days"][0]["classes"]
    language = next(c for c in thursday if c["subject"]["code"] == "XDL-2103")
    assert language["room"]["code"] == "1-207"
    assert language["teachers"] == ["Səbinə Quliyeva"]
    assert language["room_changed"]
    assert not language["teacher_changed"]


async def test_week_parity_import(upload: Upload, seed: Seed) -> None:
    await seed(ImportKind.ROOMS)
    preview = await upload(
        ImportKind.WEEK_PARITY,
        "year,term,week_starts_on,parity\n"
        "2026,Payız,2026-11-16,üst\n"
        "2026,Payız,2026-11-17,alt\n"
        "2026,Payız,2027-03-01,alt\n"
        "2026,Payız,2026-11-23,hər həftə\n"
        "2030,Payız,2030-11-18,alt\n",
    )
    assert [(e["row"], e["column"], e["code"]) for e in preview["errors"]] == [
        (3, "week_starts_on", "not_monday"),
        (4, "week_starts_on", "outside_semester"),
        (5, "parity", "invalid_choice"),
        (6, "year", "unknown_reference"),
    ]
