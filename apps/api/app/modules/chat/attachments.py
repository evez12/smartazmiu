"""Chat attachments (§5.3, §6.1, §14, D-068).

Upload: the client asks for a presigned PUT (`presign`), uploads straight to object storage under a random key,
then sends a message naming the attachment. Nothing is visible to other members or downloadable until the
worker has checked the content against its declared type and ClamAV has found it clean. Infected or mismatching
files are hidden, their uploader is notified and the object is purged. Uploads never sent are purged as well.
Object storage being down fails only the attachment parts; text chat does not touch it (§13.5).
"""

import io
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import PurePosixPath
from urllib.parse import quote

import structlog
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.antivirus import ScannerUnavailableError, VirusScanner
from app.core.errors import AppError
from app.core.ratelimit import RateLimit, enforce_rate_limit
from app.core.storage import ObjectStorage, StorageUnavailableError
from app.core.time import utc_now
from app.modules.chat.access import ChannelAccess, deny
from app.modules.chat.lookup import find_message
from app.modules.chat.models import MessageAttachment, ScanStatus
from app.modules.chat.payloads import PREVIEWABLE
from app.modules.chat.policy import Action
from app.modules.notifications.models import NotificationCategory, NotificationKind
from app.modules.notifications.service import NotificationSpec, Notifier
from app.modules.users.models import User
from app.modules.users.service import CurrentUser

logger = structlog.get_logger(__name__)

MAX_SIZE = 25 * 1024 * 1024
MAX_PER_MESSAGE = 10
# 20 attachments per hour per user (§5.5), counted when the upload is requested.
UPLOAD_LIMIT = RateLimit("chat_attachment", limit=20, window_seconds=3600)
UPLOAD_TTL = timedelta(minutes=5)
DOWNLOAD_TTL = timedelta(minutes=1)
# An upload not sent within a day is abandoned (§13.2) and purged.
ORPHAN_AFTER = timedelta(hours=24)
SUBJECT_TYPE = "chat_attachment"

ZIP_MAGIC = (b"PK\x03\x04", b"PK\x05\x06")


# Extension → type. SVG is deliberately absent: it is a document that can carry script (§13.2).
FILE_TYPES: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".zip": "application/zip",
}
# Browsers on Windows report ZIP archives and some JPEGs under older names.
MIME_ALIASES = {"application/x-zip-compressed": "application/zip", "image/jpg": "image/jpeg"}


def file_type(filename: str, mime: str) -> str:
    """The allowed MIME type of a file named ``filename`` that the browser reports as ``mime``; extension and
    reported type must agree, or a typed 422."""
    kind = FILE_TYPES.get(PurePosixPath(filename.lower()).suffix)
    declared = MIME_ALIASES.get(mime.lower(), mime.lower())
    if kind is None or kind != declared:
        raise AppError(
            "chat.attachment_type_not_allowed",
            422,
            details={"allowed": sorted({name.lstrip(".") for name in FILE_TYPES})},
        )
    return kind


def content_matches(mime: str, data: bytes) -> bool:
    """Magic-byte check: the stored bytes really are what the name and the browser claimed (§14)."""
    if mime == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if mime == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if mime == "image/gif":
        return data.startswith((b"GIF87a", b"GIF89a"))
    if mime == "image/webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    if mime == "application/pdf":
        return data.startswith(b"%PDF-")
    if not data.startswith(ZIP_MAGIC):
        return False
    if mime == "application/zip":
        return True
    # DOCX and PPTX are ZIP packages; the part that defines the document type must be there.
    marker = "word/document.xml" if "wordprocessing" in mime else "ppt/presentation.xml"
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as package:
            return marker in package.namelist()
    except zipfile.BadZipFile:
        return False


def image_size(data: bytes) -> tuple[int | None, int | None]:
    """Width and height from the header only; nothing is decoded (decompression bombs, §14)."""
    try:
        with Image.open(io.BytesIO(data)) as image:
            return image.width, image.height
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        return None, None


def safe_filename(filename: str) -> str:
    """The name shown and offered for download: the last path segment, without control characters."""
    name = PurePosixPath(filename.replace("\\", "/")).name
    cleaned = "".join(char for char in name if char.isprintable() and char not in '"<>')
    return cleaned.strip()[:200] or "fayl"


def content_disposition(filename: str, inline: bool) -> str:
    # RFC 6266 / 5987: an ASCII fallback plus the UTF-8 name, so "Mühazirə 3.pdf" keeps its letters.
    fallback = filename.encode("ascii", "replace").decode().replace("?", "_")
    kind = "inline" if inline else "attachment"
    return f"{kind}; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename)}"


@dataclass(frozen=True, slots=True)
class PresignedUpload:
    attachment: MessageAttachment
    url: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class PresignedDownload:
    url: str
    expires_at: datetime


class AttachmentService:
    def __init__(
        self, session: AsyncSession, access: ChannelAccess, storage: ObjectStorage
    ) -> None:
        self.session = session
        self.access = access
        self.storage = storage

    async def presign(
        self, user: CurrentUser, channel_id: uuid.UUID, filename: str, mime: str, size: int
    ) -> PresignedUpload:
        kind = file_type(filename, mime)
        if not 0 < size <= MAX_SIZE:
            raise AppError("chat.attachment_too_large", 422, details={"max_bytes": MAX_SIZE})
        decision = await self.access.decide(user, channel_id, Action.SEND_ATTACHMENT)
        if not decision.allowed:
            raise deny(decision)
        await enforce_rate_limit(self.access.cache, UPLOAD_LIMIT, str(user.id))
        # A random key that names neither the person nor the file, so it cannot be guessed (§14).
        key = f"chat/{channel_id}/{uuid.uuid4().hex}"
        try:
            url = await self.storage.presign_put(key, kind, UPLOAD_TTL)
        except StorageUnavailableError as exc:
            raise AppError("chat.attachments_unavailable", 503) from exc
        attachment = MessageAttachment(
            uploader_id=user.id,
            channel_id=channel_id,
            object_key=key,
            filename=safe_filename(filename),
            mime=kind,
            size_bytes=size,
        )
        self.session.add(attachment)
        await self.session.commit()
        return PresignedUpload(attachment, url, utc_now() + UPLOAD_TTL)

    async def claim(
        self, user: CurrentUser, channel_id: uuid.UUID, ids: list[uuid.UUID], message_id: int
    ) -> list[MessageAttachment]:
        """Binds the user's uploads to a new message, in the caller's transaction. Each must be the user's own,
        for this channel, not sent before, and uploaded with the size that was announced."""
        if len(ids) > MAX_PER_MESSAGE:
            raise AppError("chat.too_many_attachments", 422, details={"max": MAX_PER_MESSAGE})
        rows = list(
            await self.session.scalars(
                select(MessageAttachment).where(MessageAttachment.id.in_(ids)).with_for_update()
            )
        )
        found = {row.id: row for row in rows}
        for attachment_id in ids:
            row = found.get(attachment_id)
            if (
                row is None
                or row.uploader_id != user.id
                or row.channel_id != channel_id
                or row.message_id is not None
            ):
                # One answer for every case: an id of someone else's upload reveals nothing (§14).
                raise AppError("chat.attachment_not_found", 422)
        for row in rows:
            try:
                stored = await self.storage.head(row.object_key)
            except StorageUnavailableError as exc:
                raise AppError("chat.attachments_unavailable", 503) from exc
            if stored is None:
                raise AppError("chat.attachment_not_uploaded", 422)
            if stored != row.size_bytes or stored > MAX_SIZE:
                raise AppError("chat.attachment_size_mismatch", 422)
            row.message_id = message_id
            row.attached_at = utc_now()
        return [found[attachment_id] for attachment_id in ids]

    async def download(
        self, user: CurrentUser, attachment_id: uuid.UUID, *, inline: bool
    ) -> PresignedDownload:
        """A one-minute link for a member of the message's channel, once the file is clean (§14)."""
        attachment = await self.session.get(MessageAttachment, attachment_id)
        if attachment is None or attachment.message_id is None:
            raise AppError("chat.attachment_not_found", 404)
        message = await find_message(self.session, attachment.message_id)
        if message is None or message.deleted_at is not None:
            raise AppError("chat.attachment_not_found", 404)
        if not (await self.access.decide(user, message.channel_id, Action.READ)).allowed:
            raise AppError("chat.attachment_not_found", 404)
        if attachment.scan_status is not ScanStatus.CLEAN:
            raise AppError("chat.attachment_not_available", 409)
        try:
            url = await self.storage.presign_get(
                attachment.object_key,
                content_type=attachment.mime,
                disposition=content_disposition(
                    attachment.filename, inline and attachment.mime in PREVIEWABLE
                ),
                expires=DOWNLOAD_TTL,
            )
        except StorageUnavailableError as exc:
            raise AppError("chat.attachments_unavailable", 503) from exc
        return PresignedDownload(url, utc_now() + DOWNLOAD_TTL)


@dataclass(frozen=True, slots=True)
class ScanReport:
    clean: int = 0
    rejected: int = 0
    waiting: int = 0


class AttachmentScanner:
    """The worker side: type check, ClamAV, purge (§6.1, §13.2). Every step is idempotent (ARQ is
    at-least-once)."""

    def __init__(
        self, session: AsyncSession, storage: ObjectStorage, scanner: VirusScanner
    ) -> None:
        self.session = session
        self.storage = storage
        self.scanner = scanner

    async def scan_pending(self, limit: int = 50) -> tuple[ScanReport, list[MessageAttachment]]:
        """Scans sent attachments that are still pending, one row lock at a time; returns the report and the
        attachments whose status changed (for the caller to announce)."""
        clean = rejected = waiting = 0
        changed: list[MessageAttachment] = []
        for _ in range(limit):
            attachment = await self.session.scalar(
                select(MessageAttachment)
                .where(
                    MessageAttachment.scan_status == ScanStatus.PENDING,
                    MessageAttachment.message_id.is_not(None),
                    MessageAttachment.scan_after <= utc_now(),
                )
                .order_by(MessageAttachment.attached_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if attachment is None:
                break
            outcome = await self._scan(attachment)
            await self.session.commit()
            if outcome is None:
                waiting += 1
                continue
            changed.append(attachment)
            if outcome is ScanStatus.CLEAN:
                clean += 1
            else:
                rejected += 1
        return ScanReport(clean, rejected, waiting), changed

    async def _scan(self, attachment: MessageAttachment) -> ScanStatus | None:
        try:
            data = await self.storage.get(attachment.object_key)
        except StorageUnavailableError:
            self._later(attachment, "storage_unavailable")
            return None
        if data is None or len(data) != attachment.size_bytes:
            return await self._reject(attachment, ScanStatus.FAILED, "content_missing")
        if not content_matches(attachment.mime, data):
            return await self._reject(attachment, ScanStatus.FAILED, "type_mismatch")
        try:
            result = await self.scanner.scan(data)
        except ScannerUnavailableError as exc:
            self._later(attachment, f"scanner_unavailable:{exc}")
            return None
        if not result.clean:
            logger.warning(
                "attachment_infected", attachment_id=str(attachment.id), signature=result.signature
            )
            return await self._reject(attachment, ScanStatus.INFECTED, "infected")
        if attachment.mime.startswith("image/"):
            attachment.width, attachment.height = image_size(data)
        attachment.scan_status = ScanStatus.CLEAN
        attachment.scanned_at = utc_now()
        return ScanStatus.CLEAN

    def _later(self, attachment: MessageAttachment, reason: str) -> None:
        # Stays "scanning" for everyone; retried with a growing pause up to five minutes.
        attachment.scan_attempts += 1
        delay = min(300, 15 * 2 ** min(attachment.scan_attempts, 5))
        attachment.scan_after = utc_now() + timedelta(seconds=delay)
        logger.warning("attachment_scan_deferred", attachment_id=str(attachment.id), reason=reason)

    async def _reject(
        self, attachment: MessageAttachment, status: ScanStatus, reason: str
    ) -> ScanStatus:
        attachment.scan_status = status
        attachment.scanned_at = utc_now()
        uploader = attachment.uploader_id
        if uploader is not None:
            # In-app only: the uploader learns why the file is not shown (§13.2).
            await Notifier(self.session).notify(
                select(User.id).where(User.id == uploader),
                NotificationSpec(
                    category=NotificationCategory.CHAT,
                    kind=NotificationKind.CHAT_ATTACHMENT_REJECTED,
                    subject_type=SUBJECT_TYPE,
                    subject_id=attachment.id,
                    dedupe_key=f"chat.attachment:{attachment.id}",
                    title=attachment.filename,
                    link=f"/chat/{attachment.channel_id}",
                ),
                deliver=False,
            )
        logger.info("attachment_rejected", attachment_id=str(attachment.id), reason=reason)
        return status

    async def purge(self, now: datetime | None = None) -> int:
        """Deletes the objects of rejected uploads and of uploads never sent (§13.2); idempotent."""
        now = now or utc_now()
        purged = 0
        rejected = list(
            await self.session.scalars(
                select(MessageAttachment).where(
                    MessageAttachment.scan_status.in_([ScanStatus.INFECTED, ScanStatus.FAILED]),
                    MessageAttachment.purged_at.is_(None),
                )
            )
        )
        abandoned = list(
            await self.session.scalars(
                select(MessageAttachment).where(
                    MessageAttachment.message_id.is_(None),
                    MessageAttachment.created_at < now - ORPHAN_AFTER,
                )
            )
        )
        for attachment in [*rejected, *abandoned]:
            try:
                await self.storage.delete(attachment.object_key)
            except StorageUnavailableError:
                logger.warning("attachment_purge_deferred", attachment_id=str(attachment.id))
                continue
            if attachment.message_id is None:
                await self.session.delete(attachment)
            else:
                await self.session.execute(
                    update(MessageAttachment)
                    .where(MessageAttachment.id == attachment.id)
                    .values(purged_at=now)
                )
            purged += 1
        await self.session.commit()
        return purged
