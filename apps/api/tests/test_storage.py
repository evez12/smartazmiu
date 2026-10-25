"""S3Storage against the S3-compatible server from docker-compose (started by `make test-api`)."""

import uuid

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
