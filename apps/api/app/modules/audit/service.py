import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import BAKU
from app.modules.academics.models import AcademicImport
from app.modules.audit.models import AuditAction, AuditLog
from app.modules.users.models import User


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


@dataclass(frozen=True, slots=True)
class AuditEntry:
    log: AuditLog
    actor_name: str | None
    target_label: str | None


@dataclass(frozen=True, slots=True)
class AuditPage:
    items: list[AuditEntry]
    total: int


@dataclass(frozen=True, slots=True)
class AuditFilter:
    action: AuditAction | None = None
    actor_id: uuid.UUID | None = None
    target_id: str | None = None
    occurred_from: date | None = None
    """Inclusive, a Baku calendar day."""
    occurred_to: date | None = None
    """Inclusive, a Baku calendar day."""


class AuditLogService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def page(self, filters: AuditFilter, *, offset: int, limit: int) -> AuditPage:
        query = select(AuditLog)
        if filters.action is not None:
            query = query.where(AuditLog.action == filters.action.value)
        if filters.actor_id is not None:
            query = query.where(AuditLog.actor_id == filters.actor_id)
        if filters.target_id is not None:
            query = query.where(AuditLog.target_id == filters.target_id)
        if filters.occurred_from is not None:
            query = query.where(AuditLog.occurred_at >= _baku_midnight(filters.occurred_from))
        if filters.occurred_to is not None:
            next_day = filters.occurred_to + timedelta(days=1)
            query = query.where(AuditLog.occurred_at < _baku_midnight(next_day))

        total = await self.session.scalar(select(func.count()).select_from(query.subquery()))
        logs = list(
            await self.session.scalars(
                query.order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        names = await self._user_names(
            {log.actor_id for log in logs if log.actor_id}
            | {
                uuid.UUID(log.target_id)
                for log in logs
                if log.target_type == "user" and log.target_id
            }
        )
        files = await self._import_files(
            {
                uuid.UUID(log.target_id)
                for log in logs
                if log.target_type == "import" and log.target_id
            }
        )
        return AuditPage(
            items=[
                AuditEntry(
                    log=log,
                    actor_name=names.get(log.actor_id) if log.actor_id else None,
                    target_label=_target_label(log, names, files),
                )
                for log in logs
            ],
            total=total or 0,
        )

    async def _user_names(self, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not ids:
            return {}
        rows = await self.session.execute(
            select(User.id, User.display_name).where(User.id.in_(ids))
        )
        return {key: value for key, value in rows}

    async def _import_files(self, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not ids:
            return {}
        rows = await self.session.execute(
            select(AcademicImport.id, AcademicImport.file_name).where(AcademicImport.id.in_(ids))
        )
        return {key: value for key, value in rows}


def _baku_midnight(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=BAKU)


def _target_label(
    log: AuditLog, names: dict[uuid.UUID, str], files: dict[uuid.UUID, str]
) -> str | None:
    if not log.target_id:
        return None
    target = uuid.UUID(log.target_id)
    if log.target_type == "user":
        return names.get(target)
    if log.target_type == "import":
        return files.get(target)
    return None
