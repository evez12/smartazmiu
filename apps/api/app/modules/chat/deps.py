from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis

from app.core.deps import JobsDep, RedisDep, SessionDep, StorageDep
from app.modules.chat.access import ChannelAccess
from app.modules.chat.attachments import AttachmentService
from app.modules.chat.bus import ChatBus
from app.modules.chat.channels import ChannelService
from app.modules.chat.messages import MessageService
from app.modules.chat.reactions import ReactionService


def get_durable_redis(request: Request) -> Redis:
    redis: Redis = request.app.state.durable_redis
    return redis


def get_access(request: Request, session: SessionDep, cache: RedisDep) -> ChannelAccess:
    return ChannelAccess(session, cache, request.app.state.exam_windows)


AccessDep = Annotated[ChannelAccess, Depends(get_access)]


def get_attachments(
    session: SessionDep, access: AccessDep, storage: StorageDep
) -> AttachmentService:
    return AttachmentService(session, access, storage)


AttachmentsDep = Annotated[AttachmentService, Depends(get_attachments)]


def get_messages(
    request: Request,
    session: SessionDep,
    cache: RedisDep,
    access: AccessDep,
    attachments: AttachmentsDep,
    jobs: JobsDep,
) -> MessageService:
    return MessageService(
        session, access, request.app.state.snowflake, ChatBus(cache), attachments, jobs
    )


DurableRedisDep = Annotated[Redis, Depends(get_durable_redis)]
MessagesDep = Annotated[MessageService, Depends(get_messages)]


def get_channels(session: SessionDep, cache: RedisDep, access: AccessDep) -> ChannelService:
    return ChannelService(session, access, ChatBus(cache))


ChannelsDep = Annotated[ChannelService, Depends(get_channels)]


def get_reactions(session: SessionDep, cache: RedisDep, access: AccessDep) -> ReactionService:
    return ReactionService(session, access, ChatBus(cache))


ReactionsDep = Annotated[ReactionService, Depends(get_reactions)]
