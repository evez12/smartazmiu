"""Finding one message by its snowflake id, which also fixes its partition (ADR 0002)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.modules.chat.models import Message
from app.modules.chat.snowflake import created_at_of

MAX_MESSAGE_ID = (1 << 63) - 1


def parse_message_id(value: str) -> int:
    """A path or payload id as an integer; ids outside BIGINT cannot exist, so they are simply not found."""
    message_id = int(value)
    if not 0 < message_id <= MAX_MESSAGE_ID:
        raise AppError("chat.message_not_found", 404)
    return message_id


async def find_message(
    session: AsyncSession, message_id: int, *, lock: bool = False
) -> Message | None:
    query = select(Message).where(
        Message.id == message_id, Message.created_at == created_at_of(message_id)
    )
    if lock:
        query = query.with_for_update()
    return await session.scalar(query)
