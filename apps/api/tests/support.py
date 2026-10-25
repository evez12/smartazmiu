"""Test helpers: an in-memory signing key that stands in for Keycloak, and an in-memory object store."""

import time
import uuid
from collections.abc import Iterable
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from app.core.identity_admin import IdentityAdminUnavailableError
from app.core.security import InvalidTokenError
from app.core.storage import StorageUnavailableError

TEST_ISSUER = "http://keycloak.test/realms/smartazmiu"
TEST_AUDIENCE = "smartazmiu-api"


class StaticKeySource:
    def __init__(self, keys: dict[str, jwt.PyJWK]) -> None:
        self.keys = keys

    async def get_key(self, key_id: str) -> jwt.PyJWK:
        try:
            return self.keys[key_id]
        except KeyError as exc:
            raise InvalidTokenError("unknown signing key") from exc


class TokenFactory:
    def __init__(self, key_id: str = "test-key") -> None:
        self.key_id = key_id
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_jwk = RSAAlgorithm.to_jwk(self.private_key.public_key(), as_dict=True)
        self.jwk: dict[str, Any] = {**public_jwk, "kid": key_id, "alg": "RS256", "use": "sig"}

    def key_source(self) -> StaticKeySource:
        return StaticKeySource({self.key_id: jwt.PyJWK.from_dict(self.jwk)})

    def issue(
        self,
        subject: str | None = None,
        roles: list[str] | None = None,
        *,
        given_name: str = "Aysel",
        family_name: str = "Məmmədova",
        email: str | None = "aysel.mammadova@smartazmiu.test",
        email_verified: bool = True,
        lifetime_seconds: int = 900,
        headers: dict[str, Any] | None = None,
        **overrides: Any,
    ) -> str:
        now = int(time.time())
        claims: dict[str, Any] = {
            "iss": TEST_ISSUER,
            "aud": TEST_AUDIENCE,
            "sub": subject or str(uuid.uuid4()),
            "typ": "Bearer",
            "iat": now,
            "exp": now + lifetime_seconds,
            "given_name": given_name,
            "family_name": family_name,
            "name": f"{given_name} {family_name}",
            "email": email,
            "email_verified": email_verified,
            "realm_access": {"roles": roles if roles is not None else ["student"]},
        }
        claims.update(overrides)
        return jwt.encode(
            claims,
            self.private_key,
            algorithm="RS256",
            headers={"kid": self.key_id, **(headers or {})},
        )


class MemoryStorage:
    """Object storage double; ``available = False`` simulates an outage (§13.5)."""

    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.available = True

    def _check(self) -> None:
        if not self.available:
            raise StorageUnavailableError

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self._check()
        self.objects[key] = (data, content_type)

    async def get(self, key: str) -> bytes | None:
        self._check()
        stored = self.objects.get(key)
        return stored[0] if stored else None

    async def delete(self, key: str) -> None:
        self._check()
        self.objects.pop(key, None)


class FakeIdentityAdmin:
    """Keycloak admin API double: realm roles per subject; ``available = False`` simulates an outage."""

    def __init__(self) -> None:
        self.roles: dict[str, set[str]] = {}
        self.available = True
        self.changes: list[tuple[str, set[str], set[str]]] = []

    async def realm_roles(self, subject: str) -> set[str]:
        if not self.available:
            raise IdentityAdminUnavailableError
        # Keycloak also lists default and composite helper roles; the API must ignore them.
        return self.roles.get(subject, set()) | {"default-roles-smartazmiu", "mfa_required"}

    async def change_realm_roles(
        self, subject: str, *, add: Iterable[str], remove: Iterable[str]
    ) -> None:
        if not self.available:
            raise IdentityAdminUnavailableError
        added, removed = set(add), set(remove)
        self.changes.append((subject, added, removed))
        self.roles[subject] = (self.roles.get(subject, set()) | added) - removed


class FakeJobs:
    """Job queue double: counts wake-ups instead of enqueueing ARQ jobs."""

    def __init__(self) -> None:
        self.dispatches = 0

    async def dispatch_notifications(self) -> None:
        self.dispatches += 1

    async def close(self) -> None:
        return None
