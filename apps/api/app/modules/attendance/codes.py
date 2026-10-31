"""Rotating attendance codes (D-094).

A code is an HMAC under ``ATTENDANCE_SECRET`` of the session id and a 30-second step, so nothing secret is stored
per meeting and a database dump reveals no working code. The QR carries ``SAT1.<session id>.<step>.<signature>``;
students without a camera type the six digits derived from the same MAC. The previous step stays valid for five
seconds into the next one, which covers a scan that straddles the rotation.
"""

import base64
import hashlib
import hmac
import uuid
from dataclasses import dataclass
from typing import Literal

PREFIX = "SAT1"
STEP_SECONDS = 30
GRACE_SECONDS = 5
SIGNATURE_BYTES = 12
CODE_DIGITS = 6


@dataclass(frozen=True, slots=True)
class ScannedCode:
    session_id: uuid.UUID
    step: int
    signature: str


def step_at(unix_seconds: float) -> int:
    return int(unix_seconds // STEP_SECONDS)


def _digest(secret: str, session_id: uuid.UUID, step: int) -> bytes:
    message = b"smartazmiu-attendance:" + session_id.bytes + step.to_bytes(8, "big")
    return hmac.new(secret.encode(), message, hashlib.sha256).digest()


def qr_code(secret: str, session_id: uuid.UUID, step: int) -> str:
    signature = base64.urlsafe_b64encode(_digest(secret, session_id, step)[:SIGNATURE_BYTES])
    return f"{PREFIX}.{session_id.hex}.{step}.{signature.rstrip(b'=').decode()}"


def digits_code(secret: str, session_id: uuid.UUID, step: int) -> str:
    number = int.from_bytes(_digest(secret, session_id, step)[-4:], "big") % 10**CODE_DIGITS
    return f"{number:0{CODE_DIGITS}d}"


def parse_qr(code: str) -> ScannedCode | None:
    parts = code.strip().split(".")
    if len(parts) != 4 or parts[0] != PREFIX:
        return None
    try:
        return ScannedCode(uuid.UUID(hex=parts[1]), int(parts[2]), parts[3])
    except ValueError:
        return None


def accepted_steps(unix_seconds: float) -> tuple[int, ...]:
    """The current step, plus the previous one while its grace period lasts."""
    current = step_at(unix_seconds)
    if unix_seconds - current * STEP_SECONDS < GRACE_SECONDS:
        return (current, current - 1)
    return (current,)


def qr_status(
    secret: str, scanned: ScannedCode, unix_seconds: float
) -> Literal["ok", "expired", "forged"]:
    """A forged signature is never reported as merely expired, so old codes reveal nothing about a session."""
    expected = qr_code(secret, scanned.session_id, scanned.step).rsplit(".", 1)[1]
    if not hmac.compare_digest(expected, scanned.signature):
        return "forged"
    return "ok" if scanned.step in accepted_steps(unix_seconds) else "expired"


def digits_match(secret: str, session_id: uuid.UUID, typed: str, unix_seconds: float) -> bool:
    return any(
        hmac.compare_digest(digits_code(secret, session_id, step), typed.strip())
        for step in accepted_steps(unix_seconds)
    )
