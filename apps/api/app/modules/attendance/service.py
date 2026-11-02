import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import and_, delete, exists, func, or_, select, true, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.core.ratelimit import RateLimit, enforce_rate_limit
from app.core.time import baku_today, utc_now
from app.modules.academics.coursework import offering_labels, teaching
from app.modules.academics.models import (
    AcademicGroup,
    CourseOffering,
    CourseOfferingGroup,
    Enrollment,
    EnrollmentStatus,
    Semester,
)
from app.modules.attendance import codes
from app.modules.attendance.models import AttendanceRecord, AttendanceSession, CheckInMethod
from app.modules.attendance.schemas import (
    AttendanceCheckInIn,
    AttendanceCheckInOut,
    AttendanceCodeOut,
    AttendanceMarkIn,
    AttendanceOfferingOut,
    AttendanceReportOut,
    AttendanceReportRowOut,
    AttendanceReportSessionOut,
    AttendanceRosterEntryOut,
    AttendanceSessionDetailOut,
    AttendanceSessionOpenIn,
    AttendanceSessionOut,
    MyAttendanceOut,
    MyAttendanceSessionOut,
)
from app.modules.audit.models import AuditAction
from app.modules.audit.service import record_audit
from app.modules.health.metrics import ATTENDANCE_CHECKINS
from app.modules.users.models import User
from app.modules.users.service import CurrentUser

MANAGE = "attendance.manage"

# A code is six digits, so guessing is bounded per student; the device limit stops one phone sweeping for friends.
USER_CHECK_IN = RateLimit("attendance_user", limit=12, window_seconds=60)
DEVICE_CHECK_IN = RateLimit("attendance_device", limit=60, window_seconds=60)
SCREEN_REFRESH = RateLimit("attendance_screen", limit=60, window_seconds=60)


def _rate(attended: int, total: int) -> float:
    return round(attended / total, 4) if total else 0.0


class AttendanceService:
    def __init__(self, session: AsyncSession, cache: Redis, settings: Settings) -> None:
        self.session = session
        self.cache = cache
        self.secret = settings.attendance_secret

    # --- who may do what ---------------------------------------------------------------------

    def _managed(self, user: CurrentUser) -> Any:
        return true() if user.has_permission(MANAGE) else CourseOffering.id.in_(teaching(user))

    def _curated(self, user: CurrentUser) -> Any:
        return CourseOffering.id.in_(
            select(CourseOfferingGroup.course_offering_id)
            .join(AcademicGroup, AcademicGroup.id == CourseOfferingGroup.academic_group_id)
            .where(AcademicGroup.curator_id == user.id)
        )

    async def _offering_role(
        self, user: CurrentUser, offering_id: uuid.UUID
    ) -> tuple[str | None, set[uuid.UUID] | None]:
        """``manager``, ``curator`` (with the groups they curate in it) or ``None`` for everyone else."""
        if await self.session.scalar(
            select(exists().where(CourseOffering.id == offering_id, self._managed(user)))
        ):
            return "manager", None
        groups = set(
            await self.session.scalars(
                select(AcademicGroup.id)
                .join(
                    CourseOfferingGroup, CourseOfferingGroup.academic_group_id == AcademicGroup.id
                )
                .where(
                    CourseOfferingGroup.course_offering_id == offering_id,
                    AcademicGroup.curator_id == user.id,
                )
            )
        )
        return ("curator", groups) if groups else (None, None)

    async def _managed_session(self, user: CurrentUser, session_id: uuid.UUID) -> AttendanceSession:
        found = await self.session.get(AttendanceSession, session_id)
        if found is None:
            raise AppError("attendance.not_found", 404)
        role, _ = await self._offering_role(user, found.course_offering_id)
        if role != "manager":
            raise AppError("attendance.not_found", 404)
        return found

    async def offerings(self, user: CurrentUser) -> list[AttendanceOfferingOut]:
        """Offerings of semesters that have not finished, which the user runs or reads as a curator."""
        rows = await self.session.execute(
            select(CourseOffering.id, self._managed(user))
            .join(Semester, Semester.id == CourseOffering.semester_id)
            .where(
                or_(self._managed(user), self._curated(user)),
                Semester.ends_on >= baku_today(),
            )
        )
        roles = {offering_id: managed for offering_id, managed in rows}
        labels = await offering_labels(self.session, set(roles))
        found = [
            AttendanceOfferingOut(
                **label.model_dump(),
                role="manager" if roles[uuid.UUID(label.id)] else "curator",
            )
            for label in labels.values()
        ]
        return sorted(found, key=lambda o: (o.subject_name, o.semester, o.groups))

    # --- meetings ----------------------------------------------------------------------------

    async def open_session(
        self, user: CurrentUser, body: AttendanceSessionOpenIn
    ) -> AttendanceSessionOut:
        role, _ = await self._offering_role(user, body.course_offering_id)
        if role != "manager":
            raise AppError("attendance.offering_not_found", 404)
        # A meeting nobody closed ends when its check-in window does, so the next one can start.
        await self.session.execute(
            update(AttendanceSession)
            .where(
                AttendanceSession.course_offering_id == body.course_offering_id,
                AttendanceSession.closed_at.is_(None),
                AttendanceSession.expires_at <= utc_now(),
            )
            .values(closed_at=AttendanceSession.expires_at)
        )
        now = utc_now()
        meeting = AttendanceSession(
            course_offering_id=body.course_offering_id,
            opened_by=user.id,
            title=body.title.strip(),
            opened_at=now,
            expires_at=now + timedelta(minutes=body.duration_minutes),
        )
        self.session.add(meeting)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            raise AppError("attendance.session_open", 409) from exc
        await self.session.commit()
        return (await self._summaries([meeting.id]))[0]

    async def close_session(self, user: CurrentUser, session_id: uuid.UUID) -> AttendanceSessionOut:
        meeting = await self._managed_session(user, session_id)
        if meeting.closed_at is None:
            meeting.closed_at = min(utc_now(), meeting.expires_at)
            await self.session.commit()
        return (await self._summaries([session_id]))[0]

    async def sessions(
        self, user: CurrentUser, offering_id: uuid.UUID, limit: int = 50
    ) -> list[AttendanceSessionOut]:
        role, _ = await self._offering_role(user, offering_id)
        if role is None:
            raise AppError("attendance.offering_not_found", 404)
        ids = list(
            await self.session.scalars(
                select(AttendanceSession.id)
                .where(AttendanceSession.course_offering_id == offering_id)
                .order_by(AttendanceSession.opened_at.desc())
                .limit(limit)
            )
        )
        return await self._summaries(ids)

    async def _summaries(self, ids: list[uuid.UUID]) -> list[AttendanceSessionOut]:
        if not ids:
            return []
        present = (
            select(func.count())
            .where(AttendanceRecord.session_id == AttendanceSession.id)
            .correlate(AttendanceSession)
            .scalar_subquery()
        )
        enrolled = (
            select(func.count())
            .where(
                Enrollment.course_offering_id == AttendanceSession.course_offering_id,
                Enrollment.status == EnrollmentStatus.ACTIVE,
            )
            .correlate(AttendanceSession)
            .scalar_subquery()
        )
        rows = (
            await self.session.execute(
                select(AttendanceSession, present, enrolled)
                .where(AttendanceSession.id.in_(ids))
                .order_by(AttendanceSession.opened_at.desc())
            )
        ).all()
        labels = await offering_labels(self.session, {m.course_offering_id for m, *_ in rows})
        now = utc_now()
        return [
            AttendanceSessionOut(
                id=str(meeting.id),
                offering=labels[meeting.course_offering_id],
                title=meeting.title,
                opened_at=meeting.opened_at,
                expires_at=meeting.expires_at,
                closed_at=meeting.closed_at,
                is_open=meeting.closed_at is None and meeting.expires_at > now,
                present=count,
                enrolled=total,
            )
            for meeting, count, total in rows
        ]

    async def detail(self, user: CurrentUser, session_id: uuid.UUID) -> AttendanceSessionDetailOut:
        meeting = await self._managed_session(user, session_id)
        summary = (await self._summaries([session_id]))[0]
        return AttendanceSessionDetailOut(
            **summary.model_dump(), roster=await self._roster(meeting)
        )

    async def _roster(self, meeting: AttendanceSession) -> list[AttendanceRosterEntryOut]:
        rows = await self.session.execute(
            select(User, AcademicGroup.code, AttendanceRecord)
            .outerjoin(AcademicGroup, AcademicGroup.id == User.academic_group_id)
            .outerjoin(
                AttendanceRecord,
                and_(
                    AttendanceRecord.student_id == User.id,
                    AttendanceRecord.session_id == meeting.id,
                ),
            )
            .where(
                or_(
                    exists().where(
                        Enrollment.user_id == User.id,
                        Enrollment.course_offering_id == meeting.course_offering_id,
                        Enrollment.status == EnrollmentStatus.ACTIVE,
                    ),
                    AttendanceRecord.id.is_not(None),
                )
            )
            .order_by(User.family_name, User.given_name)
        )
        return [
            AttendanceRosterEntryOut(
                student_id=str(student.id),
                display_name=student.display_name,
                university_id=student.university_id,
                group=group,
                present=record is not None,
                method=record.method.value if record else None,
                checked_in_at=record.checked_in_at if record else None,
                reason=record.reason if record else None,
            )
            for student, group, record in rows
        ]

    async def current_code(self, user: CurrentUser, session_id: uuid.UUID) -> AttendanceCodeOut:
        meeting = await self._managed_session(user, session_id)
        await enforce_rate_limit(self.cache, SCREEN_REFRESH, str(user.id))
        summary = (await self._summaries([session_id]))[0]
        now = utc_now()
        step = codes.step_at(now.timestamp())
        return AttendanceCodeOut(
            qr=codes.qr_code(self.secret, meeting.id, step),
            digits=codes.digits_code(self.secret, meeting.id, step),
            valid_until=datetime.fromtimestamp((step + 1) * codes.STEP_SECONDS, tz=UTC),
            server_time=now,
            present=summary.present,
            enrolled=summary.enrolled,
            is_open=summary.is_open,
        )

    async def mark(
        self,
        user: CurrentUser,
        session_id: uuid.UUID,
        student_id: uuid.UUID,
        body: AttendanceMarkIn,
    ) -> AttendanceRosterEntryOut:
        meeting = await self._managed_session(user, session_id)
        enrolled = await self.session.scalar(
            select(
                exists().where(
                    Enrollment.user_id == student_id,
                    Enrollment.course_offering_id == meeting.course_offering_id,
                    Enrollment.status != EnrollmentStatus.DROPPED,
                )
            )
        )
        if not enrolled:
            raise AppError("attendance.student_not_found", 404)
        reason = body.reason.strip()
        if body.present:
            await self.session.execute(
                insert(AttendanceRecord)
                .values(
                    id=uuid.uuid4(),
                    session_id=session_id,
                    student_id=student_id,
                    method=CheckInMethod.MANUAL,
                    marked_by=user.id,
                    reason=reason,
                )
                .on_conflict_do_update(
                    index_elements=["session_id", "student_id"],
                    set_={"method": CheckInMethod.MANUAL, "marked_by": user.id, "reason": reason},
                )
            )
        else:
            await self.session.execute(
                delete(AttendanceRecord).where(
                    AttendanceRecord.session_id == session_id,
                    AttendanceRecord.student_id == student_id,
                )
            )
        record_audit(
            self.session,
            AuditAction.ATTENDANCE_MARKED if body.present else AuditAction.ATTENDANCE_UNMARKED,
            actor_id=user.id,
            target_type="attendance_session",
            target_id=session_id,
            details={"student_id": str(student_id), "reason": reason},
        )
        await self.session.commit()
        roster = await self._roster(meeting)
        return next(entry for entry in roster if entry.student_id == str(student_id))

    # --- student side ------------------------------------------------------------------------

    async def check_in(
        self, user: CurrentUser, body: AttendanceCheckInIn, device: str
    ) -> AttendanceCheckInOut:
        method = "qr" if body.qr is not None else "code"
        try:
            result = await self._check_in(user, body, device)
        except AppError as exc:
            ATTENDANCE_CHECKINS.labels(method=method, result=exc.code.rsplit(".", 1)[-1]).inc()
            raise
        ATTENDANCE_CHECKINS.labels(
            method=method, result="repeated" if result.already_present else "recorded"
        ).inc()
        return result

    async def _check_in(
        self, user: CurrentUser, body: AttendanceCheckInIn, device: str
    ) -> AttendanceCheckInOut:
        await enforce_rate_limit(self.cache, USER_CHECK_IN, str(user.id))
        await enforce_rate_limit(self.cache, DEVICE_CHECK_IN, device)
        now = utc_now()
        method = CheckInMethod.QR if body.qr is not None else CheckInMethod.CODE
        meeting = (
            await self._session_from_qr(body.qr, now)
            if body.qr is not None
            else await self._session_from_digits(user, body.digits or "", now)
        )
        if meeting.closed_at is not None or meeting.expires_at <= now:
            raise AppError("attendance.session_closed", 409)
        enrolled = await self.session.scalar(
            select(
                exists().where(
                    Enrollment.user_id == user.id,
                    Enrollment.course_offering_id == meeting.course_offering_id,
                    Enrollment.status == EnrollmentStatus.ACTIVE,
                )
            )
        )
        if not enrolled:
            raise AppError("attendance.not_enrolled", 403)
        inserted = await self.session.scalar(
            insert(AttendanceRecord)
            .values(id=uuid.uuid4(), session_id=meeting.id, student_id=user.id, method=method)
            .on_conflict_do_nothing(index_elements=["session_id", "student_id"])
            .returning(AttendanceRecord.id)
        )
        await self.session.commit()
        record = await self.session.scalar(
            select(AttendanceRecord).where(
                AttendanceRecord.session_id == meeting.id, AttendanceRecord.student_id == user.id
            )
        )
        assert record is not None
        labels = await offering_labels(self.session, {meeting.course_offering_id})
        return AttendanceCheckInOut(
            session_id=str(meeting.id),
            offering=labels[meeting.course_offering_id],
            checked_in_at=record.checked_in_at,
            already_present=inserted is None,
        )

    async def _session_from_qr(self, raw: str, now: datetime) -> AttendanceSession:
        scanned = codes.parse_qr(raw)
        if scanned is None:
            raise AppError("attendance.code_invalid", 400)
        status = codes.qr_status(self.secret, scanned, now.timestamp())
        if status == "forged":
            raise AppError("attendance.code_invalid", 400)
        if status == "expired":
            raise AppError("attendance.code_expired", 410)
        meeting = await self.session.get(AttendanceSession, scanned.session_id)
        if meeting is None:
            raise AppError("attendance.code_invalid", 400)
        return meeting

    async def _session_from_digits(
        self, user: CurrentUser, typed: str, now: datetime
    ) -> AttendanceSession:
        """The six digits name no meeting, so they are tried against the student's own open ones."""
        candidates = await self.session.scalars(
            select(AttendanceSession)
            .join(Enrollment, Enrollment.course_offering_id == AttendanceSession.course_offering_id)
            .where(
                Enrollment.user_id == user.id,
                Enrollment.status == EnrollmentStatus.ACTIVE,
                AttendanceSession.closed_at.is_(None),
                AttendanceSession.expires_at > now,
            )
        )
        for meeting in candidates:
            if codes.digits_match(self.secret, meeting.id, typed, now.timestamp()):
                return meeting
        raise AppError("attendance.code_invalid", 400)

    async def mine(self, user: CurrentUser) -> list[MyAttendanceOut]:
        return await self._my_attendance(user, None)

    async def mine_in(self, user: CurrentUser, offering_id: uuid.UUID) -> MyAttendanceOut:
        found = await self._my_attendance(user, offering_id)
        if not found:
            raise AppError("attendance.offering_not_found", 404)
        return found[0]

    async def _my_attendance(
        self, user: CurrentUser, offering_id: uuid.UUID | None
    ) -> list[MyAttendanceOut]:
        offering_ids = set(
            await self.session.scalars(
                select(Enrollment.course_offering_id).where(
                    Enrollment.user_id == user.id,
                    Enrollment.status != EnrollmentStatus.DROPPED,
                    Enrollment.course_offering_id == offering_id if offering_id else true(),
                )
            )
        )
        if not offering_ids:
            return []
        meetings = (
            await self.session.execute(
                select(
                    AttendanceSession,
                    exists().where(
                        AttendanceRecord.session_id == AttendanceSession.id,
                        AttendanceRecord.student_id == user.id,
                    ),
                )
                .where(AttendanceSession.course_offering_id.in_(offering_ids))
                .order_by(AttendanceSession.opened_at.desc())
            )
        ).all()
        labels = await offering_labels(self.session, offering_ids)
        out: list[MyAttendanceOut] = []
        for current in offering_ids:
            mine = [(m, seen) for m, seen in meetings if m.course_offering_id == current]
            attended = sum(1 for _, seen in mine if seen)
            out.append(
                MyAttendanceOut(
                    offering=labels[current],
                    attended=attended,
                    total=len(mine),
                    rate=_rate(attended, len(mine)),
                    sessions=[
                        MyAttendanceSessionOut(
                            id=str(m.id), title=m.title, opened_at=m.opened_at, present=seen
                        )
                        for m, seen in mine
                    ]
                    if offering_id
                    else [],
                )
            )
        return sorted(out, key=lambda o: o.offering.subject_name)

    # --- reports -----------------------------------------------------------------------------

    async def report(self, user: CurrentUser, offering_id: uuid.UUID) -> AttendanceReportOut:
        role, curated = await self._offering_role(user, offering_id)
        if role is None:
            raise AppError("attendance.offering_not_found", 404)
        meetings = list(
            await self.session.scalars(
                select(AttendanceSession)
                .where(AttendanceSession.course_offering_id == offering_id)
                .order_by(AttendanceSession.opened_at)
            )
        )
        marks: dict[uuid.UUID, set[uuid.UUID]] = {}
        for session_id, student_id in await self.session.execute(
            select(AttendanceRecord.session_id, AttendanceRecord.student_id).where(
                AttendanceRecord.session_id.in_([m.id for m in meetings])
            )
        ):
            if (
                student_id is not None
            ):  # a deleted account's rows stay countable but anonymous (D-108)
                marks.setdefault(student_id, set()).add(session_id)
        query = (
            select(User, AcademicGroup.code)
            .outerjoin(AcademicGroup, AcademicGroup.id == User.academic_group_id)
            .where(
                or_(
                    exists().where(
                        Enrollment.user_id == User.id,
                        Enrollment.course_offering_id == offering_id,
                        Enrollment.status != EnrollmentStatus.DROPPED,
                    ),
                    User.id.in_(list(marks)),
                )
            )
            .order_by(User.family_name, User.given_name)
        )
        if curated is not None:
            # A curator reads their own groups, not the whole joint lecture.
            query = query.where(User.academic_group_id.in_(curated))
        rows = [
            AttendanceReportRowOut(
                student_id=str(student.id),
                display_name=student.display_name,
                university_id=student.university_id,
                group=group,
                attended=len(marks.get(student.id, ())),
                total=len(meetings),
                rate=_rate(len(marks.get(student.id, ())), len(meetings)),
                marks=[m.id in marks.get(student.id, ()) for m in meetings],
            )
            for student, group in await self.session.execute(query)
        ]
        labels = await offering_labels(self.session, {offering_id})
        return AttendanceReportOut(
            offering=labels[offering_id],
            sessions=[
                AttendanceReportSessionOut(id=str(m.id), title=m.title, opened_at=m.opened_at)
                for m in meetings
            ],
            rows=rows,
        )
