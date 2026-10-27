import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request, Response
from redis.exceptions import RedisError

from app.core.deps import RedisDep, SessionDep
from app.core.errors import COMMON_ERROR_RESPONSES, AppError
from app.core.ratelimit import RateLimit, enforce_rate_limit
from app.core.rbac import CurrentUserDep
from app.core.security import TokenClaims
from app.modules.chat import tickets
from app.modules.chat.curation import validate_poll
from app.modules.chat.deps import (
    AttachmentsDep,
    ChannelsDep,
    CurationDep,
    DurableRedisDep,
    MessagesDep,
    ReactionsDep,
)
from app.modules.chat.link_previews import LinkPreviewService
from app.modules.chat.lookup import parse_message_id
from app.modules.chat.messages import MAX_PAGE_SIZE, PAGE_SIZE
from app.modules.chat.payloads import message_payload
from app.modules.chat.schemas import (
    AuthorOut,
    ChannelDetailOut,
    ChannelListOut,
    ChannelOut,
    DownloadOut,
    EditMessageIn,
    EditResultOut,
    LinkPreviewOut,
    MembershipUpdateIn,
    MembersOut,
    MessageOut,
    MessagePageOut,
    MessageSearchOut,
    MessageSearchResultOut,
    OpenDmIn,
    PinsOut,
    PollIn,
    PresignIn,
    PresignOut,
    ReactionIn,
    ReactionResultOut,
    ReadMarkerIn,
    ReadMarkerOut,
    SavedItemOut,
    SavedListOut,
    SendMessageIn,
    SendResultOut,
    ThreadOut,
    TicketOut,
    VoteIn,
)
from app.modules.chat.search import MessageSearchService
from app.modules.health.metrics import MESSAGES_SENT, counting_send

# A broken client retrying in a loop cannot fill Redis A with tickets (ADR 0003).
TICKET_ISSUES = RateLimit("ws_ticket", limit=30, window_seconds=60)

MESSAGE_ID = r"^[0-9]{1,19}$"

router = APIRouter(responses=COMMON_ERROR_RESPONSES, tags=["chat"])


@router.get(
    "/chat/search",
    response_model=MessageSearchOut,
    operation_id="searchMessages",
    summary="Search messages in channels the user can read",
)
async def search_messages(
    user: CurrentUserDep,
    session: SessionDep,
    q: Annotated[str, Query(min_length=1, max_length=200)],
    channel_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 25,
) -> MessageSearchOut:
    found = await MessageSearchService(session).search(user, q, channel_id, limit)
    items: list[MessageSearchResultOut] = []
    for message, rank in found:
        payload = await message_payload(session, message.id, user.id)
        if payload is not None:
            items.append(MessageSearchResultOut(message=payload, rank=float(rank or 0)))
    return MessageSearchOut(items=items)


@router.get(
    "/chat/link-preview",
    response_model=LinkPreviewOut,
    operation_id="fetchLinkPreview",
    summary="Fetch a safe preview for an allowlisted link",
)
async def fetch_link_preview(
    request: Request,
    _user: CurrentUserDep,
    url: Annotated[str, Query(max_length=2048)],
) -> LinkPreviewOut:
    preview = await LinkPreviewService(
        request.app.state.http, set(request.app.state.settings.link_preview_domains)
    ).fetch(url)
    return LinkPreviewOut(**preview)


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
    user: CurrentUserDep, channels: ChannelsDep, curation: CurationDep, channel_id: uuid.UUID
) -> ChannelDetailOut:
    channel, topics, subject_id = await channels.get(user, channel_id)
    can = await curation.capabilities(user, channel_id)
    return ChannelDetailOut(
        **channel.model_dump(),
        topics=topics,
        subject_id=str(subject_id) if subject_id else None,
        can_pin=can.can_pin,
        can_verify=can.can_verify,
        can_see_anonymous=can.can_see_anonymous,
    )


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
    with counting_send("rest"):
        outcome = await messages.send(
            user,
            channel_id,
            body.body,
            body.client_msg_id,
            body.topic_id,
            parse_message_id(body.parent_id) if body.parent_id else None,
            body.attachment_ids,
            body.is_anonymous,
        )
    if outcome.created:
        MESSAGES_SENT.labels("rest").inc()
    else:
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


@router.post(
    "/chat/attachments/presign",
    response_model=PresignOut,
    operation_id="presignAttachment",
    summary="Reserve an upload: a five-minute URL to PUT one file to (images, PDF, DOCX, PPTX, ZIP, 25 MB)",
)
async def presign_attachment(
    user: CurrentUserDep, attachments: AttachmentsDep, body: PresignIn
) -> PresignOut:
    upload = await attachments.presign(user, body.channel_id, body.filename, body.mime, body.size)
    return PresignOut(
        attachment_id=str(upload.attachment.id),
        url=upload.url,
        object_key=upload.attachment.object_key,
        expires_at=upload.expires_at,
        headers={"Content-Type": upload.attachment.mime},
    )


@router.get(
    "/chat/attachments/{attachment_id}/download",
    response_model=DownloadOut,
    operation_id="downloadAttachment",
    summary="A one-minute link to a clean attachment of a message I can read",
)
async def download_attachment(
    user: CurrentUserDep,
    attachments: AttachmentsDep,
    attachment_id: uuid.UUID,
    inline: bool = False,
) -> DownloadOut:
    link = await attachments.download(user, attachment_id, inline=inline)
    return DownloadOut(url=link.url, expires_at=link.expires_at)


MessageIdPath = Annotated[str, Path(pattern=MESSAGE_ID)]


@router.get(
    "/chat/channels/{channel_id}/pins",
    response_model=PinsOut,
    operation_id="listPins",
    summary='The channel "Faydali" collection: pinned messages, newest pin first',
)
async def list_pins(user: CurrentUserDep, curation: CurationDep, channel_id: uuid.UUID) -> PinsOut:
    return PinsOut(messages=await curation.pins(user, channel_id))


@router.post(
    "/chat/channels/{channel_id}/pins/{message_id}",
    response_model=MessageOut,
    operation_id="pinMessage",
    summary="Pin a message (max 50 per channel)",
)
async def pin_message(
    user: CurrentUserDep, curation: CurationDep, channel_id: uuid.UUID, message_id: MessageIdPath
) -> MessageOut:
    return await curation.pin(user, channel_id, parse_message_id(message_id))


@router.delete(
    "/chat/channels/{channel_id}/pins/{message_id}",
    status_code=204,
    operation_id="unpinMessage",
    summary="Unpin a message",
)
async def unpin_message(
    user: CurrentUserDep, curation: CurationDep, channel_id: uuid.UUID, message_id: MessageIdPath
) -> None:
    await curation.unpin(user, channel_id, parse_message_id(message_id))


@router.post(
    "/chat/channels/{channel_id}/polls",
    response_model=MessageOut,
    status_code=201,
    operation_id="createPoll",
    summary="Post a poll: a message with options, single or multiple choice, optional deadline",
)
async def create_poll(
    user: CurrentUserDep,
    messages: MessagesDep,
    curation: CurationDep,
    channel_id: uuid.UUID,
    body: PollIn,
    response: Response,
) -> MessageOut:
    validate_poll(body.options, body.closes_at)
    outcome = await messages.send(
        user, channel_id, body.question, body.client_msg_id, body.topic_id
    )
    if not outcome.created:
        response.status_code = 200
        return outcome.message
    return await curation.attach_poll(
        user, outcome.message, body.options, body.multi, body.closes_at
    )


@router.post(
    "/chat/polls/{poll_id}/votes",
    response_model=MessageOut,
    operation_id="votePoll",
    summary="Vote (replaces my earlier choice)",
)
async def vote_poll(
    user: CurrentUserDep, curation: CurationDep, poll_id: uuid.UUID, body: VoteIn
) -> MessageOut:
    return await curation.vote(user, poll_id, body.option_ids)


@router.put(
    "/chat/messages/{message_id}/saved",
    response_model=MessageOut,
    operation_id="saveMessage",
    summary="Save a message to my list",
)
async def save_message(
    user: CurrentUserDep, curation: CurationDep, message_id: MessageIdPath
) -> MessageOut:
    saved = await curation.save(user, parse_message_id(message_id), True)
    assert saved is not None
    return saved


@router.delete(
    "/chat/messages/{message_id}/saved",
    status_code=204,
    operation_id="unsaveMessage",
    summary="Remove a message from my list",
)
async def unsave_message(
    user: CurrentUserDep, curation: CurationDep, message_id: MessageIdPath
) -> None:
    await curation.save(user, parse_message_id(message_id), False)


@router.get(
    "/chat/saved",
    response_model=SavedListOut,
    operation_id="listSavedMessages",
    summary="My saved messages; unreadable ones are listed without content",
)
async def list_saved(user: CurrentUserDep, curation: CurationDep) -> SavedListOut:
    return SavedListOut(
        items=[
            SavedItemOut(
                message_id=str(item.message_id),
                channel_id=str(item.channel_id),
                channel_name=item.channel_name,
                saved_at=item.saved_at,
                message=item.message,
            )
            for item in await curation.saved(user)
        ]
    )


@router.post(
    "/chat/messages/{message_id}/verify",
    response_model=MessageOut,
    operation_id="verifyAnswer",
    summary="Mark a reply as a verified answer (course teacher or subject guide)",
)
async def verify_answer(
    user: CurrentUserDep, curation: CurationDep, message_id: MessageIdPath
) -> MessageOut:
    return await curation.verify(user, parse_message_id(message_id), True)


@router.delete(
    "/chat/messages/{message_id}/verify",
    response_model=MessageOut,
    operation_id="unverifyAnswer",
    summary="Remove the verified mark",
)
async def unverify_answer(
    user: CurrentUserDep, curation: CurationDep, message_id: MessageIdPath
) -> MessageOut:
    return await curation.verify(user, parse_message_id(message_id), False)


@router.get(
    "/chat/messages/{message_id}/anonymous-author",
    response_model=AuthorOut,
    operation_id="revealAnonymousAuthor",
    summary="Who asked an anonymous question (moderators, teachers, staff; audited)",
)
async def reveal_anonymous_author(
    user: CurrentUserDep, curation: CurationDep, message_id: MessageIdPath
) -> AuthorOut:
    return await curation.anonymous_author(user, parse_message_id(message_id))
