"""Past papers: exam papers of finished semesters, kept for later students once approved (§6, D-097).

Integrity rules, all enforced here and not only in the form: a paper belongs to a semester that has ended (the
exams of the running semester are never shared, §5.2); its uploader confirms they may share it; nobody but the
uploader sees it until a teacher of the subject or the dean's office approves it; and no one downloads a file
that has not passed the scan.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import and_, exists, func, or_, select, union, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.antivirus import VirusScanner
from app.core.errors import AppError
from app.core.file_scan import UNSAVED_AFTER, check_file
from app.core.ratelimit import RateLimit, enforce_rate_limit
from app.core.storage import ObjectStorage, StorageUnavailableError
from app.core.time import baku_today, utc_now
from app.core.uploads import (
    allowed_extensions,
    allowed_type,
    content_disposition,
    safe_filename,
)
from app.modules.academics.models import (
    CourseOffering,
    CourseOfferingTeacher,
    Enrollment,
    EnrollmentStatus,
    Semester,
    Subject,
)
from app.modules.audiences.service import TERM_NAMES
from app.modules.audit.models import AuditAction
from app.modules.audit.service import record_audit
from app.modules.chat.models import ScanStatus
from app.modules.exams.models import PastPaper, PastPaperStatus
from app.modules.exams.notifications import notify_paper_decision
from app.modules.exams.schemas import (
    FinishedSemesterOut,
    PaperDownloadOut,
    PaperFormOut,
    PaperIn,
    PaperListOut,
    PaperOut,
    PaperReviewIn,
    PaperSubjectListOut,
    PaperSubjectOut,
    PaperUploadIn,
    PaperUploadOut,
)
from app.modules.users.service import CurrentUser

MANAGE = "exams.manage"
MAX_FILE_SIZE = 25 * 1024 * 1024
UPLOAD_TTL = timedelta(minutes=10)
DOWNLOAD_TTL = timedelta(minutes=1)
UPLOAD_LIMIT = RateLimit("past_paper_upload", limit=20, window_seconds=3600)


@dataclass(frozen=True, slots=True)
class SubjectAccess:
    read: bool
    review: bool


def _term(semester: Semester) -> str:
    return f"{semester.year} {TERM_NAMES[semester.term]}"


class PastPaperService:
    def __init__(self, session: AsyncSession, storage: ObjectStorage, cache: Redis) -> None:
        self.session = session
        self.storage = storage
        self.cache = cache

    # --- who may do what ---------------------------------------------------------------------

    async def _access(self, user: CurrentUser, subject_id: uuid.UUID) -> SubjectAccess:
        if await self.session.get(Subject, subject_id) is None:
            return SubjectAccess(False, False)
        manage = user.has_permission(MANAGE)
        teaches = await self.session.scalar(
            select(
                exists().where(
                    CourseOffering.subject_id == subject_id,
                    CourseOfferingTeacher.course_offering_id == CourseOffering.id,
                    CourseOfferingTeacher.teacher_id == user.id,
                )
            )
        )
        enrolled = await self.session.scalar(
            select(
                exists().where(
                    CourseOffering.subject_id == subject_id,
                    Enrollment.course_offering_id == CourseOffering.id,
                    Enrollment.user_id == user.id,
                    Enrollment.status != EnrollmentStatus.DROPPED,
                )
            )
        )
        return SubjectAccess(
            read=bool(manage or teaches or enrolled), review=bool(manage or teaches)
        )

    async def _readable(self, user: CurrentUser, subject_id: uuid.UUID) -> SubjectAccess:
        access = await self._access(user, subject_id)
        if not access.read:
            # The same answer as a subject that does not exist (§14).
            raise AppError("exams.subject_not_found", 404)
        return access

    # --- reading -----------------------------------------------------------------------------

    async def subjects(self, user: CurrentUser) -> PaperSubjectListOut:
        """Subjects whose papers the user may open; reviewers see how many wait for them."""
        enrolled = (
            select(CourseOffering.subject_id)
            .join(Enrollment, Enrollment.course_offering_id == CourseOffering.id)
            .where(Enrollment.user_id == user.id, Enrollment.status != EnrollmentStatus.DROPPED)
        )
        taught = (
            select(CourseOffering.subject_id)
            .join(
                CourseOfferingTeacher, CourseOfferingTeacher.course_offering_id == CourseOffering.id
            )
            .where(CourseOfferingTeacher.teacher_id == user.id)
        )
        waiting = select(PastPaper.subject_id).where(
            PastPaper.status == PastPaperStatus.PENDING, PastPaper.submitted_at.is_not(None)
        )
        reachable = (
            union(enrolled, taught, waiting)
            if user.has_permission(MANAGE)
            else union(enrolled, taught)
        )
        subjects = list(
            await self.session.scalars(
                select(Subject).where(Subject.id.in_(reachable)).order_by(Subject.name_az)
            )
        )
        items = []
        for subject in subjects:
            access = await self._access(user, subject.id)
            pending = 0
            if access.review:
                pending = (
                    await self.session.scalar(
                        select(func.count()).where(
                            PastPaper.subject_id == subject.id,
                            PastPaper.status == PastPaperStatus.PENDING,
                            PastPaper.submitted_at.is_not(None),
                        )
                    )
                    or 0
                )
            items.append(
                PaperSubjectOut(
                    id=str(subject.id), code=subject.code, name=subject.name_az, pending=pending
                )
            )
        return PaperSubjectListOut(items=items)

    async def _finished_semesters(self, subject_id: uuid.UUID) -> list[Semester]:
        return list(
            await self.session.scalars(
                select(Semester)
                .where(
                    Semester.ends_on < baku_today(),
                    exists().where(
                        CourseOffering.subject_id == subject_id,
                        CourseOffering.semester_id == Semester.id,
                    ),
                )
                .order_by(Semester.starts_on.desc())
            )
        )

    async def form(self, user: CurrentUser, subject_id: uuid.UUID) -> PaperFormOut:
        await self._readable(user, subject_id)
        return PaperFormOut(
            semesters=[
                FinishedSemesterOut(id=str(s.id), label=_term(s))
                for s in await self._finished_semesters(subject_id)
            ]
        )

    async def papers(self, user: CurrentUser, subject_id: uuid.UUID) -> PaperListOut:
        access = await self._readable(user, subject_id)
        subject = await self.session.get(Subject, subject_id)
        assert subject is not None
        visible = and_(
            PastPaper.status == PastPaperStatus.APPROVED,
            PastPaper.scan_status == ScanStatus.CLEAN,
        )
        mine = PastPaper.uploader_id == user.id
        query = (
            select(PastPaper, Semester)
            .join(Semester, Semester.id == PastPaper.semester_id)
            .where(
                PastPaper.subject_id == subject_id,
                PastPaper.submitted_at.is_not(None),
                PastPaper.purged_at.is_(None),
            )
        )
        query = query if access.review else query.where(or_(visible, mine))
        rows = (
            await self.session.execute(
                query.order_by(Semester.starts_on.desc(), PastPaper.title, PastPaper.id)
            )
        ).all()
        return PaperListOut(
            subject_id=str(subject.id),
            subject_name=subject.name_az,
            can_upload=True,
            items=[self._out(user, access, paper, semester) for paper, semester in rows],
        )

    def _out(
        self, user: CurrentUser, access: SubjectAccess, paper: PastPaper, semester: Semester
    ) -> PaperOut:
        assert paper.kind is not None
        assert paper.title is not None
        clean = paper.scan_status is ScanStatus.CLEAN
        return PaperOut(
            id=str(paper.id),
            subject_id=str(paper.subject_id),
            semester=_term(semester),
            kind=paper.kind,
            title=paper.title,
            filename=paper.filename,
            size_bytes=paper.size_bytes,
            status=paper.status,
            scan_status=paper.scan_status.value,
            uploaded_by_me=paper.uploader_id == user.id,
            can_review=access.review and paper.status is PastPaperStatus.PENDING,
            can_download=clean
            and (
                paper.status is PastPaperStatus.APPROVED
                or paper.uploader_id == user.id
                or access.review
            ),
            review_note=paper.review_note,
            created_at=paper.created_at,
        )

    # --- uploading ---------------------------------------------------------------------------

    async def presign(self, user: CurrentUser, body: PaperUploadIn) -> PaperUploadOut:
        await self._readable(user, body.subject_id)
        kind = allowed_type(body.filename, body.mime)
        if kind is None:
            raise AppError("exams.type_not_allowed", 422, details={"allowed": allowed_extensions()})
        if not 0 < body.size <= MAX_FILE_SIZE:
            raise AppError("exams.too_large", 422, details={"max_bytes": MAX_FILE_SIZE})
        await enforce_rate_limit(self.cache, UPLOAD_LIMIT, str(user.id))
        key = f"past-papers/{body.subject_id}/{uuid.uuid4().hex}"
        try:
            url = await self.storage.presign_put(key, kind, UPLOAD_TTL)
        except StorageUnavailableError as exc:
            raise AppError("exams.storage_unavailable", 503) from exc
        paper = PastPaper(
            subject_id=body.subject_id,
            uploader_id=user.id,
            object_key=key,
            filename=safe_filename(body.filename),
            mime=kind,
            size_bytes=body.size,
        )
        self.session.add(paper)
        await self.session.commit()
        return PaperUploadOut(
            upload_id=str(paper.id),
            url=url,
            expires_at=utc_now() + UPLOAD_TTL,
            required_headers={"Content-Type": kind},
        )

    async def submit(self, user: CurrentUser, body: PaperIn) -> PaperOut:
        paper = await self.session.get(PastPaper, body.upload_id, with_for_update=True)
        if paper is None or paper.uploader_id != user.id:
            raise AppError("exams.upload_not_found", 422)
        access = await self._readable(user, paper.subject_id)
        semester = await self.session.get(Semester, body.semester_id)
        if paper.submitted_at is not None:
            # The same upload sent twice (double click, retry) returns the same paper.
            assert semester is not None
            assert paper.semester_id == semester.id
            return self._out(user, access, paper, semester)
        if not body.consent:
            raise AppError("exams.consent_required", 422)
        if semester is None or semester.id not in {
            s.id for s in await self._finished_semesters(paper.subject_id)
        }:
            raise AppError("exams.semester_not_finished", 422)
        try:
            stored = await self.storage.head(paper.object_key)
        except StorageUnavailableError as exc:
            raise AppError("exams.storage_unavailable", 503) from exc
        if stored is None:
            raise AppError("exams.upload_missing", 422)
        if stored != paper.size_bytes:
            raise AppError("exams.upload_size_mismatch", 422)
        now = utc_now()
        paper.semester_id = semester.id
        paper.kind = body.kind
        paper.title = body.title.strip()
        paper.consented_at = now
        paper.submitted_at = now
        paper.scan_after = now
        if access.review:
            # A teacher of the subject, or the dean's office, approves by uploading.
            paper.status = PastPaperStatus.APPROVED
            paper.reviewed_by = user.id
            paper.reviewed_at = now
        await self.session.commit()
        return self._out(user, access, paper, semester)

    # --- reviewing and downloading -----------------------------------------------------------

    async def review(self, user: CurrentUser, paper_id: uuid.UUID, body: PaperReviewIn) -> PaperOut:
        paper = await self.session.get(PastPaper, paper_id, with_for_update=True)
        if paper is None or paper.submitted_at is None or paper.purged_at is not None:
            raise AppError("exams.paper_not_found", 404)
        access = await self._readable(user, paper.subject_id)
        if not access.review:
            raise AppError("auth.forbidden", 403)
        semester = await self.session.get(Semester, paper.semester_id)
        assert semester is not None
        if body.approve:
            if paper.scan_status is not ScanStatus.CLEAN:
                raise AppError("exams.paper_not_scanned", 409)
            # The rule is checked again: a paper is never published for a semester that has not ended.
            if semester.ends_on >= baku_today():
                raise AppError("exams.semester_not_finished", 409)
        paper.status = PastPaperStatus.APPROVED if body.approve else PastPaperStatus.REJECTED
        paper.reviewed_by = user.id
        paper.reviewed_at = utc_now()
        paper.review_note = body.note.strip() or None
        record_audit(
            self.session,
            AuditAction.PAST_PAPER_REVIEWED,
            actor_id=user.id,
            target_type="past_paper",
            target_id=paper.id,
            details={"approved": body.approve, "subject_id": str(paper.subject_id)},
        )
        await notify_paper_decision(self.session, paper)
        await self.session.commit()
        return self._out(user, access, paper, semester)

    async def download(self, user: CurrentUser, paper_id: uuid.UUID) -> PaperDownloadOut:
        paper = await self.session.get(PastPaper, paper_id)
        if paper is None or paper.submitted_at is None or paper.purged_at is not None:
            raise AppError("exams.paper_not_found", 404)
        access = await self._readable(user, paper.subject_id)
        approved = paper.status is PastPaperStatus.APPROVED
        if not (approved or paper.uploader_id == user.id or access.review):
            raise AppError("exams.paper_not_found", 404)
        if paper.scan_status is not ScanStatus.CLEAN:
            raise AppError("exams.paper_not_available", 409)
        try:
            url = await self.storage.presign_get(
                paper.object_key,
                content_type=paper.mime,
                disposition=content_disposition(paper.filename, False),
                expires=DOWNLOAD_TTL,
            )
        except StorageUnavailableError as exc:
            raise AppError("exams.storage_unavailable", 503) from exc
        return PaperDownloadOut(
            url=url, filename=paper.filename, expires_at=utc_now() + DOWNLOAD_TTL
        )


@dataclass(slots=True)
class PaperScanReport:
    clean: int = 0
    rejected: int = 0
    waiting: int = 0


class PaperScanner:
    """Worker side: the same checks and back-off as material versions and submissions (D-071, D-092)."""

    def __init__(
        self, session: AsyncSession, storage: ObjectStorage, scanner: VirusScanner
    ) -> None:
        self.session = session
        self.storage = storage
        self.scanner = scanner

    async def scan_pending(self, limit: int = 20) -> PaperScanReport:
        report = PaperScanReport()
        for _ in range(limit):
            paper = await self.session.scalar(
                select(PastPaper)
                .where(
                    PastPaper.scan_status == ScanStatus.PENDING,
                    PastPaper.submitted_at.is_not(None),
                    PastPaper.scan_after <= utc_now(),
                )
                .order_by(PastPaper.scan_after)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if paper is None:
                break
            status = await check_file(paper, self.storage, self.scanner, kind="past_paper")
            await self.session.commit()
            if status is None:
                report.waiting += 1
            elif status is ScanStatus.CLEAN:
                report.clean += 1
            else:
                report.rejected += 1
        return report

    async def purge(self, now: datetime | None = None) -> int:
        """Deletes the objects of rejected files and of uploads whose form was never saved."""
        now = now or utc_now()
        rejected = list(
            await self.session.scalars(
                select(PastPaper).where(
                    PastPaper.scan_status.in_([ScanStatus.INFECTED, ScanStatus.FAILED]),
                    PastPaper.purged_at.is_(None),
                )
            )
        )
        unsaved = list(
            await self.session.scalars(
                select(PastPaper).where(
                    and_(
                        PastPaper.submitted_at.is_(None),
                        PastPaper.created_at < now - UNSAVED_AFTER,
                    )
                )
            )
        )
        purged = 0
        for paper in [*rejected, *unsaved]:
            try:
                await self.storage.delete(paper.object_key)
            except StorageUnavailableError:
                continue
            if paper.submitted_at is None:
                await self.session.delete(paper)
            else:
                await self.session.execute(
                    update(PastPaper).where(PastPaper.id == paper.id).values(purged_at=now)
                )
            purged += 1
        await self.session.commit()
        return purged
