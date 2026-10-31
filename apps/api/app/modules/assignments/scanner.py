"""Worker side of submission files: the same checks and back-off as material versions (D-071, D-092)."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.antivirus import VirusScanner
from app.core.file_scan import UNSAVED_AFTER, check_file
from app.core.storage import ObjectStorage, StorageUnavailableError
from app.core.time import utc_now
from app.modules.assignments.models import AssignmentFile
from app.modules.chat.models import ScanStatus


@dataclass(slots=True)
class SubmissionScanReport:
    clean: int = 0
    rejected: int = 0
    waiting: int = 0


class SubmissionScanner:
    def __init__(
        self, session: AsyncSession, storage: ObjectStorage, scanner: VirusScanner
    ) -> None:
        self.session = session
        self.storage = storage
        self.scanner = scanner

    async def scan_pending(self, limit: int = 20) -> SubmissionScanReport:
        report = SubmissionScanReport()
        for _ in range(limit):
            file = await self.session.scalar(
                select(AssignmentFile)
                .where(
                    AssignmentFile.scan_status == ScanStatus.PENDING,
                    AssignmentFile.submission_id.is_not(None),
                    AssignmentFile.scan_after <= utc_now(),
                )
                .order_by(AssignmentFile.scan_after)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if file is None:
                break
            status = await check_file(file, self.storage, self.scanner, kind="submission")
            await self.session.commit()
            if status is None:
                report.waiting += 1
            elif status is ScanStatus.CLEAN:
                report.clean += 1
            else:
                report.rejected += 1
        return report

    async def purge(self, now: datetime | None = None) -> int:
        """Deletes the objects of rejected files and of uploads that were never submitted."""
        now = now or utc_now()
        rejected = list(
            await self.session.scalars(
                select(AssignmentFile).where(
                    AssignmentFile.scan_status.in_([ScanStatus.INFECTED, ScanStatus.FAILED]),
                    AssignmentFile.purged_at.is_(None),
                )
            )
        )
        unsaved = list(
            await self.session.scalars(
                select(AssignmentFile).where(
                    and_(
                        AssignmentFile.submission_id.is_(None),
                        AssignmentFile.created_at < now - UNSAVED_AFTER,
                    )
                )
            )
        )
        purged = 0
        for file in [*rejected, *unsaved]:
            try:
                await self.storage.delete(file.object_key)
            except StorageUnavailableError:
                continue
            if file.submission_id is None:
                await self.session.delete(file)
            else:
                await self.session.execute(
                    update(AssignmentFile).where(AssignmentFile.id == file.id).values(purged_at=now)
                )
            purged += 1
        await self.session.commit()
        return purged
