"""@mentions (§5.3, §13.2, D-067).

The composer writes a mention as ``<@user-id>`` so that people with the same name stay distinct. Only channel
members are recorded; any other token stays plain text and its id is never looked up beyond membership, so a
mention reveals nothing about who is in the channel. ``@channel`` is honoured for teachers, channel moderators
and staff only.
"""

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import Select, delete, exists, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.modules.chat.lookup import find_message
from app.modules.chat.models import (
    Channel,
    ChannelMember,
    Message,
    MessageMention,
    NotifyLevel,
    UserBlock,
)
from app.modules.notifications.models import NotificationCategory, NotificationKind
from app.modules.notifications.service import NotificationSpec, Notifier
from app.modules.users.models import User, UserStatus
from app.modules.users.service import CurrentUser

USER_MENTION = re.compile(
    r"<@([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})>"
)
CHANNEL_MENTION = re.compile(r"(?<![\w@])@channel(?![\w-])")
# Code is quoted text: "@channel" in a snippet must not page a whole faculty.
CODE = re.compile(r"```.*?(?:```|$)|`[^`\n]*`", re.DOTALL)
MAX_MENTIONS = 50
SUBJECT_TYPE = "chat_message"


@dataclass(frozen=True, slots=True)
class ParsedMentions:
    user_ids: list[uuid.UUID]
    channel: bool


def parse(body: str) -> ParsedMentions:
    text = CODE.sub(" ", body)
    seen: dict[uuid.UUID, None] = {}
    for match in USER_MENTION.finditer(text):
        seen.setdefault(uuid.UUID(match.group(1)), None)
        if len(seen) == MAX_MENTIONS:
            break
    return ParsedMentions(list(seen), bool(CHANNEL_MENTION.search(text)))


def subject_id(message_id: int) -> uuid.UUID:
    """Notification subjects are UUIDs; a snowflake fits in one losslessly, so delivery can find the message."""
    return uuid.UUID(int=message_id)


class MentionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(self, message: Message, parsed: ParsedMentions) -> set[uuid.UUID]:
        """Stores the mentioned members (replacing earlier ones after an edit); returns those newly added."""
        members = set()
        if parsed.user_ids:
            members = set(
                await self.session.scalars(
                    select(ChannelMember.user_id).where(
                        ChannelMember.channel_id == message.channel_id,
                        ChannelMember.user_id.in_(parsed.user_ids),
                        ChannelMember.user_id != message.author_id,
                    )
                )
            )
        stored = set(
            await self.session.scalars(
                select(MessageMention.user_id).where(MessageMention.message_id == message.id)
            )
        )
        if stored - members:
            await self.session.execute(
                delete(MessageMention).where(
                    MessageMention.message_id == message.id,
                    MessageMention.user_id.in_(stored - members),
                )
            )
        added = members - stored
        if added:
            await self.session.execute(
                insert(MessageMention)
                .values([{"message_id": message.id, "user_id": user_id} for user_id in added])
                .on_conflict_do_nothing()
            )
        return added

    async def notify(
        self,
        message: Message,
        author: CurrentUser,
        *,
        mentioned: set[uuid.UUID],
        channel_wide: bool,
        reply_to: uuid.UUID | None,
    ) -> int:
        """In-app notifications plus push (§5.6), once per message and person: a reply that also mentions
        someone notifies them once. Runs in the caller's transaction."""
        channel_name = await self.session.scalar(
            select(Channel.name).where(Channel.id == message.channel_id)
        )
        title = f"{author.display_name} · {channel_name}" if channel_name else author.display_name
        thread = message.parent_id or message.id
        link = f"/chat/{message.channel_id}"
        if message.parent_id is not None:
            link += f"?thread={thread}"
        created = 0
        targets: list[tuple[NotificationKind, Select[uuid.UUID]]] = []
        if mentioned or channel_wide:
            query = self._recipients(message)
            if not channel_wide:
                query = query.where(ChannelMember.user_id.in_(mentioned))
            targets.append((NotificationKind.CHAT_MENTION, query))
        if reply_to is not None and reply_to != message.author_id:
            targets.append(
                (
                    NotificationKind.CHAT_REPLY,
                    self._recipients(message).where(ChannelMember.user_id == reply_to),
                )
            )
        for kind, recipients in targets:
            created += await Notifier(self.session).notify(
                recipients,
                NotificationSpec(
                    category=NotificationCategory.CHAT,
                    kind=kind,
                    subject_type=SUBJECT_TYPE,
                    subject_id=subject_id(message.id),
                    dedupe_key=f"chat.message:{message.id}",
                    title=title,
                    link=link,
                ),
            )
        return created

    def _recipients(self, message: Message) -> Select[uuid.UUID]:
        """Members who still want to hear from this channel and have not blocked the author (§5.6)."""
        return (
            select(ChannelMember.user_id)
            .join(User, User.id == ChannelMember.user_id)
            .where(
                ChannelMember.channel_id == message.channel_id,
                ChannelMember.user_id != message.author_id,
                ChannelMember.notify_level != NotifyLevel.NONE,
                User.status == UserStatus.ACTIVE,
                ~exists().where(
                    UserBlock.blocker_id == ChannelMember.user_id,
                    UserBlock.blocked_id == message.author_id,
                ),
            )
        )


async def still_relevant(session: AsyncSession, subject: uuid.UUID, user_id: uuid.UUID) -> bool:
    """Delivery-time check (§5.6): the message still exists, the person is still a member, has not muted the
    channel or switched it to "none", and has not blocked the author since."""
    message = await find_message(session, subject.int)
    if message is None or message.deleted_at is not None:
        return False
    now = utc_now()
    member = await session.scalar(
        select(ChannelMember).where(
            ChannelMember.channel_id == message.channel_id, ChannelMember.user_id == user_id
        )
    )
    if member is None or member.notify_level is NotifyLevel.NONE:
        return False
    if member.muted_until is not None and member.muted_until > now:
        return False
    blocked = await session.scalar(
        select(
            exists().where(
                UserBlock.blocker_id == user_id, UserBlock.blocked_id == message.author_id
            )
        )
    )
    return not blocked
