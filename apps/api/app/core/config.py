from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    release: str = "dev"
    log_level: str = "INFO"

    database_url: PostgresDsn = Field(
        default=PostgresDsn("postgresql+asyncpg://smartazmiu:smartazmiu@localhost:5433/smartazmiu")
    )
    redis_url: RedisDsn = Field(default=RedisDsn("redis://localhost:6379/0"))

    # The issuer is the browser-facing Keycloak URL; JWKS may be fetched over the internal network.
    oidc_issuer: str = "http://localhost:8080/realms/smartazmiu"
    oidc_jwks_url: str = "http://localhost:8080/realms/smartazmiu/protocol/openid-connect/certs"
    oidc_audience: str = "smartazmiu-api"

    sentry_dsn: str | None = None

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
