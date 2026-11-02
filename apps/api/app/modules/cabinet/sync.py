"""The nightly sync of the cabinet mirror (D-126).

A run first asks the provider about every active student, holding nothing in the database, and only then writes
everything in one transaction. So a source that fails half-way changes no mirror row (§13.5); the only trace is a
failed run. Writing is a diff by natural keys: re-running with the same answers touches nothing but the sync time,
and two runs that overlap leave the answer of whichever applied last.
"""

import asyncio
import uuid
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.modules.academics.models import (
    CourseOffering,
    Enrollment,
    EnrollmentStatus,
    Semester,
    SemesterTerm,
    Subject,
)
from app.modules.audit.models import AuditAction
from app.modules.audit.service import record_audit
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
from app.modules.cabinet.provider import (
    CabinetAppeals,
    CabinetGrades,
    CabinetMismatchError,
    CabinetNotFoundError,
    CabinetProvider,
    CabinetTranscript,
    CabinetUnavailableError,
)
from app.modules.users.models import PersonType, User, UserStatus

logger = structlog.get_logger(__name__)

# Held for the duration of the write transaction, so two runs never interleave their changes.
ADVISORY_LOCK_KEY = 0x5CAB_17E7
PARALLEL_REQUESTS = 8
CHUNK = 500

type CourseKey = tuple[str, int, SemesterTerm]


@dataclass(frozen=True, slots=True)
class Snapshot:
    user_id: uuid.UUID
    grades: CabinetGrades
    transcript: CabinetTranscript
    appeals: CabinetAppeals


@dataclass(slots=True)
class Fetched:
    snapshots: list[Snapshot]
    not_found: list[uuid.UUID]
    mismatched: list[uuid.UUID]


def _chunks[T](items: Sequence[T]) -> Iterator[Sequence[T]]:
    for start in range(0, len(items), CHUNK):
        yield items[start : start + CHUNK]


class CabinetSync:
    def __init__(self, session: AsyncSession, provider: CabinetProvider) -> None:
        self.session = session
        self.provider = provider

    async def run(
        self, trigger: SyncTrigger, triggered_by: uuid.UUID | None = None
    ) -> CabinetSyncRun | None:
        """Returns the recorded run, or None when another run holds the lock at this very moment."""
        started = utc_now()
        try:
            people = await self._people()
            # Nothing is held open while the network is waited on.
            await self.session.rollback()
            fetched = await self._fetch(people)
            return await self._apply(fetched, people, trigger, triggered_by, started)
        except CabinetUnavailableError:
            logger.warning("cabinet_sync_failed", reason="unavailable")
            return await self._record_failure(trigger, triggered_by, started, "cabinet.unavailable")
        except Exception:
            logger.exception("cabinet_sync_failed", reason="internal")
            await self._record_failure(trigger, triggered_by, started, "internal")
            raise

    async def _people(self) -> dict[uuid.UUID, str]:
        rows = await self.session.execute(
            select(User.id, User.university_id).where(
                User.person_type == PersonType.STUDENT,
                User.status == UserStatus.ACTIVE,
                User.university_id.is_not(None),
            )
        )
        return {user_id: university_id for user_id, university_id in rows if university_id}

    async def _fetch(self, people: dict[uuid.UUID, str]) -> Fetched:
        fetched = Fetched([], [], [])
        gate = asyncio.Semaphore(PARALLEL_REQUESTS)

        async def one(user_id: uuid.UUID, university_id: str) -> None:
            async with gate:
                try:
                    grades = await self.provider.grades(university_id)
                    transcript = await self.provider.transcript(university_id)
                    appeals = await self.provider.appeals(university_id)
                    answered = {
                        grades.university_id,
                        transcript.university_id,
                        appeals.university_id,
                    }
                    if answered != {university_id}:
                        raise CabinetMismatchError(university_id)
                except CabinetNotFoundError:
                    fetched.not_found.append(user_id)
                except CabinetMismatchError:
                    # Never trusted, never stored; the person keeps whatever the mirror held before.
                    fetched.mismatched.append(user_id)
                else:
                    fetched.snapshots.append(Snapshot(user_id, grades, transcript, appeals))

        tasks = [
            asyncio.create_task(one(user_id, university_id))
            for user_id, university_id in people.items()
        ]
        try:
            await asyncio.gather(*tasks)
        except BaseException:
            # The first failure ends the run; the requests still in flight are not waited for.
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
        return fetched

    async def _apply(
        self,
        fetched: Fetched,
        people: dict[uuid.UUID, str],
        trigger: SyncTrigger,
        triggered_by: uuid.UUID | None,
        started: datetime,
    ) -> CabinetSyncRun | None:
        locked = await self.session.scalar(
            select(func.pg_try_advisory_xact_lock(ADVISORY_LOCK_KEY))
        )
        if not locked:
            await self.session.rollback()
            logger.info("cabinet_sync_skipped", reason="another run is writing")
            return None
        now = utc_now()
        synced = [snapshot.user_id for snapshot in fetched.snapshots]

        # People the cabinet no longer knows, and accounts that stopped being active students, leave the mirror.
        gone = [*fetched.not_found, *await self._mirrored_users_outside(people)]
        for table in (
            CabinetStudent,
            CabinetGrade,
            CabinetSemester,
            CabinetAppeal,
            CabinetConflict,
        ):
            for chunk in _chunks(gone):
                await self.session.execute(delete(table).where(table.user_id.in_(chunk)))

        await self._reconcile(
            CabinetStudent,
            synced,
            {
                (s.user_id,): {
                    "user_id": s.user_id,
                    "specialty_name": s.transcript.specialty_name,
                    "credits_earned": s.transcript.credits_earned,
                    "cumulative_average": s.transcript.cumulative_average,
                    "synced_at": now,
                }
                for s in fetched.snapshots
            },
            ("user_id",),
        )
        await self._reconcile(
            CabinetGrade,
            synced,
            {
                (s.user_id, g.subject_code, g.semester_year, g.semester_term): {
                    "user_id": s.user_id,
                    "subject_code": g.subject_code,
                    "subject_name": g.subject_name,
                    "credits": g.credits,
                    "semester_year": g.semester_year,
                    "semester_term": g.semester_term,
                    "score": g.score,
                    "passed": g.passed,
                }
                for s in fetched.snapshots
                for g in s.grades.items
            },
            ("user_id", "subject_code", "semester_year", "semester_term"),
        )
        await self._reconcile(
            CabinetSemester,
            synced,
            {
                (s.user_id, m.semester_year, m.semester_term): {
                    "user_id": s.user_id,
                    "semester_year": m.semester_year,
                    "semester_term": m.semester_term,
                    "credits_attempted": m.credits_attempted,
                    "credits_earned": m.credits_earned,
                    "average": m.average,
                }
                for s in fetched.snapshots
                for m in s.transcript.semesters
            },
            ("user_id", "semester_year", "semester_term"),
        )
        await self._reconcile(
            CabinetAppeal,
            synced,
            {
                (s.user_id, a.reference): {
                    "user_id": s.user_id,
                    "reference": a.reference,
                    "subject_code": a.subject_code,
                    "semester_year": a.semester_year,
                    "semester_term": a.semester_term,
                    "status": a.status,
                    "submitted_on": a.submitted_on,
                    "decided_on": a.decided_on,
                }
                for s in fetched.snapshots
                for a in s.appeals.items
            },
            ("user_id", "reference"),
        )
        await self._reconcile_conflicts(fetched.snapshots)
        await self.session.flush()

        conflicts = await self.session.scalar(select(func.count()).select_from(CabinetConflict))
        run = CabinetSyncRun(
            trigger=trigger,
            triggered_by=triggered_by,
            outcome=SyncOutcome.SUCCEEDED,
            started_at=started,
            finished_at=utc_now(),
            students_synced=len(synced),
            students_not_found=len(fetched.not_found),
            students_mismatched=len(fetched.mismatched),
            conflicts=conflicts or 0,
        )
        self.session.add(run)
        self._audit(run)
        await self.session.commit()
        logger.info(
            "cabinet_sync_finished",
            synced=run.students_synced,
            not_found=run.students_not_found,
            mismatched=run.students_mismatched,
            conflicts=run.conflicts,
        )
        return run

    async def _mirrored_users_outside(self, people: dict[uuid.UUID, str]) -> list[uuid.UUID]:
        mirrored = set(await self.session.scalars(select(CabinetStudent.user_id)))
        return sorted(mirrored - people.keys())

    async def _reconcile(
        self,
        model: Any,
        user_ids: Sequence[uuid.UUID],
        wanted: dict[tuple[Any, ...], dict[str, Any]],
        key_columns: tuple[str, ...],
    ) -> None:
        """Makes the stored rows of these users equal ``wanted``: updates what differs, adds, removes."""
        for chunk in _chunks(user_ids):
            existing = {
                tuple(getattr(row, column) for column in key_columns): row
                for row in await self.session.scalars(select(model).where(model.user_id.in_(chunk)))
            }
            members = set(chunk)
            for key, values in wanted.items():
                if values["user_id"] not in members:
                    continue
                row = existing.pop(key, None)
                if row is None:
                    self.session.add(model(**values))
                    continue
                for column, value in values.items():
                    if getattr(row, column) != value:
                        setattr(row, column, value)
            for row in existing.values():
                await self.session.delete(row)

    async def _reconcile_conflicts(self, snapshots: list[Snapshot]) -> None:
        """A conflict is a completed registry enrollment with a grade the mirror disagrees with. The registry
        keeps its value (D-126); only the course is recorded."""
        mirror: dict[uuid.UUID, dict[CourseKey, int]] = {
            s.user_id: {
                (g.subject_code, g.semester_year, g.semester_term): g.score for g in s.grades.items
            }
            for s in snapshots
        }
        user_ids = list(mirror)
        wanted: dict[tuple[Any, ...], dict[str, Any]] = {}
        for chunk in _chunks(user_ids):
            rows = await self.session.execute(
                select(
                    Enrollment.user_id, Subject.code, Semester.year, Semester.term, Enrollment.grade
                )
                .join(CourseOffering, CourseOffering.id == Enrollment.course_offering_id)
                .join(Subject, Subject.id == CourseOffering.subject_id)
                .join(Semester, Semester.id == CourseOffering.semester_id)
                .where(
                    Enrollment.user_id.in_(chunk),
                    Enrollment.status == EnrollmentStatus.COMPLETED,
                    Enrollment.grade.is_not(None),
                )
            )
            for user_id, code, year, term, grade in rows:
                theirs = mirror[user_id].get((code, year, term))
                if theirs is not None and theirs != grade:
                    wanted[(user_id, code, year, term)] = {
                        "user_id": user_id,
                        "subject_code": code,
                        "semester_year": year,
                        "semester_term": term,
                    }
        await self._reconcile(
            CabinetConflict,
            user_ids,
            wanted,
            ("user_id", "subject_code", "semester_year", "semester_term"),
        )

    async def _record_failure(
        self,
        trigger: SyncTrigger,
        triggered_by: uuid.UUID | None,
        started: datetime,
        error_code: str,
    ) -> CabinetSyncRun:
        await self.session.rollback()
        run = CabinetSyncRun(
            trigger=trigger,
            triggered_by=triggered_by,
            outcome=SyncOutcome.FAILED,
            started_at=started,
            finished_at=utc_now(),
            students_synced=0,
            students_not_found=0,
            students_mismatched=0,
            conflicts=0,
            error_code=error_code,
        )
        self.session.add(run)
        self._audit(run)
        await self.session.commit()
        return run

    def _audit(self, run: CabinetSyncRun) -> None:
        # Counts and an outcome only: no student, subject or grade (§5.4).
        record_audit(
            self.session,
            AuditAction.CABINET_SYNC_RUN,
            actor_id=run.triggered_by,
            details={
                "trigger": run.trigger.value,
                "outcome": run.outcome.value,
                "students_synced": run.students_synced,
                "students_not_found": run.students_not_found,
                "students_mismatched": run.students_mismatched,
                "conflicts": run.conflicts,
                "error_code": run.error_code,
            },
        )
