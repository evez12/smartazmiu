"""Web Push (RFC 8030) with message encryption (RFC 8291, ``aes128gcm``) and VAPID (RFC 8292)."""

import base64
import hashlib
import os
import struct
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from urllib.parse import urlsplit

import httpx
import jwt
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

RECORD_SIZE = 4096
VAPID_TOKEN_LIFETIME = 12 * 3600


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def b64url_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _hkdf(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(ikm)


def _public_bytes(key: ec.EllipticCurvePublicKey) -> bytes:
    return key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )


def encrypt(payload: bytes, p256dh: str, auth: str) -> bytes:
    """One ``aes128gcm`` record for the subscription's keys (RFC 8291 §3.4, RFC 8188 §2)."""
    ua_public_bytes = b64url_decode(p256dh)
    ua_public = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_public_bytes)
    sender = ec.generate_private_key(ec.SECP256R1())
    sender_public = _public_bytes(sender.public_key())
    shared = sender.exchange(ec.ECDH(), ua_public)

    key_info = b"WebPush: info\x00" + ua_public_bytes + sender_public
    ikm = _hkdf(b64url_decode(auth), shared, key_info, 32)
    salt = os.urandom(16)
    cek = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    # 0x02 marks the last (and only) record; no padding.
    ciphertext = AESGCM(cek).encrypt(nonce, payload + b"\x02", None)
    header = salt + struct.pack("!IB", RECORD_SIZE, len(sender_public)) + sender_public
    return header + ciphertext


class VapidKeys:
    """The application server key pair (RFC 8292), derived from a configured secret.

    Deriving instead of storing a PEM keeps the setup to one generated value per environment; the same secret
    always gives the same public key, so browser subscriptions stay valid across restarts.
    """

    def __init__(self, secret: str, subject: str) -> None:
        digest = hashlib.sha256(b"smartazmiu-vapid:" + secret.encode()).digest()
        order = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
        self.private_key = ec.derive_private_key(
            int.from_bytes(digest) % (order - 1) + 1, ec.SECP256R1()
        )
        self.public_key = b64url(_public_bytes(self.private_key.public_key()))
        self.subject = subject

    def authorization(self, endpoint: str, now: float | None = None) -> str:
        parts = urlsplit(endpoint)
        claims = {
            "aud": f"{parts.scheme}://{parts.netloc}",
            "exp": int((now or time.time()) + VAPID_TOKEN_LIFETIME),
            "sub": self.subject,
        }
        token = jwt.encode(claims, self.private_key, algorithm="ES256")
        return f"vapid t={token}, k={self.public_key}"


def allowed_endpoint(endpoint: str, hosts: list[str]) -> bool:
    """HTTPS on a known push service only: endpoints come from browsers and the worker posts to them."""
    parts = urlsplit(endpoint)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not host or parts.username or parts.password:
        return False
    return any(
        host == pattern or (pattern.startswith("*.") and host.endswith(pattern[1:]))
        for pattern in hosts
    )


class PushOutcome(StrEnum):
    SENT = "sent"
    GONE = "gone"
    """The subscription no longer works (expired, revoked, other key); delete it."""
    RETRY = "retry"


@dataclass(frozen=True, slots=True)
class PushTarget:
    endpoint: str
    p256dh: str
    auth: str


class PushSender(Protocol):
    async def send(self, target: PushTarget, payload: bytes, ttl_seconds: int) -> PushOutcome: ...


class WebPushSender:
    def __init__(self, http: httpx.AsyncClient, keys: VapidKeys, hosts: list[str]) -> None:
        self.http = http
        self.keys = keys
        self.hosts = hosts

    async def send(self, target: PushTarget, payload: bytes, ttl_seconds: int) -> PushOutcome:
        if not allowed_endpoint(target.endpoint, self.hosts):
            return PushOutcome.GONE
        try:
            body = encrypt(payload, target.p256dh, target.auth)
        except ValueError:
            # Keys the browser sent are not a valid P-256 point or auth secret.
            return PushOutcome.GONE
        try:
            response = await self.http.post(
                target.endpoint,
                content=body,
                headers={
                    "Authorization": self.keys.authorization(target.endpoint),
                    "Content-Encoding": "aes128gcm",
                    "Content-Type": "application/octet-stream",
                    "TTL": str(ttl_seconds),
                    "Urgency": "normal",
                },
                follow_redirects=False,
            )
        except httpx.HTTPError:
            return PushOutcome.RETRY
        if response.status_code in (200, 201, 202):
            return PushOutcome.SENT
        if response.status_code in (400, 403, 404, 410):
            return PushOutcome.GONE
        return PushOutcome.RETRY
