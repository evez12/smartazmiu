"""Attachments: presign, send, scan, download, purge (§5.3, §5.5, §6.1, §13.2, §13.5, §14, D-068)."""

import io
import os
import uuid
import zipfile
from datetime import timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.antivirus import (
    ClamdScanner,
    ScannerUnavailableError,
    ScanResult,
    parse_reply,
)
from app.core.config import Settings
from app.core.db import Database
from app.core.errors import AppError
from app.core.time import utc_now
from app.modules.chat.attachments import (
    AttachmentScanner,
    content_disposition,
    content_matches,
    file_type,
    safe_filename,
)
from app.modules.chat.models import ChannelType, MessageAttachment, ScanStatus
from app.modules.notifications.models import Notification, NotificationKind
from app.modules.users.models import User
from app.workers import main as worker
from tests.support import FakeJobs, MemoryStorage

from .conftest import MakeChannel, MakePerson, Person

API = "/api/v1"
PDF = b"%PDF-1.7\n1 0 obj << >> endobj\n%%EOF\n"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
# The standard anti-virus test file: harmless, but every scanner reports it.
EICAR = rb"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


def png(width: int = 3, height: int = 2) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (10, 60, 120)).save(buffer, "PNG")
    return buffer.getvalue()


def package(*names: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in names:
            archive.writestr(name, "<xml/>")
    return buffer.getvalue()


class FakeScanner:
    def __init__(self) -> None:
        self.available = True
        self.scanned = 0

    async def scan(self, data: bytes) -> ScanResult:
        if not self.available:
            raise ScannerUnavailableError("ConnectionRefusedError")
        self.scanned += 1
        if EICAR in data:
            return ScanResult(clean=False, signature="Eicar-Test-Signature")
        return ScanResult(clean=True)


async def presign(
    client: AsyncClient,
    person: Person,
    channel_id: uuid.UUID,
    filename: str = "Mühazirə 3.pdf",
    mime: str = "application/pdf",
    size: int = len(PDF),
) -> Any:
    return await client.post(
        f"{API}/chat/attachments/presign",
        headers=person.headers,
        json={"channel_id": str(channel_id), "filename": filename, "mime": mime, "size": size},
    )


async def upload(
    client: AsyncClient,
    storage: MemoryStorage,
    person: Person,
    channel_id: uuid.UUID,
    data: bytes = PDF,
    filename: str = "Mühazirə 3.pdf",
    mime: str = "application/pdf",
) -> str:
    """Presigns and "uploads" like a browser would; returns the attachment id."""
    response = await presign(client, person, channel_id, filename, mime, len(data))
    assert response.status_code == 200, response.text
    body = response.json()
    storage.objects[body["object_key"]] = (data, mime)
    return str(body["attachment_id"])


async def send(
    client: AsyncClient, person: Person, channel_id: uuid.UUID, body: str, ids: list[str]
) -> Any:
    return await client.post(
        f"{API}/chat/channels/{channel_id}/messages",
        headers=person.headers,
        json={"body": body, "client_msg_id": str(uuid.uuid4()), "attachment_ids": ids},
    )


async def history(client: AsyncClient, person: Person, channel_id: uuid.UUID) -> list[Any]:
    response = await client.get(
        f"{API}/chat/channels/{channel_id}/messages", headers=person.headers
    )
    messages: list[Any] = response.json()["messages"]
    return messages


def test_types_are_checked_by_name_reported_type_and_content() -> None:
    assert file_type("Hesabat.DOCX", DOCX_MIME) == DOCX_MIME
    assert file_type("arxiv.zip", "application/x-zip-compressed") == "application/zip"
    for name, mime in (
        ("loqo.svg", "image/svg+xml"),
        ("hesabat.pdf", "image/png"),
        ("skript.html", "text/html"),
        ("adsiz", "application/pdf"),
    ):
        with pytest.raises(AppError) as refused:
            file_type(name, mime)
        assert refused.value.code == "chat.attachment_type_not_allowed"
    assert content_matches("application/pdf", PDF)
    assert content_matches("image/png", png())
    assert not content_matches("image/png", PDF)
    assert content_matches(DOCX_MIME, package("word/document.xml"))
    # A ZIP renamed to .docx, and a document renamed to .pptx, are both caught.
    assert not content_matches(DOCX_MIME, package("readme.txt"))
    pptx = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    assert not content_matches(pptx, package("word/document.xml"))
    assert content_matches("application/zip", package("a.txt"))
    assert not content_matches(DOCX_MIME, b"PK\x03\x04broken")
    assert safe_filename("..\\..\\C:/tmp/Mühazirə\x07 3.pdf") == "Mühazirə 3.pdf"
    assert safe_filename("\x00") == "fayl"
    assert content_disposition("Mühazirə 3.pdf", inline=False) == (
        "attachment; filename=\"M_hazir_ 3.pdf\"; filename*=UTF-8''M%C3%BChazir%C9%99%203.pdf"
    )
    assert parse_reply("stream: OK") == ScanResult(clean=True)
    assert parse_reply("stream: Eicar-Signature FOUND") == ScanResult(False, "Eicar-Signature")
    with pytest.raises(ScannerUnavailableError):
        parse_reply("INSTREAM size limit exceeded. ERROR")


async def test_presign_checks_type_size_membership_and_rate(
    client: AsyncClient, db: AsyncSession, person: MakePerson, channel: MakeChannel
) -> None:
    aysel = await person()
    room = await channel(aysel)
    ok = await presign(client, aysel, room)
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["headers"] == {"Content-Type": "application/pdf"}
    # A random key that names neither the person nor the file (§14).
    assert body["object_key"].startswith(f"chat/{room}/")
    assert "Mühazirə" not in body["object_key"]
    assert str(aysel.id) not in body["object_key"]
    stored = await db.get(MessageAttachment, uuid.UUID(body["attachment_id"]))
    assert stored is not None
    assert (stored.filename, stored.message_id, stored.uploader_id) == (
        "Mühazirə 3.pdf",
        None,
        aysel.id,
    )

    svg = await presign(client, aysel, room, "sxem.svg", "image/svg+xml", 100)
    assert (svg.status_code, svg.json()["error"]["code"]) == (
        422,
        "chat.attachment_type_not_allowed",
    )
    big = await presign(client, aysel, room, size=25 * 1024 * 1024 + 1)
    assert big.json()["error"]["code"] == "chat.attachment_too_large"
    outsider = await person("Nigar", "Quliyeva")
    assert (await presign(client, outsider, room)).status_code == 404

    # 20 uploads per hour (§5.5): one was used above.
    statuses = [(await presign(client, aysel, room)).status_code for _ in range(20)]
    assert statuses[:19] == [200] * 19
    assert statuses[19] == 429


async def test_new_accounts_cannot_attach_in_communities(
    client: AsyncClient, db: AsyncSession, person: MakePerson, channel: MakeChannel
) -> None:
    aysel = await person()
    community = await channel(aysel, name="Statistika", type=ChannelType.SUBJECT_COMMUNITY)
    group = await channel(aysel, name="765a2 layihə")
    refused = await presign(client, aysel, community)
    assert (refused.status_code, refused.json()["error"]["code"]) == (
        403,
        "chat.attachments_not_allowed",
    )
    assert (await presign(client, aysel, group)).status_code == 200
    await db.execute(
        update(User).where(User.id == aysel.id).values(created_at=utc_now() - timedelta(days=2))
    )
    await db.commit()
    assert (await presign(client, aysel, community)).status_code == 200


async def test_sending_binds_own_uploads_and_hides_them_until_clean(
    client: AsyncClient,
    db: AsyncSession,
    person: MakePerson,
    channel: MakeChannel,
    storage: MemoryStorage,
    jobs: FakeJobs,
) -> None:
    aysel, ramin = await person(), await person("Ramin", "Əliyev")
    room = await channel(aysel, ramin)
    other_room = await channel(aysel, name="Başqa qrup")
    attachment_id = await upload(client, storage, aysel, room)

    # Someone else's upload, an upload for another channel, or one not uploaded yet cannot be sent.
    stolen = await send(client, ramin, room, "", [attachment_id])
    assert (stolen.status_code, stolen.json()["error"]["code"]) == (
        422,
        "chat.attachment_not_found",
    )
    elsewhere = await send(client, aysel, other_room, "", [attachment_id])
    assert elsewhere.json()["error"]["code"] == "chat.attachment_not_found"
    missing = (await presign(client, aysel, room)).json()["attachment_id"]
    not_uploaded = await send(client, aysel, room, "", [missing])
    assert not_uploaded.json()["error"]["code"] == "chat.attachment_not_uploaded"
    short = (await presign(client, aysel, room, size=len(PDF) + 5)).json()
    storage.objects[short["object_key"]] = (PDF, "application/pdf")
    mismatch = await send(client, aysel, room, "", [short["attachment_id"]])
    assert mismatch.json()["error"]["code"] == "chat.attachment_size_mismatch"
    assert (await send(client, aysel, room, " ", [])).json()["error"][
        "code"
    ] == "chat.message_empty"

    sent = await send(client, aysel, room, "", [attachment_id])
    assert sent.status_code == 201, sent.text
    mine = sent.json()["message"]["attachments"]
    assert [(a["id"], a["status"], a["previewable"]) for a in mine] == [
        (attachment_id, "pending", True)
    ]
    assert jobs.scans == 1
    # Nobody else sees it, and nobody can download it, before the scan (§13.2).
    assert (await history(client, ramin, room))[0]["attachments"] == []
    assert (await history(client, aysel, room))[0]["attachments"][0]["status"] == "pending"
    pending = await client.get(
        f"{API}/chat/attachments/{attachment_id}/download", headers=aysel.headers
    )
    assert (pending.status_code, pending.json()["error"]["code"]) == (
        409,
        "chat.attachment_not_available",
    )
    again = await send(client, aysel, room, "Yenə", [attachment_id])
    assert again.json()["error"]["code"] == "chat.attachment_not_found"


async def test_scans_publish_clean_files_and_reject_the_rest(
    client: AsyncClient,
    db: AsyncSession,
    person: MakePerson,
    channel: MakeChannel,
    storage: MemoryStorage,
) -> None:
    aysel, ramin = await person(), await person("Ramin", "Əliyev")
    room = await channel(aysel, ramin)
    picture = await upload(client, storage, aysel, room, png(640, 480), "lövhə.png", "image/png")
    document = await upload(
        client, storage, aysel, room, package("word/document.xml"), "Hesabat.docx", DOCX_MIME
    )
    virus = await upload(client, storage, aysel, room, PDF + EICAR, "test.pdf")
    disguised = await upload(client, storage, aysel, room, package("a.txt"), "Mühazirə.pdf")
    for ids in ([picture, document], [virus], [disguised]):
        assert (await send(client, aysel, room, "Materiallar", ids)).status_code == 201

    scanner = FakeScanner()
    scanner.available = False
    report, _ = await AttachmentScanner(db, storage, scanner).scan_pending()
    # ClamAV down: the type check of the disguised file still fails, everything else waits.
    assert (report.clean, report.rejected, report.waiting) == (0, 1, 3)
    waiting = await db.get(MessageAttachment, uuid.UUID(picture))
    assert waiting is not None
    assert waiting.scan_status is ScanStatus.PENDING
    assert waiting.scan_after > utc_now()

    await db.execute(update(MessageAttachment).values(scan_after=utc_now()))
    await db.commit()
    scanner.available = True
    report, _changed = await AttachmentScanner(db, storage, scanner).scan_pending()
    assert (report.clean, report.rejected) == (2, 1)
    statuses = {
        str(a.id): a.scan_status
        for a in await db.scalars(
            select(MessageAttachment).where(MessageAttachment.message_id.is_not(None))
        )
    }
    assert statuses == {
        picture: ScanStatus.CLEAN,
        document: ScanStatus.CLEAN,
        virus: ScanStatus.INFECTED,
        disguised: ScanStatus.FAILED,
    }
    image = await db.get(MessageAttachment, uuid.UUID(picture))
    assert image is not None
    await db.refresh(image)
    assert (image.width, image.height) == (640, 480)

    seen = {a["id"] for m in await history(client, ramin, room) for a in m["attachments"]}
    assert seen == {picture, document}
    own = {
        a["id"]: a["status"] for m in await history(client, aysel, room) for a in m["attachments"]
    }
    assert own[virus] == "infected"
    assert own[disguised] == "failed"
    rejected = list(
        await db.scalars(
            select(Notification).where(
                Notification.user_id == aysel.id,
                Notification.kind == NotificationKind.CHAT_ATTACHMENT_REJECTED,
            )
        )
    )
    assert sorted(n.title for n in rejected) == ["Mühazirə.pdf", "test.pdf"]
    assert await db.scalar(select(Notification.id).where(Notification.user_id == ramin.id)) is None

    # A second run finds nothing to do (ARQ is at-least-once).
    report, _ = await AttachmentScanner(db, storage, scanner).scan_pending()
    assert report == type(report)()


async def test_downloads_are_short_lived_typed_and_for_members_only(
    client: AsyncClient,
    db: AsyncSession,
    person: MakePerson,
    channel: MakeChannel,
    storage: MemoryStorage,
) -> None:
    aysel, ramin = await person(), await person("Ramin", "Əliyev")
    room = await channel(aysel, ramin)
    pdf = await upload(client, storage, aysel, room)
    docx = await upload(
        client, storage, aysel, room, package("word/document.xml"), "Hesabat.docx", DOCX_MIME
    )
    message = (await send(client, aysel, room, "Bax", [pdf, docx])).json()["message"]
    await AttachmentScanner(db, storage, FakeScanner()).scan_pending()

    link = await client.get(
        f"{API}/chat/attachments/{pdf}/download", params={"inline": True}, headers=ramin.headers
    )
    assert link.status_code == 200, link.text
    assert link.json()["url"].endswith("ttl=60")
    assert storage.last_download["content_type"] == "application/pdf"
    assert storage.last_download["disposition"].startswith("inline;")
    # Only images and PDFs are ever shown inline.
    await client.get(
        f"{API}/chat/attachments/{docx}/download", params={"inline": True}, headers=ramin.headers
    )
    assert storage.last_download["disposition"].startswith("attachment;")
    outsider = await person("Nigar", "Quliyeva")
    for attempt in (pdf, str(uuid.uuid4())):
        hidden = await client.get(
            f"{API}/chat/attachments/{attempt}/download", headers=outsider.headers
        )
        assert (hidden.status_code, hidden.json()["error"]["code"]) == (
            404,
            "chat.attachment_not_found",
        )
    await client.delete(f"{API}/chat/messages/{message['id']}", headers=aysel.headers)
    gone = await client.get(f"{API}/chat/attachments/{pdf}/download", headers=ramin.headers)
    assert gone.status_code == 404


async def test_rejected_and_abandoned_uploads_are_purged(
    client: AsyncClient,
    db: AsyncSession,
    person: MakePerson,
    channel: MakeChannel,
    storage: MemoryStorage,
) -> None:
    aysel = await person()
    room = await channel(aysel)
    virus = await upload(client, storage, aysel, room, PDF + EICAR, "test.pdf")
    await send(client, aysel, room, "", [virus])
    abandoned = await upload(client, storage, aysel, room)
    fresh = await upload(client, storage, aysel, room)
    await db.execute(
        update(MessageAttachment)
        .where(MessageAttachment.id == uuid.UUID(abandoned))
        .values(created_at=utc_now() - timedelta(hours=25))
    )
    await db.commit()
    await AttachmentScanner(db, storage, FakeScanner()).scan_pending()
    keys = {str(a.id): a.object_key for a in await db.scalars(select(MessageAttachment))}

    storage.available = False
    assert await AttachmentScanner(db, storage, FakeScanner()).purge() == 0
    storage.available = True
    assert await AttachmentScanner(db, storage, FakeScanner()).purge() == 2
    assert keys[virus] not in storage.objects
    assert keys[abandoned] not in storage.objects
    assert keys[fresh] in storage.objects
    assert await db.get(MessageAttachment, uuid.UUID(abandoned)) is None
    infected = await db.get(MessageAttachment, uuid.UUID(virus))
    assert infected is not None
    await db.refresh(infected)
    assert infected.purged_at is not None
    assert await AttachmentScanner(db, storage, FakeScanner()).purge() == 0


async def test_a_storage_outage_leaves_text_chat_working(
    client: AsyncClient, person: MakePerson, channel: MakeChannel, storage: MemoryStorage
) -> None:
    aysel = await person()
    room = await channel(aysel)
    attachment_id = await upload(client, storage, aysel, room)
    storage.available = False
    refused = await presign(client, aysel, room)
    assert (refused.status_code, refused.json()["error"]["code"]) == (
        503,
        "chat.attachments_unavailable",
    )
    with_file = await send(client, aysel, room, "Fayl", [attachment_id])
    assert with_file.json()["error"]["code"] == "chat.attachments_unavailable"
    # §13.5: text messages do not touch object storage.
    assert (await send(client, aysel, room, "Mətn mesajı işləyir", [])).status_code == 201


async def test_clamav_reports_the_test_file(settings: Settings) -> None:
    """Against the clamd from docker-compose; CI requires it, a dev box without it skips."""
    scanner = ClamdScanner(settings.clamav_host, settings.clamav_port, timeout=30)
    if not await scanner.ping():
        if os.environ.get("CLAMAV_REQUIRED"):
            pytest.fail("clamd is not reachable")
        pytest.skip("clamd is not reachable")
    assert (await scanner.scan(PDF)).clean
    # The test file is only recognised as a whole file, not appended to another one.
    found = await scanner.scan(EICAR)
    assert not found.clean
    assert found.signature
    assert "Eicar" in found.signature
    with pytest.raises(ScannerUnavailableError):
        await ClamdScanner("127.0.0.1", 9, timeout=2).scan(PDF)


async def test_worker_jobs_announce_scan_results(
    client: AsyncClient,
    app: FastAPI,
    db: AsyncSession,
    settings: Settings,
    person: MakePerson,
    channel: MakeChannel,
    storage: MemoryStorage,
) -> None:
    aysel = await person()
    room = await channel(aysel)
    clean = await upload(client, storage, aysel, room)
    virus = await upload(client, storage, aysel, room, PDF + EICAR, "test.pdf")
    await send(client, aysel, room, "", [clean])
    await send(client, aysel, room, "", [virus])
    database = Database(str(settings.database_url))
    bus = app.state.redis.pubsub()
    await bus.psubscribe("chat:*")
    try:
        ctx: dict[str, Any] = {
            "database": database,
            "cache_redis": app.state.redis,
            "storage": storage,
            "scanner": FakeScanner(),
        }
        assert await worker.scan_attachments(ctx) == 2
        assert await worker.purge_attachments(ctx) == 1
        assert await worker.remove_chat_orphans(ctx) == 0
        topics = set()
        for _ in range(20):
            event = await bus.get_message(ignore_subscribe_messages=True, timeout=0.2)
            if event is not None:
                topics.add(event["channel"])
        # The clean file goes to the channel, the rejected one only to its uploader.
        assert {f"chat:channel:{room}", f"chat:user:{aysel.id}"} <= topics
    finally:
        await bus.aclose()
        await database.dispose()
