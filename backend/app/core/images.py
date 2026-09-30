"""Turn an uploaded product photo into a safe, small WebP.

The upload is untrusted: its name and Content-Type are ignored, and only what Pillow can
actually decode as JPEG, PNG or WebP is accepted. Metadata is dropped because a phone photo
usually carries the GPS position where it was taken.
"""

import io
import math
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 40_000_000
MAX_SIDE = 1600
_ALLOWED_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})


class ImageRejectedError(ValueError):
    """The upload is not an image this shop accepts."""


def _open(raw: bytes) -> Image.Image:
    # Pillow warns above MAX_IMAGE_PIXELS and raises only at twice that; make both an error.
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            image = Image.open(io.BytesIO(raw))
        except (
            UnidentifiedImageError,
            Image.DecompressionBombWarning,
            Image.DecompressionBombError,
        ) as exc:
            raise ImageRejectedError("Not a supported image") from exc
    if image.format not in _ALLOWED_FORMATS:
        raise ImageRejectedError("Only JPEG, PNG and WebP images are accepted")
    if image.width * image.height > MAX_PIXELS:
        raise ImageRejectedError("Image dimensions are too large")
    return image


def to_webp(raw: bytes) -> bytes:
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ImageRejectedError("Image is too large")

    # verify() checks the whole file but leaves the image unusable, so decode a second time.
    try:
        _open(raw).verify()
        image = _open(raw)
        # JPEGs can be decoded at 1/2, 1/4 or 1/8 scale: ask for the smallest one whose long side
        # is still at least MAX_SIDE, so a phone photo never sits in memory at full size (free
        # hosts give the API ~256 MB). Other formats ignore this.
        scale = MAX_SIDE / max(image.size)
        if scale < 1:
            image.draft("RGB", (math.ceil(image.width * scale), math.ceil(image.height * scale)))
        image.load()
    except ImageRejectedError:
        raise
    except Exception as exc:  # truncated or corrupt data surfaces as assorted errors
        raise ImageRejectedError("Image data is corrupt") from exc

    image = ImageOps.exif_transpose(image)  # keep the orientation the EXIF tag asked for
    image = image.convert("RGBA" if image.mode in ("RGBA", "LA", "P") else "RGB")
    image.thumbnail((MAX_SIDE, MAX_SIDE))  # never upscales

    # Some encoders fall back to image.info for EXIF/XMP/ICC; clear it so nothing is carried over.
    image.info.clear()
    out = io.BytesIO()
    image.save(out, format="WEBP", quality=85, method=4, exif=b"")
    return out.getvalue()
