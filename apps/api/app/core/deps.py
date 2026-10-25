from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.identity_admin import IdentityAdmin
from app.core.jobs import JobQueue
from app.core.storage import ObjectStorage


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async for session in request.app.state.database.session():
        yield session


def get_redis(request: Request) -> Redis:
    redis: Redis = request.app.state.redis
    return redis


def get_storage(request: Request) -> ObjectStorage:
    storage: ObjectStorage = request.app.state.storage
    return storage


def get_identity_admin(request: Request) -> IdentityAdmin:
    identity_admin: IdentityAdmin = request.app.state.identity_admin
    return identity_admin


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_jobs(request: Request) -> JobQueue:
    jobs: JobQueue = request.app.state.jobs
    return jobs


SessionDep = Annotated[AsyncSession, Depends(get_session)]
RedisDep = Annotated[Redis, Depends(get_redis)]
StorageDep = Annotated[ObjectStorage, Depends(get_storage)]
IdentityAdminDep = Annotated[IdentityAdmin, Depends(get_identity_admin)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]
JobsDep = Annotated[JobQueue, Depends(get_jobs)]
