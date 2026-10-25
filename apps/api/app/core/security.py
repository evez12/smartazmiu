import asyncio
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
import jwt
import structlog

logger = structlog.get_logger(__name__)

ALLOWED_ALGORITHMS = ["RS256"]
CLOCK_LEEWAY_SECONDS = 30


class InvalidTokenError(Exception):
    """The bearer token is missing, malformed, expired or not issued for this API."""


@dataclass(frozen=True, slots=True)
class TokenClaims:
    subject: str
    email: str | None
    email_verified: bool
    given_name: str
    family_name: str
    display_name: str
    roles: frozenset[str]
    issued_at: int
    """Unix seconds (``iat``)."""


class SigningKeySource(Protocol):
    async def get_key(self, key_id: str) -> jwt.PyJWK: ...


class JWKSKeySource:
    """Caches the identity provider's signing keys and refetches them when an unknown key id appears."""

    def __init__(
        self, jwks_url: str, http: httpx.AsyncClient, min_refresh_seconds: float = 30.0
    ) -> None:
        self._jwks_url = jwks_url
        self._http = http
        self._min_refresh_seconds = min_refresh_seconds
        self._keys: dict[str, jwt.PyJWK] = {}
        self._fetched_at = float("-inf")
        self._lock = asyncio.Lock()

    async def get_key(self, key_id: str) -> jwt.PyJWK:
        key = self._keys.get(key_id)
        if key is not None:
            return key
        async with self._lock:
            # Rate-limit refetches so tokens with random key ids cannot hammer the identity provider.
            if (
                key_id not in self._keys
                and time.monotonic() - self._fetched_at >= self._min_refresh_seconds
            ):
                await self._refresh()
        key = self._keys.get(key_id)
        if key is None:
            raise InvalidTokenError("unknown signing key")
        return key

    async def _refresh(self) -> None:
        self._fetched_at = time.monotonic()
        try:
            response = await self._http.get(self._jwks_url)
            response.raise_for_status()
            key_set = jwt.PyJWKSet.from_dict(response.json())
        except (httpx.HTTPError, ValueError, jwt.PyJWKSetError) as exc:
            logger.warning("jwks_refresh_failed", error=type(exc).__name__)
            return
        self._keys = {key.key_id: key for key in key_set.keys if key.key_id}


class TokenVerifier:
    def __init__(self, issuer: str, audience: str, keys: SigningKeySource) -> None:
        self._issuer = issuer
        self._audience = audience
        self._keys = keys

    async def verify(self, token: str) -> TokenClaims:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise InvalidTokenError("malformed token") from exc
        key_id = header.get("kid")
        if header.get("alg") not in ALLOWED_ALGORITHMS or not isinstance(key_id, str):
            raise InvalidTokenError("unsupported token header")

        key = await self._keys.get_key(key_id)
        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                key=key,
                algorithms=ALLOWED_ALGORITHMS,
                audience=self._audience,
                issuer=self._issuer,
                leeway=CLOCK_LEEWAY_SECONDS,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise InvalidTokenError(type(exc).__name__) from exc

        # Keycloak marks access tokens with typ=Bearer; ID and refresh tokens must be rejected.
        if payload.get("typ") != "Bearer":
            raise InvalidTokenError("not an access token")
        return _claims_from_payload(payload)


def _claims_from_payload(payload: dict[str, Any]) -> TokenClaims:
    realm_access = payload.get("realm_access")
    raw_roles = realm_access.get("roles", []) if isinstance(realm_access, dict) else []
    given_name = str(payload.get("given_name") or "")
    family_name = str(payload.get("family_name") or "")
    display_name = str(payload.get("name") or f"{given_name} {family_name}".strip())
    email = payload.get("email")
    return TokenClaims(
        subject=str(payload["sub"]),
        email=email.lower() if isinstance(email, str) else None,
        email_verified=payload.get("email_verified") is True,
        given_name=given_name,
        family_name=family_name,
        display_name=display_name or str(payload.get("preferred_username") or ""),
        roles=frozenset(role for role in raw_roles if isinstance(role, str)),
        issued_at=int(payload["iat"]),
    )
