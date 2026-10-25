"""Ticket codes for the QR on a registration: ``SA1.<registration id>.<signature>``.

The signature is an HMAC under ``TICKET_SECRET`` of the event id and the registration id, so a code is bound to
both and cannot be guessed or forged, and nothing secret is stored per ticket: a database dump does not reveal
working tickets. A code stays valid while its registration does; cancelling the registration voids it.
"""

import base64
import hashlib
import hmac
import uuid
from dataclasses import dataclass

PREFIX = "SA1"
SIGNATURE_BYTES = 16


@dataclass(frozen=True, slots=True)
class ScannedTicket:
    registration_id: uuid.UUID
    signature: str


def _signature(secret: str, event_id: uuid.UUID, registration_id: uuid.UUID) -> str:
    message = b"smartazmiu-ticket:" + event_id.bytes + registration_id.bytes
    digest = hmac.new(secret.encode(), message, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest[:SIGNATURE_BYTES]).rstrip(b"=").decode()


def ticket_code(secret: str, event_id: uuid.UUID, registration_id: uuid.UUID) -> str:
    return f"{PREFIX}.{registration_id.hex}.{_signature(secret, event_id, registration_id)}"


def parse_ticket(code: str) -> ScannedTicket | None:
    """The parts of a well-formed code; whether it is genuine is decided by ``is_genuine``."""
    parts = code.strip().split(".")
    if len(parts) != 3 or parts[0] != PREFIX:
        return None
    try:
        registration_id = uuid.UUID(hex=parts[1])
    except ValueError:
        return None
    return ScannedTicket(registration_id, parts[2])


def is_genuine(secret: str, ticket: ScannedTicket, event_id: uuid.UUID) -> bool:
    """Whether the signature was made by us for this registration of this event (constant-time compare)."""
    return hmac.compare_digest(
        ticket.signature, _signature(secret, event_id, ticket.registration_id)
    )
