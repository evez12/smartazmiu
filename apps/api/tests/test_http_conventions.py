"""Error envelope (§4.2), localisation and request ids, exercised through the real app."""

import json
import logging
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel


def structured(record: logging.LogRecord) -> dict[str, Any]:
    """structlog hands its event dict to stdlib logging as the record message."""
    return record.msg if isinstance(record.msg, dict) else {}


class EnrollmentProbe(BaseModel):
    group_code: str
    credits: int


@pytest.fixture
def probe_app(app: FastAPI) -> FastAPI:
    async def create_probe(body: EnrollmentProbe) -> dict[str, str]:
        return {"group_code": body.group_code}

    async def explode() -> None:
        raise RuntimeError("database password=hunter2 leaked into an exception")

    app.add_api_route("/api/v1/test/probe", create_probe, methods=["POST"])
    app.add_api_route("/api/v1/test/explode", explode, methods=["GET"])
    return app


async def test_unknown_route_uses_the_envelope(client: AsyncClient) -> None:
    response = await client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "request.not_found",
        "message": "Axtardığınız məlumat tapılmadı.",
        "details": {},
        "request_id": response.headers["x-request-id"],
    }


async def test_wrong_method_is_reported(client: AsyncClient) -> None:
    response = await client.delete("/api/v1/me", headers={"Accept-Language": "en"})
    assert response.status_code == 405
    assert response.json()["error"]["message"] == "This request method is not supported."


async def test_validation_errors_do_not_echo_input(probe_app: FastAPI, client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/test/probe", json={"group_code": "765a2", "credits": "Fin 0412 secret"}
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "request.validation_failed"
    assert error["details"] == {"fields": [{"loc": ["body", "credits"], "type": "int_parsing"}]}
    assert "secret" not in response.text


async def test_unexpected_errors_hide_internals(
    probe_app: FastAPI, caplog: pytest.LogCaptureFixture
) -> None:
    transport = ASGITransport(app=probe_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/test/explode")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "server.internal_error"
    assert "hunter2" not in response.text
    assert "unhandled_exception" in [structured(record).get("event") for record in caplog.records]


async def test_upstream_request_id_is_kept_when_well_formed(client: AsyncClient) -> None:
    response = await client.get("/healthz", headers={"X-Request-ID": "nginx-4f1c2a9e"})
    assert response.headers["x-request-id"] == "nginx-4f1c2a9e"


async def test_malformed_request_id_is_replaced(client: AsyncClient) -> None:
    response = await client.get("/healthz", headers={"X-Request-ID": "x\r\nSet-Cookie: a=b"})
    assert response.headers["x-request-id"] != "x\r\nSet-Cookie: a=b"
    assert len(response.headers["x-request-id"]) == 32


async def test_access_log_is_one_json_line_per_request(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        await client.get("/api/v1/me", headers={"X-Request-ID": "trace-0123456789"})

    record = next(r for r in caplog.records if structured(r).get("event") == "request")
    line = json.loads(logging.getLogger().handlers[0].format(record))
    assert line["path"] == "/api/v1/me"
    assert line["status"] == 401
    assert line["request_id"] == "trace-0123456789"
    assert line["level"] == "info"
    assert "timestamp" in line
