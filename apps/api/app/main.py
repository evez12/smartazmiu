from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from redis.asyncio import Redis

from app.core.config import Settings, get_settings
from app.core.db import Database
from app.core.errors import register_error_handlers
from app.core.identity_admin import KeycloakAdmin
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.core.observability import init_sentry
from app.core.security import JWKSKeySource, TokenVerifier
from app.core.storage import S3Storage
from app.modules.academics.router import imports as imports_router
from app.modules.academics.router import router as academics_router
from app.modules.admin.router import router as admin_router
from app.modules.health.router import router as health_router
from app.modules.users.router import router as users_router

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    init_sentry(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.database = Database(str(settings.database_url))
        app.state.redis = Redis.from_url(str(settings.redis_url), decode_responses=True)
        app.state.http = httpx.AsyncClient(timeout=httpx.Timeout(5.0))
        app.state.identity_admin = KeycloakAdmin(
            app.state.http,
            base_url=settings.keycloak_url,
            realm=settings.keycloak_realm,
            client_id=settings.keycloak_admin_client_id,
            client_secret=settings.keycloak_admin_client_secret,
        )
        app.state.storage = S3Storage(
            endpoint_url=settings.s3_endpoint_url,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            bucket=settings.s3_bucket,
            region=settings.s3_region,
        )
        app.state.token_verifier = TokenVerifier(
            issuer=settings.oidc_issuer,
            audience=settings.oidc_audience,
            keys=JWKSKeySource(settings.oidc_jwks_url, app.state.http),
        )
        try:
            yield
        finally:
            await app.state.http.aclose()
            await app.state.redis.aclose()
            await app.state.database.dispose()

    show_docs = not settings.is_production
    app = FastAPI(
        title="SmartAzMİU API",
        version="0.1.0",
        lifespan=lifespan,
        openapi_url=f"{API_PREFIX}/openapi.json" if show_docs else None,
        docs_url=f"{API_PREFIX}/docs" if show_docs else None,
        redoc_url=None,
    )
    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)

    app.include_router(health_router)
    app.include_router(users_router, prefix=API_PREFIX)
    app.include_router(academics_router, prefix=API_PREFIX)
    app.include_router(imports_router, prefix=API_PREFIX)
    app.include_router(admin_router, prefix=API_PREFIX)
    return app


app = create_app()
