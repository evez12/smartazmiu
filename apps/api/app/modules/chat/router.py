from datetime import UTC, datetime

from fastapi import APIRouter, Request
from redis.exceptions import RedisError

from app.core.deps import RedisDep
from app.core.errors import COMMON_ERROR_RESPONSES, AppError
from app.core.ratelimit import RateLimit, enforce_rate_limit
from app.core.rbac import CurrentUserDep
from app.core.security import TokenClaims
from app.modules.chat import tickets
from app.modules.chat.deps import DurableRedisDep
from app.modules.chat.schemas import TicketOut

# A broken client retrying in a loop cannot fill Redis A with tickets (ADR 0003).
TICKET_ISSUES = RateLimit("ws_ticket", limit=30, window_seconds=60)

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
