"""S3Storage against the S3-compatible server from docker-compose (started by `make test-api`)."""

import uuid
from datetime import timedelta

import httpx
import pytest

from app.core.config import Settings
from app.core.storage import S3Storage, StorageUnavailableError


def storage_for(settings: Settings, endpoint_url: str | None = None) -> S3Storage:
    return S3Storage(
        endpoint_url=endpoint_url or settings.s3_endpoint_url,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        bucket=settings.s3_bucket,
        region=settings.s3_region,
    )


async def test_objects_round_trip(settings: Settings) -> None:
    storage = storage_for(settings)
    key = f"avatars/{uuid.uuid4()}/test.webp"

    await storage.put(key, b"RIFF....WEBP", "image/webp")
    assert await storage.get(key) == b"RIFF....WEBP"

    await storage.delete(key)
    assert await storage.get(key) is None
    await storage.delete(key)  # deleting twice is harmless


async def test_unreachable_storage_is_reported(settings: Settings) -> None:
    storage = storage_for(settings, endpoint_url="http://127.0.0.1:9")
    with pytest.raises(StorageUnavailableError):
        await storage.put("avatars/x.webp", b"x", "image/webp")


async def test_presigned_upload_and_download(settings: Settings) -> None:
    """The browser path (D-068): a typed presigned PUT, then a download link with safe response headers."""
    storage = storage_for(settings)
    key = f"chat/{uuid.uuid4()}/{uuid.uuid4().hex}"
    url = await storage.presign_put(key, "application/pdf", timedelta(minutes=5))
    async with httpx.AsyncClient() as http:
        # The signature covers the content type: anything else is refused.
        wrong = await http.put(url, content=b"<html>", headers={"Content-Type": "text/html"})
        assert wrong.status_code == 403
        stored = await http.put(
            url, content=b"%PDF-1.7", headers={"Content-Type": "application/pdf"}
        )
        assert stored.status_code == 200
        assert await storage.head(key) == 8
        link = await storage.presign_get(
            key,
            content_type="application/pdf",
            disposition='attachment; filename="a.pdf"',
            expires=timedelta(minutes=1),
        )
        response = await http.get(link)
    assert response.content == b"%PDF-1.7"
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == 'attachment; filename="a.pdf"'
    await storage.delete(key)
    assert await storage.head(key) is None
