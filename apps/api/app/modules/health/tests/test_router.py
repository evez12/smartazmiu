from fastapi import FastAPI
from httpx import AsyncClient
from redis.asyncio import Redis


async def test_healthz_does_not_touch_dependencies(client: AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readyz_reports_each_dependency(client: AsyncClient) -> None:
    response = await client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "ok", "redis": "ok"}}


async def test_readyz_is_unavailable_when_redis_is_down(app: FastAPI, client: AsyncClient) -> None:
    healthy_redis = app.state.redis
    app.state.redis = Redis(host="127.0.0.1", port=1, socket_connect_timeout=0.2)
    try:
        response = await client.get("/readyz")
    finally:
        await app.state.redis.aclose()
        app.state.redis = healthy_redis
    assert response.status_code == 503
    assert response.json()["checks"] == {"database": "ok", "redis": "unavailable"}
