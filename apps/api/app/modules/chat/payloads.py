"""Message payloads: the message, its author, and what is attached to it (replies, reactions, mentions).

Everything attached is loaded for a whole page in one query per kind; nothing here carries grades or contact
data (§5.4).
"""

import uuid
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from typing import cast

from sqlalchemy import Select, case, exists, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academics.models import AcademicGroup, CourseOfferingTeacher
from app.modules.chat.models import (
    Channel,
    Message,
    MessageAttachment,
    MessageMention,
    MessageReaction,
    ScanStatus,
)
from app.modules.chat.reactions import REACTIONS
from app.modules.chat.schemas import (
    AttachmentOut,
    AuthorOut,
    Badge,
    MentionOut,
    MessageOut,
    ReactionOut,
)
from app.modules.chat.snowflake import created_at_of
from app.modules.users.models import User
from app.modules.users.profile import photo_url

AuthoredRow = tuple[Message, User | None, str | None]

# Images and PDFs are previewed inline (§5.3); the attachment service accepts nothing else as previewable.
PREVIEWABLE = frozenset({"image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf"})


def with_authors() -> Select[Message, User, str | None]:
    """Messages with their authors and the author's role in the channel (teacher or curator, §12.7)."""
    channel = (
        select(Channel.course_offering_id, Channel.academic_group_id)
        .where(Channel.id == Message.channel_id)
        .correlate(Message)
    )
    teaches = exists().where(
        CourseOfferingTeacher.teacher_id == Message.author_id,
        CourseOfferingTeacher.course_offering_id
        == channel.with_only_columns(Channel.course_offering_id).scalar_subquery(),
    )
    curates = exists().where(
        AcademicGroup.curator_id == Message.author_id,
        AcademicGroup.id == channel.with_only_columns(Channel.academic_group_id).scalar_subquery(),
    )
    badge = case((teaches, literal("teacher")), (curates, literal("curator")), else_=None)
    return select(Message, User, badge).outerjoin(User, User.id == Message.author_id)


def message_out(message: Message, author: User | None, badge: str | None = None) -> MessageOut:
    deleted = message.deleted_at is not None
    return MessageOut(
        id=str(message.id),
        channel_id=str(message.channel_id),
        topic_id=str(message.topic_id) if message.topic_id else None,
        parent_id=str(message.parent_id) if message.parent_id else None,
        author=AuthorOut(
            id=str(author.id),
            display_name=author.display_name,
            photo_url=photo_url(author),
            # The query yields only these two literals or NULL.
            badge=cast("Badge | None", badge),
        )
        if author is not None
        else None,
        body="" if deleted else message.body,
        client_msg_id=str(message.client_msg_id),
        created_at=message.created_at,
        edited_at=message.edited_at,
        deleted_at=message.deleted_at,
        is_verified_answer=message.is_verified_answer and not deleted,
        mentions_channel=message.mentions_channel and not deleted,
    )


async def enrich(
    session: AsyncSession, rows: Sequence[AuthoredRow], viewer: uuid.UUID | None
) -> list[MessageOut]:
    """Payloads for ``rows`` with reply counts, reaction counts and mentions.

    ``viewer`` fills ``my_reactions``; broadcasts pass None because every member receives the same frame.
    """
    if not rows:
        return []
    messages = [row[0] for row in rows]
    ids = [message.id for message in messages]
    oldest = min(message.created_at for message in messages)

    replies: dict[int, tuple[int, datetime]] = {}
    top_level = [message.id for message in messages if message.parent_id is None]
    if top_level:
        found = await session.execute(
            select(Message.parent_id, func.count(), func.max(Message.created_at))
            .where(
                Message.parent_id.in_(top_level),
                Message.deleted_at.is_(None),
                # Replies are younger than their thread root: older months are skipped (ADR 0002).
                Message.created_at >= oldest,
            )
            .group_by(Message.parent_id)
        )
        replies = {parent: (count, last) for parent, count, last in found if parent is not None}

    counts: dict[int, dict[str, int]] = defaultdict(dict)
    mine: dict[int, list[str]] = defaultdict(list)
    reacted = await session.execute(
        select(
            MessageReaction.message_id,
            MessageReaction.emoji,
            func.count(),
            func.bool_or(MessageReaction.user_id == viewer) if viewer else literal(False),
        )
        .where(MessageReaction.message_id.in_(ids))
        .group_by(MessageReaction.message_id, MessageReaction.emoji)
    )
    for message_id, emoji, count, by_viewer in reacted:
        counts[message_id][emoji] = count
        if by_viewer:
            mine[message_id].append(emoji)

    mentioned: dict[int, list[MentionOut]] = defaultdict(list)
    named = await session.execute(
        select(MessageMention.message_id, User.id, User.display_name)
        .join(User, User.id == MessageMention.user_id)
        .where(MessageMention.message_id.in_(ids))
        .order_by(MessageMention.message_id, User.display_name)
    )
    for message_id, user_id, display_name in named:
        mentioned[message_id].append(MentionOut(id=str(user_id), display_name=display_name))

    attached: dict[int, list[AttachmentOut]] = defaultdict(list)
    files = await session.scalars(
        select(MessageAttachment)
        .where(MessageAttachment.message_id.in_(ids))
        .order_by(MessageAttachment.attached_at, MessageAttachment.id)
    )
    for attachment in files:
        # Others see a file only once it is clean; the uploader also sees it while scanning or rejected.
        if attachment.scan_status is ScanStatus.CLEAN or (
            viewer is not None and attachment.uploader_id == viewer
        ):
            assert attachment.message_id is not None
            attached[attachment.message_id].append(attachment_out(attachment))

    result = []
    for message, author, badge in rows:
        out = message_out(message, author, badge)
        if message.id in replies:
            out.reply_count, out.last_reply_at = replies[message.id]
        if message.deleted_at is None:
            out.reactions = [
                ReactionOut(emoji=emoji, count=counts[message.id][emoji])
                for emoji in REACTIONS
                if emoji in counts[message.id]
            ]
            out.mentions = mentioned[message.id]
            out.attachments = attached[message.id]
            if viewer is not None:
                order = {emoji: index for index, emoji in enumerate(REACTIONS)}
                out.my_reactions = sorted(mine[message.id], key=order.__getitem__)
        elif viewer is not None:
            out.my_reactions = []
        result.append(out)
    return result


def attachment_out(attachment: MessageAttachment) -> AttachmentOut:
    return AttachmentOut(
        id=str(attachment.id),
        filename=attachment.filename,
        mime=attachment.mime,
        size_bytes=attachment.size_bytes,
        width=attachment.width,
        height=attachment.height,
        status=attachment.scan_status,
        previewable=attachment.mime in PREVIEWABLE,
    )


async def message_payload(
    session: AsyncSession, message_id: int, viewer: uuid.UUID | None
) -> MessageOut | None:
    """One message as ``viewer`` sees it (None: as every member sees it)."""
    found = await session.execute(
        with_authors().where(
            Message.id == message_id, Message.created_at == created_at_of(message_id)
        )
    )
    row = found.first()
    if row is None:
        return None
    return (await enrich(session, [(row[0], row[1], row[2])], viewer))[0]
