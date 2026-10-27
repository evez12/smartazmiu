"""What gets indexed for message search (§5.7.1). Search queries arrive in Sprint 10 and use the same forms."""

import uuid

from sqlalchemy import ColumnElement, exists, func, literal, select
from sqlalchemy.dialects.postgresql import REGCONFIG
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.text import normalize_az
from app.modules.chat.models import ChannelBan, ChannelMember, GlobalChatBan, Message
from app.modules.users.service import CurrentUser


def search_document(body: str) -> str:
    """The exact and the ASCII-folded form, so a query typed either way finds the message."""
    normalized = normalize_az(body)
    if normalized.folded == normalized.exact:
        return normalized.exact
    return f"{normalized.exact} {normalized.folded}"


def body_vector(body: str) -> ColumnElement[str]:
    # `simple` does no stemming; normalize_az has already done the language-specific work.
    return func.to_tsvector(literal("simple", REGCONFIG), search_document(body))


class MessageSearchService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(
        self, user: CurrentUser, query: str, channel_id: uuid.UUID | None, limit: int
    ) -> list[tuple[Message, float]]:
        cleaned = query.strip()
        if not cleaned:
            return []
        membership = exists().where(
            ChannelMember.channel_id == Message.channel_id,
            ChannelMember.user_id == user.id,
        )
        not_banned = ~exists().where(
            ChannelBan.channel_id == Message.channel_id, ChannelBan.user_id == user.id
        ) & ~exists().where(GlobalChatBan.user_id == user.id)
        ts_query = func.websearch_to_tsquery(literal("simple", REGCONFIG), search_document(cleaned))
        text_match = Message.body_tsv.op("@@")(ts_query)
        trigram_match = func.similarity(Message.body, cleaned) >= 0.2
        rank = func.greatest(
            func.ts_rank_cd(Message.body_tsv, ts_query),
            func.similarity(Message.body, cleaned),
        ).label("rank")
        statement = (
            select(Message, rank)
            .where(
                membership,
                not_banned,
                Message.deleted_at.is_(None),
                Message.moderation == "visible",
                text_match | trigram_match,
            )
            .order_by(rank.desc(), Message.id.desc())
            .limit(limit)
        )
        if channel_id is not None:
            statement = statement.where(Message.channel_id == channel_id)
        return list((await self.session.execute(statement)).all())
