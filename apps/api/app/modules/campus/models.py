import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import uuid7
from app.modules.users.models import AZ_COLLATION


class RoomType(StrEnum):
    LECTURE_HALL = "lecture_hall"
    CLASSROOM = "classroom"
    LABORATORY = "laboratory"
    COMPUTER_LAB = "computer_lab"
    STUDIO = "studio"
    LIBRARY = "library"
    OFFICE = "office"
    SERVICE = "service"


class _Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Building(_Timestamps, Base):
    __tablename__ = "buildings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name_az: Mapped[str] = mapped_column(String(200, collation=AZ_COLLATION))
    address: Mapped[str] = mapped_column(String(255), default="")


class Floor(_Timestamps, Base):
    """One storey of a building. Its plan is drawn from the rooms' rectangles in a ``width × height`` frame."""

    __tablename__ = "floors"
    __table_args__ = (
        UniqueConstraint("building_id", "level"),
        CheckConstraint("width > 0 AND height > 0", name="positive_size"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    building_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("buildings.id"), index=True)
    # 0 is the ground floor, negative levels are basements.
    level: Mapped[int] = mapped_column(SmallInteger)
    name_az: Mapped[str] = mapped_column(String(100, collation=AZ_COLLATION))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)


class Room(_Timestamps, Base):
    __tablename__ = "rooms"
    __table_args__ = (
        CheckConstraint("width > 0 AND height > 0 AND x >= 0 AND y >= 0", name="geometry"),
        CheckConstraint("capacity IS NULL OR capacity > 0", name="positive_capacity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    # Unique across the campus, as printed on the door and in timetables ("1-305").
    code: Mapped[str] = mapped_column(String(20, collation=AZ_COLLATION), unique=True)
    floor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("floors.id"), index=True)
    name_az: Mapped[str] = mapped_column(String(200, collation=AZ_COLLATION), default="")
    type: Mapped[RoomType] = mapped_column(
        Enum(RoomType, name="room_type", values_callable=lambda members: [m.value for m in members])
    )
    capacity: Mapped[int | None] = mapped_column(SmallInteger)
    x: Mapped[int] = mapped_column(Integer)
    y: Mapped[int] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    search_key: Mapped[str] = mapped_column(String(300), default="")
