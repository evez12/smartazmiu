import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import uuid7


class CheckInMethod(StrEnum):
    QR = "qr"
    CODE = "code"
    MANUAL = "manual"


class AttendanceSession(Base):
    """One class meeting a teacher opened for check-in. Its codes are derived, never stored (D-094)."""

    __tablename__ = "attendance_sessions"
    __table_args__ = (
        # A second open meeting for the same offering would make a scanned code ambiguous.
        Index(
            "uq_attendance_sessions_open",
            "course_offering_id",
            unique=True,
            postgresql_where=text("closed_at IS NULL"),
        ),
        CheckConstraint("expires_at > opened_at", name="expires_after_open"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    course_offering_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course_offerings.id"), index=True
    )
    opened_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(120), default="")
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Check-in stops here even if nobody pressed "close"; closed_at records the end of the meeting itself.
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    __table_args__ = (UniqueConstraint("session_id", "student_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attendance_sessions.id", ondelete="CASCADE")
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    method: Mapped[CheckInMethod] = mapped_column(
        Enum(
            CheckInMethod, name="attendance_method", values_callable=lambda m: [x.value for x in m]
        )
    )
    # Who marked a student by hand and why; both are NULL for a student's own check-in.
    marked_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reason: Mapped[str | None] = mapped_column(String(300))
    checked_in_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
