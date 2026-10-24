"""Test helpers: an in-memory signing key that stands in for Keycloak."""

import time
import uuid
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from app.core.security import InvalidTokenError

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
            "realm_access": {"roles": roles if roles is not None else ["student"]},
        }
        claims.update(overrides)
        return jwt.encode(
            claims,
            self.private_key,
            algorithm="RS256",
            headers={"kid": self.key_id, **(headers or {})},
        )
