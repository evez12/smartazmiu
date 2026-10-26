"""Materials v1 (§6, §6.1, D-071).

Who sees what is decided from the registry, inside SQL: people with a (not dropped) enrollment in any offering of a
subject read its catalogue for every semester; the subject's teachers read it and upload for the semesters they
teach; holders of ``materials.manage`` (staff) read and upload everywhere and may hide a reported material.
Uploads use presigned URLs like chat attachments (D-068) and are downloadable only once checked and clean.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

import structlog
from redis.asyncio import Redis
from sqlalchemy import Select, and_, exists, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.antivirus import ScannerUnavailableError, VirusScanner
from app.core.errors import AppError
from app.core.jobs import JobQueue
from app.core.ratelimit import RateLimit, enforce_rate_limit
from app.core.storage import ObjectStorage, StorageUnavailableError
from app.core.time import utc_now
from app.core.uploads import (
    PREVIEWABLE,
    allowed_extensions,
    allowed_type,
    content_disposition,
    content_matches,
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
from app.modules.materials.models import (
    Material,
    MaterialReport,
    MaterialReportReason,
    MaterialReportStatus,
    MaterialType,
    MaterialVersion,
)
from app.modules.materials.schemas import (
    MaterialDetailOut,
    MaterialOut,
    MaterialReportOut,
    MaterialSubjectOut,
    PersonOut,
    SemesterOut,
    SubjectCatalogOut,
    VersionOut,
)
from app.modules.users.models import User
from app.modules.users.service import CurrentUser

logger = structlog.get_logger(__name__)

MANAGE = "materials.manage"
MAX_SIZE = 50 * 1024 * 1024
UPLOAD_LIMIT = RateLimit("material_upload", limit=30, window_seconds=3600)
REPORT_LIMIT = RateLimit("material_report", limit=10, window_seconds=3600)
UPLOAD_TTL = timedelta(minutes=10)
DOWNLOAD_TTL = timedelta(minutes=1)
UNSAVED_AFTER = timedelta(hours=24)
# Bumped whenever the copyright wording in the upload form changes; stored with each version (§6.1).
CONSENT_TEXT_VERSION = "2026-10-26"


def _term(semester: Semester) -> str:
    return f"{semester.year} {TERM_NAMES[semester.term]}"


def _person(user: User | None) -> PersonOut | None:
    return PersonOut(id=str(user.id), display_name=user.display_name) if user else None


@dataclass(frozen=True, slots=True)
class Access:
    read: bool
    manage_all: bool
    teaches: frozenset[uuid.UUID]
    """Semesters in which the user teaches an offering of the subject."""

    def can_upload(self, semester_id: uuid.UUID) -> bool:
        return self.manage_all or semester_id in self.teaches

    @property
    def uploads_anywhere(self) -> bool:
        return self.manage_all or bool(self.teaches)


@dataclass(frozen=True, slots=True)
class PresignedUpload:
    version: MaterialVersion
    url: str
    expires_at: datetime


class MaterialService:
    def __init__(
        self, session: AsyncSession, storage: ObjectStorage, cache: Redis, jobs: JobQueue
    ) -> None:
        self.session = session
        self.storage = storage
        self.cache = cache
        self.jobs = jobs

    # --- access ---------------------------------------------------------------------------------

    def _readable_subjects(self, user: CurrentUser) -> Select[tuple[uuid.UUID]]:
        enrolled = (
            select(CourseOffering.subject_id)
            .join(Enrollment, Enrollment.course_offering_id == CourseOffering.id)
            .where(Enrollment.user_id == user.id, Enrollment.status != EnrollmentStatus.DROPPED)
        )
        taught = (
            select(CourseOffering.subject_id)
            .join(
                CourseOfferingTeacher,
                CourseOfferingTeacher.course_offering_id == CourseOffering.id,
            )
            .where(CourseOfferingTeacher.teacher_id == user.id)
        )
        return enrolled.union(taught)  # type: ignore[return-value]

    async def access(self, user: CurrentUser, subject_id: uuid.UUID) -> Access:
        manage_all = user.has_permission(MANAGE)
        teaches = frozenset(
            await self.session.scalars(
                select(CourseOffering.semester_id)
                .join(
                    CourseOfferingTeacher,
                    CourseOfferingTeacher.course_offering_id == CourseOffering.id,
                )
                .where(
                    CourseOffering.subject_id == subject_id,
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
        subject_exists = await self.session.get(Subject, subject_id) is not None
        read = subject_exists and (manage_all or bool(teaches) or bool(enrolled))
        return Access(read=read, manage_all=manage_all, teaches=teaches)

    async def _readable(self, user: CurrentUser, subject_id: uuid.UUID) -> Access:
        access = await self.access(user, subject_id)
        if not access.read:
            # Same answer as a subject that does not exist (§14).
            raise AppError("materials.subject_not_found", 404)
        return access

    # --- catalogue ------------------------------------------------------------------------------

    async def my_subjects(self, user: CurrentUser) -> list[MaterialSubjectOut]:
        visible = Material.hidden_at.is_(None)
        count = (
            select(func.count())
            .where(Material.subject_id == Subject.id, visible)
            .correlate(Subject)
            .scalar_subquery()
        )
        query = select(Subject, count).order_by(Subject.name_az, Subject.code)
        if not user.has_permission(MANAGE):
            query = query.where(Subject.id.in_(self._readable_subjects(user)))
        else:
            # Staff see every subject that has materials, plus their own teaching.
            query = query.where(
                or_(
                    exists().where(Material.subject_id == Subject.id),
                    Subject.id.in_(self._readable_subjects(user)),
                )
            )
        rows = await self.session.execute(query)
        return [
            MaterialSubjectOut(
                id=str(subject.id), code=subject.code, name=subject.name_az, materials=n
            )
            for subject, n in rows
        ]

    async def catalog(
        self, user: CurrentUser, subject_id: uuid.UUID, semester_id: uuid.UUID | None
    ) -> SubjectCatalogOut:
        access = await self._readable(user, subject_id)
        subject = await self.session.get(Subject, subject_id)
        assert subject is not None
        # Semesters with an offering of the subject, newest first: the catalogue's tabs.
        semesters = list(
            await self.session.scalars(
                select(Semester)
                .where(
                    exists().where(
                        CourseOffering.subject_id == subject_id,
                        CourseOffering.semester_id == Semester.id,
                    )
                )
                .order_by(Semester.starts_on.desc())
            )
        )
        query = select(Material).where(Material.subject_id == subject_id)
        if semester_id is not None:
            query = query.where(Material.semester_id == semester_id)
        if not access.manage_all:
            query = query.where(Material.hidden_at.is_(None))
        materials = list(
            await self.session.scalars(query.order_by(Material.type, Material.title, Material.id))
        )
        return SubjectCatalogOut(
            subject_id=str(subject.id),
            subject_code=subject.code,
            subject_name=subject.name_az,
            semesters=[
                SemesterOut(id=str(s.id), label=_term(s), can_upload=access.can_upload(s.id))
                for s in semesters
            ],
            can_upload=access.uploads_anywhere,
            can_manage=access.manage_all,
            materials=await self._materials_out(user, access, materials),
        )

    async def detail(self, user: CurrentUser, material_id: uuid.UUID) -> MaterialDetailOut:
        material, access = await self._material(user, material_id)
        versions = list(
            await self.session.scalars(
                select(MaterialVersion)
                .where(MaterialVersion.material_id == material.id)
                .order_by(MaterialVersion.version.desc())
            )
        )
        editor = self._can_edit(user, access, material)
        uploaders = await self._people({v.uploader_id for v in versions})
        summary = (await self._materials_out(user, access, [material]))[0]
        return MaterialDetailOut(
            **summary.model_dump(),
            versions=[
                self._version_out(v, uploaders)
                for v in versions
                if v.scan_status is ScanStatus.CLEAN or editor or v.uploader_id == user.id
            ],
        )

    async def _material(self, user: CurrentUser, material_id: uuid.UUID) -> tuple[Material, Access]:
        material = await self.session.get(Material, material_id)
        if material is None:
            raise AppError("materials.not_found", 404)
        access = await self.access(user, material.subject_id)
        if not access.read or (material.hidden_at is not None and not access.manage_all):
            raise AppError("materials.not_found", 404)
        return material, access

    @staticmethod
    def _can_edit(user: CurrentUser, access: Access, material: Material) -> bool:
        return (
            access.manage_all
            or material.created_by == user.id
            or material.semester_id in access.teaches
        )

    async def _materials_out(
        self, user: CurrentUser, access: Access, materials: list[Material]
    ) -> list[MaterialOut]:
        if not materials:
            return []
        ids = [m.id for m in materials]
        versions = list(
            await self.session.scalars(
                select(MaterialVersion)
                .where(MaterialVersion.material_id.in_(ids))
                .order_by(MaterialVersion.version.desc())
            )
        )
        latest_clean: dict[uuid.UUID, MaterialVersion] = {}
        pending: set[uuid.UUID] = set()
        counts: dict[uuid.UUID, int] = {}
        for version in versions:
            assert version.material_id is not None
            if version.scan_status is ScanStatus.CLEAN:
                latest_clean.setdefault(version.material_id, version)
                counts[version.material_id] = counts.get(version.material_id, 0) + 1
            elif version.scan_status is ScanStatus.PENDING:
                pending.add(version.material_id)
        semesters = {
            s.id: s
            for s in await self.session.scalars(
                select(Semester).where(Semester.id.in_({m.semester_id for m in materials}))
            )
        }
        people = await self._people(
            {m.created_by for m in materials} | {v.uploader_id for v in latest_clean.values()}
        )
        result = []
        for material in materials:
            current = latest_clean.get(material.id)
            editor = self._can_edit(user, access, material)
            result.append(
                MaterialOut(
                    id=str(material.id),
                    subject_id=str(material.subject_id),
                    semester=SemesterOut(
                        id=str(material.semester_id),
                        label=_term(semesters[material.semester_id]),
                        can_upload=access.can_upload(material.semester_id),
                    ),
                    type=material.type,
                    title=material.title,
                    description=material.description,
                    created_by=_person(people.get(material.created_by))
                    if material.created_by
                    else None,
                    created_at=material.created_at,
                    current=self._version_out(current, people) if current else None,
                    version_count=counts.get(material.id, 0),
                    # Only those who can do something about it learn that a scan is still running.
                    scanning=material.id in pending and editor,
                    hidden=material.hidden_at is not None,
                    can_edit=editor,
                )
            )
        return result

    async def _people(self, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, User]:
        wanted = {i for i in ids if i is not None}
        if not wanted:
            return {}
        return {
            u.id: u for u in await self.session.scalars(select(User).where(User.id.in_(wanted)))
        }

    @staticmethod
    def _version_out(version: MaterialVersion, people: dict[uuid.UUID, User]) -> VersionOut:
        assert version.version is not None
        return VersionOut(
            id=str(version.id),
            version=version.version,
            filename=version.filename,
            mime=version.mime,
            size_bytes=version.size_bytes,
            note=version.note,
            status=version.scan_status,
            previewable=version.mime in PREVIEWABLE,
            uploaded_by=_person(people.get(version.uploader_id)) if version.uploader_id else None,
            created_at=version.created_at,
        )

    # --- uploads ------------------------------------------------------------------------------

    async def presign(
        self,
        user: CurrentUser,
        subject_id: uuid.UUID,
        semester_id: uuid.UUID,
        filename: str,
        mime: str,
        size: int,
    ) -> PresignedUpload:
        access = await self._readable(user, subject_id)
        if not access.can_upload(semester_id):
            raise AppError("materials.upload_not_allowed", 403)
        kind = allowed_type(filename, mime)
        if kind is None:
            raise AppError(
                "materials.type_not_allowed", 422, details={"allowed": allowed_extensions()}
            )
        if not 0 < size <= MAX_SIZE:
            raise AppError("materials.too_large", 422, details={"max_bytes": MAX_SIZE})
        await enforce_rate_limit(self.cache, UPLOAD_LIMIT, str(user.id))
        key = f"materials/{subject_id}/{uuid.uuid4().hex}"
        try:
            url = await self.storage.presign_put(key, kind, UPLOAD_TTL)
        except StorageUnavailableError as exc:
            raise AppError("materials.storage_unavailable", 503) from exc
        version = MaterialVersion(
            uploader_id=user.id,
            subject_id=subject_id,
            semester_id=semester_id,
            object_key=key,
            filename=safe_filename(filename),
            mime=kind,
            size_bytes=size,
        )
        self.session.add(version)
        await self.session.commit()
        return PresignedUpload(version, url, utc_now() + UPLOAD_TTL)

    async def _claim_upload(
        self, user: CurrentUser, upload_id: uuid.UUID, subject_id: uuid.UUID, semester_id: uuid.UUID
    ) -> MaterialVersion:
        upload = await self.session.get(MaterialVersion, upload_id, with_for_update=True)
        if (
            upload is None
            or upload.uploader_id != user.id
            or upload.material_id is not None
            or upload.subject_id != subject_id
            or upload.semester_id != semester_id
        ):
            raise AppError("materials.upload_not_found", 422)
        try:
            stored = await self.storage.head(upload.object_key)
        except StorageUnavailableError as exc:
            raise AppError("materials.storage_unavailable", 503) from exc
        if stored is None:
            raise AppError("materials.upload_missing", 422)
        if stored != upload.size_bytes:
            raise AppError("materials.upload_size_mismatch", 422)
        return upload

    async def create(
        self,
        user: CurrentUser,
        upload_id: uuid.UUID,
        material_type: MaterialType,
        title: str,
        description: str,
        copyright_confirmed: bool,
    ) -> MaterialDetailOut:
        if not copyright_confirmed:
            raise AppError("materials.copyright_required", 422)
        if not title.strip():
            raise AppError("materials.title_required", 422)
        reserved = await self.session.get(MaterialVersion, upload_id)
        if reserved is None or reserved.uploader_id != user.id:
            raise AppError("materials.upload_not_found", 422)
        access = await self._readable(user, reserved.subject_id)
        if not access.can_upload(reserved.semester_id):
            raise AppError("materials.upload_not_allowed", 403)
        upload = await self._claim_upload(
            user, upload_id, reserved.subject_id, reserved.semester_id
        )
        material = Material(
            subject_id=upload.subject_id,
            semester_id=upload.semester_id,
            type=material_type,
            title=title.strip(),
            description=description.strip(),
            created_by=user.id,
        )
        self.session.add(material)
        await self.session.flush()
        self._attach(upload, material.id, 1)
        await self.session.commit()
        # Materials share the upload scan job with chat attachments (D-071).
        await self.jobs.scan_attachments()
        return await self.detail(user, material.id)

    async def add_version(
        self,
        user: CurrentUser,
        material_id: uuid.UUID,
        upload_id: uuid.UUID,
        note: str,
        copyright_confirmed: bool,
    ) -> MaterialDetailOut:
        """A new upload never replaces the old file: it becomes the next version (§6.1)."""
        if not copyright_confirmed:
            raise AppError("materials.copyright_required", 422)
        material, access = await self._material(user, material_id)
        if not self._can_edit(user, access, material):
            raise AppError("materials.upload_not_allowed", 403)
        await self.session.execute(
            select(Material.id).where(Material.id == material.id).with_for_update()
        )
        upload = await self._claim_upload(
            user, upload_id, material.subject_id, material.semester_id
        )
        last = await self.session.scalar(
            select(func.max(MaterialVersion.version)).where(
                MaterialVersion.material_id == material.id
            )
        )
        upload.note = note.strip()
        self._attach(upload, material.id, (last or 0) + 1)
        await self.session.commit()
        await self.jobs.scan_attachments()
        return await self.detail(user, material.id)

    @staticmethod
    def _attach(upload: MaterialVersion, material_id: uuid.UUID, number: int) -> None:
        upload.material_id = material_id
        upload.version = number
        upload.copyright_confirmed_at = utc_now()
        upload.copyright_text_version = CONSENT_TEXT_VERSION
        upload.scan_after = utc_now()

    async def download(
        self, user: CurrentUser, version_id: uuid.UUID, *, inline: bool
    ) -> tuple[str, datetime]:
        version = await self.session.get(MaterialVersion, version_id)
        if version is None or version.material_id is None:
            raise AppError("materials.not_found", 404)
        await self._material(user, version.material_id)
        if version.scan_status is not ScanStatus.CLEAN:
            raise AppError("materials.not_available", 409)
        try:
            url = await self.storage.presign_get(
                version.object_key,
                content_type=version.mime,
                disposition=content_disposition(
                    version.filename, inline and version.mime in PREVIEWABLE
                ),
                expires=DOWNLOAD_TTL,
            )
        except StorageUnavailableError as exc:
            raise AppError("materials.storage_unavailable", 503) from exc
        return url, utc_now() + DOWNLOAD_TTL

    # --- reports and moderation -----------------------------------------------------------------

    async def report(
        self, user: CurrentUser, material_id: uuid.UUID, reason: MaterialReportReason, note: str
    ) -> tuple[MaterialReport, bool]:
        material, _ = await self._material(user, material_id)
        existing = await self.session.scalar(
            select(MaterialReport).where(
                MaterialReport.material_id == material.id, MaterialReport.reporter_id == user.id
            )
        )
        if existing is not None:
            return existing, True
        await enforce_rate_limit(self.cache, REPORT_LIMIT, str(user.id))
        report_id = await self.session.scalar(
            insert(MaterialReport)
            .values(material_id=material.id, reporter_id=user.id, reason=reason, note=note.strip())
            .on_conflict_do_nothing(index_elements=["material_id", "reporter_id"])
            .returning(MaterialReport.id)
        )
        if report_id is None:
            raced = await self.session.scalar(
                select(MaterialReport).where(
                    MaterialReport.material_id == material.id,
                    MaterialReport.reporter_id == user.id,
                )
            )
            assert raced is not None
            return raced, True
        record_audit(
            self.session,
            AuditAction.MATERIAL_REPORTED,
            actor_id=user.id,
            target_type="material",
            target_id=material.id,
            details={"reason": reason.value},
        )
        await self.session.commit()
        stored = await self.session.get(MaterialReport, report_id)
        assert stored is not None
        return stored, False

    async def reports(
        self, status: MaterialReportStatus | None, offset: int, limit: int
    ) -> tuple[list[MaterialReportOut], int]:
        query = select(MaterialReport, Material).join(
            Material, Material.id == MaterialReport.material_id
        )
        count = select(func.count()).select_from(MaterialReport)
        if status is not None:
            query = query.where(MaterialReport.status == status)
            count = count.where(MaterialReport.status == status)
        rows = list(
            await self.session.execute(
                query.order_by(MaterialReport.created_at.desc(), MaterialReport.id.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        subjects = {
            s.id: s
            for s in await self.session.scalars(
                select(Subject).where(Subject.id.in_({m.subject_id for _, m in rows}))
            )
        }
        people = await self._people(
            {r.reporter_id for r, _ in rows} | {r.handled_by for r, _ in rows}
        )
        items = [
            MaterialReportOut(
                id=str(report.id),
                material_id=str(material.id),
                material_title=material.title,
                subject_id=str(material.subject_id),
                subject_name=subjects[material.subject_id].name_az,
                material_hidden=material.hidden_at is not None,
                reason=report.reason,
                note=report.note,
                status=report.status,
                reporter=_person(people.get(report.reporter_id)) if report.reporter_id else None,
                handled_by=_person(people.get(report.handled_by)) if report.handled_by else None,
                handled_at=report.handled_at,
                created_at=report.created_at,
            )
            for report, material in rows
        ]
        return items, int(await self.session.scalar(count) or 0)

    async def set_report_status(
        self, actor: CurrentUser, report_id: uuid.UUID, status: MaterialReportStatus
    ) -> None:
        report = await self.session.get(MaterialReport, report_id, with_for_update=True)
        if report is None:
            raise AppError("materials.report_not_found", 404)
        if report.status is status:
            return
        previous = report.status
        report.status = status
        reopened = status is MaterialReportStatus.OPEN
        report.handled_by = None if reopened else actor.id
        report.handled_at = None if reopened else utc_now()
        record_audit(
            self.session,
            AuditAction.MATERIAL_REPORT_HANDLED,
            actor_id=actor.id,
            target_type="material_report",
            target_id=report.id,
            details={"from": previous.value, "to": status.value},
        )
        await self.session.commit()

    async def set_hidden(self, actor: CurrentUser, material_id: uuid.UUID, hidden: bool) -> None:
        """Staff hide a reported material from the catalogue; files and versions are kept (no hard delete)."""
        if not actor.has_permission(MANAGE):
            raise AppError("auth.forbidden", 403, details={"permission": MANAGE})
        material = await self.session.get(Material, material_id, with_for_update=True)
        if material is None:
            raise AppError("materials.not_found", 404)
        if (material.hidden_at is not None) == hidden:
            return
        material.hidden_at = utc_now() if hidden else None
        record_audit(
            self.session,
            AuditAction.MATERIAL_HIDDEN if hidden else AuditAction.MATERIAL_SHOWN,
            actor_id=actor.id,
            target_type="material",
            target_id=material.id,
        )
        await self.session.commit()


@dataclass(frozen=True, slots=True)
class MaterialScanReport:
    clean: int = 0
    rejected: int = 0
    waiting: int = 0


class MaterialScanner:
    """Worker side, like chat attachments (D-068): type check, ClamAV, purge; idempotent."""

    def __init__(
        self, session: AsyncSession, storage: ObjectStorage, scanner: VirusScanner
    ) -> None:
        self.session = session
        self.storage = storage
        self.scanner = scanner

    async def scan_pending(self, limit: int = 20) -> MaterialScanReport:
        clean = rejected = waiting = 0
        for _ in range(limit):
            version = await self.session.scalar(
                select(MaterialVersion)
                .where(
                    MaterialVersion.scan_status == ScanStatus.PENDING,
                    MaterialVersion.material_id.is_not(None),
                    MaterialVersion.scan_after <= utc_now(),
                )
                .order_by(MaterialVersion.scan_after)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if version is None:
                break
            status = await self._scan(version)
            await self.session.commit()
            if status is None:
                waiting += 1
            elif status is ScanStatus.CLEAN:
                clean += 1
            else:
                rejected += 1
        return MaterialScanReport(clean, rejected, waiting)

    async def _scan(self, version: MaterialVersion) -> ScanStatus | None:
        try:
            data = await self.storage.get(version.object_key)
        except StorageUnavailableError:
            return self._defer(version, "storage_unavailable")
        if data is None or len(data) != version.size_bytes:
            return self._finish(version, ScanStatus.FAILED)
        if not content_matches(version.mime, data):
            return self._finish(version, ScanStatus.FAILED)
        try:
            result = await self.scanner.scan(data)
        except ScannerUnavailableError as exc:
            return self._defer(version, f"scanner_unavailable:{exc}")
        if not result.clean:
            logger.warning(
                "material_infected", version_id=str(version.id), signature=result.signature
            )
            return self._finish(version, ScanStatus.INFECTED)
        return self._finish(version, ScanStatus.CLEAN)

    @staticmethod
    def _finish(version: MaterialVersion, status: ScanStatus) -> ScanStatus:
        version.scan_status = status
        version.scanned_at = utc_now()
        return status

    @staticmethod
    def _defer(version: MaterialVersion, reason: str) -> None:
        version.scan_attempts += 1
        version.scan_after = utc_now() + timedelta(
            seconds=min(300, 15 * 2 ** min(version.scan_attempts, 5))
        )
        logger.warning("material_scan_deferred", version_id=str(version.id), reason=reason)
        return None

    async def purge(self, now: datetime | None = None) -> int:
        """Deletes the objects of rejected versions and of uploads whose form was never saved."""
        now = now or utc_now()
        rejected = list(
            await self.session.scalars(
                select(MaterialVersion).where(
                    MaterialVersion.scan_status.in_([ScanStatus.INFECTED, ScanStatus.FAILED]),
                    MaterialVersion.purged_at.is_(None),
                )
            )
        )
        unsaved = list(
            await self.session.scalars(
                select(MaterialVersion).where(
                    and_(
                        MaterialVersion.material_id.is_(None),
                        MaterialVersion.created_at < now - UNSAVED_AFTER,
                    )
                )
            )
        )
        purged = 0
        for version in [*rejected, *unsaved]:
            try:
                await self.storage.delete(version.object_key)
            except StorageUnavailableError:
                continue
            if version.material_id is None:
                await self.session.delete(version)
            else:
                await self.session.execute(
                    update(MaterialVersion)
                    .where(MaterialVersion.id == version.id)
                    .values(purged_at=now)
                )
            purged += 1
        await self.session.commit()
        return purged
