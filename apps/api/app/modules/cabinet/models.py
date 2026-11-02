"""The read-only mirror of the personal cabinet (D-126). Rows belong to one student and are rewritten by the sync
only; nothing here is ever sent back to the cabinet."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, MappedColumn, mapped_column

from app.core.db import Base
from app.core.ids import uuid7
from app.modules.academics.models import SemesterTerm
from app.modules.cabinet.provider import AppealStatus


def _enum(enum: type[StrEnum], name: str) -> Enum:
    return Enum(enum, name=name, values_callable=lambda members: [m.value for m in members])


def _term_column() -> MappedColumn[SemesterTerm]:
    # The type already exists: the academic registry created it.
    return mapped_column(
        Enum(
            SemesterTerm,
            name="semester_term",
            create_type=False,
            values_callable=lambda members: [m.value for m in members],
        )
    )


class SyncTrigger(StrEnum):
    NIGHTLY = "nightly"
    MANUAL = "manual"


class SyncOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class CabinetSyncRun(Base):
    """One finished run. A run that failed changed nothing else (§13.5). No names or grades are kept here."""

    __tablename__ = "cabinet_sync_runs"
    __table_args__ = (Index("ix_cabinet_sync_runs_finished_at", "finished_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    trigger: Mapped[SyncTrigger] = mapped_column(_enum(SyncTrigger, "cabinet_sync_trigger"))
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    outcome: Mapped[SyncOutcome] = mapped_column(_enum(SyncOutcome, "cabinet_sync_outcome"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    students_synced: Mapped[int] = mapped_column(Integer, default=0)
    students_not_found: Mapped[int] = mapped_column(Integer, default=0)
    students_mismatched: Mapped[int] = mapped_column(Integer, default=0)
    conflicts: Mapped[int] = mapped_column(Integer, default=0)
    # A catalogue code such as ``cabinet.unavailable``; never a message from the source.
    error_code: Mapped[str | None] = mapped_column(String(64))


class CabinetStudent(Base):
    """The cabinet's own summary of a student; its existence says the cabinet knows this person."""

    __tablename__ = "cabinet_students"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    specialty_name: Mapped[str] = mapped_column(String(200))
    credits_earned: Mapped[int] = mapped_column(SmallInteger)
    cumulative_average: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CabinetGrade(Base):
    __tablename__ = "cabinet_grades"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "subject_code",
            "semester_year",
            "semester_term",
            name="uq_cabinet_grades_natural_key",
        ),
        CheckConstraint("score BETWEEN 0 AND 100", name="score_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    subject_code: Mapped[str] = mapped_column(String(20))
    subject_name: Mapped[str] = mapped_column(String(255))
    credits: Mapped[int] = mapped_column(SmallInteger)
    semester_year: Mapped[int] = mapped_column(SmallInteger)
    semester_term: Mapped[SemesterTerm] = _term_column()
    score: Mapped[int] = mapped_column(SmallInteger)
    passed: Mapped[bool]


class CabinetSemester(Base):
    __tablename__ = "cabinet_semesters"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "semester_year", "semester_term", name="uq_cabinet_semesters_natural_key"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    semester_year: Mapped[int] = mapped_column(SmallInteger)
    semester_term: Mapped[SemesterTerm] = _term_column()
    credits_attempted: Mapped[int] = mapped_column(SmallInteger)
    credits_earned: Mapped[int] = mapped_column(SmallInteger)
    average: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))


class CabinetAppeal(Base):
    __tablename__ = "cabinet_appeals"
    __table_args__ = (
        UniqueConstraint("user_id", "reference", name="uq_cabinet_appeals_natural_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    reference: Mapped[str] = mapped_column(String(40))
    subject_code: Mapped[str] = mapped_column(String(20))
    semester_year: Mapped[int] = mapped_column(SmallInteger)
    semester_term: Mapped[SemesterTerm] = _term_column()
    status: Mapped[AppealStatus] = mapped_column(_enum(AppealStatus, "cabinet_appeal_status"))
    submitted_on: Mapped[date] = mapped_column(Date)
    decided_on: Mapped[date | None] = mapped_column(Date)


class CabinetConflict(Base):
    """Registry and mirror disagree on this grade. Only the course is recorded, never either value, so staff can
    be told which course to look at without seeing a grade (D-126)."""

    __tablename__ = "cabinet_conflicts"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "subject_code",
            "semester_year",
            "semester_term",
            name="uq_cabinet_conflicts_natural_key",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    subject_code: Mapped[str] = mapped_column(String(20))
    semester_year: Mapped[int] = mapped_column(SmallInteger)
    semester_term: Mapped[SemesterTerm] = _term_column()
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
