import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import uuid7
from app.modules.users.models import AZ_COLLATION


def _enum(enum: type[StrEnum], name: str) -> Enum:
    return Enum(enum, name=name, values_callable=lambda members: [m.value for m in members])


class InstructionLanguage(StrEnum):
    AZ = "az"
    EN = "en"
    RU = "ru"


class SemesterTerm(StrEnum):
    FALL = "fall"
    SPRING = "spring"
    SUMMER = "summer"


class EnrollmentStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    DROPPED = "dropped"


class _Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Faculty(_Timestamps, Base):
    __tablename__ = "faculties"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name_az: Mapped[str] = mapped_column(String(200, collation=AZ_COLLATION))
    name_en: Mapped[str] = mapped_column(String(200), default="")


class Specialty(_Timestamps, Base):
    __tablename__ = "specialties"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    faculty_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("faculties.id"), index=True)
    name_az: Mapped[str] = mapped_column(String(200, collation=AZ_COLLATION))
    name_en: Mapped[str] = mapped_column(String(200), default="")


class AcademicGroup(_Timestamps, Base):
    __tablename__ = "academic_groups"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    code: Mapped[str] = mapped_column(String(20, collation=AZ_COLLATION), unique=True)
    specialty_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("specialties.id"), index=True)
    admission_year: Mapped[int] = mapped_column(SmallInteger)
    language: Mapped[InstructionLanguage] = mapped_column(
        _enum(InstructionLanguage, "instruction_language")
    )
    curator_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )


class Subject(_Timestamps, Base):
    __tablename__ = "subjects"
    __table_args__ = (CheckConstraint("credits BETWEEN 0 AND 60", name="credits_range"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name_az: Mapped[str] = mapped_column(String(255, collation=AZ_COLLATION))
    name_en: Mapped[str] = mapped_column(String(255), default="")
    faculty_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("faculties.id"), index=True)
    credits: Mapped[int] = mapped_column(SmallInteger)


class Semester(_Timestamps, Base):
    __tablename__ = "semesters"
    __table_args__ = (
        UniqueConstraint("year", "term"),
        CheckConstraint("ends_on > starts_on", name="dates_ordered"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    # The calendar year the term starts in: 2026 Payız is fall 2026, 2027 Yaz is spring 2027.
    year: Mapped[int] = mapped_column(SmallInteger)
    term: Mapped[SemesterTerm] = mapped_column(_enum(SemesterTerm, "semester_term"))
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)


class CourseOffering(_Timestamps, Base):
    """A subject taught in one semester to one or more groups (joint lectures, §13.1)."""

    __tablename__ = "course_offerings"
    __table_args__ = (UniqueConstraint("subject_id", "semester_id", "code"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"), index=True)
    semester_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("semesters.id"), index=True)
    # Natural key within subject + semester; the group code for single-group offerings.
    code: Mapped[str] = mapped_column(String(64, collation=AZ_COLLATION))


class CourseOfferingGroup(Base):
    __tablename__ = "course_offering_groups"

    course_offering_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course_offerings.id", ondelete="CASCADE"), primary_key=True
    )
    academic_group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academic_groups.id"), primary_key=True, index=True
    )


class CourseOfferingTeacher(Base):
    __tablename__ = "course_offering_teachers"

    course_offering_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course_offerings.id", ondelete="CASCADE"), primary_key=True
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), primary_key=True, index=True
    )


class Enrollment(_Timestamps, Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("user_id", "course_offering_id"),
        Index("ix_enrollments_user_id_status", "user_id", "status"),
        # A result exists exactly when the enrollment is completed; grades never exist without one.
        CheckConstraint(
            "(status = 'completed') = (passed IS NOT NULL)", name="result_when_completed"
        ),
        CheckConstraint("grade IS NULL OR passed IS NOT NULL", name="grade_needs_result"),
        CheckConstraint("grade BETWEEN 0 AND 100", name="grade_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    course_offering_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course_offerings.id"), index=True
    )
    status: Mapped[EnrollmentStatus] = mapped_column(_enum(EnrollmentStatus, "enrollment_status"))
    passed: Mapped[bool | None] = mapped_column(Boolean)
    grade: Mapped[int | None] = mapped_column(SmallInteger)


class ImportKind(StrEnum):
    """One CSV/XLSX template per entity, applied in this order (later kinds reference earlier ones)."""

    FACULTIES = "faculties"
    SPECIALTIES = "specialties"
    SUBJECTS = "subjects"
    SEMESTERS = "semesters"
    TEACHERS = "teachers"
    GROUPS = "groups"
    STUDENTS = "students"
    OFFERINGS = "offerings"
    ENROLLMENTS = "enrollments"
    BUILDINGS = "buildings"
    FLOORS = "floors"
    ROOMS = "rooms"
    WEEK_PARITY = "week_parity"
    SCHEDULE = "schedule"
    SCHEDULE_CHANGES = "schedule_changes"


class ImportStatus(StrEnum):
    READY = "ready"
    """Validated without errors; can be applied."""
    INVALID = "invalid"
    """The file has errors; nothing can be applied."""
    APPLIED = "applied"
    FAILED = "failed"
    """Validation failed again at apply time (data changed since the preview); rolled back."""


class AcademicImport(Base):
    __tablename__ = "academic_imports"
    __table_args__ = (
        Index("ix_academic_imports_created_at", "created_at"),
        Index("ix_academic_imports_kind_file_sha256", "kind", "file_sha256"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    kind: Mapped[ImportKind] = mapped_column(_enum(ImportKind, "import_kind"))
    status: Mapped[ImportStatus] = mapped_column(_enum(ImportStatus, "import_status"))
    file_name: Mapped[str] = mapped_column(String(255))
    file_sha256: Mapped[str] = mapped_column(String(64))
    file_size: Mapped[int] = mapped_column(Integer)
    # NULL for XLSX, which carries its own encoding.
    encoding: Mapped[str | None] = mapped_column(String(20))
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[dict[str, int]] = mapped_column(JSONB, default=dict)
    errors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    # The file's cells, kept only until the import is applied or expires: they contain personal data.
    # SQL NULL, never JSON null, so `payload IS NULL` finds every cleared file (D-038).
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    applied_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
