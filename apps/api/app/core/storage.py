"""Object storage through the S3 API (DECISIONS D-013); any S3-compatible server works."""

import asyncio
from collections.abc import Callable
from datetime import timedelta
from typing import TYPE_CHECKING, Protocol

import boto3
import structlog
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

if TYPE_CHECKING:
    # Type stubs are a development dependency only.
    from mypy_boto3_s3 import S3Client

logger = structlog.get_logger(__name__)


class StorageUnavailableError(Exception):
    """The object store could not be reached; callers answer 503 and the rest of the app keeps working."""


class ObjectStorage(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...

    async def get(self, key: str) -> bytes | None: ...

    async def delete(self, key: str) -> None: ...

    async def head(self, key: str) -> int | None:
        """The stored size in bytes, or None when there is no such object."""
        ...

    async def presign_put(self, key: str, content_type: str, expires: timedelta) -> str:
        """A URL the browser uploads one object to, with exactly this content type."""
        ...

    async def presign_get(
        self, key: str, *, content_type: str, disposition: str, expires: timedelta
    ) -> str:
        """A short-lived download URL whose response carries the given type and disposition (§14)."""
        ...


def _client(endpoint_url: str, access_key: str, secret_key: str, region: str) -> "S3Client":
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
        config=Config(
            connect_timeout=3,
            read_timeout=10,
            retries={"max_attempts": 2},
            s3={"addressing_style": "path"},
            signature_version="s3v4",
        ),
    )


class S3Storage:
    def __init__(
        self,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str,
        public_url: str = "",
    ) -> None:
        self._bucket = bucket
        self._client: S3Client = _client(endpoint_url, access_key, secret_key, region)
        # Signing needs no connection; the signature covers the host the browser will send.
        self._public: S3Client = (
            _client(public_url, access_key, secret_key, region)
            if public_url and public_url != endpoint_url
            else self._client
        )
        self._bucket_ready = False

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        await self._run(self._put, key, data, content_type)

    async def get(self, key: str) -> bytes | None:
        return await self._run(self._get, key)

    async def delete(self, key: str) -> None:
        await self._run(self._delete, key)

    async def head(self, key: str) -> int | None:
        return await self._run(self._head, key)

    async def presign_put(self, key: str, content_type: str, expires: timedelta) -> str:
        # The bucket must exist before the browser uploads into it.
        await self._run(self._ensure_bucket)
        return self._public.generate_presigned_url(
            "put_object",
            Params={"Bucket": self._bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=int(expires.total_seconds()),
        )

    async def presign_get(
        self, key: str, *, content_type: str, disposition: str, expires: timedelta
    ) -> str:
        return self._public.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self._bucket,
                "Key": key,
                "ResponseContentType": content_type,
                "ResponseContentDisposition": disposition,
                "ResponseCacheControl": "private, no-store",
            },
            ExpiresIn=int(expires.total_seconds()),
        )

    async def _run[**P, T](self, operation: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return await asyncio.to_thread(operation, *args, **kwargs)
        except (BotoCoreError, ClientError) as exc:
            logger.warning("storage_unavailable", error=type(exc).__name__)
            raise StorageUnavailableError from exc

    def _ensure_bucket(self) -> None:
        if not self._bucket_ready:
            # Created on first use, so a fresh stack needs no separate provisioning step.
            try:
                self._client.head_bucket(Bucket=self._bucket)
            except ClientError:
                self._client.create_bucket(Bucket=self._bucket)
            self._bucket_ready = True

    def _put(self, key: str, data: bytes, content_type: str) -> None:
        self._ensure_bucket()
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

    def _head(self, key: str) -> int | None:
        try:
            response = self._client.head_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"NoSuchKey", "NoSuchBucket", "404"}:
                return None
            raise
        return int(response["ContentLength"])

    def _get(self, key: str) -> bytes | None:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"NoSuchKey", "NoSuchBucket", "404"}:
                return None
            raise
        return response["Body"].read()

    def _delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)
