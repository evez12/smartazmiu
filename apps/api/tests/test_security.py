import time
from typing import Any

import httpx
import jwt
import pytest

from app.core.security import InvalidTokenError, JWKSKeySource, TokenVerifier
from tests.support import TEST_AUDIENCE, TEST_ISSUER, TokenFactory


@pytest.fixture
def verifier(tokens: TokenFactory) -> TokenVerifier:
    return TokenVerifier(TEST_ISSUER, TEST_AUDIENCE, tokens.key_source())


async def test_valid_access_token_yields_claims(
    verifier: TokenVerifier, tokens: TokenFactory
) -> None:
    claims = await verifier.verify(
        tokens.issue("kc-1", ["student", "moderator"], email="Aysel.Mammadova@SmartAzMIU.test")
    )
    assert claims.subject == "kc-1"
    assert claims.roles == frozenset({"student", "moderator"})
    assert claims.display_name == "Aysel Məmmədova"
    assert claims.email == "aysel.mammadova@smartazmiu.test"


async def test_display_name_falls_back_to_username(
    verifier: TokenVerifier, tokens: TokenFactory
) -> None:
    claims = await verifier.verify(
        tokens.issue(
            given_name="", family_name="", name=None, preferred_username="ramin.aliyev", email=None
        )
    )
    assert claims.display_name == "ramin.aliyev"
    assert claims.email is None


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"aud": "another-api"}, id="wrong-audience"),
        pytest.param({"iss": "http://evil.test/realms/smartazmiu"}, id="wrong-issuer"),
        pytest.param({"typ": "ID"}, id="id-token"),
        pytest.param({"typ": "Refresh"}, id="refresh-token"),
        pytest.param({"exp": int(time.time()) - 120}, id="expired"),
    ],
)
async def test_rejects_tokens_not_meant_for_this_api(
    verifier: TokenVerifier, tokens: TokenFactory, overrides: dict[str, Any]
) -> None:
    with pytest.raises(InvalidTokenError):
        await verifier.verify(tokens.issue(**overrides))


async def test_rejects_missing_subject(verifier: TokenVerifier, tokens: TokenFactory) -> None:
    token = tokens.issue()
    payload = jwt.decode(token, options={"verify_signature": False})
    del payload["sub"]
    unsigned = jwt.encode(
        payload, tokens.private_key, algorithm="RS256", headers={"kid": "test-key"}
    )
    with pytest.raises(InvalidTokenError):
        await verifier.verify(unsigned)


async def test_rejects_symmetric_algorithm_confusion(verifier: TokenVerifier) -> None:
    forged = jwt.encode(
        {"sub": "x", "iss": TEST_ISSUER, "aud": TEST_AUDIENCE},
        "public-key-used-as-hmac-secret-0123456789",
        algorithm="HS256",
        headers={"kid": "test-key"},
    )
    with pytest.raises(InvalidTokenError, match="unsupported token header"):
        await verifier.verify(forged)


async def test_rejects_unknown_key_and_garbage(
    verifier: TokenVerifier, tokens: TokenFactory
) -> None:
    with pytest.raises(InvalidTokenError):
        await verifier.verify(tokens.issue(headers={"kid": "rotated-away"}))
    with pytest.raises(InvalidTokenError, match="malformed"):
        await verifier.verify("not-a-jwt")


async def test_rejects_signature_from_another_key(verifier: TokenVerifier) -> None:
    impostor = TokenFactory(key_id="test-key")
    with pytest.raises(InvalidTokenError):
        await verifier.verify(impostor.issue())


class TestJWKSKeySource:
    async def test_fetches_keys_once_and_caches_them(self, tokens: TokenFactory) -> None:
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(200, json={"keys": [tokens.jwk]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            source = JWKSKeySource("http://keycloak.test/certs", http)
            first = await source.get_key("test-key")
            second = await source.get_key("test-key")

        assert first is second
        assert calls == 1

    async def test_unknown_key_refetch_is_rate_limited(self, tokens: TokenFactory) -> None:
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(200, json={"keys": [tokens.jwk]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            source = JWKSKeySource("http://keycloak.test/certs", http, min_refresh_seconds=60)
            for _ in range(3):
                with pytest.raises(InvalidTokenError):
                    await source.get_key("random-kid")

        assert calls == 1

    async def test_identity_provider_outage_is_an_invalid_token(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            source = JWKSKeySource("http://keycloak.test/certs", http)
            with pytest.raises(InvalidTokenError):
                await source.get_key("test-key")
