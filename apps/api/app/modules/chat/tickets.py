"""One-use WebSocket tickets (ADR 0003): 256 random bits, stored only as a hash on Redis instance A for 60 s."""

import hashlib
import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis

from app.core.time import utc_now

TICKET_TTL_SECONDS = 60


def _key(ticket: str) -> str:
    return f"ws:ticket:{hashlib.sha256(ticket.encode()).hexdigest()}"


@dataclass(frozen=True, slots=True)
class Ticket:
    user_id: uuid.UUID
    token_expires_at: datetime
    """The connection's authorisation ends with the access token that minted the ticket."""


async def issue(
    redis: Redis, user_id: uuid.UUID, token_expires_at: datetime
) -> tuple[str, datetime]:
    ticket = secrets.token_urlsafe(32)
    now = utc_now()
    value = json.dumps(
        {
            "user_id": str(user_id),
            "token_expires_at": token_expires_at.isoformat(),
            "issued_at": now.isoformat(),
        }
    )
    await redis.set(_key(ticket), value, ex=TICKET_TTL_SECONDS)
    return ticket, now + timedelta(seconds=TICKET_TTL_SECONDS)


async def redeem(redis: Redis, ticket: str) -> Ticket | None:
    """GETDEL: a ticket works once; unknown, used and expired tickets all give None."""
    if not ticket or len(ticket) > 64:
        return None
    raw = await redis.getdel(_key(ticket))
    if raw is None:
        return None
    stored = json.loads(raw)
    expires_at = datetime.fromisoformat(stored["token_expires_at"]).astimezone(UTC)
    return Ticket(user_id=uuid.UUID(stored["user_id"]), token_expires_at=expires_at)
