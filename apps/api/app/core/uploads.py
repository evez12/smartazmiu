"""File checks shared by every upload path (chat attachments, materials; §14, D-068).

The extension decides the type, the browser's reported type must agree, and the stored bytes must match it
(magic bytes) before a file is scanned and offered to anyone. SVG is never accepted: it is a document that can
carry script (§13.2).
"""

import io
import zipfile
from pathlib import PurePosixPath
from urllib.parse import quote

from PIL import Image, UnidentifiedImageError

ZIP_MAGIC = (b"PK\x03\x04", b"PK\x05\x06")


# Extension → type.
FILE_TYPES: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".zip": "application/zip",
}
# Browsers on Windows report ZIP archives and some JPEGs under older names.
MIME_ALIASES = {"application/x-zip-compressed": "application/zip", "image/jpg": "image/jpeg"}


# Images and PDFs can be shown inline; everything else is a download.
PREVIEWABLE = frozenset({"image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf"})


def allowed_type(filename: str, mime: str) -> str | None:
    """The MIME type of a file named ``filename`` that the browser reports as ``mime``, if both agree."""
    kind = FILE_TYPES.get(PurePosixPath(filename.lower()).suffix)
    declared = MIME_ALIASES.get(mime.lower(), mime.lower())
    return kind if kind is not None and kind == declared else None


def allowed_extensions() -> list[str]:
    return sorted({name.lstrip(".") for name in FILE_TYPES})


def content_matches(mime: str, data: bytes) -> bool:
    """Magic-byte check: the stored bytes really are what the name and the browser claimed (§14)."""
    if mime == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if mime == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if mime == "image/gif":
        return data.startswith((b"GIF87a", b"GIF89a"))
    if mime == "image/webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    if mime == "application/pdf":
        return data.startswith(b"%PDF-")
    if not data.startswith(ZIP_MAGIC):
        return False
    if mime == "application/zip":
        return True
    # DOCX and PPTX are ZIP packages; the part that defines the document type must be there.
    marker = "word/document.xml" if "wordprocessing" in mime else "ppt/presentation.xml"
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as package:
            return marker in package.namelist()
    except zipfile.BadZipFile:
        return False


def image_size(data: bytes) -> tuple[int | None, int | None]:
    """Width and height from the header only; nothing is decoded (decompression bombs, §14)."""
    try:
        with Image.open(io.BytesIO(data)) as image:
            return image.width, image.height
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        return None, None


def safe_filename(filename: str) -> str:
    """The name shown and offered for download: the last path segment, without control characters."""
    name = PurePosixPath(filename.replace("\\", "/")).name
    cleaned = "".join(char for char in name if char.isprintable() and char not in '"<>')
    return cleaned.strip()[:200] or "fayl"


def content_disposition(filename: str, inline: bool) -> str:
    # RFC 6266 / 5987: an ASCII fallback plus the UTF-8 name, so "Mühazirə 3.pdf" keeps its letters.
    fallback = filename.encode("ascii", "replace").decode().replace("?", "_")
    kind = "inline" if inline else "attachment"
    return f"{kind}; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename)}"
