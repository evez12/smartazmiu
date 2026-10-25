"""KeycloakAdmin against a stand-in for the Keycloak admin REST API."""

import json

import httpx
import pytest

from app.core.identity_admin import IdentityAdminUnavailableError, KeycloakAdmin

BASE = "http://keycloak.test"
ROLES = {
    "student": {"id": "r-student", "name": "student"},
    "moderator": {"id": "r-moderator", "name": "moderator"},
}


class FakeKeycloak:
    def __init__(self) -> None:
        self.mappings: dict[str, list[dict[str, str]]] = {"kc-ramin": [ROLES["student"]]}
        self.token_requests = 0
        self.fail_admin = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/realms/smartazmiu/protocol/openid-connect/token":
            self.token_requests += 1
            form = dict(httpx.QueryParams(request.content.decode()))
            if form != {
                "grant_type": "client_credentials",
                "client_id": "smartazmiu-api-admin",
                "client_secret": "s3cret",
            }:
                return httpx.Response(401)
            return httpx.Response(200, json={"access_token": "admin-token", "expires_in": 300})
        if request.headers.get("authorization") != "Bearer admin-token" or self.fail_admin:
            return httpx.Response(403)
        if path.startswith("/admin/realms/smartazmiu/roles/"):
            name = path.rsplit("/", 1)[-1]
            return httpx.Response(200, json=ROLES[name]) if name in ROLES else httpx.Response(404)
        if path == "/admin/realms/smartazmiu/users/kc-ramin/role-mappings/realm":
            mappings = self.mappings["kc-ramin"]
            if request.method == "GET":
                return httpx.Response(200, json=mappings)
            body = json.loads(request.content)
            if request.method == "POST":
                mappings.extend(body)
            else:
                ids = {role["id"] for role in body}
                self.mappings["kc-ramin"] = [m for m in mappings if m["id"] not in ids]
            return httpx.Response(204)
        return httpx.Response(404)


def admin_for(fake: FakeKeycloak, secret: str = "s3cret") -> KeycloakAdmin:
    http = httpx.AsyncClient(transport=httpx.MockTransport(fake))
    return KeycloakAdmin(http, BASE, "smartazmiu", "smartazmiu-api-admin", secret)


async def test_reads_and_changes_realm_role_mappings() -> None:
    fake = FakeKeycloak()
    admin = admin_for(fake)

    assert await admin.realm_roles("kc-ramin") == {"student"}
    await admin.change_realm_roles("kc-ramin", add=["moderator"], remove=[])
    assert await admin.realm_roles("kc-ramin") == {"student", "moderator"}
    await admin.change_realm_roles("kc-ramin", add=[], remove=["student"])
    assert await admin.realm_roles("kc-ramin") == {"moderator"}
    # The service-account token is reused until shortly before it expires.
    assert fake.token_requests == 1


async def test_refused_or_unreachable_keycloak_is_reported() -> None:
    fake = FakeKeycloak()
    with pytest.raises(IdentityAdminUnavailableError):
        await admin_for(fake, secret="wrong").realm_roles("kc-ramin")

    fake.fail_admin = True
    with pytest.raises(IdentityAdminUnavailableError):
        await admin_for(fake).change_realm_roles("kc-ramin", add=["moderator"], remove=[])

    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    http = httpx.AsyncClient(transport=httpx.MockTransport(unreachable))
    with pytest.raises(IdentityAdminUnavailableError):
        await KeycloakAdmin(http, BASE, "smartazmiu", "c", "s").realm_roles("kc-ramin")
