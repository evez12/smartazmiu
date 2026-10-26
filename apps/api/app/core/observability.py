from typing import Any

import sentry_sdk
from sentry_sdk.types import Event, Hint

from app.core.config import Settings

_SCRUBBED_HEADERS = frozenset({"authorization", "cookie", "x-csrf-token"})


def scrub_event(event: Event, _hint: Hint) -> Event | None:
    """Drop credentials and personal data before an event leaves the server (§14)."""
    request: dict[str, Any] = event.get("request") or {}
    request.pop("cookies", None)
    request.pop("data", None)
    # WebSocket tickets travel in the query string (ADR 0003); no URL leaves with one.
    request.pop("query_string", None)
    url = request.get("url")
    if isinstance(url, str):
        request["url"] = url.split("?", 1)[0]
    headers = request.get("headers")
    if isinstance(headers, dict):
        request["headers"] = {
            key: value for key, value in headers.items() if key.lower() not in _SCRUBBED_HEADERS
        }
    user = event.get("user")
    if user:
        event["user"] = {"id": user["id"]} if "id" in user else {}
    return event


def init_sentry(settings: Settings) -> bool:
    if not settings.sentry_dsn:
        return False
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        release=settings.release,
        send_default_pii=False,
        traces_sample_rate=0.1,
        before_send=scrub_event,
    )
    return True
