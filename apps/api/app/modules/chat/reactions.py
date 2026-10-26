"""Reactions from a fixed set of eight (§5.3, D-067), one per (message, user, emoji)."""

from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.ratelimit import RateLimit, enforce_rate_limit
from app.modules.chat.access import ChannelAccess, deny
from app.modules.chat.bus import ChatBus, channel_topic
from app.modules.chat.lookup import find_message
from app.modules.chat.models import MessageReaction
from app.modules.chat.policy import Action
from app.modules.users.service import CurrentUser

# Order is the picker's order and the order of counts in payloads.
REACTIONS = ("👍", "❤️", "😂", "😮", "😢", "🙏", "🎉", "✅")
# Generous for a person clicking; stops a script toggling reactions to flood a channel with events.
REACT_LIMIT = RateLimit("chat_react", limit=60, window_seconds=60)


@dataclass(frozen=True, slots=True)
class ReactionResult:
    message_id: int
    emoji: str
    count: int
    reacted: bool


class ReactionService:
    def __init__(self, session: AsyncSession, access: ChannelAccess, bus: ChatBus) -> None:
        self.session = session
        self.access = access
        self.bus = bus

    async def add(self, user: CurrentUser, message_id: int, emoji: str) -> ReactionResult:
        return await self._change(user, message_id, emoji, add=True)

    async def remove(self, user: CurrentUser, message_id: int, emoji: str) -> ReactionResult:
        return await self._change(user, message_id, emoji, add=False)

    async def _change(
        self, user: CurrentUser, message_id: int, emoji: str, *, add: bool
    ) -> ReactionResult:
        if emoji not in REACTIONS:
            raise AppError("chat.reaction_not_allowed", 422, details={"allowed": list(REACTIONS)})
        # The table has no foreign key to the partitioned messages table: existence is checked here (ADR 0002).
        message = await find_message(self.session, message_id)
        if message is None or message.deleted_at is not None:
            raise AppError("chat.message_not_found", 404)
        decision = await self.access.decide(user, message.channel_id, Action.REACT)
        if not decision.allowed:
            raise deny(decision, missing="chat.message_not_found")
        await enforce_rate_limit(self.access.cache, REACT_LIMIT, str(user.id))
        if add:
            changed = await self.session.scalar(
                insert(MessageReaction)
                .values(message_id=message_id, user_id=user.id, emoji=emoji)
                .on_conflict_do_nothing()
                .returning(MessageReaction.message_id)
            )
        else:
            changed = await self.session.scalar(
                delete(MessageReaction)
                .where(
                    MessageReaction.message_id == message_id,
                    MessageReaction.user_id == user.id,
                    MessageReaction.emoji == emoji,
                )
                .returning(MessageReaction.message_id)
            )
        count = await self.session.scalar(
            select(func.count()).where(
                MessageReaction.message_id == message_id, MessageReaction.emoji == emoji
            )
        )
        await self.session.commit()
        result = ReactionResult(message_id, emoji, count or 0, reacted=add)
        if changed is not None:
            # Repeating an add or a remove changes nothing and announces nothing (idempotent).
            await self.bus.publish(
                channel_topic(message.channel_id),
                "reaction.updated",
                {
                    "message_id": str(message_id),
                    "channel_id": str(message.channel_id),
                    "emoji": emoji,
                    "count": result.count,
                    "user_id": str(user.id),
                    "added": add,
                },
            )
        return result
