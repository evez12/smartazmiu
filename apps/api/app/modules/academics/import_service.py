"""Import lifecycle: upload → validated preview → apply in one transaction (§6.1, DECISIONS D-031)."""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.time import utc_now
from app.modules.academics.files import FileEncoding, Row, Table, read_table
from app.modules.academics.importers import MAX_STORED_ISSUES, ImportRun, RowIssue, process
from app.modules.academics.models import AcademicImport, ImportKind, ImportStatus
from app.modules.academics.registry import SPECS
from app.modules.audit.models import AuditAction
from app.modules.audit.service import record_audit

logger = structlog.get_logger(__name__)

# A preview can be applied for a day; afterwards its stored cells are purged.
PREVIEW_TTL = timedelta(hours=24)
# Serializes applies: later kinds read what earlier ones wrote, and two staff members may press "apply".
APPLY_LOCK_ID = 7_652_002


@dataclass(frozen=True, slots=True)
class ImportPage:
    items: list[AcademicImport]
    total: int


def expires_at(record: AcademicImport) -> datetime | None:
    return record.created_at + PREVIEW_TTL if record.status is ImportStatus.READY else None


class ImportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        kind: ImportKind,
        file_name: str,
        data: bytes,
        encoding: FileEncoding | None,
        actor_id: uuid.UUID | None,
    ) -> AcademicImport:
        """Validate a file without changing academic data; raises ``UnreadableFileError``."""
        table = read_table(file_name, data, encoding)
        await self._purge_expired_payloads()
        run = await process(SPECS[kind], table, self.session, write=False)
        valid = not run.issues
        record = AcademicImport(
            kind=kind,
            status=ImportStatus.READY if valid else ImportStatus.INVALID,
            file_name=file_name[-255:],
            file_sha256=hashlib.sha256(data).hexdigest(),
            file_size=len(data),
            encoding=table.encoding.value if table.encoding else None,
            row_count=len(table.rows),
            created_by=actor_id,
            payload=_payload(table) if valid else None,
        )
        _store_result(record, run)
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        logger.info("import_previewed", kind=kind.value, status=record.status.value)
        return record

    async def apply(self, import_id: uuid.UUID, actor_id: uuid.UUID | None) -> AcademicImport:
        record = await self._locked(import_id)
        if record.status is ImportStatus.APPLIED:
            return record
        if record.status is not ImportStatus.READY:
            raise AppError("import.not_applicable", 409)
        if record.payload is None or record.created_at + PREVIEW_TTL < utc_now():
            raise AppError("import.expired", 409)
        await self.session.execute(select(func.pg_advisory_xact_lock(APPLY_LOCK_ID)))

        table = _table(record.payload, record.encoding)
        try:
            run = await process(SPECS[record.kind], table, self.session, write=True)
            if not run.issues:
                await self.session.flush()
        except IntegrityError:
            # A concurrent change outside imports violated a constraint; nothing is written.
            run = ImportRun(self.session, write=True)
            run.issues.append(RowIssue("conflicting_data"))

        if run.issues:
            # Data changed since the preview (another import, a sign-in): report, write nothing.
            await self.session.rollback()
            record = await self._locked(import_id)
            record.status = ImportStatus.FAILED
            record.payload = None
            _store_result(record, run)
            await self.session.commit()
            logger.info("import_failed", kind=record.kind.value, issues=len(run.issues))
            return record

        record.status = ImportStatus.APPLIED
        record.payload = None
        record.applied_by = actor_id
        record.applied_at = utc_now()
        _store_result(record, run)
        record_audit(
            self.session,
            AuditAction.IMPORT_APPLIED,
            actor_id=actor_id,
            target_type="import",
            target_id=record.id,
            details={"kind": record.kind.value, **record.summary},
        )
        await self.session.commit()
        logger.info("import_applied", kind=record.kind.value, **record.summary)
        return record

    async def get(self, import_id: uuid.UUID) -> AcademicImport:
        record = await self.session.get(AcademicImport, import_id)
        if record is None:
            raise AppError("request.not_found", 404)
        return record

    async def previously_applied_at(self, record: AcademicImport) -> datetime | None:
        """When the same file was applied before; re-applying it changes nothing (§6.1)."""
        applied_at: datetime | None = await self.session.scalar(
            select(func.max(AcademicImport.applied_at)).where(
                AcademicImport.kind == record.kind,
                AcademicImport.file_sha256 == record.file_sha256,
                AcademicImport.status == ImportStatus.APPLIED,
                AcademicImport.id != record.id,
            )
        )
        return applied_at

    async def page(self, *, kind: ImportKind | None, offset: int, limit: int) -> ImportPage:
        query = select(AcademicImport)
        if kind is not None:
            query = query.where(AcademicImport.kind == kind)
        total = await self.session.scalar(select(func.count()).select_from(query.subquery()))
        items = await self.session.scalars(
            query.order_by(AcademicImport.created_at.desc(), AcademicImport.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return ImportPage(list(items), total or 0)

    async def _locked(self, import_id: uuid.UUID) -> AcademicImport:
        record = await self.session.get(
            AcademicImport, import_id, with_for_update=True, populate_existing=True
        )
        if record is None:
            raise AppError("request.not_found", 404)
        return record

    async def _purge_expired_payloads(self) -> None:
        await self.session.execute(
            update(AcademicImport)
            .where(
                AcademicImport.payload.is_not(None),
                AcademicImport.created_at < utc_now() - PREVIEW_TTL,
            )
            .values(payload=None)
        )


def _store_result(record: AcademicImport, run: ImportRun) -> None:
    # File-level problems first, then by row; the sort is stable, so columns keep their order.
    issues = sorted(run.issues, key=lambda issue: issue.row or 0)
    record.summary = dict(run.counts)
    record.errors = [issue.as_dict() for issue in issues[:MAX_STORED_ISSUES]]
    record.error_count = len(run.issues)


def _payload(table: Table) -> dict[str, Any]:
    return {
        "columns": table.columns,
        "rows": [{"row": row.number, "cells": row.cells} for row in table.rows],
    }


def _table(payload: dict[str, Any], encoding: str | None) -> Table:
    return Table(
        columns=list(payload["columns"]),
        rows=[Row(row["row"], row["cells"]) for row in payload["rows"]],
        encoding=FileEncoding(encoding) if encoding else None,
    )
