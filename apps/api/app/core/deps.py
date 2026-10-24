from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async for session in request.app.state.database.session():
        yield session


def get_redis(request: Request) -> Redis:
    redis: Redis = request.app.state.redis
    return redis


SessionDep = Annotated[AsyncSession, Depends(get_session)]
RedisDep = Annotated[Redis, Depends(get_redis)]
