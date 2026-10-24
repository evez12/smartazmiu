import uuid
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditAction, AuditLog


def record_audit(
    session: AsyncSession,
    action: AuditAction,
    *,
    actor_id: uuid.UUID | None,
    target_type: str | None = None,
    target_id: uuid.UUID | str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    """Add an audit entry to the caller's transaction, so it is written if and only if the change is."""
    entry = AuditLog(
        action=action.value,
        actor_id=actor_id,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        details=details or {},
        request_id=structlog.contextvars.get_contextvars().get("request_id"),
    )
    session.add(entry)
    return entry
