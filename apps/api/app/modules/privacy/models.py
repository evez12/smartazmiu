import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, func
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
