"""The worker-side check every saved upload goes through: stored object, magic bytes, ClamAV (§14, D-068).

Shared by material versions and assignment submission files so the retry and rejection rules stay in one place.
"""

import uuid
from datetime import datetime, timedelta
from typing import Protocol

import structlog

from app.core.antivirus import ScannerUnavailableError, VirusScanner
from app.core.storage import ObjectStorage, StorageUnavailableError
from app.core.time import utc_now
from app.core.uploads import content_matches
from app.modules.chat.models import ScanStatus

logger = structlog.get_logger(__name__)

# Uploads whose form or submission was never saved are removed after this long.
UNSAVED_AFTER = timedelta(hours=24)


class ScannableFile(Protocol):
    id: uuid.UUID
    object_key: str
    size_bytes: int
    mime: str
    scan_status: ScanStatus
    scan_attempts: int
    scan_after: datetime
    scanned_at: datetime | None


async def check_file(
    file: ScannableFile, storage: ObjectStorage, scanner: VirusScanner, *, kind: str
) -> ScanStatus | None:
    """Clean, infected or failed, recorded on ``file``; ``None`` when storage or ClamAV is unavailable, in which
    case the file stays pending and is tried again later with back-off (§13.5)."""
    try:
        data = await storage.get(file.object_key)
    except StorageUnavailableError:
        defer(file, "storage_unavailable", kind)
        return None
    if data is None or len(data) != file.size_bytes or not content_matches(file.mime, data):
        return finish(file, ScanStatus.FAILED)
    try:
        result = await scanner.scan(data)
    except ScannerUnavailableError as exc:
        defer(file, f"scanner_unavailable:{exc}", kind)
        return None
    if not result.clean:
        logger.warning(f"{kind}_infected", file_id=str(file.id), signature=result.signature)
        return finish(file, ScanStatus.INFECTED)
    return finish(file, ScanStatus.CLEAN)


def finish(file: ScannableFile, status: ScanStatus) -> ScanStatus:
    file.scan_status = status
    file.scanned_at = utc_now()
    return status


def defer(file: ScannableFile, reason: str, kind: str) -> None:
    """Schedules the next attempt with back-off, up to five minutes apart."""
    file.scan_attempts += 1
    file.scan_after = utc_now() + timedelta(seconds=min(300, 15 * 2 ** min(file.scan_attempts, 5)))
    logger.warning(f"{kind}_scan_deferred", file_id=str(file.id), reason=reason)
