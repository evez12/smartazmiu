import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, SmallInteger, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import uuid7


class ConsentPurpose(StrEnum):
    """Processing the user agreed to or declined (Law "On Personal Data", §5.4)."""

    PRIVACY_NOTICE = "privacy_notice"
    """Acknowledged the privacy notice of a given version."""
    CONTACT_SHARING = "contact_sharing"
    """E-mail visible to other users."""
    PROFILE_PHOTO = "profile_photo"
    """Photo shown to other users."""
    MATERIAL_COPYRIGHT = "material_copyright"
    """Confirmed the right to share an uploaded course material (§6.1); one record per version."""


class ConsentRecord(Base):
    """Append-only history; the current state of a purpose is its latest record."""

    __tablename__ = "consent_records"
    __table_args__ = (
        Index(
            "ix_consent_records_user_id_purpose_recorded_at", "user_id", "purpose", "recorded_at"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    purpose: Mapped[ConsentPurpose] = mapped_column(
        Enum(ConsentPurpose, name="consent_purpose", values_callable=lambda e: [m.value for m in e])
    )
    granted: Mapped[bool] = mapped_column(Boolean)
    policy_version: Mapped[str | None] = mapped_column(String(20))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DeletionReason(StrEnum):
    SELF_SERVICE = "self_service"
    STAFF = "staff"
    TEST_CLEANUP = "test_cleanup"
    """Throwaway ``e2e-`` accounts of a development stack (D-046)."""


class AccountDeletion(Base):
    """The purge ledger: one row per deletion request, kept after the purge as the proof it happened.

    It holds no name, e-mail or university id. ``subject_hash`` is what survives a restore from backup: the
    restore runbook matches every user of the restored database against it and purges the matches again.
    """

    __tablename__ = "account_deletions"
    __table_args__ = (
        Index(
            "ix_account_deletions_due",
            "purge_due_at",
            postgresql_where=text("completed_at IS NULL AND cancelled_at IS NULL"),
        ),
        Index(
            "ix_account_deletions_user_id",
            "user_id",
            unique=True,
            postgresql_where=text("completed_at IS NULL AND cancelled_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    subject_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reason: Mapped[DeletionReason] = mapped_column(
        Enum(
            DeletionReason,
            name="account_deletion_reason",
            values_callable=lambda e: [m.value for m in e],
        )
    )
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    purge_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # One timestamp per purge step: a retry skips what is done (at-least-once, idempotent).
    database_purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    objects_purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    identity_removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    # The class of the last failure, never its message: messages can quote personal data.
    last_error: Mapped[str | None] = mapped_column(String(80))
