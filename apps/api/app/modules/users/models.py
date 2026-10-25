import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
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


class DmPolicy(StrEnum):
    """Who may start a direct message with the user (§5.4); teachers and staff always can."""

    EVERYONE = "everyone"
    SHARED_CONTEXT = "shared_context"
    GUIDES_AND_TEACHERS = "guides_and_teachers"
    NOBODY = "nobody"


class ContactVisibility(StrEnum):
    """Who sees the user's e-mail address; hidden unless the user opts in (§5.4, §1.1)."""

    HIDDEN = "hidden"
    SHARED_CONTEXT = "shared_context"
    EVERYONE = "everyone"


def _enum(enum: type[StrEnum], name: str) -> Enum:
    return Enum(enum, name=name, values_callable=lambda members: [m.value for m in members])


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
    bio: Mapped[str] = mapped_column(String(300), default="", server_default="")
    # Object key of the re-encoded profile photo; the random part doubles as the cache version.
    photo_key: Mapped[str | None] = mapped_column(String(200))
    dm_policy: Mapped[DmPolicy] = mapped_column(
        _enum(DmPolicy, "dm_policy"),
        default=DmPolicy.SHARED_CONTEXT,
        server_default=DmPolicy.SHARED_CONTEXT.value,
    )
    contact_visibility: Mapped[ContactVisibility] = mapped_column(
        _enum(ContactVisibility, "contact_visibility"),
        default=ContactVisibility.HIDDEN,
        server_default=ContactVisibility.HIDDEN.value,
    )
    # Optimistic concurrency for profile edits (§4.2); photo changes do not bump it.
    profile_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
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
