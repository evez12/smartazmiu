"""Changes realm role mappings in Keycloak, which owns global role membership (DECISIONS D-016, D-035)."""

import asyncio
import time
from collections.abc import Iterable
from typing import Any, Protocol

import httpx
import structlog

logger = structlog.get_logger(__name__)

# Renew the service-account token a little before it expires.
TOKEN_MARGIN_SECONDS = 30


class IdentityAdminUnavailableError(Exception):
    """Keycloak could not be reached or refused the change."""


class IdentityAdmin(Protocol):
    async def realm_roles(self, subject: str) -> set[str]: ...

    async def change_realm_roles(
        self, subject: str, *, add: Iterable[str], remove: Iterable[str]
    ) -> None: ...


class KeycloakAdmin:
    def __init__(
        self, http: httpx.AsyncClient, base_url: str, realm: str, client_id: str, client_secret: str
    ) -> None:
        self._http = http
        self._token_url = f"{base_url}/realms/{realm}/protocol/openid-connect/token"
        self._admin_url = f"{base_url}/admin/realms/{realm}"
        self._client_id = client_id
        self._client_secret = client_secret
        self._token: str | None = None
        self._token_expires = 0.0
        self._lock = asyncio.Lock()

    async def realm_roles(self, subject: str) -> set[str]:
        mappings = await self._request("GET", f"/users/{subject}/role-mappings/realm")
        return {role["name"] for role in mappings}

    async def change_realm_roles(
        self, subject: str, *, add: Iterable[str], remove: Iterable[str]
    ) -> None:
        path = f"/users/{subject}/role-mappings/realm"
        if added := [await self._role(name) for name in add]:
            await self._request("POST", path, json=added)
        if removed := [await self._role(name) for name in remove]:
            await self._request("DELETE", path, json=removed)

    async def _role(self, name: str) -> dict[str, Any]:
        role: dict[str, Any] = await self._request("GET", f"/roles/{name}")
        return {"id": role["id"], "name": role["name"]}

    async def _request(self, method: str, path: str, json: Any = None) -> Any:
        headers = {"Authorization": f"Bearer {await self._access_token()}"}
        try:
            response = await self._http.request(
                method, f"{self._admin_url}{path}", headers=headers, json=json
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("identity_admin_failed", method=method, error=type(exc).__name__)
            raise IdentityAdminUnavailableError from exc
        return response.json() if response.content else None

    async def _access_token(self) -> str:
        async with self._lock:
            if self._token and time.monotonic() < self._token_expires:
                return self._token
            try:
                response = await self._http.post(
                    self._token_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                    },
                )
                response.raise_for_status()
                body = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning("identity_admin_token_failed", error=type(exc).__name__)
                raise IdentityAdminUnavailableError from exc
            self._token = str(body["access_token"])
            self._token_expires = time.monotonic() + int(body["expires_in"]) - TOKEN_MARGIN_SECONDS
            return self._token
