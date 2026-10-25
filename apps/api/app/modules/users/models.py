import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import uuid7

AZ_COLLATION = "az-x-icu"


class UserStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class PersonType(StrEnum):
    """Role in the university registry (academic imports), independent of RBAC roles."""

    STUDENT = "student"
    TEACHER = "teacher"


class RoleCode(StrEnum):
    STUDENT = "student"
    TEACHER = "teacher"
    STAFF = "staff"
    MODERATOR = "moderator"
    ADMIN = "admin"
    GUEST = "guest"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    # Stable subject from the identity provider; e-mail and names may change. NULL until an imported
    # person signs in for the first time (DECISIONS D-029).
    idp_subject: Mapped[str | None] = mapped_column(String(255), unique=True)
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    # Student or employee number from the university registry: the stable key of academic imports.
    university_id: Mapped[str | None] = mapped_column(String(32), unique=True)
    person_type: Mapped[PersonType | None] = mapped_column(
        Enum(PersonType, name="person_type", values_callable=lambda e: [m.value for m in e])
    )
    academic_group_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("academic_groups.id"), index=True
    )
    given_name: Mapped[str] = mapped_column(String(100, collation=AZ_COLLATION), default="")
    family_name: Mapped[str] = mapped_column(String(100, collation=AZ_COLLATION), default="")
    display_name: Mapped[str] = mapped_column(String(200, collation=AZ_COLLATION))
    # normalize_az-folded names and identifiers for diacritic-insensitive admin search (§13.1).
    search_key: Mapped[str] = mapped_column(String(700), default="")
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status", values_callable=lambda e: [m.value for m in e]),
        default=UserStatus.ACTIVE,
        server_default=UserStatus.ACTIVE.value,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    code: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
