"""The nightly sync: matching, conflicts, idempotence, outages (D-126, §13.1, §13.5)."""

import asyncio
from collections.abc import Awaitable, Callable

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.modules.academics.models import (
    CourseOffering,
    Enrollment,
    ImportKind,
    Semester,
    Subject,
)
from app.modules.audit.models import AuditAction, AuditLog
from app.modules.cabinet.fake import FakeCabinetProvider
from app.modules.cabinet.models import (
    CabinetAppeal,
    CabinetConflict,
    CabinetGrade,
    CabinetSemester,
    CabinetStudent,
    CabinetSyncRun,
    SyncOutcome,
    SyncTrigger,
)
from app.modules.cabinet.provider import CabinetGrades, CabinetUnavailableError
from app.modules.cabinet.schemas import SourceState
from app.modules.cabinet.service import CabinetReadService
from app.modules.cabinet.sync import ADVISORY_LOCK_KEY, CabinetSync
from app.modules.chat.tests.conftest import MakePerson
from app.modules.users.models import PersonType, User

Seed = Callable[..., Awaitable[None]]

AYSEL = "25765201"
RAMIN = "25765202"
STUDENTS = 47  # the sample data has 48 students, one of them inactive


@pytest.fixture
async def seeded(seed: Seed) -> None:
    await seed(ImportKind.ENROLLMENTS)


@pytest.fixture
def cabinet() -> FakeCabinetProvider:
    return FakeCabinetProvider()


async def user_of(db: AsyncSession, university_id: str) -> User:
    user = await db.scalar(select(User).where(User.university_id == university_id))
    assert user is not None
    # A run rolls the session back before it waits for the network; a loaded row would be expired by that.
    db.expunge(user)
    return user


async def sync(
    db: AsyncSession, cabinet: FakeCabinetProvider, trigger: SyncTrigger = SyncTrigger.NIGHTLY
) -> CabinetSyncRun:
    run = await CabinetSync(db, cabinet).run(trigger)
    assert run is not None
    return run


async def count(db: AsyncSession, model: type) -> int:
    return await db.scalar(select(func.count()).select_from(model)) or 0


async def set_registry_grade(
    db: AsyncSession, university_id: str, subject: str, grade: int
) -> None:
    user = await user_of(db, university_id)
    offerings = select(CourseOffering.id).join(Subject).where(Subject.code == subject)
    await db.execute(
        update(Enrollment)
        .where(Enrollment.user_id == user.id, Enrollment.course_offering_id.in_(offerings))
        .values(grade=grade, passed=grade >= 51)
    )
    await db.commit()


async def test_every_active_student_is_mirrored_by_university_id(
    seeded: None, db: AsyncSession, cabinet: FakeCabinetProvider
) -> None:
    run = await sync(db, cabinet)

    assert run.outcome is SyncOutcome.SUCCEEDED
    assert run.students_synced == STUDENTS
    assert await count(db, CabinetStudent) == STUDENTS
    assert await count(db, CabinetGrade) == STUDENTS * 10
    assert await count(db, CabinetSemester) == STUDENTS * 2
    aysel = await user_of(db, AYSEL)
    expected = {g.subject_code: g.score for g in (await cabinet.grades(AYSEL)).items}
    stored = await db.scalars(select(CabinetGrade).where(CabinetGrade.user_id == aysel.id))
    assert {g.subject_code: g.score for g in stored} == expected


async def test_teachers_and_people_without_a_university_id_are_not_synced(
    seeded: None, db: AsyncSession, cabinet: FakeCabinetProvider, person: MakePerson
) -> None:
    stranger = await person("Orxan", "Rzayev")
    teacher = await user_of(db, "T-10457")
    assert teacher.person_type is PersonType.TEACHER

    await sync(db, cabinet)

    mirrored = set(await db.scalars(select(CabinetStudent.user_id)))
    assert stranger.id not in mirrored
    assert teacher.id not in mirrored


async def test_an_email_alone_never_matches_a_record(
    seeded: None, db: AsyncSession, cabinet: FakeCabinetProvider
) -> None:
    """The source is asked for a university ID only: an account whose e-mail equals a student's but which carries
    no ID of its own gets nothing (D-029 stays for sign-in; the mirror uses the ID)."""
    aysel = await user_of(db, AYSEL)
    await db.execute(update(User).where(User.id == aysel.id).values(university_id=None))
    await db.commit()

    await sync(db, cabinet)

    assert aysel.id not in set(await db.scalars(select(CabinetStudent.user_id)))
    assert await count(db, CabinetStudent) == STUDENTS - 1


async def test_a_second_run_with_the_same_answers_changes_no_row(
    seeded: None, db: AsyncSession, cabinet: FakeCabinetProvider
) -> None:
    await sync(db, cabinet)
    before = {row.id: row.score for row in await db.scalars(select(CabinetGrade))}
    appeals_before = {row.id for row in await db.scalars(select(CabinetAppeal))}

    second = await sync(db, cabinet)
    outcome = second.outcome
    db.expire_all()

    assert outcome is SyncOutcome.SUCCEEDED
    assert {row.id: row.score for row in await db.scalars(select(CabinetGrade))} == before
    assert {row.id for row in await db.scalars(select(CabinetAppeal))} == appeals_before
    assert await count(db, CabinetSyncRun) == 2


async def test_a_changed_score_is_updated_in_place(
    seeded: None, db: AsyncSession, cabinet: FakeCabinetProvider
) -> None:
    await sync(db, cabinet)
    aysel = await user_of(db, AYSEL)
    row = await db.scalar(
        select(CabinetGrade).where(
            CabinetGrade.user_id == aysel.id, CabinetGrade.subject_code == "IQT-1201"
        )
    )
    assert row is not None
    row_id, old = row.id, row.score

    cabinet.set_score(AYSEL, "IQT-1201", 100 if old != 100 else 99)
    await sync(db, cabinet)
    db.expire_all()

    changed = await db.get(CabinetGrade, row_id)
    assert changed is not None
    assert changed.score != old


async def test_a_person_the_cabinet_forgot_leaves_the_mirror(
    seeded: None, db: AsyncSession, cabinet: FakeCabinetProvider
) -> None:
    await sync(db, cabinet)
    aysel = await user_of(db, AYSEL)

    cabinet.drop(AYSEL)
    run = await sync(db, cabinet)

    assert run.students_not_found == 1
    assert await db.get(CabinetStudent, aysel.id) is None
    assert await db.scalar(select(func.count()).where(CabinetGrade.user_id == aysel.id)) == 0


async def test_an_answer_about_someone_else_is_never_stored(
    seeded: None, db: AsyncSession, cabinet: FakeCabinetProvider
) -> None:
    cabinet.answer_for_someone_else(AYSEL)

    run = await sync(db, cabinet)

    assert run.students_mismatched == 1
    assert run.outcome is SyncOutcome.SUCCEEDED
    aysel = await user_of(db, AYSEL)
    assert await db.get(CabinetStudent, aysel.id) is None
    assert await count(db, CabinetStudent) == STUDENTS - 1


async def test_a_mismatch_keeps_what_was_mirrored_before(
    seeded: None, db: AsyncSession, cabinet: FakeCabinetProvider
) -> None:
    await sync(db, cabinet)
    aysel = await user_of(db, AYSEL)

    cabinet.answer_for_someone_else(AYSEL)
    await sync(db, cabinet)

    assert await db.get(CabinetStudent, aysel.id) is not None


async def test_an_outage_changes_nothing_and_is_recorded(
    seeded: None, db: AsyncSession, cabinet: FakeCabinetProvider
) -> None:
    await sync(db, cabinet)
    before = {row.id: row.score for row in await db.scalars(select(CabinetGrade))}
    cabinet.set_score(AYSEL, "IQT-1201", 11)

    cabinet.break_connection()
    run = await sync(db, cabinet)
    outcome, error_code, synced = run.outcome, run.error_code, run.students_synced
    db.expire_all()

    assert outcome is SyncOutcome.FAILED
    assert error_code == "cabinet.unavailable"
    assert synced == 0
    assert {row.id: row.score for row in await db.scalars(select(CabinetGrade))} == before
    source = await CabinetReadService(db).source()
    assert source.state is SourceState.UNAVAILABLE
    assert source.last_synced_at is not None


class FailsAfter(FakeCabinetProvider):
    """Answers the first few students, then loses the connection: the run must not keep the early answers."""

    def __init__(self, answers: int) -> None:
        super().__init__()
        self.left = answers

    async def grades(self, university_id: str) -> CabinetGrades:
        self.left -= 1
        if self.left < 0:
            raise CabinetUnavailableError("gone")
        return await super().grades(university_id)


async def test_an_outage_half_way_through_leaves_no_partial_mirror(
    seeded: None, db: AsyncSession
) -> None:
    run = await CabinetSync(db, FailsAfter(20)).run(SyncTrigger.NIGHTLY)

    assert run is not None
    assert run.outcome is SyncOutcome.FAILED
    assert await count(db, CabinetStudent) == 0
    assert await count(db, CabinetGrade) == 0
    source = await CabinetReadService(db).source()
    assert (source.state, source.last_synced_at) == (SourceState.UNAVAILABLE, None)


async def test_a_bug_is_recorded_and_raised(
    seeded: None, db: AsyncSession, cabinet: FakeCabinetProvider
) -> None:
    class Broken(FakeCabinetProvider):
        async def appeals(self, university_id: str):  # type: ignore[no-untyped-def]
            raise ZeroDivisionError

    with pytest.raises(ZeroDivisionError):
        await CabinetSync(db, Broken()).run(SyncTrigger.NIGHTLY)

    failed = await db.scalar(select(CabinetSyncRun))
    assert failed is not None
    assert failed.error_code == "internal"


async def test_a_different_grade_in_the_registry_is_a_conflict_and_the_registry_wins(
    seeded: None, db: AsyncSession, cabinet: FakeCabinetProvider
) -> None:
    cabinet.set_score(AYSEL, "SOS-1101", 60)
    await set_registry_grade(db, AYSEL, "SOS-1101", 87)

    run = await sync(db, cabinet)

    assert run.conflicts == 1
    conflict = await db.scalar(select(CabinetConflict))
    assert conflict is not None
    assert (conflict.subject_code, conflict.semester_year) == ("SOS-1101", 2025)
    aysel = await user_of(db, AYSEL)
    transcript = await CabinetReadService(db).transcript(aysel.id)
    course = next(
        c for s in transcript.semesters for c in s.courses if c.subject_code == "SOS-1101"
    )
    assert (course.score, course.differs) == (87, True)
    # The registry row itself is untouched: the mirror never writes to it (§13.1).
    enrollment = await db.scalar(
        select(Enrollment.grade)
        .join(CourseOffering)
        .join(Subject)
        .join(Semester, Semester.id == CourseOffering.semester_id)
        .where(Enrollment.user_id == aysel.id, Subject.code == "SOS-1101", Semester.year == 2025)
    )
    assert enrollment == 87


async def test_agreeing_grades_are_no_conflict_and_a_fixed_one_clears_it(
    seeded: None, db: AsyncSession, cabinet: FakeCabinetProvider
) -> None:
    cabinet.set_score(AYSEL, "SOS-1101", 87)
    await set_registry_grade(db, AYSEL, "SOS-1101", 87)
    assert (await sync(db, cabinet)).conflicts == 0

    await set_registry_grade(db, AYSEL, "SOS-1101", 70)
    assert (await sync(db, cabinet)).conflicts == 1

    await set_registry_grade(db, AYSEL, "SOS-1101", 87)
    assert (await sync(db, cabinet)).conflicts == 0
    assert await count(db, CabinetConflict) == 0


async def test_registry_courses_without_a_grade_are_no_conflict(
    seeded: None, db: AsyncSession, cabinet: FakeCabinetProvider
) -> None:
    """The cabinet fills a gap the registry has; it does not disagree with it."""
    await db.execute(update(Enrollment).values(grade=None))
    await db.commit()

    assert (await sync(db, cabinet)).conflicts == 0


async def test_the_run_is_audited_with_counts_and_no_values(
    seeded: None, db: AsyncSession, cabinet: FakeCabinetProvider
) -> None:
    await sync(db, cabinet)

    entry = await db.scalar(select(AuditLog).where(AuditLog.action == AuditAction.CABINET_SYNC_RUN))
    assert entry is not None
    assert entry.actor_id is None
    assert set(entry.details) == {
        "trigger",
        "outcome",
        "students_synced",
        "students_not_found",
        "students_mismatched",
        "conflicts",
        "error_code",
    }
    assert entry.details["students_synced"] == STUDENTS
    assert AYSEL not in str(entry.details)


async def test_a_manual_run_names_who_asked(
    seeded: None, db: AsyncSession, cabinet: FakeCabinetProvider
) -> None:
    staff = await user_of(db, AYSEL)  # any existing account; permission is checked by the router

    run = await CabinetSync(db, cabinet).run(SyncTrigger.MANUAL, staff.id)

    assert run is not None
    assert run.triggered_by == staff.id
    entry = await db.scalar(select(AuditLog).where(AuditLog.action == AuditAction.CABINET_SYNC_RUN))
    assert entry is not None
    assert entry.actor_id == staff.id


async def test_a_run_waits_out_another_run_that_is_writing(
    seeded: None, db: AsyncSession, engine: AsyncEngine, cabinet: FakeCabinetProvider
) -> None:
    async with async_sessionmaker(engine)() as other:
        await other.execute(select(func.pg_advisory_xact_lock(ADVISORY_LOCK_KEY)))

        skipped = await CabinetSync(db, cabinet).run(SyncTrigger.NIGHTLY)
        await other.rollback()

    assert skipped is None
    assert await count(db, CabinetStudent) == 0
    assert await count(db, CabinetSyncRun) == 0


async def test_students_who_stopped_being_active_leave_the_mirror(
    seeded: None, db: AsyncSession, cabinet: FakeCabinetProvider
) -> None:
    await sync(db, cabinet)
    ramin = await user_of(db, RAMIN)
    await db.execute(update(User).where(User.id == ramin.id).values(status="inactive"))
    await db.commit()

    await sync(db, cabinet)

    assert await db.get(CabinetStudent, ramin.id) is None
    assert await count(db, CabinetStudent) == STUDENTS - 1


async def test_concurrent_runs_end_in_the_same_state(
    seeded: None, db: AsyncSession, engine: AsyncEngine, cabinet: FakeCabinetProvider
) -> None:
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def one() -> CabinetSyncRun | None:
        async with maker() as session:
            return await CabinetSync(session, cabinet).run(SyncTrigger.NIGHTLY)

    results = await asyncio.gather(one(), one())

    assert any(result is not None for result in results)
    assert await count(db, CabinetStudent) == STUDENTS
    assert await count(db, CabinetGrade) == STUDENTS * 10
