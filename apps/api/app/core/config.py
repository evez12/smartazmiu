from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    release: str = "dev"
    log_level: str = "INFO"

    database_url: PostgresDsn = Field(
        default=PostgresDsn("postgresql+asyncpg://smartazmiu:smartazmiu@127.0.0.1:5433/smartazmiu")
    )
    redis_url: RedisDsn = Field(default=RedisDsn("redis://127.0.0.1:6379/0"))

    # The issuer is the browser-facing Keycloak URL; JWKS may be fetched over the internal network.
    oidc_issuer: str = "http://localhost:8080/realms/smartazmiu"
    oidc_jwks_url: str = "http://localhost:8080/realms/smartazmiu/protocol/openid-connect/certs"
    oidc_audience: str = "smartazmiu-api"

    # Keycloak admin API, used through a service account to assign realm roles (D-016, D-035).
    keycloak_url: str = "http://127.0.0.1:8080"
    keycloak_realm: str = "smartazmiu"
    keycloak_admin_client_id: str = "smartazmiu-api-admin"
    keycloak_admin_client_secret: str = ""

    # S3-compatible object storage (profile photos; attachments and materials later).
    s3_endpoint_url: str = "http://127.0.0.1:8333"
    s3_access_key: str = "smartazmiu"
    s3_secret_key: str = ""
    s3_bucket: str = "smartazmiu"
    s3_region: str = "us-east-1"

    sentry_dsn: str | None = None

    # Browser-facing base URL, for links in e-mails and push messages.
    app_public_url: str = "http://localhost"

    # Notification e-mail through SMTP (Mailpit locally).
    smtp_host: str = "127.0.0.1"
    smtp_port: int = 1025
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = False
    mail_from: str = "bildiris@smartazmiu.test"

    # Web Push: the VAPID key pair is derived from this secret (D-049).
    vapid_secret: str = ""
    vapid_subject: str = "mailto:it@smartazmiu.test"
    # Push endpoints are URLs supplied by browsers; the worker only posts to these services (SSRF guard, §14).
    push_service_hosts: list[str] = Field(
        default=[
            "fcm.googleapis.com",
            "updates.push.services.mozilla.com",
            "*.push.services.mozilla.com",
            "*.notify.windows.com",
            "web.push.apple.com",
            "*.push.apple.com",
        ]
    )

    # Signs event tickets; a QR code carries the ticket id and this signature (D-051).
    ticket_secret: str = ""

    @model_validator(mode="after")
    def production_secrets(self) -> "Settings":
        # An empty signing key would make ticket codes forgeable; development falls back to .env values.
        if self.app_env == "production" and not self.ticket_secret:
            raise ValueError("TICKET_SECRET must be set in production")
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
