from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis

from app.core.deps import RedisDep, SessionDep
from app.modules.chat.access import ChannelAccess
from app.modules.chat.bus import ChatBus
from app.modules.chat.messages import MessageService


def get_durable_redis(request: Request) -> Redis:
    redis: Redis = request.app.state.durable_redis
    return redis


def get_access(request: Request, session: SessionDep, cache: RedisDep) -> ChannelAccess:
    return ChannelAccess(session, cache, request.app.state.exam_windows)


AccessDep = Annotated[ChannelAccess, Depends(get_access)]


def get_messages(
    request: Request, session: SessionDep, cache: RedisDep, access: AccessDep
) -> MessageService:
    return MessageService(session, access, request.app.state.snowflake, ChatBus(cache))


DurableRedisDep = Annotated[Redis, Depends(get_durable_redis)]
MessagesDep = Annotated[MessageService, Depends(get_messages)]
