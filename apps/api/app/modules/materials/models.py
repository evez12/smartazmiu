"""Course materials (§6, §6.1, D-071): a catalogue per subject and semester. Every upload is a new version; old
versions stay. A version becomes downloadable only after the type check and ClamAV."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import uuid7
from app.modules.chat.models import ScanStatus
from app.modules.users.models import AZ_COLLATION


def _enum(enum: type[StrEnum], name: str) -> Enum:
    return Enum(enum, name=name, values_callable=lambda members: [m.value for m in members])


class MaterialType(StrEnum):
    LECTURE = "lecture"
    SEMINAR = "seminar"
    LAB = "lab"
    SYLLABUS = "syllabus"
    EXAM_PREP = "exam_prep"
    OTHER = "other"


class MaterialReportReason(StrEnum):
    COPYRIGHT = "copyright"
    WRONG_CONTENT = "wrong_content"
    INAPPROPRIATE = "inappropriate"
    OTHER = "other"


class MaterialReportStatus(StrEnum):
    OPEN = "open"
    ACTIONED = "actioned"
    DISMISSED = "dismissed"


class Material(Base):
    __tablename__ = "materials"
    __table_args__ = (Index("ix_materials_subject_id_semester_id", "subject_id", "semester_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"))
    semester_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("semesters.id", ondelete="CASCADE"))
    type: Mapped[MaterialType] = mapped_column(_enum(MaterialType, "material_type"))
    title: Mapped[str] = mapped_column(String(200, collation=AZ_COLLATION))
    description: Mapped[str] = mapped_column(String(1000), default="", server_default="")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    # Hidden by staff after a report; the versions and their files stay (no hard delete in v1).
    hidden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MaterialVersion(Base):
    """One uploaded file. ``material_id`` is NULL between the presigned upload and the form being saved."""

    __tablename__ = "material_versions"
    __table_args__ = (
        UniqueConstraint("material_id", "version"),
        Index(
            "ix_material_versions_pending",
            "scan_after",
            postgresql_where=text("scan_status = 'pending' AND material_id IS NOT NULL"),
        ),
        Index(
            "ix_material_versions_unsaved",
            "created_at",
            postgresql_where=text("material_id IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    material_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int | None] = mapped_column(SmallInteger)
    uploader_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    # The subject and semester the upload was reserved for; a version can only join a material of the same.
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"))
    semester_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("semesters.id", ondelete="CASCADE"))
    object_key: Mapped[str] = mapped_column(String(300))
    filename: Mapped[str] = mapped_column(String(255))
    mime: Mapped[str] = mapped_column(String(127))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    note: Mapped[str] = mapped_column(String(300), default="", server_default="")
    scan_status: Mapped[ScanStatus] = mapped_column(
        _enum(ScanStatus, "scan_status"),
        default=ScanStatus.PENDING,
        server_default=ScanStatus.PENDING.value,
    )
    scan_attempts: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    scan_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The uploader confirmed the right to share the file (§6.1); the text shown is CONSENT_TEXT_VERSION.
    copyright_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    copyright_text_version: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MaterialReport(Base):
    __tablename__ = "material_reports"
    __table_args__ = (
        UniqueConstraint("material_id", "reporter_id"),
        Index("ix_material_reports_status_created_at", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    material_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("materials.id", ondelete="CASCADE"))
    reporter_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reason: Mapped[MaterialReportReason] = mapped_column(
        _enum(MaterialReportReason, "material_report_reason")
    )
    note: Mapped[str] = mapped_column(String(500), default="", server_default="")
    status: Mapped[MaterialReportStatus] = mapped_column(
        _enum(MaterialReportStatus, "material_report_status"),
        default=MaterialReportStatus.OPEN,
        server_default=MaterialReportStatus.OPEN.value,
    )
    handled_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
