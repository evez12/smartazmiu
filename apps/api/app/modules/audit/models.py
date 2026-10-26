import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import uuid7


class AuditAction(StrEnum):
    """Privileged actions that must leave a trace (§14). Codes are stable; the UI localizes them."""

    ROLES_SYNCED = "user.roles_synced"
    ROLES_CHANGED = "user.roles_changed"
    ACCOUNT_LINKED = "user.account_linked"
    IMPORT_APPLIED = "import.applied"
    DATA_EXPORTED = "user.data_exported"
    ANNOUNCEMENT_PUBLISHED = "announcement.published"
    ANNOUNCEMENT_EDITED = "announcement.edited"
    ANNOUNCEMENT_ARCHIVED = "announcement.archived"
    EVENT_PUBLISHED = "event.published"
    EVENT_EDITED = "event.edited"
    EVENT_CANCELLED = "event.cancelled"
    EVENT_MANUAL_CHECK_IN = "event.manual_check_in"
    REPORT_CREATED = "report.created"
    REPORT_HANDLED = "report.handled"
    MATERIAL_REPORTED = "material.reported"
    MATERIAL_REPORT_HANDLED = "material.report_handled"
    MATERIAL_HIDDEN = "material.hidden"
    MATERIAL_SHOWN = "material.shown"


class AuditLog(Base):
    """Append-only. ``details`` never holds secrets, grades or free text typed by the affected user."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_occurred_at", "occurred_at"),
        Index("ix_audit_logs_actor_id_occurred_at", "actor_id", "occurred_at"),
        Index("ix_audit_logs_target", "target_type", "target_id", "occurred_at"),
        Index("ix_audit_logs_action_occurred_at", "action", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # NULL when the change came from the system itself (identity provider sync, seed imports).
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(64))
    target_type: Mapped[str | None] = mapped_column(String(32))
    target_id: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    request_id: Mapped[str | None] = mapped_column(String(64))
