"""Object storage through the S3 API (DECISIONS D-013); any S3-compatible server works."""

import asyncio
from collections.abc import Callable
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


class S3Storage:
    def __init__(
        self, endpoint_url: str, access_key: str, secret_key: str, bucket: str, region: str
    ) -> None:
        self._bucket = bucket
        self._client: S3Client = boto3.client(
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
            ),
        )
        self._bucket_ready = False

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        await self._run(self._put, key, data, content_type)

    async def get(self, key: str) -> bytes | None:
        return await self._run(self._get, key)

    async def delete(self, key: str) -> None:
        await self._run(self._delete, key)

    async def _run[**P, T](self, operation: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return await asyncio.to_thread(operation, *args, **kwargs)
        except (BotoCoreError, ClientError) as exc:
            logger.warning("storage_unavailable", error=type(exc).__name__)
            raise StorageUnavailableError from exc

    def _put(self, key: str, data: bytes, content_type: str) -> None:
        if not self._bucket_ready:
            # Created on first use, so a fresh stack needs no separate provisioning step.
            try:
                self._client.head_bucket(Bucket=self._bucket)
            except ClientError:
                self._client.create_bucket(Bucket=self._bucket)
            self._bucket_ready = True
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

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
