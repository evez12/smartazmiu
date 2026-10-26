import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request, Response
from redis.exceptions import RedisError

from app.core.deps import RedisDep
from app.core.errors import COMMON_ERROR_RESPONSES, AppError
from app.core.ratelimit import RateLimit, enforce_rate_limit
from app.core.rbac import CurrentUserDep
from app.core.security import TokenClaims
from app.modules.chat import tickets
from app.modules.chat.deps import ChannelsDep, DurableRedisDep, MessagesDep, ReactionsDep
from app.modules.chat.lookup import parse_message_id
from app.modules.chat.messages import MAX_PAGE_SIZE, PAGE_SIZE
from app.modules.chat.schemas import (
    ChannelDetailOut,
    ChannelListOut,
    ChannelOut,
    EditMessageIn,
    EditResultOut,
    MembershipUpdateIn,
    MembersOut,
    MessageOut,
    MessagePageOut,
    OpenDmIn,
    ReactionIn,
    ReactionResultOut,
    ReadMarkerIn,
    ReadMarkerOut,
    SendMessageIn,
    SendResultOut,
    ThreadOut,
    TicketOut,
)

# A broken client retrying in a loop cannot fill Redis A with tickets (ADR 0003).
TICKET_ISSUES = RateLimit("ws_ticket", limit=30, window_seconds=60)

MESSAGE_ID = r"^[0-9]{1,19}$"

router = APIRouter(responses=COMMON_ERROR_RESPONSES, tags=["chat"])


@router.post(
    "/ws/ticket",
    response_model=TicketOut,
    operation_id="issueSocketTicket",
    summary="A one-use, 60-second ticket for opening the chat WebSocket",
)
async def issue_socket_ticket(
    request: Request, user: CurrentUserDep, cache: RedisDep, durable: DurableRedisDep
) -> TicketOut:
    await enforce_rate_limit(cache, TICKET_ISSUES, str(user.id))
    claims: TokenClaims = request.state.token_claims
    try:
        ticket, expires_at = await tickets.issue(
            durable, user.id, datetime.fromtimestamp(claims.expires_at, UTC)
        )
    except (RedisError, OSError) as exc:
        raise AppError("chat.unavailable", 503) from exc
    return TicketOut(ticket=ticket, expires_at=expires_at)


@router.get(
    "/chat/channels",
    response_model=ChannelListOut,
    operation_id="listMyChannels",
    summary="My channels with unread counts",
)
async def list_my_channels(user: CurrentUserDep, channels: ChannelsDep) -> ChannelListOut:
    found = await channels.mine(user)
    return ChannelListOut(channels=found.channels, blocked_user_ids=found.blocked_user_ids)


@router.get(
    "/chat/channels/{channel_id}",
    response_model=ChannelDetailOut,
    operation_id="readChannel",
    summary="A channel I am in, with its topics",
)
async def read_channel(
    user: CurrentUserDep, channels: ChannelsDep, channel_id: uuid.UUID
) -> ChannelDetailOut:
    channel, topics = await channels.get(user, channel_id)
    return ChannelDetailOut(**channel.model_dump(), topics=topics)


@router.get(
    "/chat/channels/{channel_id}/members",
    response_model=MembersOut,
    operation_id="listChannelMembers",
    summary="Members of a channel I am in (first 500 by name)",
)
async def list_channel_members(
    user: CurrentUserDep, channels: ChannelsDep, channel_id: uuid.UUID
) -> MembersOut:
    return MembersOut(members=await channels.members(user, channel_id))


@router.get(
    "/chat/channels/{channel_id}/messages",
    response_model=MessagePageOut,
    operation_id="listChannelMessages",
    summary="Message history, oldest first, paged with before/after cursors",
)
async def list_channel_messages(
    user: CurrentUserDep,
    messages: MessagesDep,
    channel_id: uuid.UUID,
    before: Annotated[str | None, Query(pattern=MESSAGE_ID)] = None,
    after: Annotated[str | None, Query(pattern=MESSAGE_ID)] = None,
    topic: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = PAGE_SIZE,
) -> MessagePageOut:
    page = await messages.history(
        user,
        channel_id,
        before=parse_message_id(before) if before else None,
        after=parse_message_id(after) if after else None,
        topic_id=topic,
        limit=limit,
    )
    return MessagePageOut(messages=page.messages, has_more=page.has_more)


@router.post(
    "/chat/channels/{channel_id}/messages",
    response_model=SendResultOut,
    status_code=201,
    operation_id="sendChannelMessage",
    summary="Send a message (fallback while the WebSocket is unavailable)",
    responses={200: {"model": SendResultOut, "description": "Sent before with this client_msg_id"}},
)
async def send_channel_message(
    user: CurrentUserDep,
    messages: MessagesDep,
    channel_id: uuid.UUID,
    body: SendMessageIn,
    response: Response,
) -> SendResultOut:
    outcome = await messages.send(
        user,
        channel_id,
        body.body,
        body.client_msg_id,
        body.topic_id,
        parse_message_id(body.parent_id) if body.parent_id else None,
    )
    if not outcome.created:
        response.status_code = 200
    return SendResultOut(
        message=outcome.message, duplicate=not outcome.created, notices=outcome.notices
    )


@router.patch(
    "/chat/messages/{message_id}",
    response_model=EditResultOut,
    operation_id="editMessage",
    summary="Edit my message within 15 minutes",
)
async def edit_message(
    user: CurrentUserDep,
    messages: MessagesDep,
    message_id: Annotated[str, Path(pattern=MESSAGE_ID)],
    body: EditMessageIn,
) -> EditResultOut:
    outcome = await messages.edit(user, parse_message_id(message_id), body.body)
    return EditResultOut(message=outcome.message, notices=outcome.notices)


@router.delete(
    "/chat/messages/{message_id}",
    response_model=MessageOut,
    operation_id="deleteMessage",
    summary="Delete my message within 15 minutes (soft delete; replies stay)",
)
async def delete_message(
    user: CurrentUserDep,
    messages: MessagesDep,
    message_id: Annotated[str, Path(pattern=MESSAGE_ID)],
) -> MessageOut:
    return await messages.delete(user, parse_message_id(message_id))


@router.get(
    "/chat/messages/{message_id}/thread",
    response_model=ThreadOut,
    operation_id="readThread",
    summary="A message's thread: the root and its replies, oldest first",
)
async def read_thread(
    user: CurrentUserDep,
    messages: MessagesDep,
    message_id: Annotated[str, Path(pattern=MESSAGE_ID)],
    after: Annotated[str | None, Query(pattern=MESSAGE_ID)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = PAGE_SIZE,
) -> ThreadOut:
    thread = await messages.thread(
        user,
        parse_message_id(message_id),
        after=parse_message_id(after) if after else None,
        limit=limit,
    )
    return ThreadOut(root=thread.root, replies=thread.replies, has_more=thread.has_more)


@router.post(
    "/chat/messages/{message_id}/reactions",
    response_model=ReactionResultOut,
    operation_id="addReaction",
    summary="React to a message with one of the eight reactions (idempotent)",
)
async def add_reaction(
    user: CurrentUserDep,
    reactions: ReactionsDep,
    message_id: Annotated[str, Path(pattern=MESSAGE_ID)],
    body: ReactionIn,
) -> ReactionResultOut:
    result = await reactions.add(user, parse_message_id(message_id), body.emoji)
    return ReactionResultOut(
        message_id=str(result.message_id), emoji=result.emoji, count=result.count, reacted=True
    )


@router.delete(
    "/chat/messages/{message_id}/reactions/{emoji}",
    response_model=ReactionResultOut,
    operation_id="removeReaction",
    summary="Remove my reaction (idempotent)",
)
async def remove_reaction(
    user: CurrentUserDep,
    reactions: ReactionsDep,
    message_id: Annotated[str, Path(pattern=MESSAGE_ID)],
    emoji: Annotated[str, Path(max_length=32)],
) -> ReactionResultOut:
    result = await reactions.remove(user, parse_message_id(message_id), emoji)
    return ReactionResultOut(
        message_id=str(result.message_id), emoji=result.emoji, count=result.count, reacted=False
    )


@router.post(
    "/chat/channels/{channel_id}/read",
    response_model=ReadMarkerOut,
    operation_id="markChannelRead",
    summary="Move my read marker forward",
)
async def mark_channel_read(
    user: CurrentUserDep, messages: MessagesDep, channel_id: uuid.UUID, body: ReadMarkerIn
) -> ReadMarkerOut:
    marker = await messages.mark_read(user, channel_id, int(body.last_read_message_id))
    return ReadMarkerOut(channel_id=str(channel_id), last_read_message_id=str(marker))


@router.patch(
    "/chat/channels/{channel_id}/members/me",
    response_model=ChannelOut,
    operation_id="updateMyChannelMembership",
    summary="My notification level and snooze in a channel",
)
async def update_my_channel_membership(
    user: CurrentUserDep, channels: ChannelsDep, channel_id: uuid.UUID, body: MembershipUpdateIn
) -> ChannelOut:
    return await channels.update_membership(
        user,
        channel_id,
        notify_level=body.notify_level,
        muted_until=body.muted_until,
        set_muted="muted_until" in body.model_fields_set,
    )


@router.post(
    "/chat/dm",
    response_model=ChannelOut,
    status_code=201,
    operation_id="openDirectMessage",
    summary="Open (or create) a direct message, subject to dm_policy and blocks",
    responses={200: {"model": ChannelOut, "description": "The existing direct message"}},
)
async def open_direct_message(
    user: CurrentUserDep, channels: ChannelsDep, body: OpenDmIn, response: Response
) -> ChannelOut:
    channel, created = await channels.open_dm(user, body.user_id)
    if not created:
        response.status_code = 200
    return channel


@router.post(
    "/users/{user_id}/block",
    status_code=204,
    operation_id="blockUser",
    summary="Block a person: no DMs either way, their messages collapsed for me",
)
async def block_user(user: CurrentUserDep, channels: ChannelsDep, user_id: uuid.UUID) -> None:
    await channels.block(user, user_id)


@router.delete(
    "/users/{user_id}/block",
    status_code=204,
    operation_id="unblockUser",
    summary="Unblock a person",
)
async def unblock_user(user: CurrentUserDep, channels: ChannelsDep, user_id: uuid.UUID) -> None:
    await channels.unblock(user, user_id)
