import os
import time
import uuid


def uuid7() -> uuid.UUID:
    """Time-ordered UUID (RFC 9562, version 7): 48-bit Unix milliseconds followed by random bits."""
    timestamp_ms = time.time_ns() // 1_000_000
    random_bits = int.from_bytes(os.urandom(10), "big")
    value = (timestamp_ms & 0xFFFF_FFFF_FFFF) << 80 | random_bits
    value = (value & ~(0xF << 76)) | (0x7 << 76)  # version
    value = (value & ~(0x3 << 62)) | (0x2 << 62)  # RFC 4122 variant
    return uuid.UUID(int=value)
