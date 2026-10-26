"""The data-subject export (`GET /me/export`, §5.4): everything the platform stores about the requester.

Every query is filtered by the requester's id. The user's own grades are included (product owner decision,
DECISIONS D-036); other people appear only as names of teachers and groups, never with their own data.
"""

import base64
import uuid
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.storage import ObjectStorage, StorageUnavailableError
from app.core.time import utc_now
from app.modules.academics.models import (
    CourseOffering,
    CourseOfferingTeacher,
    Enrollment,
    Semester,
    Subject,
)
from app.modules.academics.service import AcademicsService
from app.modules.audit.models import AuditAction, AuditLog
from app.modules.audit.service import record_audit
from app.modules.privacy.service import ConsentService
from app.modules.users.models import Role, User, UserRole

EXPORT_FORMAT_VERSION = 1


class DataExportService:
    def __init__(self, session: AsyncSession, storage: ObjectStorage) -> None:
        self.session = session
        self.storage = storage

    async def export(self, user_id: uuid.UUID) -> dict[str, Any]:
        user = await self.session.get(User, user_id)
        if user is None:
            raise AppError("request.not_found", 404)
        document = {
            "format_version": EXPORT_FORMAT_VERSION,
            "generated_at": utc_now().isoformat(),
            "account": {
                "id": str(user.id),
                "signed_in_with_identity_provider": user.idp_subject is not None,
                "email": user.email,
                "given_name": user.given_name,
                "family_name": user.family_name,
                "display_name": user.display_name,
                "university_id": user.university_id,
                "person_type": user.person_type,
                "status": user.status,
                "created_at": user.created_at.isoformat(),
                "onboarded_at": user.onboarded_at.isoformat() if user.onboarded_at else None,
            },
            "roles": await self._roles(user.id),
            "profile": {"bio": user.bio, "photo": await self._photo(user)},
            "privacy_settings": {
                "dm_policy": user.dm_policy,
                "contact_visibility": user.contact_visibility,
            },
            "academic": await self._academic(user.id),
            "consents": [
                {
                    "purpose": record.purpose,
                    "granted": record.granted,
                    "policy_version": record.policy_version,
                    "recorded_at": record.recorded_at.isoformat(),
                }
                for record in await ConsentService(self.session).history(user.id)
            ],
            "audit": await self._audit(user.id),
        }
        # Exporting personal data is itself a privileged action (§14).
        record_audit(
            self.session,
            AuditAction.DATA_EXPORTED,
            actor_id=user.id,
            target_type="user",
            target_id=user.id,
        )
        await self.session.commit()
        return document

    async def _roles(self, user_id: uuid.UUID) -> list[str]:
        codes = await self.session.scalars(
            select(Role.code)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
            .order_by(Role.code)
        )
        return list(codes)

    async def _photo(self, user: User) -> dict[str, str] | None:
        if user.photo_key is None:
            return None
        try:
            data = await self.storage.get(user.photo_key)
        except StorageUnavailableError as exc:
            raise AppError("storage.unavailable", 503) from exc
        if data is None:
            return None
        return {"content_type": "image/webp", "base64": base64.b64encode(data).decode("ascii")}

    async def _academic(self, user_id: uuid.UUID) -> dict[str, Any]:
        placement = (await AcademicsService(self.session).overview(user_id)).placement
        enrollments = await self.session.execute(
            select(Enrollment, CourseOffering.code, Subject, Semester)
            .join(CourseOffering, CourseOffering.id == Enrollment.course_offering_id)
            .join(Subject, Subject.id == CourseOffering.subject_id)
            .join(Semester, Semester.id == CourseOffering.semester_id)
            .where(Enrollment.user_id == user_id)
            .order_by(Semester.starts_on, Subject.name_az)
        )
        teaching = await self.session.execute(
            select(CourseOffering.code, Subject, Semester)
            .join(
                CourseOfferingTeacher, CourseOfferingTeacher.course_offering_id == CourseOffering.id
            )
            .join(Subject, Subject.id == CourseOffering.subject_id)
            .join(Semester, Semester.id == CourseOffering.semester_id)
            .where(CourseOfferingTeacher.teacher_id == user_id)
            .order_by(Semester.starts_on, Subject.name_az)
        )
        return {
            "group": {
                "code": placement.group.code,
                "admission_year": placement.group.admission_year,
                "language": placement.group.language,
                "specialty": {
                    "code": placement.specialty.code,
                    "name": placement.specialty.name_az,
                },
                "faculty": {"code": placement.faculty.code, "name": placement.faculty.name_az},
            }
            if placement
            else None,
            "enrollments": [
                {
                    "subject": {"code": subject.code, "name": subject.name_az},
                    "semester": {"year": semester.year, "term": semester.term},
                    "offering_code": offering_code,
                    "status": enrollment.status,
                    "passed": enrollment.passed,
                    "grade": enrollment.grade,
                }
                for enrollment, offering_code, subject, semester in enrollments
            ],
            "teaching": [
                {
                    "subject": {"code": subject.code, "name": subject.name_az},
                    "semester": {"year": semester.year, "term": semester.term},
                    "offering_code": offering_code,
                }
                for offering_code, subject, semester in teaching
            ],
        }

    async def _audit(self, user_id: uuid.UUID) -> list[dict[str, Any]]:
        """Entries about the user or by the user; who else acted is not disclosed, only whether it was them."""
        logs = await self.session.scalars(
            select(AuditLog)
            .where(
                or_(
                    AuditLog.actor_id == user_id,
                    (AuditLog.target_type == "user") & (AuditLog.target_id == str(user_id)),
                )
            )
            .order_by(AuditLog.occurred_at)
        )
        return [
            {
                "action": log.action,
                "occurred_at": log.occurred_at.isoformat(),
                "by_you": log.actor_id == user_id,
                "details": log.details,
            }
            for log in logs
        ]
