"""Virus scanning through clamd's INSTREAM command (ClamAV, §7, §14).

The protocol is a few lines, so it is spoken directly instead of through a client library: the command, then the
data in chunks each prefixed with its length as a 4-byte big-endian integer, then a zero-length chunk. clamd
answers ``stream: OK`` or ``stream: <signature> FOUND``.
"""

import asyncio
import struct
from dataclasses import dataclass
from typing import Protocol

CHUNK = 64 * 1024


class ScannerUnavailableError(Exception):
    """clamd could not be reached or answered with an error; the file stays unscanned and is retried."""


@dataclass(frozen=True, slots=True)
class ScanResult:
    clean: bool
    signature: str | None = None


class VirusScanner(Protocol):
    async def scan(self, data: bytes) -> ScanResult: ...


class ClamdScanner:
    def __init__(self, host: str, port: int, timeout: float = 60.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout

    async def scan(self, data: bytes) -> ScanResult:
        try:
            async with asyncio.timeout(self.timeout):
                reader, writer = await asyncio.open_connection(self.host, self.port)
                try:
                    writer.write(b"zINSTREAM\0")
                    for start in range(0, len(data), CHUNK):
                        chunk = data[start : start + CHUNK]
                        writer.write(struct.pack(">I", len(chunk)) + chunk)
                        await writer.drain()
                    writer.write(struct.pack(">I", 0))
                    await writer.drain()
                    reply = (await reader.read(4096)).rstrip(b"\0\n").decode("utf-8", "replace")
                finally:
                    writer.close()
                    await writer.wait_closed()
        except (OSError, TimeoutError) as exc:
            raise ScannerUnavailableError(type(exc).__name__) from exc
        return parse_reply(reply)

    async def ping(self) -> bool:
        try:
            async with asyncio.timeout(5):
                reader, writer = await asyncio.open_connection(self.host, self.port)
                writer.write(b"zPING\0")
                await writer.drain()
                answer = await reader.read(16)
                writer.close()
                await writer.wait_closed()
        except (OSError, TimeoutError):
            return False
        return answer.rstrip(b"\0\n") == b"PONG"


def parse_reply(reply: str) -> ScanResult:
    # "stream: OK", "stream: Win.Test.EICAR_HDB-1 FOUND", or "INSTREAM size limit exceeded. ERROR".
    message = reply.split(":", 1)[-1].strip()
    if message == "OK":
        return ScanResult(clean=True)
    if message.endswith(" FOUND"):
        return ScanResult(clean=False, signature=message.removesuffix(" FOUND").strip()[:200])
    raise ScannerUnavailableError(message[:200] or "empty reply")
