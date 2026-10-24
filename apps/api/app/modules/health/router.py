import asyncio

import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.deps import RedisDep, SessionDep

logger = structlog.get_logger(__name__)

router = APIRouter(include_in_schema=False)

CHECK_TIMEOUT_SECONDS = 2.0


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness: the process is up. Never touches dependencies, so restarts are not cascaded."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(session: SessionDep, redis: RedisDep) -> JSONResponse:
    """Readiness: the API can serve requests that need its database and Redis."""

    async def check_database() -> None:
        await session.execute(text("SELECT 1"))

    async def check_redis() -> None:
        await redis.ping()

    checks = {"database": check_database, "redis": check_redis}
    results: dict[str, str] = {}
    for name, check in checks.items():
        try:
            await asyncio.wait_for(check(), timeout=CHECK_TIMEOUT_SECONDS)
            results[name] = "ok"
        except Exception as exc:
            logger.warning("readiness_check_failed", check=name, error=type(exc).__name__)
            results[name] = "unavailable"

    ready = all(result == "ok" for result in results.values())
    return JSONResponse(
        {"status": "ok" if ready else "unavailable", "checks": results},
        status_code=200 if ready else 503,
    )
