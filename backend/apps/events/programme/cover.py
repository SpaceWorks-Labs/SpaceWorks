"""Bounded cover canonicalization (PNG for the legacy path, WebP for stored event and series covers)."""

from django.utils.translation import gettext
from io import BytesIO
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework.exceptions import ValidationError


MAX_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 16_000_000


def _clean_pixels(data, max_bytes):
    """Sniff bytes, orient, bound and return a pixel-only RGBA image (no EXIF/XMP/ICC)."""
    if not isinstance(data, bytes) or not data or len(data) > max_bytes:
        raise ValidationError({"image": gettext("Use an image of at most 5 MiB.")})
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as source:
                if source.format not in {"JPEG", "PNG", "WEBP"} or getattr(source, "n_frames", 1) != 1:
                    raise ValueError("Unsupported image.")
                if source.width * source.height > MAX_PIXELS:
                    raise ValueError("Image dimensions are too large.")
                source.load()
                normalized = ImageOps.exif_transpose(source).convert("RGBA")
                normalized.thumbnail((2048, 2048))
                # New pixel-only image avoids copying source EXIF/XMP/ICC metadata.
                clean = Image.new("RGBA", normalized.size)
                clean.paste(normalized)
                return clean
    except (ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise ValidationError({"image": gettext("Use a valid, single-frame image of at most 16 megapixels.")}) from exc


def _encode(clean, **options):
    output = BytesIO()
    clean.save(output, **options)
    result = output.getvalue()
    if len(result) > MAX_BYTES:
        raise ValidationError({"image": gettext("The normalized image exceeds 5 MiB.")})
    return result


def canonical_cover(data):
    """PNG form of the cover. Claimed MIME is not an input."""
    return _encode(_clean_pixels(data, MAX_BYTES), format="PNG", optimize=True)


def canonical_cover_webp(data, *, max_bytes=MAX_BYTES):
    """The stored form of an event or series cover: decoded, oriented, bounded, WebP, no metadata.

    A fresh pixel-only image is encoded, so no EXIF (GPS, camera), XMP or ICC block survives.
    """
    return _encode(_clean_pixels(data, max_bytes), format="WEBP", quality=85, method=4)
