"""Ticket codes for the QR on a registration: ``SA1.<registration id>.<signature>``.

The signature is an HMAC of the id under ``TICKET_SECRET``, so codes cannot be guessed or forged, and nothing
secret is stored per ticket: a database dump does not reveal working tickets. A code stays valid while its
registration does; cancelling the registration voids it.
"""

import base64
import hashlib
import hmac
import uuid

PREFIX = "SA1"
SIGNATURE_BYTES = 16


def _signature(secret: str, registration_id: uuid.UUID) -> str:
    digest = hmac.new(
        secret.encode(), b"smartazmiu-ticket:" + registration_id.bytes, hashlib.sha256
    ).digest()
    return base64.urlsafe_b64encode(digest[:SIGNATURE_BYTES]).rstrip(b"=").decode()


def ticket_code(secret: str, registration_id: uuid.UUID) -> str:
    return f"{PREFIX}.{registration_id.hex}.{_signature(secret, registration_id)}"


def read_ticket(secret: str, code: str) -> uuid.UUID | None:
    """The registration id of a genuine code; None for anything else (typos, forgeries, other formats)."""
    parts = code.strip().split(".")
    if len(parts) != 3 or parts[0] != PREFIX:
        return None
    try:
        registration_id = uuid.UUID(hex=parts[1])
    except ValueError:
        return None
    if not hmac.compare_digest(parts[2], _signature(secret, registration_id)):
        return None
    return registration_id
