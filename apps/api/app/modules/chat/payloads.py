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

from app.core.uploads import PREVIEWABLE
from app.modules.academics.models import AcademicGroup, CourseOfferingTeacher
from app.modules.chat.models import (
    Channel,
    Message,
    MessageAttachment,
    MessageMention,
    MessageReaction,
    PinnedMessage,
    Poll,
    PollOption,
    PollVote,
    SavedMessage,
    ScanStatus,
)
from app.modules.chat.reactions import REACTIONS
from app.modules.chat.schemas import (
    AttachmentOut,
    AuthorOut,
    Badge,
    MentionOut,
    MessageOut,
    PollOptionOut,
    PollOut,
    ReactionOut,
)
from app.modules.chat.snowflake import created_at_of
from app.modules.mentorship.badges import guide_terms
from app.modules.users.models import User
from app.modules.users.profile import photo_url

AuthoredRow = tuple[Message, User | None, str | None]


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
        # An anonymous question names nobody in any payload; moderators ask for the author separately (D-084).
        if author is not None and not message.is_anonymous
        else None,
        body="" if deleted else message.body,
        client_msg_id=str(message.client_msg_id),
        created_at=message.created_at,
        edited_at=message.edited_at,
        deleted_at=message.deleted_at,
        is_verified_answer=message.is_verified_answer and not deleted,
        is_anonymous=message.is_anonymous,
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

    extras = await curation(session, messages, viewer)
    # Teacher and curator badges come from the query; guides only matter in subject communities (§5.2).
    guides = await guide_terms(
        session,
        (
            (message.channel_id, author.id)
            for message, author, badge in rows
            if author is not None and badge is None and not message.is_anonymous
        ),
    )
    result = []
    for message, author, badge in rows:
        out = message_out(message, author, badge)
        extras.apply(out, message)
        if out.author is not None and author is not None:
            term = guides.get((message.channel_id, author.id))
            if term is not None:
                out.author.badge = "guide"
                out.author.guide_semester = term
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


class Curation:
    """Pins, polls, saves and verifiers of a page of messages, loaded in one query per kind."""

    def __init__(self) -> None:
        self.pinned: set[int] = set()
        self.saved: set[int] = set()
        self.viewer: uuid.UUID | None = None
        self.verifiers: dict[uuid.UUID, str] = {}
        self.polls: dict[int, PollOut] = {}

    def apply(self, out: MessageOut, message: Message) -> None:
        if message.deleted_at is not None:
            return
        out.pinned = message.id in self.pinned
        if self.viewer is not None:
            out.saved = message.id in self.saved
        if message.is_verified_answer and message.verified_by is not None:
            out.verified_by_name = self.verifiers.get(message.verified_by)
        out.poll = self.polls.get(message.id)


async def curation(
    session: AsyncSession, messages: Sequence[Message], viewer: uuid.UUID | None
) -> Curation:
    found = Curation()
    found.viewer = viewer
    ids = [message.id for message in messages]
    found.pinned = set(
        await session.scalars(
            select(PinnedMessage.message_id).where(PinnedMessage.message_id.in_(ids))
        )
    )
    if viewer is not None:
        found.saved = set(
            await session.scalars(
                select(SavedMessage.message_id).where(
                    SavedMessage.user_id == viewer, SavedMessage.message_id.in_(ids)
                )
            )
        )
    verifier_ids = {m.verified_by for m in messages if m.is_verified_answer and m.verified_by}
    if verifier_ids:
        found.verifiers = dict(
            (
                await session.execute(
                    select(User.id, User.display_name).where(User.id.in_(verifier_ids))
                )
            ).all()
        )
    polls = list(await session.scalars(select(Poll).where(Poll.message_id.in_(ids))))
    if polls:
        found.polls = await poll_payloads(session, polls, viewer)
    return found


async def poll_payloads(
    session: AsyncSession, polls: Sequence[Poll], viewer: uuid.UUID | None
) -> dict[int, PollOut]:
    poll_ids = [poll.id for poll in polls]
    options = list(
        await session.scalars(
            select(PollOption)
            .where(PollOption.poll_id.in_(poll_ids))
            .order_by(PollOption.poll_id, PollOption.position)
        )
    )
    counts = dict(
        (
            await session.execute(
                select(PollVote.option_id, func.count())
                .where(PollVote.poll_id.in_(poll_ids))
                .group_by(PollVote.option_id)
            )
        ).all()
    )
    voters = dict(
        (
            await session.execute(
                select(PollVote.poll_id, func.count(func.distinct(PollVote.user_id)))
                .where(PollVote.poll_id.in_(poll_ids))
                .group_by(PollVote.poll_id)
            )
        ).all()
    )
    mine: dict[uuid.UUID, list[str]] = defaultdict(list)
    if viewer is not None:
        for poll_id, option_id in await session.execute(
            select(PollVote.poll_id, PollVote.option_id).where(
                PollVote.poll_id.in_(poll_ids), PollVote.user_id == viewer
            )
        ):
            mine[poll_id].append(str(option_id))
    now = datetime.now(tz=next(iter(polls)).created_at.tzinfo)
    result: dict[int, PollOut] = {}
    for poll in polls:
        result[poll.message_id] = PollOut(
            id=str(poll.id),
            multi=poll.multi,
            closes_at=poll.closes_at,
            closed=poll.closes_at is not None and poll.closes_at <= now,
            options=[
                PollOptionOut(id=str(option.id), text=option.text, votes=counts.get(option.id, 0))
                for option in options
                if option.poll_id == poll.id
            ],
            voters=voters.get(poll.id, 0),
            my_votes=mine.get(poll.id, []) if viewer is not None else None,
        )
    return result
