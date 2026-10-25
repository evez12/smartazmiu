import uuid
from datetime import date, datetime, time
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import uuid7


def _enum(enum: type[StrEnum], name: str) -> Enum:
    return Enum(enum, name=name, values_callable=lambda members: [m.value for m in members])


class WeekParity(StrEnum):
    """``upper`` (üst) and ``lower`` (alt) weeks alternate; ``every`` entries take place in both."""

    EVERY = "every"
    UPPER = "upper"
    LOWER = "lower"


class ClassType(StrEnum):
    LECTURE = "lecture"
    SEMINAR = "seminar"
    LABORATORY = "laboratory"


class _Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ScheduleEntry(_Timestamps, Base):
    """A weekly class of a course offering, in Baku wall-clock time (§6.1).

    ``active_from``/``active_until`` keep the timetable's history: an entry replaced by a later import stops at
    the day before the import instead of disappearing from weeks that already happened.
    """

    __tablename__ = "schedule_entries"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 1 AND 7", name="iso_weekday"),
        CheckConstraint("ends_at > starts_at", name="times_ordered"),
        CheckConstraint("active_until IS NULL OR active_until >= active_from", name="active_range"),
        Index("ix_schedule_entries_offering_weekday", "course_offering_id", "weekday"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    course_offering_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course_offerings.id", ondelete="CASCADE")
    )
    weekday: Mapped[int] = mapped_column(SmallInteger)
    """ISO weekday: 1 is Monday."""
    starts_at: Mapped[time] = mapped_column(Time)
    ends_at: Mapped[time] = mapped_column(Time)
    week_parity: Mapped[WeekParity] = mapped_column(_enum(WeekParity, "week_parity"))
    class_type: Mapped[ClassType] = mapped_column(_enum(ClassType, "class_type"))
    room_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("rooms.id", ondelete="SET NULL"), index=True
    )
    # NULL: every teacher of the offering teaches this class.
    teacher_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    active_from: Mapped[date] = mapped_column(Date)
    active_until: Mapped[date | None] = mapped_column(Date)


class ScheduleEntryGroup(Base):
    """Restricts an entry to some groups of a joint offering; an entry without rows is for all of them."""

    __tablename__ = "schedule_entry_groups"

    schedule_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schedule_entries.id", ondelete="CASCADE"), primary_key=True
    )
    academic_group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academic_groups.id"), primary_key=True, index=True
    )


class ScheduleChange(_Timestamps, Base):
    """Overrides one occurrence of an entry: cancelled, moved, another room or a substitute teacher."""

    __tablename__ = "schedule_changes"
    __table_args__ = (
        UniqueConstraint("schedule_entry_id", "occurs_on"),
        CheckConstraint(
            "NOT cancelled OR (new_date IS NULL AND new_starts_at IS NULL AND new_ends_at IS NULL"
            " AND room_id IS NULL AND teacher_id IS NULL)",
            name="cancel_has_no_changes",
        ),
        CheckConstraint(
            "(new_starts_at IS NULL) = (new_ends_at IS NULL)", name="new_times_together"
        ),
        CheckConstraint(
            "new_ends_at IS NULL OR new_ends_at > new_starts_at", name="new_times_ordered"
        ),
        Index("ix_schedule_changes_new_date", "new_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    schedule_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schedule_entries.id", ondelete="CASCADE")
    )
    occurs_on: Mapped[date] = mapped_column(Date)
    """The date the class was scheduled for."""
    cancelled: Mapped[bool] = mapped_column(Boolean, default=False)
    new_date: Mapped[date | None] = mapped_column(Date)
    new_starts_at: Mapped[time | None] = mapped_column(Time)
    new_ends_at: Mapped[time | None] = mapped_column(Time)
    room_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rooms.id", ondelete="SET NULL"))
    teacher_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    note: Mapped[str] = mapped_column(String(300), default="")


class WeekParityOverride(Base):
    """From ``week_starts_on`` on, weeks alternate starting with ``parity`` (holidays shift the rhythm)."""

    __tablename__ = "week_parity_overrides"
    __table_args__ = (
        UniqueConstraint("semester_id", "week_starts_on"),
        CheckConstraint("extract(isodow from week_starts_on) = 1", name="starts_on_monday"),
        CheckConstraint("parity <> 'every'", name="upper_or_lower"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    semester_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("semesters.id", ondelete="CASCADE"), index=True
    )
    week_starts_on: Mapped[date] = mapped_column(Date)
    parity: Mapped[WeekParity] = mapped_column(_enum(WeekParity, "week_parity"))
