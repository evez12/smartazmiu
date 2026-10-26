import logging
import re
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

# Keys whose values must never be written to logs (§14: no secrets, PII redacted).
SENSITIVE_KEYS = frozenset(
    {
        "access_token",
        "authorization",
        "cookie",
        "email",
        "id_token",
        "password",
        "phone",
        "refresh_token",
        "secret",
        "set-cookie",
        "ticket",
        "token",
    }
)
REDACTED = "[redacted]"
# uvicorn logs WebSocket handshakes with the query string, which carries the one-use ticket (ADR 0003).
_TICKET_IN_URL = re.compile(r"(ticket=)[^&\s\"']+")


class RedactTicketsFilter(logging.Filter):
    """Removes ``ticket=…`` from any log line, whoever wrote it."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str) and "ticket=" in record.getMessage():
            record.msg = _TICKET_IN_URL.sub(rf"\g<1>{REDACTED}", record.getMessage())
            record.args = ()
        return True


def redact_sensitive(
    _logger: Any, _method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    for key in event_dict:
        if key.lower() in SENSITIVE_KEYS:
            event_dict[key] = REDACTED
    return event_dict


def configure_logging(level: str) -> None:
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        redact_sensitive,
    ]
    structlog.configure(
        processors=[*shared_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(RedactTicketsFilter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers.clear()
        logging.getLogger(name).propagate = True
    # The request middleware writes one structured access line per request instead.
    logging.getLogger("uvicorn.access").disabled = True
