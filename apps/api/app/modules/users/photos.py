"""Profile photos are decoded and re-encoded on upload (DECISIONS D-033).

Re-encoding keeps only pixels: EXIF (including GPS position) and anything hidden in the file are dropped, so
the stored image is safe to serve before virus scanning exists (§14 upload rules, ClamAV from Sprint 6).
"""

import io

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
# Checked from the header before decoding, which stops decompression bombs.
MAX_PIXELS = 40_000_000
PHOTO_SIZE = 512
ALLOWED_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})


class InvalidPhotoError(Exception):
    """Not a JPEG, PNG or WebP image, or not decodable."""


def normalize_photo(data: bytes) -> bytes:
    """A square 512 px WebP without metadata, cropped around the centre."""
    try:
        with Image.open(io.BytesIO(data)) as source:
            if source.format not in ALLOWED_FORMATS:
                raise InvalidPhotoError
            if source.width * source.height > MAX_PIXELS:
                raise InvalidPhotoError
            image = ImageOps.exif_transpose(source)
            if image.mode in {"RGBA", "LA", "P"}:
                # Transparent areas become white rather than black.
                rgba = image.convert("RGBA")
                image = Image.new("RGB", rgba.size, "white")
                image.paste(rgba, mask=rgba.getchannel("A"))
            square = ImageOps.fit(
                image.convert("RGB"), (PHOTO_SIZE, PHOTO_SIZE), Image.Resampling.LANCZOS
            )
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as exc:
        raise InvalidPhotoError from exc
    output = io.BytesIO()
    square.save(output, "WEBP", quality=85, method=4)
    return output.getvalue()
