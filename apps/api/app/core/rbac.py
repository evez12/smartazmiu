from collections.abc import Awaitable, Callable
from typing import Annotated

import structlog
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.deps import SessionDep
from app.core.errors import AppError
from app.core.security import InvalidTokenError, TokenVerifier
from app.modules.users.service import CurrentUser, UserService

logger = structlog.get_logger(__name__)

_bearer = HTTPBearer(auto_error=False, description="Keycloak access token")
_UNAUTHENTICATED_HEADERS = {"WWW-Authenticate": "Bearer"}


async def get_current_user(
    request: Request,
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> CurrentUser:
    if credentials is None:
        raise AppError("auth.unauthenticated", 401, headers=_UNAUTHENTICATED_HEADERS)
    verifier: TokenVerifier = request.app.state.token_verifier
    try:
        claims = await verifier.verify(credentials.credentials)
    except InvalidTokenError as exc:
        logger.info("token_rejected", reason=str(exc))
        raise AppError("auth.unauthenticated", 401, headers=_UNAUTHENTICATED_HEADERS) from exc

    user = await UserService(session).sync_from_claims(claims)
    structlog.contextvars.bind_contextvars(user_id=str(user.id))
    if not user.is_active:
        raise AppError("auth.account_inactive", 403)
    return user


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


def require_permission(code: str) -> Callable[[CurrentUser], Awaitable[CurrentUser]]:
    """Dependency factory: the request proceeds only if one of the user's roles grants ``code``."""

    async def dependency(user: CurrentUserDep) -> CurrentUser:
        if not user.has_permission(code):
            logger.info("permission_denied", permission=code)
            raise AppError("auth.forbidden", 403, details={"permission": code})
        return user

    dependency.__name__ = f"require_permission[{code}]"
    return dependency
