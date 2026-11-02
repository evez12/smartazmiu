import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
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


def _enum(enum: type[StrEnum], name: str) -> Enum:
    return Enum(enum, name=name, values_callable=lambda members: [m.value for m in members])


class ExamSlot(Base):
    """One exam of a course offering. Exam mode of its course channel and of the subject community follows from
    it at read time (D-003, D-059, D-097)."""

    __tablename__ = "exam_slots"
    __table_args__ = (
        UniqueConstraint("course_offering_id", "starts_at", name="uq_exam_slots_offering_start"),
        CheckConstraint("ends_at > starts_at", name="exam_slot_valid_window"),
        Index("ix_exam_slots_window", "starts_at", "ends_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    course_offering_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course_offerings.id", ondelete="CASCADE")
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # The code as printed in the timetable; ``room_id`` links it to the campus map when the room is known.
    room_code: Mapped[str | None] = mapped_column(String(20))
    room_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rooms.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SubjectExamMode(Base):
    """Staff's per-subject switch for exam mode (§5.2, D-104). A subject without a row follows its exam slots."""

    __tablename__ = "subject_exam_modes"

    subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PastPaperKind(StrEnum):
    MIDTERM = "midterm"
    FINAL = "final"
    RETAKE = "retake"


class PastPaperStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PastPaper(Base):
    """An exam paper of a finished semester, kept for later students once a teacher or the dean's office approves it.

    The row exists from the presigned upload; the details stay NULL until the uploader saves the form (D-097).
    """

    __tablename__ = "past_papers"
    __table_args__ = (
        CheckConstraint("size_bytes > 0", name="positive_file_size"),
        Index("ix_past_papers_subject_id_status", "subject_id", "status"),
        Index(
            "ix_past_papers_pending_scan",
            "scan_after",
            postgresql_where=text("scan_status = 'pending' AND submitted_at IS NOT NULL"),
        ),
        Index(
            "ix_past_papers_unsaved", "created_at", postgresql_where=text("submitted_at IS NULL")
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"))
    # NULL once the uploader's account is deleted; the approved paper stays in the archive (D-108).
    uploader_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    semester_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("semesters.id", ondelete="CASCADE")
    )
    kind: Mapped[PastPaperKind | None] = mapped_column(_enum(PastPaperKind, "past_paper_kind"))
    title: Mapped[str | None] = mapped_column(String(200))
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    object_key: Mapped[str] = mapped_column(String(300))
    filename: Mapped[str] = mapped_column(String(255))
    mime: Mapped[str] = mapped_column(String(127))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    scan_status: Mapped[ScanStatus] = mapped_column(
        _enum(ScanStatus, "scan_status"), server_default="pending"
    )
    scan_attempts: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    scan_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[PastPaperStatus] = mapped_column(
        _enum(PastPaperStatus, "past_paper_status"), server_default="pending"
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
